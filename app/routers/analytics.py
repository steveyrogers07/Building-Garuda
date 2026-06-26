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

Phase 6 — predictive & explainable risk forecasting (places x times, not people):
  POST /risk/run            : walk-forward backtest (PAI/PEI/PR-AUC) + write Predictive_Risk.
  GET  /risk/top            : current highest-risk area x crime-type cells.
  GET  /risk/explain        : SHAP drivers for one area x crime-type prediction.
  GET  /risk/fairness       : per-ward predicted-vs-actual bias audit.

Phase 7 — intelligence copilot (hybrid RAG over FIRs):
  POST /copilot             : NL -> structured filters + semantic retrieval -> cited answer
                              (guardrails: never asserts guilt; refuses out-of-scope; audited).

Reads/writes go through shared.store (local CSV by default; Catalyst Data Store via ZCQL
when GARUDA_BACKEND=zcql). The heavy ML stays here on AppSail; Node stays thin.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from engines import copilot as cp
from engines import forecasting as fc
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


# --------------------------------------------------------------------------- #
# Phase 6 — predictive & explainable risk forecasting
# --------------------------------------------------------------------------- #
# Training is expensive; cache the model + backtest + current risk surface.
_RISK_CACHE = {"state": None}


def _risk_state(rebuild=False):
    if _RISK_CACHE["state"] is None or rebuild:
        t, feats = fc.build_feature_table(store.fetch_incidents_p5(),
                                          store.fetch_socioeconomic())
        wf = fc.walk_forward(t, feats, n_folds=3)
        model = fc.fit(t, feats)
        cur, last = fc.forecast_next(t, feats, model)
        samp = t.sample(min(40000, len(t)), random_state=0).copy()
        samp["score"] = model.predict_proba(samp[feats])[:, 1]
        fair_df, fair_sum = fc.fairness_audit(samp, "score")
        _RISK_CACHE["state"] = {"t": t, "feats": feats, "model": model, "cur": cur,
                                "last": last, "wf": wf, "fair": (fair_df, fair_sum)}
    return _RISK_CACHE["state"]


def _risk_rows(st, n=None):
    """Predictive_Risk rows for the current risk surface (top SHAP drivers inline)."""
    cur = st["cur"] if n is None else st["cur"].head(n)
    feats, model = st["feats"], st["model"]
    booster = getattr(model, "booster_", model)
    contrib = booster.predict(cur[feats].to_numpy(dtype=float), pred_contrib=True)
    period = str(pd.Timestamp(st["last"]).date())
    pai = st["wf"]["summary"].get("pai")
    rows = []
    for i, (_, r) in enumerate(cur.reset_index(drop=True).iterrows()):
        vals = contrib[i][:-1]
        drivers = [feats[j] for j in np.argsort(np.abs(vals))[::-1][:3]]
        rows.append({"grid_id": r["area_code"], "district_code": r["area_code"],
                     "crime_type": r["crime_type"], "period": period,
                     "risk_score": round(float(r["risk_score"]), 4), "rank": int(r["rank"]),
                     "top_drivers": json.dumps(drivers), "model_version": fc.MODEL_VERSION,
                     "backtest_pai": pai})
    return rows


@router.post("/risk/run")
def risk_run(body: RunIn):
    st = _risk_state(rebuild=True)
    rows = _risk_rows(st)
    written = store.write_predictive_risk(rows) if body.write else 0
    return {"ok": True, "metrics": st["wf"]["summary"], "base_rate": st["wf"]["base_rate"],
            "model_version": fc.MODEL_VERSION, "risk_cells": len(rows),
            "written": written, "top": rows[:10]}


@router.get("/risk/top")
def risk_top(n: int = 20):
    st = _risk_state()
    return {"as_of": str(pd.Timestamp(st["last"]).date()), "top": _risk_rows(st, n=n)}


@router.get("/risk/explain")
def risk_explain(area: str, crime_type: str):
    """SHAP drivers: why is this area x crime-type risky right now?"""
    st = _risk_state()
    cur = st["cur"]
    row = cur[(cur["area_code"] == area) & (cur["crime_type"] == crime_type)]
    if row.empty:
        return {"error": "unknown area/crime_type", "area": area, "crime_type": crime_type}
    drivers = fc.shap_drivers(st["model"], row[st["feats"]].to_numpy(dtype=float),
                              st["feats"], top=8)
    return {"area": area, "crime_type": crime_type,
            "risk_score": round(float(row.iloc[0]["risk_score"]), 4), "drivers": drivers}


@router.get("/risk/fairness")
def risk_fairness():
    st = _risk_state()
    fair_df, fair_sum = st["fair"]
    return {"summary": fair_sum, "wards": fair_df.to_dict("records")}


# --------------------------------------------------------------------------- #
# Phase 7 — intelligence copilot (hybrid RAG over FIRs)
# --------------------------------------------------------------------------- #
_COPILOT_CACHE = {"state": None}


def _copilot_state(rebuild=False):
    if _COPILOT_CACHE["state"] is None or rebuild:
        inc = store.fetch_incidents_copilot()
        index, refs = cp.prepare(inc, store.fetch_socioeconomic())
        _COPILOT_CACHE["state"] = {"incidents": inc, "index": index, "refs": refs}
    return _COPILOT_CACHE["state"]


class CopilotIn(BaseModel):
    query: str
    actor: Optional[str] = "demo"
    role: Optional[str] = "analyst"
    top_k: int = 10


@router.post("/copilot")
def copilot(body: CopilotIn):
    """Plain-English Q&A over FIRs: hybrid retrieval + mandatory citations + guardrails."""
    st = _copilot_state()
    res = cp.answer(body.query, st["incidents"], st["index"], st["refs"], top_k=body.top_k)
    store.write_audit_log(cp.audit_entry(body.query, res, actor=body.actor, role=body.role))
    return res
