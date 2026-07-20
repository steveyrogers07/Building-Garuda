"""GARUDA - ML brain (AppSail | Python/FastAPI).

Phase 1: hello-world health endpoints that prove the AppSail compute surface
deploys and binds the Catalyst-injected listen port. The heavy ML engines
(entity resolution, MO clustering, co-offender network, forecasting, anomaly,
copilot) arrive in Phases 4-7 under app/engines and app/routers.

Start command (see app-config.json):
    uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}
"""
import os
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

_ENV = os.environ.get("ENV", "dev")

# Interactive API docs are a recon gift on a public URL — dev keeps them,
# prod serves 404 for /docs, /redoc and the OpenAPI schema.
app = FastAPI(title="GARUDA ML Brain", version="0.4.0",
              docs_url=None if _ENV == "prod" else "/docs",
              redoc_url=None if _ENV == "prod" else "/redoc",
              openapi_url=None if _ENV == "prod" else "/openapi.json")
# NB: do NOT re-add FastAPI's GZipMiddleware. It streams Content-Encoding: gzip
# through Catalyst's ZGS edge proxy, which re-chunks the body — the combination
# corrupted ~66% of browser responses on the deployed instance (every browser
# sends Accept-Encoding: gzip), so map/officers/absconding intermittently threw
# "Failed to fetch" and the SPA fell back to mock. curl without gzip was always
# 200. The edge proxy already compresses at its hop; app-level gzip is pure
# downside here. (Measured 2026-07-18.)


# --- Rate limiting: the copilot / extraction / recompute endpoints each burn
# real CPU (TF-IDF search, LightGBM retrain, graph rebuild) and the Dev URL is
# public, so cap them per client IP with a sliding window. Generous enough
# that no human demo ever notices; GARUDA_RATELIMIT=off disables entirely
# (the API Gateway takes over throttling in prod, plan §4.5). ---
_RL_LIMIT = int(os.environ.get("GARUDA_RATELIMIT_PER_MIN", "20"))
_RL_PREFIXES = ("/copilot", "/extract", "/jobs")
_RL_SUFFIXES = ("/run",)
_RL_BUCKETS: dict = {}


def _client_key(request):
    """Rate-limit key. Behind the AppSail load balancer request.client.host is
    a per-request proxy address (verified live: 25 parallel POSTs never shared
    a bucket), so prefer the first X-Forwarded-For hop — the real client as
    recorded by the outermost Catalyst proxy."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _rate_limited(ip, path):
    now = time.time()
    if len(_RL_BUCKETS) > 4096:               # bound memory on scan floods
        _RL_BUCKETS.clear()
    hits = [t for t in _RL_BUCKETS.get(ip, []) if now - t < 60]
    if len(hits) >= _RL_LIMIT:
        _RL_BUCKETS[ip] = hits
        return True
    hits.append(now)
    _RL_BUCKETS[ip] = hits
    return False


# Capture Catalyst's internal request headers so every SDK arm (Data Store,
# Cache, NoSQL, Mail/Push, SmartBrowz, provisioning) can authenticate. Must be
# pure-ASGI and registered before the security middleware: BaseHTTPMiddleware
# runs downstream in its own task, where a ContextVar set here would not
# reliably survive. See shared/catalyst_ctx.py for the full reasoning.
try:
    from shared.catalyst_ctx import CatalystContextMiddleware
    app.add_middleware(CatalystContextMiddleware)
except Exception as _exc:  # noqa: BLE001
    import logging
    logging.getLogger("garuda").warning("catalyst context middleware off: %s", _exc)


@app.middleware("http")
async def _security_middleware(request, call_next):
    path = request.url.path
    if (os.environ.get("GARUDA_RATELIMIT", "on") != "off"
            and (path.startswith(_RL_PREFIXES) or path.endswith(_RL_SUFFIXES))
            and request.method == "POST"):
        if _rate_limited(_client_key(request), path):
            return JSONResponse({"detail": "rate limit exceeded — retry in a minute"},
                                status_code=429, headers={"Retry-After": "60"})
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "same-origin")
    # microphone stays self-allowed for the Kannada voice copilot (plan §4.13)
    h.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    if _ENV == "prod":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # the SPA is fully self-hosted (no CDN/fonts); inline styles are React's
        h.setdefault("Content-Security-Policy",
                     "default-src 'self'; img-src 'self' data:; "
                     "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
    return resp

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


# Backend self-provisioning (console-minimal path): status + bundled-CSV load.
try:
    from routers.provision import router as provision_router
    app.include_router(provision_router)
except Exception as _exc:  # noqa: BLE001
    import logging
    import traceback
    _ROUTER_ERRORS["provision"] = traceback.format_exc(limit=-3)
    logging.getLogger("garuda").warning("provision router not loaded: %s", _exc)


@app.get("/health")
def health():
    """Liveness probe for the Phase 1 exit gate (+ remote router diagnostics)."""
    out = {"status": "ok", "service": "garuda-appsail", "phase": 1,
           "routers_loaded": [r for r in ("ingestion", "analytics", "provision")
                              if r not in _ROUTER_ERRORS]}
    # Router *names* always show (operationally harmless). Full tracebacks leak
    # paths and library versions, and the Dev URL is public - so they are
    # opt-in via GARUDA_DEBUG=1 (flip the env var in app-config while
    # diagnosing, never leave it on), regardless of ENV.
    if _ROUTER_ERRORS:
        out["routers_failed"] = sorted(_ROUTER_ERRORS)
        if os.environ.get("GARUDA_DEBUG") == "1":
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
