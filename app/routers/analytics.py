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
import threading
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from automation import briefs
from governance import audit as gaudit, masking, rbac
from engines import copilot as cp
from engines import district as district_engine
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


class _Lazy:
    """Thread-safe memoize-once for an expensive build (graph analysis, LightGBM
    walk-forward, TF-IDF index, anomaly scan). Plain "if cache is None: build()"
    is fine for a single request thread, but the background warm-up thread
    (main.py startup) can race a live request hitting the same cold cache —
    without a lock both would redundantly run the full computation at once,
    doubling CPU contention right when someone is watching. The lock only
    guards the (rare) build path; reads of an already-warm cache never block."""

    def __init__(self, build):
        self._build = build
        self._lock = threading.Lock()
        self._value = None

    def get(self, rebuild=False):
        if self._value is not None and not rebuild:
            return self._value
        with self._lock:
            if self._value is None or rebuild:
                self._value = self._build()
        return self._value


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
_NET_CACHE = _Lazy(lambda: net_engine.analyze(
    store.fetch_incidents_p5(), store.fetch_entities_p5(), store.fetch_edges_p5()))


def _network_analysis(rebuild=False):
    return _NET_CACHE.get(rebuild=rebuild)


@router.get("/network/top")
def network_top(n: int = 10, node_type: str = "person"):
    """Candidate kingpins: highest-centrality nodes (default persons)."""
    a = _network_analysis()
    return {"top": net_engine.top_actors(a["graph"], a["betweenness"], a["degree"],
                                         n=n, node_type=node_type)}


@router.get("/network/rings")
def network_rings(min_districts: int = 2, min_incidents: int = 4, top: int = 20):
    """Organized cross-district rings — the 'show me the gangs' query."""
    a = _network_analysis()
    return {"rings": net_engine.cross_district_rings(
        a["graph"], a["communities"], min_districts=min_districts,
        min_incidents=min_incidents, top=top)}


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


# The z-score/MAD scan is O(months^2) per (district, crime) series in pure Python
# and the frontend calls this (as a read, write=False) from both the Overview and
# Alerts screens on every mount — cache the detection result the same way the
# network/risk/copilot state is cached, and only rescan on an explicit write run.
_ANOMALY_CACHE = _Lazy(lambda: detect_anomalies(store.fetch_incidents_p5()))


def _anomaly_result(rebuild=False):
    return _ANOMALY_CACHE.get(rebuild=rebuild)


@router.post("/anomaly/run")
def anomaly_run(body: RunIn):
    res = _anomaly_result(rebuild=body.write)
    written = store.write_alerts(res["alerts"]) if body.write else 0
    return {"ok": True, "alerts": len(res["alerts"]), "written": written,
            "sample": res["alerts"][:20]}


# --------------------------------------------------------------------------- #
# Phase 6 — predictive & explainable risk forecasting
# --------------------------------------------------------------------------- #
# Training is expensive; cache the model + backtest + current risk surface.
def _build_risk_state():
    t, feats = fc.build_feature_table(store.fetch_incidents_p5(), store.fetch_socioeconomic())
    wf = fc.walk_forward(t, feats, n_folds=3)
    model = fc.fit(t, feats)
    cur, last = fc.forecast_next(t, feats, model)
    samp = t.sample(min(40000, len(t)), random_state=0).copy()
    samp["score"] = model.predict_proba(samp[feats])[:, 1]
    fair_df, fair_sum = fc.fairness_audit(samp, "score")
    return {"t": t, "feats": feats, "model": model, "cur": cur,
            "last": last, "wf": wf, "fair": (fair_df, fair_sum)}


_RISK_CACHE = _Lazy(_build_risk_state)


def _risk_state(rebuild=False):
    return _RISK_CACHE.get(rebuild=rebuild)


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
def _build_copilot_state():
    inc = store.fetch_incidents_copilot()
    index, refs = cp.prepare(inc, store.fetch_socioeconomic())
    return {"incidents": inc, "index": index, "refs": refs}


_COPILOT_CACHE = _Lazy(_build_copilot_state)


def _copilot_state(rebuild=False):
    return _COPILOT_CACHE.get(rebuild=rebuild)


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


# --------------------------------------------------------------------------- #
# Phase 8 — lightweight read endpoints for the frontend (stats + geo)
# --------------------------------------------------------------------------- #
@router.get("/stats")
def stats():
    """Headline counts for the Overview dashboard."""
    from collections import Counter
    inc = store.fetch_incidents_p5()
    cc = Counter(r.get("crime_type", "") for r in inc if r.get("crime_type"))
    dates = [r["occurred_at"][:10] for r in inc if r.get("occurred_at")]
    return {"incidents": len(inc), "entities": len(store.fetch_entities_p5()),
            "districts": len({r.get("district_code") for r in inc if r.get("district_code")}),
            "crime_types": len(cc), "by_crime": cc.most_common(10),
            "date_from": min(dates) if dates else None,
            "date_to": max(dates) if dates else None}


@router.get("/geo/districts")
def geo_districts():
    """Per-district centroid + incident load + top crime — powers the hotspot map."""
    inc = store.fetch_incidents_p5()
    socio = {s.get("area_code"): s for s in store.fetch_socioeconomic()}
    agg = {}
    for r in inc:
        d = r.get("district_code")
        if not d:
            continue
        a = agg.setdefault(d, {"n": 0, "lat": 0.0, "lng": 0.0, "k": 0, "crimes": {}})
        a["n"] += 1
        try:
            a["lat"] += float(r.get("lat")); a["lng"] += float(r.get("long")); a["k"] += 1
        except (TypeError, ValueError):
            pass
        ct = r.get("crime_type")
        if ct:
            a["crimes"][ct] = a["crimes"].get(ct, 0) + 1
    out = []
    for d, a in agg.items():
        k = a["k"] or 1
        top = max(a["crimes"].items(), key=lambda x: x[1])[0] if a["crimes"] else None
        out.append({"code": d, "name": (socio.get(d) or {}).get("district_name", d),
                    "incidents": a["n"], "lat": round(a["lat"] / k, 4),
                    "lng": round(a["lng"] / k, 4), "top_crime": top})
    out.sort(key=lambda x: -x["incidents"])
    return {"districts": out}


# --------------------------------------------------------------------------- #
# Phase 9 — governance (RBAC + PII masking + audit) + automation (briefs)
# --------------------------------------------------------------------------- #
def get_principal(x_actor: Optional[str] = Header(None),
                  x_role: Optional[str] = Header(None),
                  x_scope: Optional[str] = Header(None)) -> rbac.Principal:
    """Resolve the caller (Catalyst Web SDK / API Gateway in prod; headers locally)."""
    return rbac.Principal(actor=x_actor or "demo", role=(x_role or "analyst"), scope=x_scope)


@router.get("/governed/incidents")
def governed_incidents(limit: int = 50, principal: rbac.Principal = Depends(get_principal)):
    """Incident list filtered to the caller's jurisdiction; access audited."""
    rows = rbac.jurisdiction_filter(store.fetch_incidents_copilot(), principal)[:limit]
    gaudit.record(principal, "read", "Incidents", "governed/incidents")
    return {"count": len(rows), "viewer": {"role": principal.role, "scope": principal.scope},
            "incidents": [{k: r.get(k) for k in ("incident_id", "fir_no", "district_code",
                           "crime_type", "occurred_at", "status")} for r in rows]}


@router.get("/case/{incident_id}/parties")
def case_parties(incident_id: str, principal: rbac.Principal = Depends(get_principal)):
    """Parties on a FIR with victim/witness PII masked by role (IPC 228A / POCSO)."""
    inc = store.fetch_incident(incident_id)
    if not inc:
        return {"error": "not found", "incident_id": incident_id}
    _authz(principal, "read", "incident_pii")                   # ethics denied -> 403
    if principal.role in ("district", "station") and not rbac.in_scope(
            principal, district=inc.get("district_code"), station=inc.get("station_code")):
        raise HTTPException(403, "outside your jurisdiction")
    parties = masking.mask_parties(store.fetch_incident_parties(incident_id),
                                   principal.role, principal.scope,
                                   crime_type=inc.get("crime_type"),
                                   district=inc.get("district_code"),
                                   station=inc.get("station_code"))
    gaudit.record(principal, "read", "Incident:" + incident_id, "case/parties")
    return {"incident": inc, "protected": masking.is_protected(inc.get("crime_type")),
            "viewer": {"role": principal.role, "scope": principal.scope}, "parties": parties}


@router.get("/audit")
def audit_log(limit: int = 100, principal: rbac.Principal = Depends(get_principal)):
    """The governance audit trail — restricted to admin / ethics."""
    if principal.role not in ("scrb-admin", "ethics"):
        raise HTTPException(403, "audit log restricted to admin/ethics")
    return {"entries": store.read_audit_log(limit)}


# --------------------------------------------------------------------------- #
# Iteration 11 — investigation workbench (dossier / case file / universal search)
# --------------------------------------------------------------------------- #
from engines import workbench as wb  # noqa: E402


def _authz(principal, action, resource):
    """rbac.authorize mapped to a proper 403 (not a 500)."""
    try:
        rbac.authorize(principal, action, resource)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.get("/entity/{canonical_id}")
def entity_dossier(canonical_id: str, principal: rbac.Principal = Depends(get_principal)):
    """360-degree dossier: aliases, appearances, associates, timeline — masked by role."""
    _authz(principal, "read", "incident_pii")                   # ethics denied -> 403
    res = wb.dossier(canonical_id, principal)
    if res.get("error"):
        raise HTTPException(404, "unknown entity: " + canonical_id)
    gaudit.record(principal, "read", "Entity:" + res["canonical_id"], "workbench/dossier")
    return res


@router.get("/case/{incident_id}")
def case_full(incident_id: str, principal: rbac.Principal = Depends(get_principal)):
    """Full case file: FIR + parties (masked) + linked cases with explained reasons."""
    _authz(principal, "read", "incident_pii")
    res = wb.case_file(incident_id, principal)
    if res.get("error"):
        raise HTTPException(404, "unknown case: " + incident_id)
    inc = res["incident"]
    if principal.role in ("district", "station") and not rbac.in_scope(
            principal, district=inc.get("district_code"), station=inc.get("station_code")):
        raise HTTPException(403, "outside your jurisdiction")
    gaudit.record(principal, "read", "Incident:" + incident_id, "workbench/case")
    return res


@router.get("/search")
def universal_search(q: str, principal: rbac.Principal = Depends(get_principal)):
    """Universal search across cases, people, vehicles, phones, places (+semantic)."""
    res = wb.search(q, principal)
    gaudit.record(principal, "read", "Search", q[:200])
    return res


# --------------------------------------------------------------------------- #
# District Command Card (blueprint §B1/§B2) — clearance/conviction rate from
# ChargesheetDetails.cs_type, backlog aging, officer leaderboard. district/
# station roles are scoped to their own jurisdiction; others may query any.
# --------------------------------------------------------------------------- #
@router.get("/district/{code}/command")
def district_command(code: str, principal: rbac.Principal = Depends(get_principal)):
    """One district's cockpit — load, backlog, clearance rate, top officers."""
    if principal.role in ("district", "station") and not rbac.in_scope(principal, district=code):
        raise HTTPException(403, "outside your jurisdiction")
    card = district_engine.command_card(
        code, store.fetch_incidents_full(), store.fetch_chargesheets(),
        store.fetch_officers())
    gaudit.record(principal, "read", "District:" + code, "district/command")
    return card


@router.get("/district/rank")
def district_rank(principal: rbac.Principal = Depends(get_principal)):
    """All districts ranked by clearance rate — "who's improving, who's slipping" (§B2)."""
    if principal.role in ("district", "station"):
        raise HTTPException(403, "statewide ranking requires SP/analyst clearance or higher")
    inc = store.fetch_incidents_full()
    codes = sorted({r["district_code"] for r in inc if r.get("district_code")})
    ranked = district_engine.rank_districts(
        codes, inc, store.fetch_chargesheets(), store.fetch_officers())
    gaudit.record(principal, "read", "District:ALL", "district/rank")
    return {"districts": ranked}


@router.post("/brief/run")
def brief_run(scope: str = "STATE"):
    """Assemble the intelligence brief (SmartBrowz renders HTML→PDF in prod)."""
    a = _network_analysis()
    inc = store.fetch_incidents_p5()
    st = _risk_state()
    brief = briefs.build_brief(
        scope, stats=stats(),
        rings=net_engine.cross_district_rings(a["graph"], a["communities"], top=5),
        alerts=_anomaly_result()["alerts"], series=link_series(inc)["series"][:5],
        risk=_risk_rows(st, n=5), fairness=st["fair"][1])
    return {"ok": True, "brief": brief, "html_bytes": len(briefs.render_html(brief))}


# --------------------------------------------------------------------------- #
# Cache warm-up — the network graph / LightGBM walk-forward / copilot TF-IDF
# index / anomaly scan / workbench state are each expensive exactly once and
# cheap forever after (module-level caches above). Left lazy, that one-time
# cost lands on whichever user's click happens to be first — a multi-second
# stall right when someone is looking. Precompute them at process start
# instead, off the request path.
# --------------------------------------------------------------------------- #
def warm():
    _network_analysis()
    _risk_state()
    _copilot_state()
    _anomaly_result()
    wb.state()
