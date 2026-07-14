"""GARUDA — field-officer intelligence engine (docs/product/08 §1/§2/§6).

The statute the whole module hangs on: once an accused is arrested, the
chargesheet must reach court within 60 days (Non-Heinous) or 90 days (Heinous)
of the arrest — CrPC 167(2) / BNSS 187 — or the accused walks on **default
bail** regardless of the evidence. No IO tool in the source schema tracks this;
these aggregations turn the Arrests/Officers/gravity columns into:

  §1  case_deadline()     — the default-bail clock for one case (traffic-light
                            buckets: green >30d / amber 10-30d / red <10d /
                            overdue), from the *earliest* arrest — the first
                            accused in custody sets the binding deadline.
  §2  officer_worklist()  — one IO's open cases, worst-first: §1 urgency, then
                            case age, then gravity. officers_roster() feeds the
                            console's officer picker with load + urgency counts.
  §6  absconding_board()  — suspects on open cases with no arrest row, grouped
                            by canonical person: the live "still out there"
                            list, and the seed for a future watchlist/BOLO.

Pure functions over rows (the engines/district.py pattern) — no I/O; the router
passes whatever store.fetch_* returned. All day math anchors to the dataset's
own timeline (max occurred_at), never datetime.now() — same convention as the
district backlog aging and the A4 test gate in tests/test_arrests_sections.py.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from engines.district import OPEN_STATUSES

WINDOW_HEINOUS, WINDOW_DEFAULT = 90, 60
BUCKETS = ("overdue", "red", "amber", "green")            # most → least urgent
_URGENCY = {b: i for i, b in enumerate(BUCKETS)}
_NO_CLOCK = len(BUCKETS)                                  # sorts after every bucket


def _d(s):
    """Date part of an ISO date/timestamp string, or None."""
    try:
        return datetime.strptime(str(s or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def data_as_of(incidents):
    """Anchor day = the dataset's own latest occurrence, never wall-clock now —
    the corpus is dated in the past, so datetime.now() would mark every open
    case overdue regardless of how recent it is."""
    dates = [d for d in (_d(r.get("occurred_at")) for r in incidents) if d]
    return max(dates) if dates else date.today()


def bucket_for(days_remaining):
    """A4 gate boundaries: green >30 / amber 10-30 / red 0-9 / overdue <0."""
    if days_remaining > 30:
        return "green"
    if days_remaining >= 10:
        return "amber"
    if days_remaining >= 0:
        return "red"
    return "overdue"


def case_deadline(incident, arrests_for_case, *, anchor, has_chargesheet=False):
    """§1 — the default-bail clock for one case, or None when no clock runs
    (nobody arrested yet, final report already filed, or the case is no longer
    under investigation)."""
    if has_chargesheet or incident.get("status") != "Under Investigation":
        return None
    dates = [d for d in (_d(a.get("event_date")) for a in arrests_for_case) if d]
    if not dates:
        return None
    window = WINDOW_HEINOUS if incident.get("gravity") == "Heinous" else WINDOW_DEFAULT
    arrest_date = min(dates)
    remaining = window - (anchor - arrest_date).days
    return {
        "window_days": window,
        "arrest_date": str(arrest_date),
        "due_date": str(arrest_date + timedelta(days=window)),
        "days_remaining": remaining,
        "bucket": bucket_for(remaining),
        "arrested": len(arrests_for_case),
    }


# --------------------------------------------------------------------------- #
# §2 — "My cases" worklist
# --------------------------------------------------------------------------- #
def _by_incident(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["incident_id"]].append(r)
    return out


def _sort_key(c):
    """Worst first: §1 urgency (bucket, then days on the clock), then case age,
    then gravity."""
    dl = c["deadline"]
    return (
        _URGENCY[dl["bucket"]] if dl else _NO_CLOCK,
        dl["days_remaining"] if dl else 10 ** 6,
        -(c["case_age_days"] or 0),
        0 if c.get("gravity") == "Heinous" else 1,
    )


def officer_worklist(officer, incidents, arrests, chargesheets, now=None):
    """One IO's open cases, worst-first — the landing view that replaces the
    paper case-diary stack."""
    anchor = now or data_as_of(incidents)
    oid = officer["officer_id"]
    arr_by_inc = _by_incident(arrests)
    cs_incs = {c["incident_id"] for c in chargesheets}

    cases = []
    for r in incidents:
        if r.get("officer_id") != oid or r.get("status") not in OPEN_STATUSES:
            continue
        occ = _d(r.get("occurred_at"))
        dl = case_deadline(r, arr_by_inc.get(r["incident_id"], []),
                           anchor=anchor, has_chargesheet=r["incident_id"] in cs_incs)
        cases.append({
            "incident_id": r["incident_id"], "fir_no": r.get("fir_no"),
            "crime_type": r.get("crime_type"), "district_code": r.get("district_code"),
            "station_code": r.get("station_code"),
            "occurred_at": (r.get("occurred_at") or "")[:10],
            "status": r.get("status"), "gravity": r.get("gravity"),
            "case_age_days": (anchor - occ).days if occ else None,
            "deadline": dl,
        })
    cases.sort(key=_sort_key)

    summary = {"open": len(cases), "no_clock": 0, "heinous": 0,
               **{b: 0 for b in BUCKETS}}
    for c in cases:
        summary[c["deadline"]["bucket"] if c["deadline"] else "no_clock"] += 1
        if c.get("gravity") == "Heinous":
            summary["heinous"] += 1

    return {
        "officer": {k: officer.get(k, "") for k in
                    ("officer_id", "name", "rank", "designation",
                     "district_code", "unit_code")},
        "as_of": str(anchor),
        "summary": summary,
        "cases": cases,
    }


def officers_roster(incidents, officers, arrests, chargesheets,
                    district=None, station=None, now=None):
    """Officer list with open-case load and urgent-clock count (overdue+red) —
    feeds the My-Cases picker, worst worklist first."""
    anchor = now or data_as_of(incidents)
    arr_by_inc = _by_incident(arrests)
    cs_incs = {c["incident_id"] for c in chargesheets}

    open_n, urgent = defaultdict(int), defaultdict(int)
    for r in incidents:
        oid = r.get("officer_id")
        if not oid or r.get("status") not in OPEN_STATUSES:
            continue
        open_n[oid] += 1
        dl = case_deadline(r, arr_by_inc.get(r["incident_id"], []),
                           anchor=anchor, has_chargesheet=r["incident_id"] in cs_incs)
        if dl and dl["bucket"] in ("overdue", "red"):
            urgent[oid] += 1

    out = []
    for o in officers:
        if district and o.get("district_code") != district:
            continue
        if station and o.get("unit_code") != station:
            continue
        out.append({"officer_id": o["officer_id"], "name": o.get("name", ""),
                    "rank": o.get("rank", ""), "district_code": o.get("district_code", ""),
                    "unit_code": o.get("unit_code", ""),
                    "open": open_n.get(o["officer_id"], 0),
                    "urgent": urgent.get(o["officer_id"], 0)})
    out.sort(key=lambda x: (-x["urgent"], -x["open"], x["officer_id"]))
    return {"as_of": str(anchor), "officers": out}


# --------------------------------------------------------------------------- #
# §6 — absconding-accused board
# --------------------------------------------------------------------------- #
def absconding_people(incidents, arrests, chargesheets, edges, entities, now=None):
    """Phase 1 — the expensive, filter-independent derivation: every
    (person × open case) absconding pair, exactly as the A3 test gate proves it
    (suspect edges on chargesheet-free cases minus arrest rows). The router
    caches this once (a full pass over ~10k edges/arrests/incidents); filters
    and grouping happen per request in absconding_board_from()."""
    anchor = now or data_as_of(incidents)
    by_inc = {r["incident_id"]: r for r in incidents}
    cs_incs = {c["incident_id"] for c in chargesheets}
    ent_by_id = {e["entity_id"]: e for e in entities}

    arrested = defaultdict(set)
    for a in arrests:
        arrested[a["incident_id"]].add(a["entity_id"])
    suspects = defaultdict(set)
    for e in edges:
        if e.get("role") == "suspect":
            suspects[e["incident_id"]].add(e["entity_id"])

    people = {}
    total_pairs = 0
    for iid, sus in suspects.items():
        inc = by_inc.get(iid)
        if inc is None or iid in cs_incs:
            continue
        for eid in sus - arrested[iid]:
            ent = ent_by_id.get(eid)
            if not ent or ent.get("type") != "person":
                continue
            rep = _d(inc.get("reported_at")) or _d(inc.get("occurred_at"))
            case = {
                "incident_id": iid, "fir_no": inc.get("fir_no"),
                "crime_type": inc.get("crime_type"),
                "district_code": inc.get("district_code"),
                "station_code": inc.get("station_code"),
                "gravity": inc.get("gravity"), "status": inc.get("status"),
                "occurred_at": (inc.get("occurred_at") or "")[:10],
                # clamp: an FIR reported after the anchor day is simply brand-new
                "days_open": max(0, (anchor - rep).days) if rep else None,
            }
            rec = people.setdefault(ent["canonical_id"], {
                "canonical_id": ent["canonical_id"],
                "name": ent.get("value", ent["canonical_id"]),
                "districts": set(), "cases": []})
            rec["districts"].add(inc.get("district_code"))
            rec["cases"].append(case)
            total_pairs += 1

    return {"as_of": str(anchor), "people": people, "total_pairs": total_pairs}


def absconding_board_from(state, district=None, station=None, gravity=None,
                          min_days=0, limit=100):
    """Phase 2 — cheap filter/group/sort over a (cached) phase-1 state.
    Filters apply to cases; a person's district span keeps the unfiltered set so
    the cross-district signal survives a district-scoped view."""
    rows = []
    for rec in state["people"].values():
        kept = [c for c in rec["cases"]
                if (not district or c["district_code"] == district)
                and (not station or c["station_code"] == station)
                and (not gravity or c["gravity"] == gravity)
                and (c["days_open"] or 0) >= (min_days or 0)]
        if not kept:
            continue
        kept.sort(key=lambda c: -(c["days_open"] or 0))
        rows.append({
            "canonical_id": rec["canonical_id"], "name": rec["name"],
            "case_count": len(kept),
            "max_days_open": kept[0]["days_open"] or 0,
            "heinous": any(c["gravity"] == "Heinous" for c in kept),
            "districts": sorted(d for d in rec["districts"] if d),
            "cases": kept[:6],
        })
    rows.sort(key=lambda p: (not p["heinous"], -p["case_count"],
                             -p["max_days_open"], p["canonical_id"]))

    return {
        "as_of": state["as_of"],
        "summary": {
            "people": len(rows),
            "cases": sum(p["case_count"] for p in rows),
            "heinous_people": sum(1 for p in rows if p["heinous"]),
            "districts": len({c["district_code"] for p in rows
                              for c in p["cases"] if c["district_code"]}),
            "total_pairs_unfiltered": state["total_pairs"],
        },
        "people": rows[:limit],
        "guardrail": "Persons listed are suspects named in FIRs on open cases "
                     "with no recorded arrest; inclusion is not a determination "
                     "of guilt.",
    }


def absconding_board(incidents, arrests, chargesheets, edges, entities,
                     district=None, station=None, gravity=None,
                     min_days=0, limit=100, now=None):
    """One-shot convenience over the two-phase split (tests and ad-hoc callers;
    the router caches phase 1 and calls absconding_board_from per request)."""
    return absconding_board_from(
        absconding_people(incidents, arrests, chargesheets, edges, entities, now=now),
        district=district, station=station, gravity=gravity,
        min_days=min_days, limit=limit)
