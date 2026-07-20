"""Per-request Catalyst SDK context (AppSail).

The SDK authenticates off Catalyst's *internal request headers*: passing
`initialize(req=...)` makes it call `parse_headers_from_request`, which stores
`dict(req.headers)` in a **thread-local**. A bare `initialize()` inside AppSail
therefore fails with "Catalyst headers are empty", which took down every
Catalyst arm at once (Data Store/ZCQL, Cache, Mail/Push, SmartBrowz,
provisioning).

Two wrinkles decide the design here:

* FastAPI runs `def` endpoints in a threadpool worker, so the SDK's
  thread-local set anywhere else never reaches the handler's thread.
  A ContextVar does reach it - anyio copies the context into the worker.
* `BaseHTTPMiddleware` runs the downstream app in its own task, and
  ContextVars set there are unreliable across it. A *pure ASGI* middleware
  runs in the same task as the endpoint, so the value propagates.

So: capture headers in pure-ASGI middleware, replay them into the SDK at each
call site via `app()`. Outside a request (nightly jobs, startup warm-up) it
degrades to a bare `initialize()`, which is correct for runtime-supplied
credentials.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_HEADERS: ContextVar[Optional[dict]] = ContextVar("catalyst_headers", default=None)


class _Req:
    """Stand-in request: the SDK only ever reads `.headers` off it."""

    def __init__(self, headers: dict):
        self.headers = headers


def set_headers(headers: dict) -> None:
    _HEADERS.set(headers)


def headers() -> Optional[dict]:
    return _HEADERS.get()


def app():
    """An initialized CatalystApp bound to the current request's headers."""
    import zcatalyst_sdk                        # deferred (account-gated)

    h = _HEADERS.get()
    if h:
        return zcatalyst_sdk.initialize(req=_Req(h))
    return zcatalyst_sdk.initialize()


class CatalystContextMiddleware:
    """Pure-ASGI: remember the Catalyst headers for the life of the request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            try:
                set_headers({k.decode("latin-1"): v.decode("latin-1")
                             for k, v in scope.get("headers") or []})
            except Exception:                   # noqa: BLE001 - never block a request
                pass
        await self.app(scope, receive, send)
