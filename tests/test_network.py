"""GARUDA — local Phase-5 analytics evaluation (no Catalyst).

Builds the co-offender network + crime-series + anomalies over the synthetic set
and checks the Phase-5 exit gates against ground_truth.json:
  - G1  graph builds; the kingpin's ego-subgraph serialises (nodes + edges).
  - G2  planted gang recovered: kingpin = top betweenness among members,
        the gang is one Louvain community, and links span BNU/RMN/TMK/KLR.
  - G3  the planted MYS house-burglary series is recovered as one series.
  - G4  the planted spikes (BNU two-wheeler x4, etc.) are flagged as Alerts.

Run:  python tests/test_network.py
Prereqs: python data/generate.py   (Phase-4 outputs optional; falls back to the
         planted canonical_id in entities.csv)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))    # AppSail-style imports (engines/, shared/)

from engines import network as net               # noqa: E402
from engines.anomaly import detect               # noqa: E402
from engines.series import link_series           # noqa: E402

SYN = REPO / "data" / "synthetic"


def _load():
    inc = pd.read_csv(SYN / "incidents.csv", dtype=str, keep_default_na=False).to_dict("records")
    ent = pd.read_csv(SYN / "entities.csv", dtype=str, keep_default_na=False)
    ent["canonical_id"] = [c or e for c, e in zip(ent["canonical_id"], ent["entity_id"])]
    ent = ent.to_dict("records")
    edg = pd.read_csv(SYN / "incident_edges.csv", dtype=str, keep_default_na=False).to_dict("records")
    ground = json.loads((SYN / "ground_truth.json").read_text(encoding="utf-8"))
    return inc, ent, edg, ground


def run():
    inc, ent, edg, ground = _load()

    # ---- G1: build graph + metrics ----
    a = net.analyze(inc, ent, edg)
    G, betw, deg, comm = a["graph"], a["betweenness"], a["degree"], a["communities"]
    print(f"graph: {G.number_of_nodes():,} nodes  {G.number_of_edges():,} edges  "
          f"communities={len(set(comm.values())):,}")

    gnet = ground["network"]
    members = gnet["member_entity_ids"]
    kingpin = gnet["kingpin_entity_id"]
    strength = a["strength"]

    # click the kingpin -> the whole gang (members + the shared phone & vehicle)
    ego = net.ego_json(G, kingpin, betw, deg, comm, radius=2)
    ego_ids = {nd["id"] for nd in ego["nodes"]}
    print(f"kingpin {kingpin} ({gnet['kingpin_value']}) 2-hop ego: "
          f"{ego['node_count']} nodes / {ego['edge_count']} edges")
    assert set(members).issubset(ego_ids), "kingpin ego does not reveal the full gang"
    types_in_ego = {nd["type"] for nd in ego["nodes"]}
    assert {"phone", "vehicle"} <= types_in_ego, "shared phone/vehicle not in the ego graph"

    # ---- G2a: kingpin = top centrality among the gang (betweenness, then strength) ----
    ranked = sorted(members, key=lambda m: (betw.get(m, 0.0), strength.get(m, 0)),
                    reverse=True)
    print("gang ranking (betweenness, strength):",
          [(m, round(betw.get(m, 0.0), 3), strength.get(m)) for m in ranked])
    assert ranked[0] == kingpin, f"kingpin not top centrality ({ranked[0]} != {kingpin})"
    # the kingpin must lead the candidate list built from its own gang community
    gang_ids = [x for x in comm if comm[x] == comm[kingpin]
                and G.nodes[x].get("type") == "person"]
    gang_top = net.top_actors(G.subgraph(gang_ids), betw, deg, n=1, node_type="person")
    assert gang_top and gang_top[0]["id"] == kingpin, "kingpin not #1 in its community"

    # ---- G2b: the gang is one community ----
    member_comms = {comm.get(m) for m in members}
    print("gang communities:", member_comms)
    assert len(member_comms) == 1, f"gang split across communities {member_comms}"

    # ---- G2c: links span the planted districts ----
    spanned = set()
    for m in members:
        spanned |= set(G.nodes[m]["districts"])
    print("gang districts:", sorted(spanned))
    assert set(gnet["districts"]).issubset(spanned), \
        f"missing districts {set(gnet['districts']) - spanned}"

    # ---- G2d: the 'show me the gangs' query surfaces this gang as ring #1 ----
    rings = net.cross_district_rings(G, comm, top=5)
    assert rings, "no cross-district rings found"
    top_ring = rings[0]
    print(f"top ring: kingpin={top_ring['kingpin_label']} persons={top_ring['persons']} "
          f"districts={top_ring['districts']} shared={top_ring['shared_links']}")
    assert top_ring["kingpin_id"] == kingpin, "planted gang is not the #1 ring"
    assert set(gnet["districts"]).issubset(set(top_ring["districts"]))

    # ---- G3: crime-series linkage recovers the planted MYS burglary series ----
    sres = link_series(inc)
    planted = ground["series"]["incident_ids"]
    got = Counter(sres["assignments"].get(i) for i in planted)
    modal, modal_n = got.most_common(1)[0]
    print(f"series: {len(sres['series'])} total; planted {modal_n}/{len(planted)} in {modal}")
    assert modal is not None and modal_n >= len(planted) - 1, "planted series not recovered"

    # ---- G4: anomaly detection recovers the planted spikes ----
    alerts = detect(inc)["alerts"]
    found = []
    for an in ground["anomalies"]:
        hit = any(al["district_code"] == an["district_code"]
                  and al["crime_type"] == an["crime_type"]
                  and al["window_start"].startswith(an["month"])
                  for al in alerts)
        found.append(hit)
    print(f"anomaly: {len(alerts)} alerts; planted spikes found {sum(found)}/{len(found)}")
    for al in alerts[:6]:
        print(f"  {al['severity']:6} {al['detail']}")
    assert all(found), "not all planted spikes detected"

    print("\nPASS")


def test_network():
    run()


if __name__ == "__main__":
    run()
