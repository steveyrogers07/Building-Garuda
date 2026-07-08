"""GARUDA — District Command Card (blueprint §B1/§B2).

Turns the choropleth into command intelligence: load, backlog aging, and —
the metric nobody else in the dataset computes — the **clearance rate** from
`Chargesheets.cs_type` (A=Chargesheet, B=False Case, C=Undetected), sourced
straight from the organizer's `ChargesheetDetails` table. It sits unused in
the raw schema; this is the aggregation that turns it into a rating.

Pure functions over rows (like engines/anomaly/detect.py) — no I/O, easy to
unit-test, called by the router with whatever store.fetch_* already returned.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")

# A case open this long past occurrence without a final report is "aging backlog".
BACKLOG_DAYS = 90
OPEN_STATUSES = {"Under Investigation", "Pending Trial"}
_CS_TYPES = ("A", "B", "C")


def _parse_dt(s):
    s = (s or "").strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _outcome_counts(chargesheets):
    counts = {"A": 0, "B": 0, "C": 0}
    for c in chargesheets:
        t = (c.get("cs_type") or "").strip().upper()
        if t in counts:
            counts[t] += 1
    return counts


def _clearance_rate(counts):
    total = sum(counts.values())
    return round(counts["A"] / total, 3) if total else None


def _data_as_of(incidents):
    """Backlog aging is relative to the dataset's own timeline, not wall-clock
    time — the demo/synthetic corpus is dated in the past, so datetime.now()
    would count every open case as "aging" regardless of how recent it is."""
    dates = [d for d in (_parse_dt(r.get("occurred_at")) for r in incidents) if d]
    return max(dates) if dates else datetime.now()


def command_card(district_code, incidents, chargesheets, officers, now=None):
    """One district's cockpit: load vs baseline shape, backlog aging, clearance
    rate, crime mix, and an officer leaderboard by case count + own clearance rate."""
    now = now or _data_as_of(incidents)
    inc = [r for r in incidents if r.get("district_code") == district_code]
    inc_ids = {r["incident_id"] for r in inc}
    total = len(inc)
    open_n = sum(1 for r in inc if r.get("status") in OPEN_STATUSES)

    backlog = 0
    for r in inc:
        if r.get("status") not in OPEN_STATUSES:
            continue
        occ = _parse_dt(r.get("occurred_at"))
        if occ and (now - occ).days > BACKLOG_DAYS:
            backlog += 1

    cs = [c for c in chargesheets if c.get("incident_id") in inc_ids]
    outcomes = _outcome_counts(cs)
    outcomes_total = sum(outcomes.values())

    crime_counts: dict[str, int] = defaultdict(int)
    for r in inc:
        if r.get("crime_type"):
            crime_counts[r["crime_type"]] += 1
    top_crimes = sorted(crime_counts.items(), key=lambda x: -x[1])[:5]

    off_cases: dict[str, int] = defaultdict(int)
    off_outcomes: dict[str, dict] = defaultdict(lambda: {"A": 0, "B": 0, "C": 0})
    for r in inc:
        oid = r.get("officer_id")
        if oid:
            off_cases[oid] += 1
    for c in cs:
        oid, t = c.get("officer_id"), (c.get("cs_type") or "").strip().upper()
        if oid and t in _CS_TYPES:
            off_outcomes[oid][t] += 1
    off_meta = {o["officer_id"]: o for o in officers}
    leaderboard = []
    for oid, n in off_cases.items():
        meta = off_meta.get(oid, {})
        leaderboard.append({
            "officer_id": oid, "name": meta.get("name", oid), "rank": meta.get("rank", ""),
            "cases": n, "chargesheeted": off_outcomes[oid]["A"],
            "clearance_rate": _clearance_rate(off_outcomes[oid]),
        })
    leaderboard.sort(key=lambda x: -x["cases"])

    return {
        "district_code": district_code,
        "total_incidents": total,
        "open": open_n,
        "disposed": total - open_n,
        "backlog_aging": backlog,
        "backlog_threshold_days": BACKLOG_DAYS,
        "outcomes": outcomes,
        "outcomes_total": outcomes_total,
        "clearance_rate": _clearance_rate(outcomes),
        "top_crimes": top_crimes,
        "top_officers": leaderboard[:8],
    }


def rank_districts(district_codes, incidents, chargesheets, officers, now=None):
    """All districts ranked by clearance rate — "who's improving, who's slipping" (§B2)."""
    now = now or _data_as_of(incidents)
    cards = [command_card(d, incidents, chargesheets, officers, now=now) for d in district_codes]
    cards.sort(key=lambda c: (c["clearance_rate"] is None, -(c["clearance_rate"] or 0)))
    return cards
