"""GARUDA — copy read-only reference data into app/ before `catalyst deploy`.

Catalyst AppSail's build_path ("." in app/app-config.json) bundles only the
*contents* of app/ as the production deployment root. data/synthetic (the
demo dataset), data/reference (census/IPC-BNS lookups) and data/gazetteer
live one level above app/ in the repo — outside that bundle — so without this
step the deployed instance 404s/500s on its very first read.

app/shared/store.py and app/shared/refs.py both resolve their data directory
by checking (in order) the repo-root layout and this bundled-app-root layout,
so no env vars need setting for this — just run this once before deploying:

    python scripts/bundle_data_for_deploy.py

Safe to re-run (mirrors the source directories exactly each time). Not
required for local dev (`python app/run_phase8.py`) — only for `catalyst
deploy`. See docs/CATALYST_CREDITS_AND_DEPLOYMENT.md for the full go-live
checklist.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "app"

# (source under data/, destination under app/data/)
_DIRS = ["synthetic", "reference", "gazetteer"]


def main() -> None:
    copied = []
    for name in _DIRS:
        src = REPO / "data" / name
        if not src.is_dir():
            print(f"skip {name}: {src} does not exist (run data/generate.py "
                  f"or data/build_reference.py first)")
            continue
        dst = APP / "data" / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied.append(name)
    if copied:
        print(f"bundled into app/data/: {', '.join(copied)}")
    else:
        print("nothing bundled — nothing to deploy data-wise yet")


if __name__ == "__main__":
    main()
