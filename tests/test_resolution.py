"""GARUDA — local entity-resolution evaluation (no Catalyst).

Runs the Phase-4 resolver over the Phase-2 entities and scores the *rediscovered*
canonical groupings against the planted truth. The truth lives in entities.csv itself:
the generator wrote each alias with canonical_id = its parent's id (and alias_of = parent).
The resolver is fed ONLY entity_id/type/value/age/gender — never canonical_id/alias_of —
and must recover those groupings.

Reports pairwise precision/recall/F1 (target precision >= 0.90) and asserts the planted
gang resolves correctly: the shared phone/vehicle stay single canonical entities that link
incidents across BNU/RMN/TMK/KLR, and the kingpin stays one entity.

Run:  python tests/test_resolution.py
Prereqs: python data/generate.py && python data/build_reference.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))   # AppSail-style imports (engines/, shared/)

from engines.resolution import resolve_entities   # noqa: E402

SYN = REPO / "data" / "synthetic"


def _pairs(groups):
    """Set of same-cluster (a,b) pairs over a {cluster_key: [ids]} mapping."""
    out = set()
    for ids in groups.values():
        for a, b in combinations(sorted(ids), 2):
            out.add((a, b))
    return out


def run():
    ent = pd.read_csv(SYN / "entities.csv", dtype=str, keep_default_na=False)
    edges = pd.read_csv(SYN / "incident_edges.csv", dtype=str, keep_default_na=False)
    inc = pd.read_csv(SYN / "incidents.csv", dtype=str, keep_default_na=False)
    ground = json.loads((SYN / "ground_truth.json").read_text(encoding="utf-8"))

    # feed the resolver ONLY the observable fields (no canonical_id / alias_of)
    rows = ent[["entity_id", "type", "value", "age", "gender"]].to_dict("records")
    result = resolve_entities(rows)
    assign = result["assignments"]
    print(f"entities: {result['stats']['entities']:,}  "
          f"canonical clusters: {result['stats']['canonical_clusters']:,}  "
          f"merged: {result['stats']['merged']:,}  "
          f"review pairs: {result['stats']['review_pairs']:,}")

    # ---- pairwise precision/recall/F1 on PERSONS (the alias challenge) ----
    persons = ent[ent["type"] == "person"]
    truth_groups = defaultdict(list)
    for r in persons.itertuples():
        truth_groups[r.canonical_id].append(r.entity_id)      # planted truth
    pred_groups = defaultdict(list)
    for eid in persons["entity_id"]:
        pred_groups[assign[eid]["canonical_id"]].append(eid)  # rediscovered

    tp_set = _pairs(truth_groups)
    pp_set = _pairs(pred_groups)
    tp = len(tp_set & pp_set)
    precision = tp / max(len(pp_set), 1)
    recall = tp / max(len(tp_set), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    print("\nperson resolution vs planted truth (pairwise):")
    print(f"  true alias pairs : {len(tp_set):,}")
    print(f"  predicted pairs  : {len(pp_set):,}")
    print(f"  precision        : {precision:6.3f}")
    print(f"  recall           : {recall:6.3f}")
    print(f"  F1               : {f1:6.3f}")

    # ---- G5: planted gang ----
    net = ground["network"]
    print("\nplanted gang (G5):")

    def canon_of_value(value, etype):
        m = ent[(ent["value"] == value) & (ent["type"] == etype)]
        eid = m["entity_id"].iloc[0]
        return eid, assign[eid]["canonical_id"]

    ph_eid, ph_canon = canon_of_value(net["shared_phone"], "phone")
    vh_eid, vh_canon = canon_of_value(net["shared_vehicle"], "vehicle")

    # the shared phone/vehicle must each be a single canonical entity that does NOT
    # absorb a different number/plate (exact-merge keeps them clean)
    ph_cluster = [e for e in assign if assign[e]["canonical_id"] == ph_canon]
    vh_cluster = [e for e in assign if assign[e]["canonical_id"] == vh_canon]
    ph_vals = set(ent[ent["entity_id"].isin(ph_cluster)]["value"])
    vh_vals = set(ent[ent["entity_id"].isin(vh_cluster)]["value"])

    # districts the shared phone/vehicle reach, via edges -> incidents
    def districts_for(canon):
        cluster = {e for e in assign if assign[e]["canonical_id"] == canon}
        iids = set(edges[edges["entity_id"].isin(cluster)]["incident_id"])
        return set(inc[inc["incident_id"].isin(iids)]["district_code"])

    ph_districts = districts_for(ph_canon)
    vh_districts = districts_for(vh_canon)
    want = set(net["districts"])

    kp = net["kingpin_entity_id"]
    kp_canon = assign[kp]["canonical_id"]
    kp_cluster_vals = set(ent[ent["entity_id"].isin(
        [e for e in assign if assign[e]["canonical_id"] == kp_canon])]["value"])
    members_canon = {m: assign[m]["canonical_id"] for m in net["member_entity_ids"]}

    print(f"  shared phone {net['shared_phone']}  -> 1 number? {ph_vals == {net['shared_phone']}}; "
          f"districts {sorted(ph_districts)} superset of {sorted(want)}? {want <= ph_districts}")
    print(f"  shared vehicle {net['shared_vehicle']} -> 1 plate?  {vh_vals == {net['shared_vehicle']}}; "
          f"districts {sorted(vh_districts)} superset of {sorted(want)}? {want <= vh_districts}")
    print(f"  kingpin {net['kingpin_value']!r} stays one entity (no wrong merge)? "
          f"{kp_cluster_vals == {net['kingpin_value']}}")
    print(f"  members resolve to {len(set(members_canon.values()))} distinct canonical ids "
          f"(of {len(net['member_entity_ids'])})")

    # ---- gate ----
    assert precision >= 0.90, f"person precision {precision:.3f} < 0.90"
    assert ph_vals == {net["shared_phone"]}, "shared phone over-merged with another number"
    assert vh_vals == {net["shared_vehicle"]}, "shared vehicle over-merged with another plate"
    assert want <= ph_districts, "shared phone does not link all 4 gang districts"
    assert want <= vh_districts, "shared vehicle does not link all 4 gang districts"
    assert kp_cluster_vals == {net["kingpin_value"]}, "kingpin wrongly merged with another person"
    print("\nPASS")


def test_resolution():
    run()


if __name__ == "__main__":
    run()
