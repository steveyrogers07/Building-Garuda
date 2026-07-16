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
    """Route a notification envelope (plan §4.10). Default (local/demo): no
    send — return the would-send envelope, which tests/test_governance.py
    asserts on. With GARUDA_NOTIFY=catalyst: send Catalyst Mail for every
    enveloped alert and a web Push for the high ones, on the channels already
    routed by notification_for(). Best-effort — a failed send still returns
    the envelope, flagged instead of raised. (The Signals row itself is the
    console-bound Stratus → ingest-event trigger; this is the Mail/Push arm
    those signals ultimately fan into.)"""
    import os
    if os.environ.get("GARUDA_NOTIFY") != "catalyst":
        return {"queued": True, "notification": notification,
                "note": "Signal/Push/Mail send is account-gated (Catalyst Dev/Prod)"}
    sent, errors = [], []
    try:
        import zcatalyst_sdk               # deferred (account-gated)
        app = zcatalyst_sdk.initialize()
        if "mail" in notification.get("channels", []):
            try:
                app.email().send_mail({
                    "from_email": os.environ.get("GARUDA_MAIL_FROM",
                                                 "garuda-alerts@garuda-system.dev"),
                    "to_email": [notification["to"]],
                    "subject": notification["title"],
                    "content": notification["body"] or notification["title"],
                })
                sent.append("mail")
            except Exception as exc:       # noqa: BLE001
                errors.append(f"mail: {exc}")
        if "push" in notification.get("channels", []):
            try:
                app.push_notification().web().send_notification(
                    notification["title"], [notification["to"]])
                sent.append("push")
            except Exception as exc:       # noqa: BLE001
                errors.append(f"push: {exc}")
    except Exception as exc:               # noqa: BLE001 — SDK init failed
        errors.append(f"sdk: {exc}")
    return {"queued": True, "notification": notification,
            "sent": sent, "errors": errors or None}


def notifications_for_alerts(alerts, recipients=None, severity_min="high"):
    order = {"high": 0, "medium": 1, "low": 2}
    cap = order.get(severity_min, 1)
    return [notification_for(a, recipients) for a in alerts
            if order.get(a.get("severity", "medium"), 1) <= cap]
