"""GARUDA — Phase 8 local console launcher (no Catalyst account needed).

Serves the React-grade single-page intelligence console (client/) alongside the
live analytics API, so the whole product — overview, network reveal, hotspot map,
copilot, alerts/risk — is clickable in a browser at $0.

    python app/run_phase8.py        then open  http://127.0.0.1:9000/ui/

The engines are exactly what deploys to AppSail; only the static serving is local.
In production the SPA lives on Web Client Hosting and calls AppSail via API Gateway.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("PORT", "9000"))


def main():
    os.environ["GARUDA_LOCAL"] = "1"
    # auto-bootstrap the synthetic dataset on first run
    if not (REPO / "data" / "synthetic" / "incidents.csv").exists():
        import subprocess
        print("First run: generating synthetic dataset…")
        subprocess.check_call([sys.executable, str(REPO / "data" / "generate.py")])
    app_dir = REPO / "app"
    sys.path.insert(0, str(app_dir))
    os.chdir(str(app_dir))
    import uvicorn
    print("\nGARUDA console -> http://127.0.0.1:%d/ui/\n" % PORT)
    uvicorn.run("main:app", host="127.0.0.1", port=PORT, reload=False)


if __name__ == "__main__":
    main()
