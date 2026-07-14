"""GARUDA — field-officer intelligence evaluation (no Catalyst).

Checks the 08 §1/§2/§6 engine (app/engines/deadlines.py) — the default-bail
deadline clock, the per-IO worklist, and the absconding-accused board:
  - F1  case_deadline semantics: exact A4 bucket boundaries (green >30 / amber
        10-30 / red 0-9 / overdue <0), 90d Heinous vs 60d window, earliest
        arrest sets the clock, and no clock when nobody is arrested / a final
        report exists / the case left Under Investigation.
  - F2  bucket totals over every open case equal an independent A4-style
        recomputation, and all four urgency buckets are populated.
  - F3  officers_roster: every officer exactly once, open-case loads sum to the
        open-incident count, urgent counts match F2, sorted worst-first, and
        the district filter scopes correctly.
  - F4  officer_worklist: cases belong to the officer and are open, sorted by
        urgency -> days left -> case age -> gravity, summary matches rows, and
        per-case deadlines equal a direct case_deadline call.
  - F5  absconding_board: pair total equals the A3 derivation from raw edges/
        arrests, every listed case is chargesheet-free with a suspect edge and
        no arrest for that person, persons are unique canonicals, heinous
        persons rank first, district/gravity/min_days filters hold, and the
        cached two-phase split (absconding_people -> absconding_board_from,
        the router's path) is identical to the one-shot board.
  - F6  the case file carries the deadline object + due-date timeline entry
        (and none once a final report exists); RBAC in_scope gates the
        worklist by the officer's district/unit.

Run:  python tests/test_field_officer.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from engines import deadlines as dl  # noqa: E402
from governance import rbac  # noqa: E402
from shared import store  # noqa: E402


def _d(s):
    from datetime import datetime
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def run():
    incidents = store.fetch_incidents_full()
    arrests = store.fetch_arrests()
    chargesheets = store.fetch_chargesheets()
    officers = store.fetch_officers()
    edges = store.fetch_edges_p5()
    entities = store.fetch_entities_p5()
    assert incidents and arrests and officers, "run data/generate.py first"

    anchor = dl.data_as_of(incidents)
    assert anchor == max(_d(r["occurred_at"]) for r in incidents)
    print(f"field-officer: {len(incidents):,} incidents, {len(arrests):,} arrests, "
          f"{len(officers)} officers, anchor {anchor}")

    # ---- F1: case_deadline unit semantics ----
    a0 = date(2025, 1, 1)
    ui = {"status": "Under Investigation", "gravity": "Non-Heinous"}

    def clock(days_since_arrest, gravity="Non-Heinous", n_arrests=1, status="Under Investigation",
              has_cs=False):
        inc = {"status": status, "gravity": gravity}
        arr = [{"event_date": str(a0 - timedelta(days=days_since_arrest + i))}
               for i in range(n_arrests)]
        return dl.case_deadline(inc, arr, anchor=a0, has_chargesheet=has_cs)

    assert clock(29)["bucket"] == "green" and clock(29)["days_remaining"] == 31
    assert clock(30)["bucket"] == "amber" and clock(50)["bucket"] == "amber"   # 30, 10 left
    assert clock(51)["bucket"] == "red" and clock(60)["bucket"] == "red"       # 9, 0 left
    assert clock(61)["bucket"] == "overdue" and clock(61)["days_remaining"] == -1
    assert clock(61, gravity="Heinous")["bucket"] == "amber"                   # 90d window
    assert clock(61, gravity="Heinous")["window_days"] == 90
    c = clock(10, n_arrests=3)                          # earliest of 3 sets the clock
    assert c["arrested"] == 3 and c["arrest_date"] == str(a0 - timedelta(days=12))
    assert c["due_date"] == str(a0 - timedelta(days=12) + timedelta(days=60))
    assert dl.case_deadline(ui, [], anchor=a0) is None                  # nobody arrested
    assert clock(10, has_cs=True) is None                               # final report filed
    assert clock(10, status="Pending Trial") is None                    # left investigation
    print("  F1 deadline clock semantics ok (A4 boundaries, 90/60 windows)")

    # ---- F2: bucket totals over every open case == independent A4-style pass ----
    arr_by_inc = {}
    for a in arrests:
        arr_by_inc.setdefault(a["incident_id"], []).append(a)
    cs_incs = {c["incident_id"] for c in chargesheets}
    want = {"green": 0, "amber": 0, "red": 0, "overdue": 0}
    got = dict(want)
    for r in incidents:
        rows = arr_by_inc.get(r["incident_id"], [])
        d = dl.case_deadline(r, rows, anchor=anchor,
                             has_chargesheet=r["incident_id"] in cs_incs)
        if d:
            got[d["bucket"]] += 1
        if rows and r["incident_id"] not in cs_incs and r["status"] == "Under Investigation":
            window = 90 if r["gravity"] == "Heinous" else 60
            first = min(_d(a["event_date"]) for a in rows)
            rem = window - (anchor - first).days
            want["green" if rem > 30 else "amber" if rem >= 10
                 else "red" if rem >= 0 else "overdue"] += 1
    assert got == want, f"engine buckets {got} != recomputation {want}"
    assert all(v > 0 for v in got.values()), f"empty urgency bucket: {got}"
    print(f"  F2 per-case clock buckets match recomputation: {got}")

    # ---- F3: officers_roster ----
    roster = dl.officers_roster(incidents, officers, arrests, chargesheets)["officers"]
    assert len(roster) == len(officers)
    assert len({o["officer_id"] for o in roster}) == len(officers)
    open_total = sum(1 for r in incidents if r["status"] in dl.OPEN_STATUSES)
    assert sum(o["open"] for o in roster) == open_total
    assert sum(o["urgent"] for o in roster) == got["overdue"] + got["red"]
    keys = [(-o["urgent"], -o["open"]) for o in roster]
    assert keys == sorted(keys), "roster not sorted worst-first"
    dist = roster[0]["district_code"]
    scoped = dl.officers_roster(incidents, officers, arrests, chargesheets,
                                district=dist)["officers"]
    assert scoped and all(o["district_code"] == dist for o in scoped)
    print(f"  F3 roster: {len(roster)} officers, {open_total:,} open cases, "
          f"urgent={got['overdue'] + got['red']}, top={roster[0]['officer_id']}")

    # ---- F4: officer_worklist for the three worst-loaded officers ----
    off_by_id = {o["officer_id"]: o for o in officers}
    for pick in roster[:3]:
        wl = dl.officer_worklist(off_by_id[pick["officer_id"]], incidents,
                                 arrests, chargesheets)
        cases = wl["cases"]
        assert len(cases) == pick["open"] == wl["summary"]["open"]
        s = {"green": 0, "amber": 0, "red": 0, "overdue": 0, "no_clock": 0, "heinous": 0}
        seen_keys = []
        for c in cases:
            r = next(x for x in incidents if x["incident_id"] == c["incident_id"])
            assert r["officer_id"] == pick["officer_id"]
            assert r["status"] in dl.OPEN_STATUSES
            d = dl.case_deadline(r, arr_by_inc.get(c["incident_id"], []), anchor=anchor,
                                 has_chargesheet=c["incident_id"] in cs_incs)
            assert c["deadline"] == d
            s[d["bucket"] if d else "no_clock"] += 1
            if c["gravity"] == "Heinous":
                s["heinous"] += 1
            seen_keys.append((
                dl._URGENCY[d["bucket"]] if d else dl._NO_CLOCK,
                d["days_remaining"] if d else 10 ** 6,
                -(c["case_age_days"] or 0),
                0 if c["gravity"] == "Heinous" else 1))
        assert seen_keys == sorted(seen_keys), "worklist not sorted worst-first"
        assert {k: wl["summary"][k] for k in s} == s
        assert wl["summary"]["overdue"] + wl["summary"]["red"] == pick["urgent"]
    print(f"  F4 worklists consistent for top-3 officers "
          f"(worst: {roster[0]['officer_id']}, urgent={roster[0]['urgent']})")

    # ---- F5: absconding board == A3 derivation; filters + ordering hold ----
    board = dl.absconding_board(incidents, arrests, chargesheets, edges, entities,
                                limit=10 ** 6)
    # the router caches phase 1 and filters per request — must be byte-identical
    two_phase = dl.absconding_board_from(
        dl.absconding_people(incidents, arrests, chargesheets, edges, entities),
        limit=10 ** 6)
    assert two_phase == board, "cached two-phase path must equal the one-shot board"
    by_inc = {r["incident_id"]: r for r in incidents}
    sus_by_inc, person_ids = {}, {e["entity_id"] for e in entities if e["type"] == "person"}
    for e in edges:
        if e["role"] == "suspect":
            sus_by_inc.setdefault(e["incident_id"], set()).add(e["entity_id"])
    arrested_by_inc = {}
    for a in arrests:
        arrested_by_inc.setdefault(a["incident_id"], set()).add(a["entity_id"])
    a3_pairs = 0
    for iid, sus in sus_by_inc.items():
        if iid in cs_incs or iid not in by_inc:
            continue
        a3_pairs += len((sus & person_ids) - arrested_by_inc.get(iid, set()))
    assert board["summary"]["total_pairs_unfiltered"] == a3_pairs
    assert board["summary"]["cases"] == a3_pairs, "unfiltered board must keep every pair"
    assert board["summary"]["people"] == len(board["people"])
    assert len({p["canonical_id"] for p in board["people"]}) == len(board["people"])
    ent_by_id = {e["entity_id"]: e for e in entities}
    canon_of = {}   # canonical -> alias entity ids
    for e in entities:
        canon_of.setdefault(e["canonical_id"], set()).add(e["entity_id"])
    for p in board["people"][:50] + board["people"][-50:]:
        for c in p["cases"]:
            assert c["incident_id"] not in cs_incs
            assert by_inc[c["incident_id"]]["status"] in dl.OPEN_STATUSES
            aliases = canon_of[p["canonical_id"]]
            free = (aliases & sus_by_inc.get(c["incident_id"], set())) \
                - arrested_by_inc.get(c["incident_id"], set())
            assert free, "listed person has no un-arrested suspect alias on the case"
            assert (c["days_open"] or 0) >= 0
    flags = [p["heinous"] for p in board["people"]]
    assert flags == sorted(flags, reverse=True), "heinous persons must rank first"
    dist = board["people"][0]["cases"][0]["district_code"]
    fb = dl.absconding_board(incidents, arrests, chargesheets, edges, entities,
                             district=dist, gravity="Heinous", min_days=90, limit=10 ** 6)
    for p in fb["people"]:
        for c in p["cases"]:
            assert c["district_code"] == dist and c["gravity"] == "Heinous"
            assert c["days_open"] >= 90
    print(f"  F5 absconding board: {board['summary']['people']:,} persons / "
          f"{a3_pairs:,} pairs (A3 match); heinous-first; filters ok")

    # ---- F6: case-file deadline + RBAC scope gate ----
    from engines import workbench as wb
    admin = rbac.Principal(actor="test", role="scrb-admin")
    with_clock = next(r for r in incidents
                      if r["status"] == "Under Investigation"
                      and r["incident_id"] in arr_by_inc
                      and r["incident_id"] not in cs_incs)
    cf = wb.case_file(with_clock["incident_id"], admin)
    d = dl.case_deadline(with_clock, arr_by_inc[with_clock["incident_id"]], anchor=anchor)
    assert cf["deadline"] == d and d is not None
    assert any("default bail" in t["label"] or "Default-bail" in t["label"]
               for t in cf["timeline"])
    closed = next(r for r in incidents if r["incident_id"] in cs_incs)
    assert wb.case_file(closed["incident_id"], admin)["deadline"] is None

    off = off_by_id[roster[0]["officer_id"]]
    assert rbac.in_scope(rbac.Principal(role="district", scope=off["district_code"]),
                         district=off["district_code"], station=off["unit_code"])
    assert not rbac.in_scope(rbac.Principal(role="district", scope="ZZZ"),
                             district=off["district_code"], station=off["unit_code"])
    assert rbac.in_scope(rbac.Principal(role="station", scope=off["unit_code"]),
                         district=off["district_code"], station=off["unit_code"])
    assert not rbac.in_scope(rbac.Principal(role="ethics"),
                             district=off["district_code"], station=off["unit_code"])
    print(f"  F6 case-file deadline ({with_clock['incident_id']}: "
          f"{d['bucket']}, {d['days_remaining']}d) + RBAC scope gates ok")

    print("ALL FIELD-OFFICER GATES PASSED")


if __name__ == "__main__":
    run()
