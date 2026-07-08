"""GARUDA - ML brain (AppSail | Python/FastAPI).

Phase 1: hello-world health endpoints that prove the AppSail compute surface
deploys and binds the Catalyst-injected listen port. The heavy ML engines
(entity resolution, MO clustering, co-offender network, forecasting, anomaly,
copilot) arrive in Phases 4-7 under app/engines and app/routers.

Start command (see app-config.json):
    uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}
"""
from fastapi import FastAPI

app = FastAPI(title="GARUDA ML Brain", version="0.4.0")

# Phase 3 ingestion endpoints (/extract, /geocode, /promote). Wrapped so the health
# probe stays up even if an optional import is missing in a given environment.
try:
    from routers.ingestion import router as ingestion_router
    app.include_router(ingestion_router)
except Exception as _exc:  # noqa: BLE001
    import logging
    logging.getLogger("garuda").warning("ingestion router not loaded: %s", _exc)

# Phase 4 analytics endpoints (/resolve/run, /mo/run, /geocode/backfill). Same guard.
try:
    from routers.analytics import router as analytics_router
    from routers.analytics import warm as _warm_analytics
    app.include_router(analytics_router)

    @app.on_event("startup")
    def _warm_caches():
        # The network graph, LightGBM walk-forward model, copilot TF-IDF index,
        # anomaly scan and workbench state are each expensive exactly once
        # (in-process caches thereafter). Build them off the request path in a
        # background thread so the console is reachable immediately, but the
        # first real click doesn't stall on a multi-second cold-start.
        import logging
        import threading

        def _run():
            try:
                _warm_analytics()
            except Exception as exc:  # noqa: BLE001
                logging.getLogger("garuda").warning("cache warm-up failed: %s", exc)

        threading.Thread(target=_run, daemon=True, name="garuda-warmup").start()

except Exception as _exc:  # noqa: BLE001
    import logging
    logging.getLogger("garuda").warning("analytics router not loaded: %s", _exc)


@app.get("/health")
def health():
    """Liveness probe for the Phase 1 exit gate."""
    return {"status": "ok", "service": "garuda-appsail", "phase": 1}


@app.get("/")
def root():
    return {
        "service": "garuda-appsail",
        "message": "GARUDA ML brain - Phase 1 hello-world. See /health.",
    }


# --- Phase 8 local console (GARUDA_LOCAL=1): serve the client SPA same-origin so it
# can call the analytics API directly. In production the SPA is on Web Client Hosting
# and reaches AppSail via the API Gateway; this block is skipped there. ---
import os  # noqa: E402

if os.environ.get("GARUDA_LOCAL") == "1":
    from pathlib import Path
    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    _REPO = Path(__file__).resolve().parent.parent
    # Prefer the built React console (client-react/dist); fall back to the
    # legacy static SPA so `python app/run_phase8.py` works before any build.
    _CLIENT = _REPO / "client-react" / "dist"
    if not (_CLIENT / "index.html").exists():
        _CLIENT = _REPO / "client"

    @app.get("/console")
    def _console():
        return RedirectResponse("/ui/")

    app.mount("/ui", StaticFiles(directory=str(_CLIENT), html=True), name="ui")
