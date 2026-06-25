"""GARUDA AppSail — analytics endpoints (Phases 4-5).

Phase 4 — entity resolution + MO fingerprinting:
  POST /resolve/run     : Entities -> canonical_id + match_confidence (borderline -> Review_Queue).
  POST /mo/run          : Incidents -> mo_cluster_id + MO_Clusters signatures.
  POST /geocode/backfill: fill Incidents missing lat/long.

Phase 5 — co-offender network / crime-series / anomaly (the hero reveal):
  GET  /network/top         : highest-centrality persons (candidate kingpins).
  GET  /network/{canonical} : ego-subgraph JSON for the force graph (+optional cache).
  POST /network/run         : (re)build the graph; report size + communities + top actors.
  POST /series/run          : link incidents into Crime_Series (MO + space-time near-repeat).
  POST /anomaly/run         : flag emerging-trend spikes into Alerts.

Reads/writes go through shared.store (local CSV by default; Catalyst Data Store via ZCQL
when GARUDA_BACKEND=zcql). The heavy ML stays here on AppSail; Node stays thin.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from engines import mo as mo_engine
from engines import network as net_engine
from engines.anomaly import detect as detect_anomalies
from engines.geocode.geocoder import geocode
from engines.resolution import resolve_entities, to_review_record
from engines.series import link_series
from shared import store

router = APIRouter(tags=["analytics"])

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MO_VECTOR_PATH = os.path.join(REPO, "data", "synthetic", "mo_vectors.npz")


class RunIn(BaseModel):
    write: bool = True          # write results back (Data Store / resolved CSVs)
    limit: Optional[int] = None  # cap rows (smoke tests)


@router.post("/resolve/run")
def resolve_run(body: RunIn):
    rows = store.fetch_entities()
    if body.limit:
        rows = rows[: body.limit]
    result = resolve_entities(rows)

    written = store.write_entity_resolution(result["assignments"]) if body.write else 0
    # borderline merges -> Review_Queue records (human decides; reuse the P3 pattern)
    reviews = [to_review_record(etype, a, b, s) for (etype, a, b, s) in result["review_pairs"]]
    return {
        "ok": True,
        "stats": result["stats"],
        "entities_written": written,
        "review_records": reviews[:500],   # cap the payload; full set goes to Review_Queue
        "review_total": len(reviews),
    }


@router.post("/mo/run")
def mo_run(body: RunIn):
    rows = store.fetch_incidents()
    if body.limit:
        rows = rows[: body.limit]
    res = mo_engine.fit_mo(rows)

    inc_written = clusters_written = 0
    if body.write:
        inc_written = store.write_incident_mo(res["assignments"])
        clusters_written = store.write_mo_clusters(res["clusters"])
        mo_engine.save_vectors(MO_VECTOR_PATH, res["ids"], res["vectors"])

    noise = sum(1 for v in res["assignments"].values() if v == "")
    return {
        "ok": True,
        "incidents": len(rows),
        "clusters": len(res["clusters"]),
        "noise": noise,
        "incidents_written": inc_written,
        "clusters_written": clusters_written,
        "sample_signatures": [
            {"cluster_id": c["cluster_id"], "label": c["label"], "size": c["size"]}
            for c in sorted(res["clusters"], key=lambda x: -x["size"])[:10]
        ],
    }


@router.post("/geocode/backfill")
def geocode_backfill(body: RunIn):
    """Fill lat/long for Incidents that are missing coordinates (reuses the geocoder)."""
    rows = store.fetch_incidents()
    if body.limit:
        rows = rows[: body.limit]
    updates = {}
    for r in rows:
        if not (r.get("lat") and r.get("long")) and r.get("address_text"):
            lat, lng, _conf, method = geocode(r["address_text"], r.get("district_code"))
            if lat is not None:
                updates[r["incident_id"]] = (lat, lng)
    written = store.write_incident_coords(updates) if body.write else 0
    return {"ok": True, "scanned": len(rows), "backfilled": len(updates), "written": written}


# --------------------------------------------------------------------------- #
# Phase 5 — co-offender network / crime-series / anomaly
# --------------------------------------------------------------------------- #
# The graph is expensive to build, so cache it in-process. /network/run rebuilds.
_NET_CACHE = {"analysis": None}


def _network_analysis(rebuild=False):
    if _NET_CACHE["analysis"] is None or rebuild:
        _NET_CACHE["analysis"] = net_engine.analyze(
            store.fetch_incidents_p5(), store.fetch_entities_p5(), store.fetch_edges_p5())
    return _NET_CACHE["analysis"]


@router.get("/network/top")
def network_top(n: int = 10, node_type: str = "person"):
    """Candidate kingpins: highest-centrality nodes (default persons)."""
    a = _network_analysis()
    return {"top": net_engine.top_actors(a["graph"], a["betweenness"], a["degree"],
                                         n=n, node_type=node_type)}


@router.get("/network/rings")
def network_rings(min_persons: int = 3, min_districts: int = 2, top: int = 20):
    """Organized cross-district rings — the 'show me the gangs' query."""
    a = _network_analysis()
    return {"rings": net_engine.cross_district_rings(
        a["graph"], a["communities"], min_persons=min_persons,
        min_districts=min_districts, top=top)}


@router.get("/network/{canonical_id}")
def network_ego(canonical_id: str, radius: int = 2, cache: bool = False):
    """Ego-subgraph around a canonical entity — the JSON the Phase-8 force graph draws."""
    a = _network_analysis()
    payload = net_engine.ego_json(a["graph"], canonical_id, a["betweenness"],
                                  a["degree"], a["communities"], radius=radius)
    if cache and payload.get("node_count"):
        payload["cached_to"] = store.write_network_cache(canonical_id, payload)
    return payload


@router.post("/network/run")
def network_run():
    """(Re)build the whole co-offender graph; report size, communities, top actors."""
    a = _network_analysis(rebuild=True)
    G = a["graph"]
    return {"ok": True, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
            "communities": len(set(a["communities"].values())),
            "top": net_engine.top_actors(G, a["betweenness"], a["degree"], n=5)}


@router.post("/series/run")
def series_run(body: RunIn):
    rows = store.fetch_incidents_p5()
    if body.limit:
        rows = rows[: body.limit]
    res = link_series(rows)
    series_written = inc_written = 0
    if body.write:
        series_written = store.write_crime_series(res["series"])
        inc_written = store.write_incident_series(res["assignments"])
    return {"ok": True, "series": len(res["series"]),
            "incidents_linked": len(res["assignments"]),
            "series_written": series_written, "incidents_written": inc_written,
            "sample": res["series"][:10]}


@router.post("/anomaly/run")
def anomaly_run(body: RunIn):
    rows = store.fetch_incidents_p5()
    res = detect_anomalies(rows)
    written = store.write_alerts(res["alerts"]) if body.write else 0
    return {"ok": True, "alerts": len(res["alerts"]), "written": written,
            "sample": res["alerts"][:20]}
