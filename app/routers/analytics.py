"""GARUDA AppSail - analytics endpoints (Phases 4-5).

Phase 4 - entity resolution + MO fingerprinting:
  POST /resolve/run     : Entities -> canonical_id + match_confidence (borderline -> Review_Queue).
  POST /mo/run          : Incidents -> mo_cluster_id + MO_Clusters signatures.
  POST /geocode/backfill: fill Incidents missing lat/long.

Phase 5 - co-offender network / crime-series / anomaly (the hero reveal):
  GET  /network/top         : highest-centrality persons (candidate kingpins).
  GET  /network/{canonical} : ego-subgraph JSON for the force graph (+optional cache).
  POST /network/run         : (re)build the graph; report size + communities + top actors.
  POST /series/run          : link incidents into Crime_Series (MO + space-time near-repeat).
  POST /anomaly/run         : flag emerging-trend spikes into Alerts.

Phase 6 - predictive & explainable risk forecasting (places x times, not people):
  POST /risk/run            : walk-forward backtest (PAI/PEI/PR-AUC) + write Predictive_Risk.
  GET  /risk/top            : current highest-risk area x crime-type cells.
  GET  /risk/explain        : SHAP drivers for one area x crime-type prediction.
  GET  /risk/fairness       : per-ward predicted-vs-actual bias audit.

Phase 7 - intelligence copilot (hybrid RAG over FIRs):
  POST /copilot             : NL -> structured filters + semantic retrieval -> cited answer
                              (guardrails: never asserts guilt; refuses out-of-scope; audited).

Reads/writes go through shared.store (local CSV by default; Catalyst Data Store via ZCQL
when GARUDA_BACKEND=zcql). The heavy ML stays here on AppSail; Node stays thin.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from automation import briefs
from automation import jobs as automation_jobs
from automation import notify
from governance import audit as gaudit, masking, rbac
from engines import actions as act_engine
from engines import copilot as cp
from engines.copilot import kannada as knq
from engines import deadlines as dl_engine
from engines import district as district_engine
from engines import forecasting as fc
from engines import mo as mo_engine
from engines import network as net_engine
from engines.anomaly import detect as detect_anomalies
from engines.geocode.geocoder import geocode
from engines.resolution import resolve_entities, to_review_record
from engines.series import link_series
from shared import kvcache as kv
from shared import store

router = APIRouter(tags=["analytics"])

# Flipped by warm(): before it, /stats and /geo/districts may serve the L2
# kvcache (a restarted instance answers immediately from the last publish);
# after it, they always compute from the live corpus as before.
_WARMED = False

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MO_VECTOR_PATH = os.path.join(REPO, "data", "synthetic", "mo_vectors.npz")


class _Lazy:
    """Thread-safe memoize-once for an expensive build (graph analysis, LightGBM
    walk-forward, TF-IDF index, anomaly scan). Plain "if cache is None: build()"
    is fine for a single request thread, but the background warm-up thread
    (main.py startup) can race a live request hitting the same cold cache -
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

    def ready(self):
        """True once built - lets endpoints serve the kvcache L2 while this
        L1 is still cold (warm() builds it in the background) without ever
        paying the L2 round-trip on a warm instance."""
        return self._value is not None


def _publish(key, value):
    """Best-effort L2 publish of a freshly built output (plan §4.7)."""
    kv.put(key, value)
    return value


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
# Phase 5 - co-offender network / crime-series / anomaly
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
    """Organized cross-district rings - the 'show me the gangs' query."""
    if not _NET_CACHE.ready() and (min_districts, min_incidents) == (2, 4):
        c = kv.get("network:rings")            # baked at deploy + nightly publish
        if c:
            return {"rings": c["rings"][:top]}
    a = _network_analysis()
    return {"rings": net_engine.cross_district_rings(
        a["graph"], a["communities"], min_districts=min_districts,
        min_incidents=min_incidents, top=top)}


@router.get("/network/{canonical_id}")
def network_ego(canonical_id: str, radius: int = 2, cache: bool = False,
                cached: bool = False):
    """Ego-subgraph around a canonical entity - the JSON the Phase-8 force graph draws.
    ?cache=true writes the payload to the ego cache (NoSQL in prod, plan §4.6);
    ?cached=true serves from that cache when present, skipping the graph build."""
    if cached:
        hit = store.read_network_cache(canonical_id)
        if hit:
            return hit
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
# Alerts screens on every mount - cache the detection result the same way the
# network/risk/copilot state is cached, and only rescan on an explicit write run.
_ANOMALY_CACHE = _Lazy(lambda: detect_anomalies(store.fetch_incidents_p5()))


def _anomaly_result(rebuild=False):
    return _ANOMALY_CACHE.get(rebuild=rebuild)


@router.post("/anomaly/run")
def anomaly_run(body: RunIn):
    if not body.write and not _ANOMALY_CACHE.ready():
        c = kv.get("anomaly:alerts")           # baked at deploy + nightly publish
        if c:
            return {"ok": True, "alerts": len(c["alerts"]), "written": 0,
                    "sample": c["alerts"][:20]}
    res = _anomaly_result(rebuild=body.write)
    written = store.write_alerts(res["alerts"]) if body.write else 0
    return {"ok": True, "alerts": len(res["alerts"]), "written": written,
            "sample": res["alerts"][:20]}


# --------------------------------------------------------------------------- #
# Phase 6 - predictive & explainable risk forecasting
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
    _publish("risk:top", {"as_of": str(pd.Timestamp(st["last"]).date()),
                          "top": rows[:100]})
    written = store.write_predictive_risk(rows) if body.write else 0
    return {"ok": True, "metrics": st["wf"]["summary"], "base_rate": st["wf"]["base_rate"],
            "model_version": fc.MODEL_VERSION, "risk_cells": len(rows),
            "written": written, "top": rows[:10]}


@router.get("/risk/top")
def risk_top(n: int = 20):
    if not _RISK_CACHE.ready():
        c = kv.get("risk:top")                 # published by /risk/run + nightly
        if c and len(c.get("top", [])) >= n:
            return {"as_of": c["as_of"], "top": c["top"][:n]}
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
    if not _RISK_CACHE.ready():
        c = kv.get("risk:fairness")            # baked at deploy + nightly publish
        if c:
            return c
    st = _risk_state()
    fair_df, fair_sum = st["fair"]
    return {"summary": fair_sum, "wards": fair_df.to_dict("records")}


# --------------------------------------------------------------------------- #
# Phase 7 - intelligence copilot (hybrid RAG over FIRs)
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
    lang: Optional[str] = None   # "kn" = Kannada voice/text (plan §4.13)


@router.post("/copilot")
def copilot(body: CopilotIn):
    """Plain-English (or Kannada - §4.13) Q&A over FIRs: hybrid retrieval +
    mandatory citations + guardrails. Kannada queries are normalized to the
    English tokens the parser keys on; the response carries the translation
    trace so the UI can show its work."""
    query, voice = body.query, None
    if body.lang == "kn" or knq.has_kannada(query):
        t = knq.kn_to_en(query)
        if t["had_kannada"]:
            query = t["english"]
            voice = {"original": body.query, "english": t["english"],
                     "replacements": t["replacements"]}
    st = _copilot_state()
    res = cp.answer(query, st["incidents"], st["index"], st["refs"], top_k=body.top_k)
    if voice:
        res["voice"] = voice
    # audit the ORIGINAL utterance - the governance trail must show what was asked
    store.write_audit_log(cp.audit_entry(body.query, res, actor=body.actor, role=body.role))
    return res


# --------------------------------------------------------------------------- #
# Phase 8 - lightweight read endpoints for the frontend (stats + geo)
# --------------------------------------------------------------------------- #
@router.get("/stats")
def stats():
    """Headline counts for the Overview dashboard."""
    from collections import Counter
    if not _WARMED:
        c = kv.get("stats")                    # published by warm() + nightly
        if c:
            return c
    inc = store.fetch_incidents_p5()
    cc = Counter(r.get("crime_type", "") for r in inc if r.get("crime_type"))
    dates = [r["occurred_at"][:10] for r in inc if r.get("occurred_at")]
    return {"incidents": len(inc), "entities": len(store.fetch_entities_p5()),
            "districts": len({r.get("district_code") for r in inc if r.get("district_code")}),
            "crime_types": len(cc), "by_crime": cc.most_common(10),
            "date_from": min(dates) if dates else None,
            "date_to": max(dates) if dates else None}


def _in_hour_band(ts, hour_from, hour_to):
    """occurred_at within [hour_from, hour_to); wraps midnight (20→5 = night)."""
    try:
        h = int(str(ts)[11:13])
    except (ValueError, TypeError):
        return False
    if hour_from <= hour_to:
        return hour_from <= h < hour_to
    return h >= hour_from or h < hour_to


@router.get("/geo/districts")
def geo_districts(hour_from: Optional[int] = None, hour_to: Optional[int] = None):
    """Per-district centroid + incident load + top crime - powers the hotspot map.
    ?hour_from/&hour_to layer time-of-day onto location (the brief's
    'spatiotemporal clusters'): counts include only incidents in that band."""
    if hour_from is None and hour_to is None and not _WARMED:
        c = kv.get("geo:districts")            # published by warm() + nightly
        if c:
            return c
    inc = store.fetch_incidents_p5()
    if hour_from is not None and hour_to is not None:
        inc = [r for r in inc if _in_hour_band(r.get("occurred_at"), hour_from, hour_to)]
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


@router.get("/socio/correlation")
def socio_correlation():
    """Socio-economic correlation - the brief's "why behind the where".

    Overlays per-district crime load on the Census indicators (population,
    density, literacy, urbanisation) and reports both the per-district table
    and the Pearson correlation of each indicator against crime rate per
    100k. Rate, not raw count: raw counts only re-discover that Bengaluru is
    big. Reported as association, never causation - these are ecological
    correlations over 31 districts, which is exactly how they must be read."""
    if not _WARMED:
        c = kv.get("socio:correlation")
        # Shape guard: a warmstart file baked before this payload grew would
        # otherwise serve the old structure and silently render a degraded
        # card. Only trust a cached payload that carries every key this
        # endpoint now returns; anything older falls through and recomputes.
        if c and "by_crime" in c and "model" in c:
            return c
    socio = {s.get("area_code"): s for s in store.fetch_socioeconomic()}
    counts: dict = {}
    for r in store.fetch_incidents_p5():
        d = r.get("district_code")
        if d:
            counts[d] = counts.get(d, 0) + 1

    rows = []
    for code, s in socio.items():
        try:
            pop = float(s.get("population") or 0)
        except (TypeError, ValueError):
            pop = 0.0
        if pop <= 0:
            continue
        n = counts.get(code, 0)

        def _f(key):
            try:
                return float(s.get(key) or 0)
            except (TypeError, ValueError):
                return 0.0

        rows.append({
            "district_code": code,
            "name": s.get("district_name") or code,
            "incidents": n,
            "population": int(pop),
            "rate_per_100k": round(n / pop * 100_000, 2),
            "density": _f("density"),
            "literacy": _f("literacy"),
            "urbanization": _f("urbanization"),
        })
    rows.sort(key=lambda r: -r["rate_per_100k"])

    def _pearson(key):
        if len(rows) < 3:
            return None
        x = np.array([r[key] for r in rows], dtype=float)
        y = np.array([r["rate_per_100k"] for r in rows], dtype=float)
        if x.std() == 0 or y.std() == 0:
            return None
        return round(float(np.corrcoef(x, y)[0, 1]), 3)

    def _strength(r):
        a = abs(r or 0)
        return "strong" if a >= 0.6 else "moderate" if a >= 0.35 else "weak"

    INDICATORS = (("urbanization", "Urbanisation"),
                  ("density", "Population density"),
                  ("literacy", "Literacy"))

    correlations = []
    for key, label in INDICATORS:
        r = _pearson(key)
        correlations.append({
            "indicator": key, "label": label, "r": r,
            "direction": ("none" if r is None else "positive" if r > 0 else "negative"),
            "strength": _strength(r),
        })
    correlations.sort(key=lambda c: -abs(c["r"] or 0))

    # ---- per-crime-type profile -------------------------------------------
    # The headline correlation hides that different offences track different
    # social conditions: economic/cyber crime follows literacy and urbanisation,
    # street property crime follows density. That contrast is the actual
    # sociological finding, and it tells a commander which lever applies where.
    per_district_crime: dict = {}
    crime_totals: dict = {}
    for r in store.fetch_incidents_p5():
        d, ct = r.get("district_code"), r.get("crime_type")
        if not d or not ct:
            continue
        per_district_crime.setdefault(ct, {})
        per_district_crime[ct][d] = per_district_crime[ct].get(d, 0) + 1
        crime_totals[ct] = crime_totals.get(ct, 0) + 1

    pop_by_code = {r["district_code"]: r["population"] for r in rows}
    by_crime = []
    for ct in sorted(crime_totals, key=lambda k: -crime_totals[k])[:8]:
        per_d = per_district_crime.get(ct, {})
        y = np.array([per_d.get(r["district_code"], 0) / pop_by_code[r["district_code"]] * 100_000
                      for r in rows], dtype=float)
        if y.std() == 0:
            continue
        entry = {"crime_type": ct, "incidents": crime_totals[ct]}
        best_label, best_r = None, 0.0
        for key, label in INDICATORS:
            x = np.array([r[key] for r in rows], dtype=float)
            rr = None if x.std() == 0 else round(float(np.corrcoef(x, y)[0, 1]), 3)
            entry[key] = rr
            if rr is not None and abs(rr) > abs(best_r):
                best_label, best_r = label, rr
        entry["driver"] = best_label
        entry["driver_r"] = round(best_r, 3) if best_label else None
        by_crime.append(entry)
    by_crime.sort(key=lambda e: -abs(e.get("driver_r") or 0))

    # ---- expected vs actual (the part a commander can act on) --------------
    # Regress crime rate on the socio-economic profile, then read the residual.
    # A district well ABOVE its predicted rate has more crime than its
    # demographics explain - something local is driving it, and that is where
    # attention belongs; below-expected districts are doing better than their
    # conditions predict. This separates "high crime because it is a big city"
    # from "high crime for what this place is", which raw counts never show.
    model = None
    if len(rows) >= 6:
        X = np.array([[r["urbanization"], r["literacy"], r["density"]] for r in rows],
                     dtype=float)
        y = np.array([r["rate_per_100k"] for r in rows], dtype=float)
        Xd = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(Xd, y, rcond=None)
        pred = Xd @ coef
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = round(1 - ss_res / ss_tot, 3) if ss_tot else None
        for i, r in enumerate(rows):
            r["expected_rate"] = round(float(pred[i]), 2)
            r["residual"] = round(float(y[i] - pred[i]), 2)
        ranked = sorted(rows, key=lambda r: -r["residual"])
        keep = ("district_code", "name", "rate_per_100k", "expected_rate", "residual")
        model = {
            "r2": r2,
            "explains_pct": round((r2 or 0) * 100),
            "above_expected": [{k: d[k] for k in keep} for d in ranked[:5]],
            "below_expected": [{k: d[k] for k in keep} for d in ranked[-5:][::-1]],
        }

    return {
        "districts": rows,
        "correlations": correlations,
        "by_crime": by_crime,
        "model": model,
        "n_districts": len(rows),
        "note": "Ecological correlation across districts - association, not "
                "causation. Used to explain where risk concentrates; the "
                "forecast model consumes these same indicators as features.",
    }


@router.get("/geo/stations")
def geo_stations(district: str, hour_from: Optional[int] = None,
                 hour_to: Optional[int] = None):
    """Station-level drill-down inside one district (brief: 'district-level
    drill-down… and specific police stations'). Unit names/centroids come from
    the Units master (organizer schema: Unit/UnitType)."""
    units = {u["station_code"]: u for u in store.fetch_units()
             if u.get("unit_type") == "Police Station"
             and u.get("district_code") == district}
    agg: dict = {}
    for r in store.fetch_incidents_full():     # p5 columns lack station_code
        if r.get("district_code") != district:
            continue
        if hour_from is not None and hour_to is not None and \
                not _in_hour_band(r.get("occurred_at"), hour_from, hour_to):
            continue
        st_code = r.get("station_code") or ""
        a = agg.setdefault(st_code, {"n": 0, "crimes": {}})
        a["n"] += 1
        ct = r.get("crime_type")
        if ct:
            a["crimes"][ct] = a["crimes"].get(ct, 0) + 1
    out = []
    for st_code, a in agg.items():
        u = units.get(st_code, {})
        top = max(a["crimes"].items(), key=lambda x: x[1])[0] if a["crimes"] else None
        out.append({"station_code": st_code,
                    "name": u.get("unit_name") or st_code,
                    "unit_id": u.get("unit_id", ""),
                    "incidents": a["n"],
                    "lat": float(u["lat"]) if u.get("lat") else None,
                    "lng": float(u["long"]) if u.get("long") else None,
                    "top_crime": top})
    out.sort(key=lambda x: -x["incidents"])
    return {"district": district, "stations": out}


# --------------------------------------------------------------------------- #
# Phase 9 - governance (RBAC + PII masking + audit) + automation (briefs)
# --------------------------------------------------------------------------- #
def get_principal(x_actor: Optional[str] = Header(None),
                  x_role: Optional[str] = Header(None),
                  x_scope: Optional[str] = Header(None),
                  x_garuda_user: Optional[str] = Header(None)) -> rbac.Principal:
    """Resolve the caller. Under ENV=prod only X-Garuda-User is trusted - the
    API Gateway strips it from inbound traffic and injects the Catalyst-verified
    email server-side (plan §4.5), and role/scope come from Console_Users
    (§4.4). Everywhere else (local, Dev demo) the client-supplied X-Role /
    X-Scope headers keep working - the role-switcher IS the governance demo."""
    if os.environ.get("ENV") == "prod":
        if not x_garuda_user:
            raise HTTPException(401, "sign-in required")
        u = store.fetch_console_user(x_garuda_user)
        if not u:
            raise HTTPException(403, "no console access provisioned for " + x_garuda_user)
        return rbac.Principal(actor=u.get("email"), role=u.get("role"),
                              scope=(u.get("scope") or None))
    return rbac.Principal(actor=x_actor or "demo", role=(x_role or "analyst"), scope=x_scope)


@router.get("/whoami")
def whoami(principal: rbac.Principal = Depends(get_principal)):
    """The resolved principal - Login.tsx calls this after a Catalyst sign-in
    to learn its GARUDA role/scope; harmless echo under the demo login."""
    u = store.fetch_console_user(principal.actor)
    return {"actor": principal.actor, "role": principal.role,
            "scope": principal.scope or "",
            "display_name": (u or {}).get("display_name", ""),
            "officer_id": (u or {}).get("officer_id", "")}


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
    """The governance audit trail - restricted to admin / ethics."""
    if principal.role not in ("scrb-admin", "ethics"):
        raise HTTPException(403, "audit log restricted to admin/ethics")
    return {"entries": store.read_audit_log(limit)}


# --------------------------------------------------------------------------- #
# Iteration 11 - investigation workbench (dossier / case file / universal search)
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
    """360-degree dossier: aliases, appearances, associates, timeline - masked by role."""
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
# District Command Card (blueprint §B1/§B2) - clearance/conviction rate from
# ChargesheetDetails.cs_type, backlog aging, officer leaderboard. district/
# station roles are scoped to their own jurisdiction; others may query any.
# --------------------------------------------------------------------------- #
@router.get("/district/{code}/command")
def district_command(code: str, principal: rbac.Principal = Depends(get_principal)):
    """One district's cockpit - load, backlog, clearance rate, top officers."""
    if principal.role in ("district", "station") and not rbac.in_scope(principal, district=code):
        raise HTTPException(403, "outside your jurisdiction")
    card = district_engine.command_card(
        code, store.fetch_incidents_full(), store.fetch_chargesheets(),
        store.fetch_officers())
    gaudit.record(principal, "read", "District:" + code, "district/command")
    return card


def _build_rank():
    inc = store.fetch_incidents_full()
    codes = sorted({r["district_code"] for r in inc if r.get("district_code")})
    return district_engine.rank_districts(
        codes, inc, store.fetch_chargesheets(), store.fetch_officers())


# 31 command_card passes over the full corpus - computed once, reused by both
# the ranking endpoint and the action card's state-median baseline.
_RANK_CACHE = _Lazy(_build_rank)


@router.get("/district/rank")
def district_rank(principal: rbac.Principal = Depends(get_principal)):
    """All districts ranked by clearance rate - "who's improving, who's slipping" (§B2)."""
    if principal.role in ("district", "station"):
        raise HTTPException(403, "statewide ranking requires SP/analyst clearance or higher")
    gaudit.record(principal, "read", "District:ALL", "district/rank")
    return {"districts": _RANK_CACHE.get()}


@router.get("/district/{code}/actions")
def district_actions(code: str, principal: rbac.Principal = Depends(get_principal)):
    """Action card - the district's signals fused into prioritised directives
    (anomaly x hotspot, default-bail pressure, absconders, clearance, forecast).
    Best-effort on a cold instance: expensive inputs fall back to the baked
    kvcache payloads and are simply omitted when neither is available yet."""
    if principal.role in ("district", "station") and not rbac.in_scope(principal, district=code):
        raise HTTPException(403, "outside your jurisdiction")
    inc = store.fetch_incidents_full()
    card = district_engine.command_card(
        code, inc, store.fetch_chargesheets(), store.fetch_officers())

    alerts = (((kv.get("anomaly:alerts") if not _ANOMALY_CACHE.ready() else None)
               or (_ANOMALY_CACHE.get() if _ANOMALY_CACHE.ready() else None)
               or {"alerts": []})["alerts"])
    if _RISK_CACHE.ready():
        risk_rows = _risk_rows(_risk_state(), 100)
    else:
        risk_rows = (kv.get("risk:top") or {}).get("top") or []
    roster_full = (kv.get("workbench:roster") if not _ROSTER_CACHE.ready() else None) \
        or _ROSTER_CACHE.get()
    absc = dl_engine.absconding_board_from(_ABSCONDING_CACHE.get(), district=code, limit=1)

    res = act_engine.district_actions(
        code, card=card, all_cards=_RANK_CACHE.get(), alerts=alerts,
        risk_rows=risk_rows, roster=roster_full["officers"],
        absconding_summary=absc.get("summary"), incidents=inc)
    gaudit.record(principal, "read", "District:" + code, "district/actions")
    return res


# --------------------------------------------------------------------------- #
# Field-officer intelligence (docs/product/08 §1/§2/§6) - the default-bail
# deadline clock, the per-IO worklist, and the absconding-accused board.
# district/station roles are scoped to their own jurisdiction; ethics sees none.
# The statewide roster and the absconding pair derivation are each a full pass
# over the corpus (~100-130ms) and hit on every page mount / filter change -
# cache them like the network/risk/copilot state; per-request work is only the
# cheap filter/sort (jurisdiction scoping stays per request, on the principal).
# --------------------------------------------------------------------------- #
_ROSTER_CACHE = _Lazy(lambda: _publish("workbench:roster", dl_engine.officers_roster(
    store.fetch_incidents_full(), store.fetch_officers(),
    store.fetch_arrests(), store.fetch_chargesheets())))
# NOT L2-published: absconding_people's phase-1 state carries sets, which a JSON
# round-trip through the Cache would silently turn into lists and corrupt
# absconding_board_from's filtering - cold instances build it locally instead.
_ABSCONDING_CACHE = _Lazy(lambda: dl_engine.absconding_people(
    store.fetch_incidents_full(), store.fetch_arrests(),
    store.fetch_chargesheets(), store.fetch_edges_p5(), store.fetch_entities_p5()))


@router.get("/officers")
def officers_roster(district: Optional[str] = None,
                    principal: rbac.Principal = Depends(get_principal)):
    """Officer picker feed: open-case load + urgent-clock count, worst first."""
    if principal.role == "ethics":
        raise HTTPException(403, "case data restricted for ethics role")
    station = None
    if principal.role == "district":
        district = principal.scope
    elif principal.role == "station":
        station = principal.scope
    full = (kv.get("workbench:roster") if not _ROSTER_CACHE.ready() else None) \
        or _ROSTER_CACHE.get()
    rows = full["officers"]     # per-officer aggregates: scoping is a row filter
    if district:
        rows = [o for o in rows if o["district_code"] == district]
    if station:
        rows = [o for o in rows if o["unit_code"] == station]
    gaudit.record(principal, "read", "Officers:" + (district or station or "ALL"), "officers")
    return {"as_of": full["as_of"], "officers": rows}


@router.get("/officer/{officer_id}/cases")
def officer_cases(officer_id: str, principal: rbac.Principal = Depends(get_principal)):
    """§2 - one IO's open cases sorted by default-bail urgency → age → gravity."""
    off = next((o for o in store.fetch_officers()
                if o["officer_id"] == officer_id), None)
    if not off:
        raise HTTPException(404, "unknown officer: " + officer_id)
    if not rbac.in_scope(principal, district=off.get("district_code"),
                         station=off.get("unit_code")):
        raise HTTPException(403, "outside your jurisdiction")
    res = dl_engine.officer_worklist(
        off, store.fetch_incidents_full(), store.fetch_arrests(),
        store.fetch_chargesheets())
    gaudit.record(principal, "read", "Officer:" + officer_id, "officer/cases")
    return res


@router.get("/absconding")
def absconding(district: Optional[str] = None, gravity: Optional[str] = None,
               min_days: int = 0, limit: int = 100,
               principal: rbac.Principal = Depends(get_principal)):
    """§6 - suspects on open cases with no arrest row, grouped by person."""
    if principal.role == "ethics":
        raise HTTPException(403, "case data restricted for ethics role")
    station = None
    if principal.role == "district":
        district = principal.scope
    elif principal.role == "station":
        station = principal.scope
    # cold + unscoped default view -> baked board (scoped roles always compute:
    # the baked payload is the statewide view and must never leak cross-scope)
    if (not _ABSCONDING_CACHE.ready() and station is None and district is None
            and gravity is None and min_days == 0 and limit == 100):
        c = kv.get("absconding:default")
        if c:
            gaudit.record(principal, "read", "Absconding:ALL", "absconding")
            return c
    res = dl_engine.absconding_board_from(
        _ABSCONDING_CACHE.get(), district=district, station=station,
        gravity=gravity, min_days=min_days, limit=limit)
    gaudit.record(principal, "read", "Absconding:" + (district or station or "ALL"),
                  "absconding")
    return res


@router.post("/brief/run")
def brief_run(scope: str = "STATE", pdf: bool = False):
    """Assemble the intelligence brief. ?pdf=true additionally renders it to
    PDF via SmartBrowz into the Stratus briefs bucket (plan §4.9) - best-effort,
    the JSON+HTML response is unchanged either way."""
    a = _network_analysis()
    inc = store.fetch_incidents_p5()
    st = _risk_state()
    brief = briefs.build_brief(
        scope, stats=stats(),
        rings=net_engine.cross_district_rings(a["graph"], a["communities"], top=5),
        alerts=_anomaly_result()["alerts"], series=link_series(inc)["series"][:5],
        risk=_risk_rows(st, n=5), fairness=st["fair"][1])
    html_text = briefs.render_html(brief)
    out = {"ok": True, "brief": brief, "html_bytes": len(html_text)}
    if pdf:
        name = f"garuda-brief-{scope.lower()}-{brief['period']}"
        _start_pdf_render(html_text, name)
        out["pdf"] = {"state": "rendering", "name": name,
                      "poll": "/brief/pdf/status"}
    return out


# SmartBrowz conversion + the Stratus upload run far longer than AppSail's
# request budget (a 2 KB brief exceeded it), so the render is detached and the
# caller polls. The brief JSON/HTML is returned immediately either way.
_PDF_STATUS: dict = {"state": "idle"}


def _start_pdf_render(html_text, name):
    from shared import catalyst_ctx
    # The SDK context lives in a ContextVar that does NOT cross into a new
    # thread - capture the request's headers here and replay them inside.
    headers = catalyst_ctx.headers()
    _PDF_STATUS.clear()
    _PDF_STATUS.update({"state": "rendering", "name": name})

    def _run():
        from shared import catalyst_ctx as ctx
        if headers:
            ctx.set_headers(headers)
        try:
            res = briefs.publish_pdf(html_text, name)
            _PDF_STATUS.update(
                {"state": "done", "result": res} if res
                else {"state": "failed",
                      "error": "publish_pdf returned None - SmartBrowz or the "
                               "briefs bucket is unavailable for this project"})
        except Exception as exc:                   # noqa: BLE001
            _PDF_STATUS.update({"state": "failed", "error": str(exc)[:300]})

    threading.Thread(target=_run, daemon=True, name="garuda-brief-pdf").start()


@router.get("/brief/pdf/status")
def brief_pdf_status():
    """Outcome of the most recent ?pdf=true render (see _start_pdf_render)."""
    return dict(_PDF_STATUS)


# --------------------------------------------------------------------------- #
# FIR provenance - the scanned source document behind an incident. Locally the
# scans are the bundled synthetic renders (data/fir_samples, CCTNS-style);
# in prod the same panel reads the Stratus raw-fir bucket the Zia-OCR
# ingestion pipeline consumes. Every analytical claim traces to its document.
# --------------------------------------------------------------------------- #
_FIR_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "fir_samples"
if not _FIR_DIR.is_dir():           # full checkout: data/ sits beside app/
    _FIR_DIR = Path(REPO) / "data" / "fir_samples"


@router.get("/fir/{incident_id}")
def fir_scan(incident_id: str):
    """The scanned FIR image for an incident (404 when no scan exists -
    only a sample of the corpus has rendered documents)."""
    from fastapi.responses import FileResponse
    safe = re.sub(r"[^A-Za-z0-9_]", "", incident_id)
    hits = sorted(_FIR_DIR.glob(f"FIR_*_{safe}.png")) if _FIR_DIR.is_dir() else []
    if not hits:
        raise HTTPException(404, "no scanned FIR on file for " + safe)
    return FileResponse(str(hits[0]), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


# --------------------------------------------------------------------------- #
# Scheduled jobs (plan §4.8) - Catalyst Job Scheduling fires the thin Node job
# function (functions/jobs), which makes ONE call here; ordering/error capture
# lives in automation.jobs so the batch runs identically locally and in prod.
# --------------------------------------------------------------------------- #
def _check_jobs_token(token):
    """Shared-secret gate for the job endpoints. Default-off: with no
    GARUDA_JOBS_TOKEN env set (local/demo) the endpoints stay open, same as
    every other admin run endpoint until the Gateway hardening (plan §4.5)."""
    expected = os.environ.get("GARUDA_JOBS_TOKEN")
    if expected and token != expected:
        raise HTTPException(403, "bad or missing X-Jobs-Token")


def _heavy_payloads():
    """Every precomputed JSON a cold instance should serve instantly - one
    source of truth for warm()'s L2 publish, the nightly republish, and the
    deploy-time warmstart bake (scripts/bake_warmstart.py)."""
    a = _network_analysis()
    st = _risk_state()
    fair_df, fair_sum = st["fair"]
    return {
        "stats": stats(),
        "geo:districts": geo_districts(),
        "socio:correlation": socio_correlation(),
        "risk:top": {"as_of": str(pd.Timestamp(st["last"]).date()),
                     "top": _risk_rows(st, n=100)},
        "risk:fairness": {"summary": fair_sum, "wards": fair_df.to_dict("records")},
        "network:rings": {"rings": net_engine.cross_district_rings(
            a["graph"], a["communities"], min_districts=2, min_incidents=4, top=20)},
        "anomaly:alerts": {"alerts": _anomaly_result()["alerts"]},
        "workbench:roster": _ROSTER_CACHE.get(),
        "absconding:default": dl_engine.absconding_board_from(
            _ABSCONDING_CACHE.get(), district=None, station=None,
            gravity=None, min_days=0, limit=100),
    }


def _publish_heavy():
    for key, payload in _heavy_payloads().items():
        kv.put(key, payload)


def _refresh_workbench():
    _ROSTER_CACHE.get(rebuild=True)
    _ABSCONDING_CACHE.get(rebuild=True)
    _copilot_state(rebuild=True)
    _publish_heavy()
    return {"roster": True, "absconding": True, "copilot_index": True,
            "published": True}


def _report_ok(report):
    return all(v.get("ok") for k, v in report.items() if not k.startswith("_"))


@router.post("/jobs/nightly")
def jobs_nightly(x_jobs_token: Optional[str] = Header(None)):
    """Nightly recompute: anomaly scan, risk retrain, network rebuild, workbench
    caches - each task's error is captured, never aborting the batch."""
    _check_jobs_token(x_jobs_token)
    body = RunIn(write=True)
    report = automation_jobs.nightly_recompute([
        ("anomaly", lambda: anomaly_run(body)),
        ("notify", _dispatch_alerts),
        ("risk", lambda: risk_run(body)),
        ("network", network_run),
        ("workbench", _refresh_workbench),
    ])
    return {"ok": _report_ok(report), "report": report}


def _dispatch_alerts():
    """Fan the fresh anomaly alerts out as notifications (plan §4.10): Mail for
    severity ≥ medium, Push for high. dispatch() is a no-send envelope echo
    unless GARUDA_NOTIFY=catalyst, so this task is free locally."""
    envelopes = notify.notifications_for_alerts(
        _anomaly_result()["alerts"], severity_min="medium")
    results = [notify.dispatch(n) for n in envelopes]
    return {"dispatched": len(results),
            "sent": sum(1 for r in results if r.get("sent"))}


@router.post("/jobs/weekly")
def jobs_weekly(scope: str = "STATE", x_jobs_token: Optional[str] = Header(None)):
    """Weekly intelligence brief (SmartBrowz PDF step joins in plan §4.9)."""
    _check_jobs_token(x_jobs_token)
    report = automation_jobs.nightly_recompute([
        ("brief", lambda: brief_run(scope)),
    ])
    return {"ok": _report_ok(report), "report": report}


# --------------------------------------------------------------------------- #
# Cache warm-up - the network graph / LightGBM walk-forward / copilot TF-IDF
# index / anomaly scan / workbench state are each expensive exactly once and
# cheap forever after (module-level caches above). Left lazy, that one-time
# cost lands on whichever user's click happens to be first - a multi-second
# stall right when someone is looking. Precompute them at process start
# instead, off the request path.
# --------------------------------------------------------------------------- #
def warm():
    global _WARMED
    _network_analysis()
    _risk_state()
    _copilot_state()
    _anomaly_result()
    _ROSTER_CACHE.get()
    _ABSCONDING_CACHE.get()
    _WARMED = True
    _publish_heavy()
    wb.state()
