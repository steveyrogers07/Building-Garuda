"""GARUDA - TTL cache (Phase 9 hardening).

A tiny in-process TTL cache for expensive engine aggregations (top rings, risk
surface, dashboard stats). Locally this is a dict + expiry; in production the same
keys are backed by the Catalyst **Cache** service so hot reads stay sub-300ms and
cross-instance. Nightly Job Scheduling recompute invalidates/refreshes the keys.
"""
from __future__ import annotations

import time

_STORE = {}


def cached(key, ttl, producer):
    """Return cached value for `key`, else compute via `producer()` and store for `ttl` s."""
    now = time.time()
    hit = _STORE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    val = producer()
    _STORE[key] = (now + ttl, val)
    return val


def invalidate(key=None):
    if key is None:
        _STORE.clear()
    else:
        _STORE.pop(key, None)


def stats():
    now = time.time()
    return {"entries": len(_STORE), "live": sum(1 for v in _STORE.values() if v[0] > now)}
