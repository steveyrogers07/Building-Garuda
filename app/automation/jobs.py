"""GARUDA - scheduled-job orchestration (Phase 9 automation).

The *logic* of the proactive loop. Cron *triggers* are Catalyst **Job Scheduling**
(nightly 02:00 recompute, weekly Mon 08:00 brief) - not the EOL Cron service.
Each job is a plain callable so it runs identically locally and from a Job Pool.
"""
from __future__ import annotations

import datetime


def nightly_recompute(tasks):
    """Refresh the engines in order. `tasks`: ordered list of (name, callable).
    Returns a per-task status report (errors are captured, never abort the batch)."""
    report, started = {}, datetime.datetime.utcnow()
    for name, fn in tasks:
        try:
            res = fn()
            report[name] = {"ok": True, "result": res}
        except Exception as exc:                       # noqa: BLE001
            report[name] = {"ok": False, "error": str(exc)}
    report["_started"] = started.strftime("%Y-%m-%d %H:%M:%S")
    report["_duration_s"] = round((datetime.datetime.utcnow() - started).total_seconds(), 1)
    return report


def weekly_brief(build_fn, render_fn, write_fn=None):
    """Build the brief, render HTML (SmartBrowz→PDF in prod), optionally persist."""
    brief = build_fn()
    html = render_fn(brief)
    path = write_fn(html) if write_fn else None
    return {"brief": brief, "html_len": len(html), "written": path}
