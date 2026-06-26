"""GARUDA — audit trail (Phase 9 governance).

Every privileged read/query produces an immutable Audit_Log entry (who, what role,
what action, which resource, the query, when, from where). Persisted via
shared.store.write_audit_log (local append-only CSV / ZCQL INSERT in prod).
"""
from __future__ import annotations

import datetime
import uuid


def entry(principal, action, resource, query=""):
    return {
        "log_id": "AUD-" + uuid.uuid4().hex[:12],
        "actor": getattr(principal, "actor", "anonymous"),
        "role": getattr(principal, "role", "?"),
        "action": action,
        "resource": resource,
        "query_text": query,
        "ts": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "ip": getattr(principal, "ip", ""),
    }


def record(principal, action, resource, query=""):
    """Build + persist an audit entry; returns it (so callers can echo the log_id)."""
    e = entry(principal, action, resource, query)
    try:
        from shared import store
        store.write_audit_log(e)
    except Exception:                         # never let auditing break the read path
        pass
    return e
