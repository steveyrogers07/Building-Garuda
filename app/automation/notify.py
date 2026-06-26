"""GARUDA — alert → notification (Phase 9 automation).

Turns an anomaly Alert into a routed notification envelope (recipient by district,
severity → channels, priority). The actual emit — Catalyst **Signal** → Event
Function → **Push** + **Mail** — is account-gated; `dispatch()` returns the
would-send envelope locally so the flow is testable at $0.
"""
from __future__ import annotations

DEFAULT_RECIPIENT = "district-control-room@ksp.gov.in"


def notification_for(alert, recipients=None):
    dist = alert.get("district_code", "")
    sev = alert.get("severity", "medium")
    return {
        "alert_id": alert.get("alert_id"),
        "district_code": dist,
        "severity": sev,
        "channels": ["push", "mail"] if sev == "high" else ["mail"],
        "priority": 1 if sev == "high" else 2,
        "to": (recipients or {}).get(dist, DEFAULT_RECIPIENT),
        "title": "[%s] %s spike - %s" % (sev.upper(), alert.get("crime_type"), dist),
        "body": alert.get("detail", ""),
    }


def dispatch(notification):
    """Account-gated: emit Signal → Event Function → Push + Mail. Local = no send."""
    return {"queued": True, "notification": notification,
            "note": "Signal/Push/Mail send is account-gated (Catalyst Dev/Prod)"}


def notifications_for_alerts(alerts, recipients=None, severity_min="high"):
    order = {"high": 0, "medium": 1, "low": 2}
    cap = order.get(severity_min, 1)
    return [notification_for(a, recipients) for a in alerts
            if order.get(a.get("severity", "medium"), 1) <= cap]
