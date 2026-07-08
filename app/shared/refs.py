"""GARUDA AppSail — reference-data loaders (districts, IPC<->BNS codes, gazetteer).

Locally these read the repo's data/reference + data/gazetteer (so the engines are
testable without Catalyst). In production point them at Data Store / Stratus via the
GARUDA_REF_DIR / GARUDA_GAZ_DIR env vars. Cached.
"""
from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

# Locally, data/ sits two levels up from shared/refs.py (repo_root/app/shared/).
# But Catalyst AppSail's build_path bundles only the *contents* of app/ as the
# deployment root, so in production data/ (once bundled — see
# docs/CATALYST_CREDITS_AND_DEPLOYMENT.md) sits just one level up instead. Try
# both so the same code runs unchanged from a full checkout or a deployed
# instance, instead of hard-failing with FileNotFoundError in prod.
_HERE = Path(__file__).resolve()
for _candidate in (_HERE.parents[2], _HERE.parents[1]):
    if (_candidate / "data").is_dir():
        REPO = _candidate
        break
else:
    REPO = _HERE.parents[2]
REF_DIR = Path(os.environ.get("GARUDA_REF_DIR", REPO / "data" / "reference"))
GAZ_DIR = Path(os.environ.get("GARUDA_GAZ_DIR", REPO / "data" / "gazetteer"))


def _read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def districts():
    """Return (code->name, name_lower->code)."""
    rows = _read(REF_DIR / "census_2011.csv")
    code2name = {r["area_code"]: r["district_name"] for r in rows}
    name2code = {r["district_name"].lower(): r["area_code"] for r in rows}
    return code2name, name2code


@lru_cache(maxsize=1)
def known_codes():
    """Set of all valid IPC + BNS section codes."""
    rows = _read(REF_DIR / "ipc_bns_map.csv")
    return {r["ipc_code"] for r in rows} | {r["bns_code"] for r in rows}


@lru_cache(maxsize=1)
def gazetteer():
    """List of {place, district_code, level, lat, long}."""
    return _read(GAZ_DIR / "gazetteer.csv")
