"""GARUDA — bake the warmstart JSONs into the deploy bundle.

Runs the heavy engines ONCE on the build machine and writes their outputs to
data/warmstart/, which bundle_data_for_deploy.py ships inside the AppSail
bundle. A freshly (re)started instance then serves REAL results instantly via
kvcache's warmstart fallback — no 2-3 min warm stall, no mock fixtures, no
dependency on the Cache segment existing. warm() and the nightly job keep
publishing fresher copies to the live cache; these files are only the floor.

    python scripts/bake_warmstart.py          (takes a few minutes — LightGBM)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "warmstart"

os.environ.setdefault("GARUDA_KVCACHE", "off")
sys.path.insert(0, str(REPO / "app"))


def main():
    t0 = time.time()
    from routers import analytics as A
    from shared.kvcache import _safe

    print("building engines (network + LightGBM + copilot + anomaly + workbench)…")
    A.warm()
    payloads = A._heavy_payloads()

    OUT.mkdir(parents=True, exist_ok=True)
    for key, payload in payloads.items():
        p = OUT / (_safe(key) + ".json")
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"  {p.name:<28} {p.stat().st_size // 1024:>5} KB")
    print(f"baked {len(payloads)} warmstart payloads in {time.time() - t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
