"""GARUDA district action cards - proactive-policing directives (blueprint §B).

Fuses the signals the other engines already compute for one district into a
short, prioritised list of operational directives: the brief's "reactive ->
proactive, evidence-based prevention" ask made concrete. Pure templating over
existing engine outputs - no new model, no new data - so every recommendation
is fully explainable and carries the exact numbers that produced it.

Inputs are the *already-computed* products of the other engines (anomaly
alerts, risk rows, officer roster, absconding summary, command cards); this
module never fetches or trains anything itself. Day-math anchors to the
dataset's own timeline via deadlines.data_as_of, never wall-clock now().
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from engines.deadlines import data_as_of
from engines.district import OPEN_STATUSES

_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
_SEV_ORDER = {"high": 0, "medium": 1, "info": 2}
HOTSPOT_WINDOW_DAYS = 90


def _parse_dt(s):
    for f in _DT_FORMATS:
        try:
            return datetime.strptime(str(s)[: len(f) + 2].strip(), f)
        except ValueError:
            continue
    return None


def _as_date(d):
    """deadlines.data_as_of yields a date while _parse_dt yields a datetime -
    normalise before any subtraction (mixing the two raises TypeError)."""
    return d.date() if isinstance(d, datetime) else d


def _band_label(h0):
    return f"{h0:02d}:00-{(h0 + 4) % 24:02d}:00"


def hotspot(incidents, district_code, crime_type=None, *, now=None,
            days=HOTSPOT_WINDOW_DAYS):
    """Peak 4-hour band + busiest station for one district (optionally one
    crime type) over the trailing window - the "where and when to patrol"
    half of a patrol directive. Returns None when too thin to be meaningful."""
    anchor = _as_date(now or data_as_of(incidents))
    band_counts: dict[int, int] = defaultdict(int)
    station_counts: dict[tuple, int] = defaultdict(int)
    for r in incidents:
        if r.get("district_code") != district_code:
            continue
        if crime_type and r.get("crime_type") != crime_type:
            continue
        occ = _parse_dt(r.get("occurred_at"))
        if not occ or (anchor - occ.date()).days > days:
            continue
        band = (occ.hour // 4) * 4
        band_counts[band] += 1
        station_counts[(band, r.get("station_code") or "?")] += 1
    if not band_counts:
        return None
    peak, n = max(band_counts.items(), key=lambda kv: kv[1])
    if n < 3:                       # too thin to direct a patrol shift at
        return None
    station, sn = max(((s, c) for (b, s), c in station_counts.items() if b == peak),
                      key=lambda kv: kv[1])
    return {"band": _band_label(peak), "station_code": station,
            "count": n, "station_count": sn, "days": days}


def _median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2


def district_actions(code, *, card, all_cards, alerts, risk_rows, roster,
                     absconding_summary, incidents, now=None):
    """Assemble one district's action card.

    card                district.command_card(code, ...)
    all_cards           district.rank_districts(...) - for the state median
    alerts              anomaly detect(...)["alerts"] (statewide; filtered here)
    risk_rows           forecasting risk rows (statewide top; filtered here)
    roster              deadlines.officers_roster(...)["officers"] (statewide)
    absconding_summary  absconding_board_from(state, district=code)["summary"]
    incidents           canonical incident rows (for the hotspot fusion only)
    """
    now = now or data_as_of(incidents)
    signals, recs = [], []

    def rec(severity, action, why, sources):
        recs.append({"severity": severity, "action": action, "why": why,
                     "sources": sources})

    # 1 - emerging-trend anomalies, fused with the spatiotemporal hotspot so the
    # directive says not just "act on X" but where and during which shift.
    mine = [a for a in alerts if a.get("district_code") == code]
    if mine:
        latest = max(a.get("window_end", "") for a in mine)
        current = sorted((a for a in mine if a.get("window_end") == latest),
                         key=lambda a: -(a.get("ratio") or 0))[:2]
        for a in current:
            sev = "high" if a.get("severity") == "high" else "medium"
            signals.append({"source": "anomaly", "severity": sev,
                            "text": f"{a['crime_type']} at {a['ratio']}x baseline "
                                    f"({a['observed']} vs {a['baseline']}, "
                                    f"window to {a['window_end']})"})
            spot = hotspot(incidents, code, a["crime_type"], now=now)
            where = (f" - concentrate {spot['band']} around {spot['station_code']}"
                     f" ({spot['station_count']} of {spot['count']} recent there)"
                     if spot else "")
            rec(sev,
                f"Surge {a['crime_type'].lower()} patrols{where}",
                f"{a['observed']} incidents vs {a['baseline']} baseline "
                f"({a['ratio']}x) in the window to {a['window_end']}",
                ["anomaly"] + (["hotspot"] if spot else []))

    # 2 - default-bail clock pressure (CrPC 167(2)/BNSS 187)
    urgent = sum(o.get("urgent", 0) for o in roster
                 if o.get("district_code") == code)
    if urgent:
        signals.append({"source": "deadlines", "severity": "high",
                        "text": f"{urgent} open cases with the chargesheet clock "
                                f"red or already blown"})
        rec("high",
            f"Prioritise {urgent} chargesheet filings inside or past the "
            f"default-bail window",
            "CrPC 167(2)/BNSS 187: past 60d (90d heinous) from first arrest "
            "the accused walk on default bail",
            ["deadlines"])

    # 3 - absconding accused (the BOLO/watchlist seed)
    s = absconding_summary or {}
    if s.get("heinous_people"):
        signals.append({"source": "absconding", "severity": "medium",
                        "text": f"{s['people']} wanted persons, "
                                f"{s['heinous_people']} tied to heinous cases"})
        rec("medium",
            f"Issue BOLO / watchlist push on {s['heinous_people']} heinous "
            f"absconders",
            f"{s['people']} persons named on open FIRs with no arrest recorded "
            f"in {code}",
            ["absconding"])

    # 4 - clearance vs the state, and backlog aging
    med = _median([c.get("clearance_rate") for c in all_cards])
    cr = card.get("clearance_rate")
    if cr is not None and med is not None and cr < med:
        signals.append({"source": "district", "severity": "medium",
                        "text": f"clearance {cr:.0%} vs state median {med:.0%}"})
        rec("medium",
            "Audit undetected (C-type) case closures",
            f"clearance rate {cr:.0%} is below the state median {med:.0%} "
            f"({card['outcomes'].get('C', 0)} cases closed undetected)",
            ["district"])
    if card.get("backlog_aging"):
        signals.append({"source": "district", "severity": "medium",
                        "text": f"{card['backlog_aging']} open cases pending "
                                f"> {card['backlog_threshold_days']}d"})
        rec("medium",
            f"Review {card['backlog_aging']} cases open beyond "
            f"{card['backlog_threshold_days']} days",
            "aging backlog erodes evidence quality and witness recall",
            ["district"])

    # 5 - predicted risk (forecasting top cells that land in this district)
    rr = sorted((r for r in risk_rows if r.get("district_code") == code),
                key=lambda r: -(r.get("risk_score") or 0))[:2]
    for r in rr:
        signals.append({"source": "forecast", "severity": "medium",
                        "text": f"{r['crime_type']} predicted high-risk "
                                f"(statewide rank #{r['rank']})"})
        spot = hotspot(incidents, code, r.get("crime_type"), now=now)
        where = f" ({spot['band']} around {spot['station_code']})" if spot else ""
        rec("medium",
            f"Pre-position for {r['crime_type'].lower()}{where} next period",
            f"model risk score {r['risk_score']:.2f}, statewide rank "
            f"#{r['rank']} for the coming period",
            ["forecast"] + (["hotspot"] if spot else []))

    if not recs:
        rec("info", "No urgent directives",
            "no anomaly, deadline, absconding, clearance or forecast signal "
            "crosses its action threshold for this district", [])

    recs.sort(key=lambda r: _SEV_ORDER.get(r["severity"], 9))
    for i, r in enumerate(recs, 1):
        r["priority"] = i

    open_n = sum(1 for r in incidents
                 if r.get("district_code") == code
                 and r.get("status") in OPEN_STATUSES)
    return {"district_code": code, "as_of": str(now)[:10],
            "open_cases": open_n, "signals": signals,
            "recommendations": recs}
