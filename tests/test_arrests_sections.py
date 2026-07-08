"""GARUDA — Arrests + Case_Sections evaluation (no Catalyst).

Checks the 08 §9 schema-gap tables (organizer's ArrestSurrender + ActSectionAssociation)
that unlock the statutory deadline tracker (§1), per-section evidence gaps (§5) and the
absconding-accused board (§6):
  - A1  referential integrity: every arrest points at a real incident, at a *suspect*
        on that incident, and a real officer; enums/dates are sane (never pre-FIR).
  - A2  custody precedes the final report: arrest date <= cs_date whenever the case
        has a chargesheet row.
  - A3  the absconding board is derivable and non-empty (open-case suspects with no
        arrest row); undetected (cs_type C) cases are essentially arrest-free.
  - A4  the §1 default-bail clock has all four urgency buckets populated among open
        cases (window: Heinous=90d / Non-Heinous=60d from arrest, anchored to the
        dataset's own end — same convention as the district backlog aging).
  - S1  every incident has exactly one section_order=1 row that equals its
        ipc_bns_code under the act it was coded in; orders are contiguous; no
        duplicate act+section per case.
  - S2  the one-to-many actually happened: a healthy share of cases invoke >1 section.
  - S3  acts are IPC|BNS|IT_ACT and every IPC/BNS section is covered by the
        ipc_bns_map.csv reference (the same coverage the validation gate checks).
  - V1  both tables pass the Phase-2 validation gate against canonical_schema.yaml.

Run:  python tests/test_arrests_sections.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
sys.path.insert(0, str(REPO / "ingestion" / "adapter"))

import validate  # noqa: E402
from shared import store  # noqa: E402


def _d(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def run():
    incidents = store.fetch_incidents_full()
    arrests = store.fetch_arrests()
    sections = store.fetch_case_sections()
    chargesheets = store.fetch_chargesheets()
    officers = store.fetch_officers()
    edges = store.fetch_edges_p5()
    assert incidents and arrests and sections, "run data/generate.py first"

    inc_by_id = {r["incident_id"]: r for r in incidents}
    cs_by_inc = {c["incident_id"]: c for c in chargesheets}
    officer_ids = {o["officer_id"] for o in officers}
    suspects = {}
    for e in edges:
        if e["role"] == "suspect":
            suspects.setdefault(e["incident_id"], set()).add(e["entity_id"])
    print(f"arrests+sections: {len(arrests):,} arrests, {len(sections):,} section rows, "
          f"{len(incidents):,} incidents")

    # ---- A1: referential integrity + sane enums/dates ----
    assert len({a["arrest_id"] for a in arrests}) == len(arrests)
    seen_pairs = set()
    for a in arrests:
        inc = inc_by_id[a["incident_id"]]                      # KeyError = broken ref
        assert a["entity_id"] in suspects[a["incident_id"]], \
            f"{a['arrest_id']}: arrested entity is not a suspect on the case"
        assert a["event_type"] in ("arrest", "surrender")
        assert a["district_code"] == inc["district_code"]
        assert a["io_officer_id"] in officer_ids
        assert _d(a["event_date"]) >= _d(inc["reported_at"]), \
            f"{a['arrest_id']}: arrest predates the FIR"
        pair = (a["incident_id"], a["entity_id"])
        assert pair not in seen_pairs, f"duplicate arrest for {pair}"
        seen_pairs.add(pair)
    n_surr = sum(1 for a in arrests if a["event_type"] == "surrender")
    print(f"  A1 integrity ok; surrenders={n_surr} ({n_surr / len(arrests):.0%})")

    # ---- A2: arrest precedes the final report ----
    checked = 0
    for a in arrests:
        cs = cs_by_inc.get(a["incident_id"])
        if cs:
            assert _d(a["event_date"]) <= _d(cs["cs_date"]), \
                f"{a['arrest_id']}: arrested after the chargesheet was filed"
            checked += 1
    print(f"  A2 arrest<=cs_date on {checked:,} chargesheeted arrests")

    # ---- A3: absconding board derivable; undetected cases arrest-free ----
    arrested_by_inc = {}
    for a in arrests:
        arrested_by_inc.setdefault(a["incident_id"], set()).add(a["entity_id"])
    absconding = 0
    for iid, sus in suspects.items():
        inc = inc_by_id.get(iid)
        if inc is None or iid in cs_by_inc:
            continue
        absconding += len(sus - arrested_by_inc.get(iid, set()))
    assert absconding > 0, "no absconding accused derivable — §6 board would be empty"
    c_incs = {c["incident_id"] for c in chargesheets if c["cs_type"] == "C"}
    c_sus = sum(len(suspects.get(i, ())) for i in c_incs)
    c_arr = sum(len(arrested_by_inc.get(i, ())) for i in c_incs)
    assert c_sus == 0 or c_arr / c_sus < 0.15, "undetected (C) cases should be ~arrest-free"
    print(f"  A3 absconding accused on open cases: {absconding:,}; "
          f"C-type arrest share {c_arr}/{c_sus}")

    # ---- A4: §1 clock buckets all populated among open cases ----
    anchor = max(_d(r["occurred_at"]) for r in incidents)
    buckets = {"green": 0, "amber": 0, "red": 0, "overdue": 0}
    for a in arrests:
        inc = inc_by_id[a["incident_id"]]
        if a["incident_id"] in cs_by_inc or inc["status"] != "Under Investigation":
            continue
        window = 90 if inc["gravity"] == "Heinous" else 60
        remaining = window - (anchor - _d(a["event_date"])).days
        buckets["green" if remaining > 30 else "amber" if remaining >= 10
                else "red" if remaining >= 0 else "overdue"] += 1
    assert all(v > 0 for v in buckets.values()), f"empty urgency bucket: {buckets}"
    print(f"  A4 deadline clock (anchor {anchor}): {buckets}")

    # ---- S1: primary section coherence + contiguous orders + no dups ----
    cfg = yaml.safe_load((REPO / "data" / "generator_config.yaml").read_text(encoding="utf-8"))
    bns_by_crime = {c["name"]: c["bns"] for c in cfg["crime_types"]}
    by_inc = {}
    for s in sections:
        by_inc.setdefault(s["incident_id"], []).append(s)
    assert set(by_inc) == set(inc_by_id), "sections must cover every incident exactly"
    multi = 0
    for iid, rows in by_inc.items():
        inc = inc_by_id[iid]
        orders = sorted(int(r["section_order"]) for r in rows)
        assert orders == list(range(1, len(rows) + 1)), f"{iid}: non-contiguous orders"
        assert len({(r["act_code"], r["section_code"]) for r in rows}) == len(rows)
        prim = [r for r in rows if int(r["section_order"]) == 1]
        assert len(prim) == 1 and prim[0]["section_code"] == inc["ipc_bns_code"]
        want_act = "BNS" if inc["ipc_bns_code"] == bns_by_crime[inc["crime_type"]] else "IPC"
        assert prim[0]["act_code"] == want_act
        if len(rows) > 1:
            multi += 1

    # ---- S2: the one-to-many is real ----
    share = multi / len(by_inc)
    assert 0.5 <= share <= 0.9, f"multi-section share {share:.0%} out of expected band"
    print(f"  S1/S2 primaries coherent; multi-section cases {share:.0%}")

    # ---- S3: act enum + reference-map coverage ----
    known = validate.known_codes()
    assert known, "ipc_bns_map.csv missing"
    for s in sections:
        assert s["act_code"] in ("IPC", "BNS", "IT_ACT")
        if s["act_code"] != "IT_ACT":
            assert s["section_code"] in known, \
                f"{s['section_code']} not in ipc_bns_map.csv"
    print(f"  S3 all IPC/BNS sections covered by the reference map")

    # ---- V1: the Phase-2 validation gate passes on both tables ----
    for table, rows in (("Arrests", arrests), ("Case_Sections", sections)):
        rep = validate.validate(pd.DataFrame(rows), table)
        assert validate.is_ok(rep), f"{table} failed the gate: {rep['errors']}"
        print(f"  V1 {table}: gate OK ({rep['stats']['rows']:,} rows)")

    print("ALL ARRESTS/CASE-SECTIONS GATES PASSED")


if __name__ == "__main__":
    run()
