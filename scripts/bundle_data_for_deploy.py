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
_DIRS = ["synthetic", "reference", "gazetteer", "warmstart", "fir_samples"]

# Build-time artefacts that must NOT ship. `_canonical` is the loader's
# --dry-run output (~7 MB) - it exists only to be fed to ds:import and is never
# read at runtime, so shipping it just inflates every upload. `_dev_subset` is
# deliberately NOT excluded: app/routers/provision.py loads the Data Store from
# it. `__pycache__` is regenerated on the instance.
_SKIP = shutil.ignore_patterns("_canonical", "__pycache__", "*.pyc")


def main() -> None:
    copied = []
    for name in _DIRS:
        src = REPO / "data" / name
        if not src.is_dir():
            hint = ("scripts/bake_warmstart.py" if name == "warmstart"
                    else "data/generate.py or data/build_reference.py")
            print(f"skip {name}: {src} does not exist (run {hint} first)")
            continue
        dst = APP / "data" / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=_SKIP)
        copied.append(name)

    # SPA: copy the built React console into app/webclient so a single AppSail
    # instance serves it at /ui/ (app/main.py picks it up when GARUDA_LOCAL=1).
    spa_src = REPO / "client-react" / "dist"
    spa_dst = APP / "webclient"
    if (spa_src / "index.html").exists():
        if spa_dst.exists():
            shutil.rmtree(spa_dst)
        shutil.copytree(spa_src, spa_dst)
        print("bundled SPA into app/webclient/ (from client-react/dist)")
    else:
        print(f"skip SPA: {spa_src}/index.html missing — run "
              f"`npm --prefix client-react run build` first")

    if copied:
        print(f"bundled into app/data/: {', '.join(copied)}")
    else:
        print("no reference data bundled — run data/generate.py if unexpected")


if __name__ == "__main__":
    main()
