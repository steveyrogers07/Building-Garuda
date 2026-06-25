# GARUDA — Phase 5 Kickoff (paste into a fresh build chat) — ★ THE HERO

> Fresh build session for **Phase 5** of GARUDA. Read fully, execute step by step, don't jump ahead.

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, deploy on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/acadflip/Building-Garuda`
- Read in repo: `docs/GARUDA_BLUEPRINT.md` (network/link analysis), `docs/PHASE_2_RUNBOOK.md`+`PHASE_3_RUNBOOK.md`+`PHASE_4_RUNBOOK.md` (if present) + `docs/PHASE_4_KICKOFF.md`, `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**Dev only, $0 credits**).
- Stack: React/Web Client Hosting · Node functions · **Python/FastAPI on AppSail** · Data Store (ZCQL) · QuickML · Zia.

## ⚠️ Dependency
**Phase 5 consumes Phase 4 outputs:** `canonical_id` + `match_confidence` on Entities, `mo_cluster_id` on Incidents, the `MO_Clusters` table. If Phase 4 isn't merged yet, run its engine first (or coordinate with that owner). Otherwise build on the Phase 2 synthetic data + `data/synthetic/ground_truth.json` + the local PoC store (`data/local/`).

## Convention (same as P2–P4)
Split into a **pure-Python brain verified locally** (against the CSVs / local PoC store + `ground_truth.json`, no creds/credits) + a **deferred account-gated** section (ZCQL read/write, NoSQL, deploy). **Text business keys** (`incident_id`,`entity_id`,`canonical_id`), not ROWID. Produce `docs/PHASE_5_RUNBOOK.md` at the end.

## Goal
The reveal: turn siloed FIRs into one **co-offender network** + **crime-series** + **emerging-trend anomalies** — so an analyst clicks a hotspot and sees the organized gang, its kingpin, and a spike alert.

## Exit Gate (✅ local · ⧖ needs live project)
- [ ] **G1** `app/engines/network/` builds a graph from canonical entities (nodes) + edges (same-incident co-occurrence, shared phone/vehicle, shared MO cluster + proximity); `/network/{canonical_id}` returns an ego-subgraph JSON (nodes, edges, **betweenness/degree centrality**, **Louvain community**). ✅
- [ ] **G2** **Planted gang recovered:** kingpin = top betweenness; gang = one community; links span **BNU/KLR/RMN/TMK** (verify vs `ground_truth.json`). ✅
- [ ] **G3** `app/engines/series/` links incidents by `mo_cluster_id` + space-time near-repeat → populates `Crime_Series` + `series_id` on Incidents; recovers the planted MYS burglary series. ✅
- [ ] **G4** `app/engines/anomaly/` (STL/EWMA per area×crime_type vs seasonal baseline) → populates `Alerts`; recovers the planted spikes (BNU two-wheeler ×4, etc.). ✅
- [ ] **G5** Deployed; subgraphs cached in NoSQL; batch run writes `Crime_Series`/`Alerts`/`series_id` via ZCQL. ⧖

## Prerequisites
`pip install networkx scikit-learn statsmodels pandas python-louvain`. Phase 4 canonical entities available (run the P4 engine if not merged).

## Steps
1. **Network → `app/engines/network/`** (+ extend `app/routers/analytics.py`): nodes = canonical entities; edges from (a) co-occurrence in the same incident, (b) shared phone/vehicle canonical entity, (c) same `mo_cluster_id` + spatial/temporal proximity. Compute **degree + betweenness** centrality, **Louvain** communities, optional **link prediction** (Adamic-Adar/Jaccard) for hidden ties. `/network/{canonical_id}` → ego-subgraph JSON for the Phase 8 force-graph; **cache** results.
2. **Crime-series → `app/engines/series/`**: group incidents sharing `mo_cluster_id` within a spatial (haversine) + temporal (near-repeat / Knox-style) window → `Series_ID`; write `Crime_Series` + `series_id`.
3. **Anomaly → `app/engines/anomaly/`**: per (area_code × crime_type) monthly series → STL decompose + EWMA/CUSUM or z-score vs seasonal baseline → flag → `Alerts` (area, crime_type, baseline, observed, z_score, created_at).
4. **Eval → `tests/test_network.py`** (mirror `tests/test_ingestion_pipeline.py`): vs `ground_truth.json` — kingpin via centrality, gang community = planted members, series = planted, anomalies = planted spikes. Print metrics.
5. **Account-gated:** batch endpoints (`/network/run`, etc.) read via ZCQL, write back; store adjacency in NoSQL; cache hot subgraphs.

## Gotchas
Dev only ($0). Build edges from **`canonical_id`**, not raw `entity_id` (that's why P4 must run first). Betweenness is O(VE) — sample/approximate if slow on the full graph. Keep graph build batch + cached (cheap + fast for the live demo).

## Out of scope
Forecasting → P6 · copilot → P7 · the actual graph UI → P8 (this phase returns the JSON the UI draws).

## When done
`feat/phase-5-network` → PR → `main`; write `docs/PHASE_5_RUNBOOK.md`. This is the demo centerpiece — Phase 8 renders it.
