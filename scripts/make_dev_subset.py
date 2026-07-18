"""GARUDA — carve a Dev-tier Data Store subset out of the canonical CSVs.

The Catalyst *development* environment hard-caps the Data Store at 5,000 records
per table and 25,000 records per project (production is uncapped) — the full
corpus (~75k rows) cannot be loaded there. Under plan §4.1 Option A that's fine:
Dev's Data Store is the write system-of-record + ZCQL smoke-test surface, not
the read path. This script emits the largest *referentially coherent* subset
that fits the caps, force-including the planted network (ground_truth.json)
so the cross-district JOIN smoke test in schema/create_tables.md works.

Run AFTER the canonical CSVs exist (loader --dry-run emits them):
    python scripts/make_dev_subset.py
Output: data/synthetic/_dev_subset/<Table>.csv  (ds:import / console-Import ready)
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SYN_CANON = REPO / "data" / "synthetic" / "_canonical"
REF_CANON = REPO / "data" / "reference" / "_canonical"
OUT = REPO / "data" / "synthetic" / "_dev_subset"

TABLE_CAP = 5000
PROJECT_CAP = 25000

# Copied whole — tiny reference/master tables.
SMALL = ["Officers", "Courts", "Case_Status", "Crime_Head_Sections",
         "Socioeconomic", "Geo_Boundaries", "Units"]


def read(table):
    p = (REF_CANON if table in ("Socioeconomic", "Geo_Boundaries") else SYN_CANON) / f"{table}.csv"
    if not p.exists():
        raise SystemExit(f"missing {p} — run the loader --dry-run commands in "
                         "schema/create_tables.md first to emit the canonical CSVs")
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def carve(n_incidents, tables, forced_inc, forced_ent):
    """Coherent subset around the first n incidents + the forced (planted) ids."""
    inc_ids = set(forced_inc)
    for r in tables["Incidents"]:
        if len(inc_ids) >= n_incidents:
            break
        inc_ids.add(r["incident_id"])
    sub = {"Incidents": [r for r in tables["Incidents"] if r["incident_id"] in inc_ids]}
    sub["Incident_Edges"] = [r for r in tables["Incident_Edges"] if r["incident_id"] in inc_ids]
    sub["Case_Sections"] = [r for r in tables["Case_Sections"] if r["incident_id"] in inc_ids]
    sub["Arrests"] = [r for r in tables["Arrests"] if r["incident_id"] in inc_ids]
    sub["Chargesheets"] = [r for r in tables["Chargesheets"] if r["incident_id"] in inc_ids]
    ent_ids = ({r["entity_id"] for r in sub["Incident_Edges"]}
               | {r["entity_id"] for r in sub["Arrests"]} | set(forced_ent))
    sub["Entities"] = [r for r in tables["Entities"] if r["entity_id"] in ent_ids]
    return sub


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--headroom", type=int, default=6000,
                    help="project-level rows reserved for runtime writes "
                         "(Audit_Log/Alerts/Review_Queue/Predictive_Risk/...)")
    args = ap.parse_args()
    budget = PROJECT_CAP - args.headroom

    gt = json.load(open(REPO / "data" / "synthetic" / "ground_truth.json", encoding="utf-8"))
    forced_inc = gt["network"]["incident_ids"]
    forced_ent = gt["network"]["member_entity_ids"]

    tables = {t: read(t) for t in
              ["Incidents", "Entities", "Incident_Edges", "Case_Sections",
               "Arrests", "Chargesheets"] + SMALL}
    small_total = sum(len(tables[t]) for t in SMALL)

    n = 4000
    while n >= 100:
        sub = carve(n, tables, forced_inc, forced_ent)
        total = sum(len(v) for v in sub.values()) + small_total
        if total <= budget and all(len(v) <= TABLE_CAP for v in sub.values()):
            break
        n -= 100
    else:
        raise SystemExit("could not fit the caps even at 100 incidents")

    for t in SMALL:
        sub[t] = tables[t]
    OUT.mkdir(exist_ok=True)
    for t, rows in sub.items():
        with open(OUT / f"{t}.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    total = sum(len(v) for v in sub.values())
    print(f"dev subset @ {n} incidents (+{len(forced_inc)} planted) -> {OUT}")
    for t, rows in sorted(sub.items(), key=lambda kv: -len(kv[1])):
        print(f"  {t:<20} {len(rows):>6}")
    print(f"  {'TOTAL':<20} {total:>6}  (cap {PROJECT_CAP}, headroom {args.headroom})")
    planted = {r["incident_id"] for r in sub["Incidents"]} >= set(forced_inc)
    print(f"  planted network incidents included: {planted}")


if __name__ == "__main__":
    main()
