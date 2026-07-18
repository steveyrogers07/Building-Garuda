"""GARUDA co-offender network engine (Phase 5) — the hero.

Turns siloed FIRs into one visible criminal network. Nodes are *canonical*
entities (persons / phones / vehicles, after Phase-4 resolution); an edge means
two canonical entities co-occur in the same incident. Because a shared phone or
vehicle is itself a canonical node, the people who used it become connected
through it — so a gang that never appears together in a single FIR still lights
up as one structure.

We then compute:
  * degree + betweenness centrality  -> the "kingpin" signal (who bridges the gang)
  * Louvain communities              -> the "gang" signal (who clusters together)
  * (optional) Adamic-Adar link prediction -> likely-hidden associates

and emit an ego-subgraph JSON for the Phase-8 force graph.

Pure Python + networkx. Storage-agnostic: callers pass plain row dicts (the
shared.store layer reads them from local CSV or the Catalyst Data Store / ZCQL).
"""
from __future__ import annotations

import itertools
from collections import defaultdict

import networkx as nx

try:                                    # networkx >= 3 ships Louvain in core
    from networkx.algorithms.community import louvain_communities
except Exception:                       # pragma: no cover - very old networkx
    louvain_communities = None

PERSON, PHONE, VEHICLE = "person", "phone", "vehicle"
LINK_TYPES = (PHONE, VEHICLE)           # entities that connect their users

# Exact betweenness is O(V*E); above this many nodes in a single component we
# sample pivots instead (deterministic seed). Components are tiny in practice,
# so the planted gang is always computed exactly.
_BETWEENNESS_EXACT_MAX = 1500


# --------------------------------------------------------------------------- #
# graph construction
# --------------------------------------------------------------------------- #
def _canon_map(entities):
    """entity_id -> canonical_id, plus canonical_id -> {type, value} (label)."""
    cid_of, meta = {}, {}
    for e in entities:
        eid = e["entity_id"]
        cid = (e.get("canonical_id") or "").strip() or eid
        cid_of[eid] = cid
        # the canonical record itself wins the label; otherwise first-seen
        if cid not in meta or eid == cid:
            meta[cid] = {"type": e.get("type", ""), "value": e.get("value", "")}
    return cid_of, meta


def build_graph(incidents, entities, edges):
    """Build the canonical co-offender graph.

    Returns an ``nx.Graph`` whose nodes carry ``type/value/label/incidents/
    districts`` and whose edges carry ``weight`` (co-occurrence count),
    ``kinds`` (set) and ``incidents`` (set).
    """
    cid_of, meta = _canon_map(entities)
    inc_meta = {
        i["incident_id"]: {
            "district": i.get("district_code", ""),
            "crime_type": i.get("crime_type", ""),
            "occurred_at": i.get("occurred_at", ""),
            "mo_cluster_id": i.get("mo_cluster_id", ""),
        }
        for i in incidents
    }

    inc_cids = defaultdict(set)          # incident_id -> {canonical_id}
    for ed in edges:
        # Complainants are FIR *reporters*, not actors in the offence — linking
        # them into a co-offender graph would fabricate associations (and, at
        # ~1 per FIR, drown the real network's centrality in reporting noise).
        # They still appear on the case file and in dossiers via the parties
        # path; only the offender-network build excludes them.
        if ed.get("role") == "complainant":
            continue
        cid = cid_of.get(ed["entity_id"])
        if cid is not None:
            inc_cids[ed["incident_id"]].add(cid)

    G = nx.Graph()

    def _touch(cid, iid):
        if cid not in G:
            m = meta.get(cid, {"type": "", "value": cid})
            G.add_node(cid, type=m["type"], value=m["value"], label=m["value"],
                       incidents=set(), districts=set())
        node = G.nodes[cid]
        node["incidents"].add(iid)
        dist = inc_meta.get(iid, {}).get("district")
        if dist:
            node["districts"].add(dist)

    def _kind(a, b):
        ta, tb = meta.get(a, {}).get("type"), meta.get(b, {}).get("type")
        if ta in LINK_TYPES:
            return "shared_" + ta
        if tb in LINK_TYPES:
            return "shared_" + tb
        return "co_offence"

    for iid, cids in inc_cids.items():
        for cid in cids:
            _touch(cid, iid)
        for a, b in itertools.combinations(sorted(cids), 2):
            if G.has_edge(a, b):
                e = G[a][b]
                e["weight"] += 1
                e["kinds"].add(_kind(a, b))
                e["incidents"].add(iid)
            else:
                G.add_edge(a, b, weight=1, kinds={_kind(a, b)}, incidents={iid})

    return G


# --------------------------------------------------------------------------- #
# metrics
# --------------------------------------------------------------------------- #
def betweenness(G):
    """Betweenness centrality, computed per connected component (exact for the
    small components that matter, sampled only inside any huge one)."""
    bc = {}
    for comp in nx.connected_components(G):
        if len(comp) < 3:               # dyads/singletons: nobody bridges
            bc.update({n: 0.0 for n in comp})
            continue
        sub = G.subgraph(comp)
        if sub.number_of_nodes() <= _BETWEENNESS_EXACT_MAX:
            bc.update(nx.betweenness_centrality(sub, normalized=True))
        else:                           # pragma: no cover - perf guard
            k = _BETWEENNESS_EXACT_MAX
            bc.update(nx.betweenness_centrality(sub, k=k, normalized=True, seed=42))
    return bc


def detect_communities(G):
    """canonical_id -> community index (Louvain; component fallback)."""
    if G.number_of_edges() == 0:
        comms = [{n} for n in G.nodes]
    elif louvain_communities is not None:
        comms = louvain_communities(G, weight="weight", seed=42)
    else:                               # pragma: no cover
        comms = list(nx.connected_components(G))
    return {n: i for i, comm in enumerate(comms) for n in comm}


def analyze(incidents, entities, edges):
    """One-shot: build the graph and compute degree + betweenness + communities."""
    G = build_graph(incidents, entities, edges)
    deg = nx.degree_centrality(G) if G.number_of_nodes() else {}
    return {
        "graph": G,
        "degree": deg,
        "strength": dict(G.degree(weight="weight")),
        "betweenness": betweenness(G),
        "communities": detect_communities(G),
    }


# --------------------------------------------------------------------------- #
# serialization (for the Phase-8 force graph)
# --------------------------------------------------------------------------- #
def _node_row(G, n, betw=None, deg=None, comm=None):
    a = G.nodes[n]
    row = {
        "id": n,
        "label": a.get("value", ""),
        "type": a.get("type", ""),
        "incident_count": len(a.get("incidents", ())),
        "degree_count": G.degree(n),
        "strength": G.degree(n, weight="weight"),     # weighted degree (co-occurrence)
        "districts": sorted(a.get("districts", ())),
    }
    if deg is not None:
        row["degree"] = round(deg.get(n, 0.0), 5)
    if betw is not None:
        row["betweenness"] = round(betw.get(n, 0.0), 5)
    if comm is not None:
        row["community"] = comm.get(n)
    return row


def centrality_score(G, betw, nodes=None):
    """Normalized 0..1 "key player" score = mean of betweenness and weighted
    degree, each scaled by the max over ``nodes`` (default: all nodes).

    This deliberately blends two signals: betweenness surfaces *brokers* in loose
    networks, while weighted degree (strength) surfaces *prolific co-offenders* —
    e.g. a kingpin inside a tight clique, where betweenness alone is degenerate.
    """
    nodes = list(nodes if nodes is not None else G.nodes)
    strength = {x: G.degree(x, weight="weight") for x in nodes}
    bmax = max((betw.get(x, 0.0) for x in nodes), default=0.0) or 1.0
    smax = max(strength.values(), default=0) or 1
    return {x: round(0.5 * betw.get(x, 0.0) / bmax + 0.5 * strength[x] / smax, 5)
            for x in nodes}


def top_actors(G, betw, deg, n=10, node_type="person"):
    """Highest-centrality nodes (default: persons) — the candidate kingpins."""
    nodes = [x for x in G.nodes
             if node_type is None or G.nodes[x].get("type") == node_type]
    score = centrality_score(G, betw, nodes)
    nodes.sort(key=lambda x: (score[x], len(G.nodes[x].get("incidents", ()))),
               reverse=True)
    rows = []
    for x in nodes[:n]:
        row = _node_row(G, x, betw, deg)
        row["centrality_score"] = score[x]
        rows.append(row)
    return rows


def cross_district_rings(G, communities=None, min_districts=2, min_incidents=4,
                         top=20, max_districts=8):
    """Organized rings anchored on a SHARED phone/vehicle reused across districts.

    A single reused burner phone or number plate crossing district lines is the
    organized-crime fingerprint. We take each link entity (phone/vehicle) that
    spans >= ``min_districts`` districts over >= ``min_incidents`` incidents, build
    the crew that co-offended with it, and de-duplicate rings with the same crew
    (so a gang's phone and vehicle collapse into one ring). Ranked by how heavily
    the link is used, then how many distinct shared links the crew runs (phone AND
    vehicle beats a lone plate), then district reach — which is what makes a
    deliberate cross-district gang stand out from incidental plate reuse.

    ``max_districts`` drops implausibly wide crews: a real syndicate sharing one
    burner/plate works a cluster of neighbouring districts, so a "ring" smeared
    across a third of the state is a graph artefact (incidental reuse chaining
    through a high-degree node), not organised crime — filtering it keeps the
    surfaced rings believable instead of noisy."""
    rings_by_crew = {}
    for n in G.nodes:
        if G.nodes[n].get("type") not in LINK_TYPES:
            continue
        districts = G.nodes[n].get("districts", ())
        incidents = G.nodes[n].get("incidents", ())
        if len(districts) < min_districts or len(incidents) < min_incidents:
            continue
        crew = frozenset(m for m in G[n] if G.nodes[m].get("type") == PERSON)
        if not crew:
            continue
        ring = rings_by_crew.get(crew)
        if ring is None:
            d_all, i_all = set(), set()
            for p in crew:
                d_all |= set(G.nodes[p].get("districts", ()))
                i_all |= set(G.nodes[p].get("incidents", ()))
            kingpin = max(crew, key=lambda x: G.degree(x, weight="weight"))
            ring = {
                "persons": len(crew),
                "districts": sorted(d_all),
                "district_count": len(d_all),
                "incident_count": len(i_all),
                "kingpin_id": kingpin,
                "kingpin_label": G.nodes[kingpin].get("value", ""),
                "shared_links": [],
                "link_uses": 0,
                "community": (communities or {}).get(kingpin),
            }
            rings_by_crew[crew] = ring
        ring["shared_links"].append(G.nodes[n].get("value", ""))
        ring["link_uses"] = max(ring["link_uses"], len(incidents))

    rings = [r for r in rings_by_crew.values() if r["district_count"] <= max_districts]
    rings.sort(key=lambda r: (r["link_uses"], len(r["shared_links"]),
                              r["district_count"]), reverse=True)
    return rings[:top]


def ego_json(G, center, betw, deg, comm, radius=1, max_nodes=80):
    """Ego subgraph around ``center`` as force-graph JSON (nodes + edges)."""
    if center not in G:
        return {"center": center, "node_count": 0, "edge_count": 0,
                "nodes": [], "edges": [], "error": "unknown canonical_id"}
    sub = nx.ego_graph(G, center, radius=radius)
    if sub.number_of_nodes() > max_nodes:        # keep center + densest neighbours
        keep = set(sorted(sub.nodes, key=lambda x: deg.get(x, 0.0),
                          reverse=True)[:max_nodes]) | {center}
        sub = sub.subgraph(keep)
    edges = [{"source": a, "target": b, "weight": d["weight"],
              "kinds": sorted(d["kinds"]), "incidents": sorted(d["incidents"])}
             for a, b, d in sub.edges(data=True)]
    return {
        "center": center,
        "node_count": sub.number_of_nodes(),
        "edge_count": len(edges),
        "nodes": [_node_row(G, x, betw, deg, comm) for x in sub.nodes],
        "edges": edges,
    }


def predict_links(G, center, top=5):
    """Adamic-Adar suggestions for likely-hidden ties to ``center`` (within 2 hops)."""
    if center not in G:
        return []
    cand = (nx.ego_graph(G, center, radius=2).nodes() - set(G[center]) - {center})
    pairs = [(center, c) for c in cand]
    scored = sorted(nx.adamic_adar_index(G, pairs), key=lambda t: -t[2])
    return [{"id": c, "label": G.nodes[c].get("value", ""),
             "type": G.nodes[c].get("type", ""), "score": round(s, 4)}
            for _u, c, s in scored[:top] if s > 0]
