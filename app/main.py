"""GARUDA - ML brain (AppSail | Python/FastAPI).

Phase 1: hello-world health endpoints that prove the AppSail compute surface
deploys and binds the Catalyst-injected listen port. The heavy ML engines
(entity resolution, MO clustering, co-offender network, forecasting, anomaly,
copilot) arrive in Phases 4-7 under app/engines and app/routers.

Start command (see app-config.json):
    uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}
"""
from fastapi import FastAPI

app = FastAPI(title="GARUDA ML Brain", version="0.2.0")

# Phase 3 ingestion endpoints (/extract, /geocode, /promote). Wrapped so the health
# probe stays up even if an optional import is missing in a given environment.
try:
    from routers.ingestion import router as ingestion_router
    app.include_router(ingestion_router)
except Exception as _exc:  # noqa: BLE001
    import logging
    logging.getLogger("garuda").warning("ingestion router not loaded: %s", _exc)


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
