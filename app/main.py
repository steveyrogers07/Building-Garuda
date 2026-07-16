"""GARUDA - ML brain (AppSail | Python/FastAPI).

Phase 1: hello-world health endpoints that prove the AppSail compute surface
deploys and binds the Catalyst-injected listen port. The heavy ML engines
(entity resolution, MO clustering, co-offender network, forecasting, anomaly,
copilot) arrive in Phases 4-7 under app/engines and app/routers.

Start command (see app-config.json):
    uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}
"""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="GARUDA ML Brain", version="0.4.0")
# The Dev AppSail proxy adds a fixed per-request latency floor (~0.7s measured),
# so payload transfer is the only wire cost we control — gzip the big JSON
# responses (officer roster ~28KB, ego graphs, geo aggregates shrink ~5x).
app.add_middleware(GZipMiddleware, minimum_size=1500)

# Optional-router import failures land here and are surfaced by /health, so a
# deployed instance can be diagnosed remotely without shell or log access.
_ROUTER_ERRORS: dict = {}

# Phase 3 ingestion endpoints (/extract, /geocode, /promote). Wrapped so the health
# probe stays up even if an optional import is missing in a given environment.
try:
    from routers.ingestion import router as ingestion_router
    app.include_router(ingestion_router)
except Exception as _exc:  # noqa: BLE001
    import logging
    import traceback
    _ROUTER_ERRORS["ingestion"] = traceback.format_exc(limit=-3)
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
    import traceback
    _ROUTER_ERRORS["analytics"] = traceback.format_exc(limit=-3)
    logging.getLogger("garuda").warning("analytics router not loaded: %s", _exc)


@app.get("/health")
def health():
    """Liveness probe for the Phase 1 exit gate (+ remote router diagnostics)."""
    out = {"status": "ok", "service": "garuda-appsail", "phase": 1,
           "routers_loaded": [r for r in ("ingestion", "analytics")
                              if r not in _ROUTER_ERRORS]}
    if _ROUTER_ERRORS:
        out["router_errors"] = _ROUTER_ERRORS
    return out


@app.get("/")
def root():
    return {
        "service": "garuda-appsail",
        "message": "GARUDA ML brain - Phase 1 hello-world. See /health.",
    }


# --- Console SPA serving (GARUDA_LOCAL=1): serve the client SPA same-origin so it
# can call the analytics API directly. Enabled locally (python app/run_phase8.py) and
# on the single-service AppSail deploy, where the SPA is bundled into app/webclient
# (scripts/bundle_data_for_deploy.py) and GARUDA_LOCAL=1 is set in app-config.json. ---
import os  # noqa: E402

if os.environ.get("GARUDA_LOCAL") == "1":
    from pathlib import Path
    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    _APP_DIR = Path(__file__).resolve().parent
    # SPA location, in priority order: the live local client-react/dist build (kept
    # fresh in dev), then app/webclient bundled into the AppSail deploy (the only one
    # present in prod, since client-react/ is outside the app/ bundle), then legacy.
    _CLIENT = next((c for c in (_APP_DIR.parent / "client-react" / "dist",
                                _APP_DIR / "webclient",
                                _APP_DIR.parent / "client")
                    if (c / "index.html").exists()), None)

    # Mount only when a real SPA dir is found — a missing dir would make StaticFiles
    # raise at import time and take the whole API down (AppSail "Execution failed").
    if _CLIENT is not None:
        @app.get("/console")
        def _console():
            return RedirectResponse("/ui/")

        app.mount("/ui", StaticFiles(directory=str(_CLIENT), html=True), name="ui")
