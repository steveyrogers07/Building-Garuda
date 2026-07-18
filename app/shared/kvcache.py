"""GARUDA - L2 JSON cache over Catalyst Cache (plan §4.7).

The in-process _Lazy caches in the routers are the L1: free to read, but they
die with the instance, so an AppSail restart/scale-out re-pays every heavy
build (LightGBM walk-forward, graph analysis) before those endpoints respond -
the 2-3 min cold start. This module is the L2: heavy *outputs* (plain JSON,
never models/graphs) are published here when built - by warm(), the run
endpoints, and above all the nightly job - and a cold instance serves from L2
until its own L1 finishes building in the background.

Backend, selected by GARUDA_KVCACHE:
  - unset/"off" (default): get() always misses, put() is a no-op - local
    behavior stays byte-identical (the no-feature-loss contract, plan §0).
  - "memory": in-process dict with TTL - exercises the wiring in tests.
  - "catalyst": the Catalyst Cache default segment (set in prod app-config).

Strictly best-effort: every failure (SDK missing, value over the segment's
size cap, network) degrades to a miss - the request path never breaks.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

MODE = os.environ.get("GARUDA_KVCACHE", "off").lower()
DEFAULT_TTL_HOURS = 26          # nightly job republishes; +2h grace

_MEM: dict[str, tuple[float, str]] = {}

# Deploy-time warmstart (the "data missing" killer): scripts/bake_warmstart.py
# precomputes the heavy outputs and ships them as JSON inside the bundle, so a
# freshly (re)started instance serves REAL results instantly - no dependency
# on the Cache segment existing, no mock fixtures, no 2-3 min warm stall.
# Live L1/L2 always win; these files are only the cold-start floor.
_HERE = Path(__file__).resolve()
for _c in (_HERE.parents[2], _HERE.parents[1]):
    if (_c / "data").is_dir():
        _WARMSTART = _c / "data" / "warmstart"
        break
else:
    _WARMSTART = _HERE.parents[2] / "data" / "warmstart"


def _safe(key):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", key)


def warmstart_get(key):
    p = _WARMSTART / (_safe(key) + ".json")
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def _segment():
    import zcatalyst_sdk                       # deferred (account-gated)
    return zcatalyst_sdk.initialize().cache().segment()


def get(key):
    """Cached object or None. A miss is always safe - callers fall through
    to building the real thing. Miss order: live cache first, then the
    deploy-time warmstart file, so results are never staler than the last
    publish OR the last deploy, whichever is fresher."""
    try:
        if MODE == "memory":
            hit = _MEM.get(key)
            if hit and hit[0] > time.time():
                return json.loads(hit[1])
            _MEM.pop(key, None)
            return warmstart_get(key)
        if MODE == "catalyst":
            raw = _segment().get_value(key)
            if raw:
                return json.loads(raw)
    except Exception:                          # noqa: BLE001 - degrade
        pass
    return warmstart_get(key)


def put(key, obj, ttl_hours=DEFAULT_TTL_HOURS):
    """Publish a JSON-able object. Returns True if stored (best-effort)."""
    try:
        raw = json.dumps(obj, ensure_ascii=False)
        if MODE == "memory":
            _MEM[key] = (time.time() + ttl_hours * 3600, raw)
            return True
        if MODE == "catalyst":
            seg = _segment()
            try:
                seg.put(key, raw, ttl_hours)
            except Exception:                  # key exists -> POST rejects; update
                seg.update(key, raw, ttl_hours)
            return True
    except Exception:                          # noqa: BLE001 - oversized/offline
        return False
    return False
