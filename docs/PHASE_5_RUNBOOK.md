# GARUDA — Phase 5 (Core Analytics: Network + Series + Anomaly) Runbook ★ THE HERO

> Goal: turn siloed FIRs into one **co-offender network** + **crime-series** +
> **emerging-trend anomalies** — so an analyst sees the organized gang, its kingpin,
> the repeat series, and the spike alerts. Built on the Phase-4 canonical entities
> (`canonical_id`) and MO clusters (`mo_cluster_id`), measured against
> `data/synthetic/ground_truth.json`.

Same split as P2–P4: the **build-side brain is done & locally verified** (branch
`feat/phase-5-network`); the **account-gated** Catalyst write-back (ZCQL `Crime_Series`/
`Alerts`, NoSQL subgraph cache, deploy) is a deferred section needing the live project.
Everything local runs at **$0** — pure `networkx` / `statsmodels`, no QuickML credits.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Co-offender network (brain) | [app/engines/network/graph.py](../app/engines/network/graph.py) | graph build · degree+betweenness · Louvain · ego-JSON · ring detection · link prediction |
| Crime-series linkage (brain) | [app/engines/series/linkage.py](../app/engines/series/linkage.py) | MO/crime-type block → space-time near-repeat (Knox) → `Crime_Series` |
| Anomaly detection (brain) | [app/engines/anomaly/detect.py](../app/engines/anomaly/detect.py) | monthly area×crime series → robust median/MAD z-score → `Alerts` |
| Batch data access (extended) | [app/shared/store.py](../app/shared/store.py) | P5 reads (resolved/MO CSV → base fallback) + writes (CSV ↔ ZCQL); `GARUDA_HOME` outputs |
| AppSail endpoints | [app/routers/analytics.py](../app/routers/analytics.py) | `/network/top`, `/network/rings`, `/network/{id}`, `POST /network/run`, `/series/run`, `/anomaly/run` |
| Local runner | [app/run_phase5.py](../app/run_phase5.py) | runs all three engines → writes artifacts to local storage → prints the reveal |
| Phase-5 eval | [tests/test_network.py](../tests/test_network.py) | recovers gang / series / anomalies vs planted truth |

**Verified locally** (`python tests/test_network.py`), over 10,130 incidents / 14,608
entities / 18,214 edges → graph of **7,339 nodes, 9,528 edges**:

- **Network (G1/G2):** the planted gang is recovered as the **#1 cross-district ring** —
  kingpin **Aayush Zachariah** (`ENT014602`), 5 members, links spanning **BNU/RMN/TMK/KLR**,
  10 incidents, shared phone `+916534933629` + vehicle `KA68MC3164`. Clicking the kingpin
  (2-hop ego) returns the whole gang incl. both shared links.
- **Series (G3):** the planted **MYS house-burglary** series is recovered **6/6** in one
  `Crime_Series`; 127 series total across the set.
- **Anomaly (G4):** all **3 planted spikes** detected and they are the **top-3 by z-score**
  (BNU two-wheeler ×4.0 / BNU burglary ×4.8 / MYS two-wheeler ×5.2); 12 alerts total.

---

## 1. Exit gates

| Gate | What | Status |
|---|---|---|
| **G1** | graph from canonical entities; `/network/{id}` returns ego-subgraph JSON (degree, betweenness, community) | ✅ local |
| **G2** | planted gang recovered: kingpin by centrality, one community, links span BNU/KLR/RMN/TMK | ✅ local |
| **G3** | series linkage populates `Crime_Series` + `series_id`; recovers the MYS burglary series | ✅ local |
| **G4** | anomaly detection populates `Alerts`; recovers the planted spikes | ✅ local |
| **G5** | deployed; subgraphs cached in NoSQL; batch run writes `Crime_Series`/`Alerts`/`series_id` via ZCQL | ⧖ account-gated |

---

## 2. Flow

```
Phase-4 outputs                 Phase-5 engines                         outputs
─────────────────               ───────────────                         ───────
entities_resolved.csv ┐         network.analyze(inc,ent,edg)            ego-JSON  ─→ /network/{id}
 (canonical_id)        ├─ store ─→  build_graph → betweenness            rings     ─→ /network/rings
incidents_mo.csv       │            + Louvain + cross_district_rings     top       ─→ /network/top
 (mo_cluster_id)       │
incident_edges.csv    ─┘         series.link_series(inc)            ─→  Crime_Series + series_id
                                 anomaly.detect(inc)                ─→  Alerts
```

Reads prefer the Phase-4 outputs and **fall back to the base CSVs** (which carry the
planted `canonical_id`), so Phase 5 runs even before Phase 4 has been executed. The graph
is built once and cached in-process; `POST /network/run` rebuilds it.

---

## 3. Run it locally ($0, no Catalyst)

```bash
# prereq: synthetic data (Phase 2). Phase-4 outputs are optional (auto-fallback).
python data/generate.py

# gate test — recovers gang / series / anomalies vs ground_truth.json
python tests/test_network.py

# full runner — writes artifacts to local storage and prints the reveal
python app/run_phase5.py
```

`run_phase5.py` writes to **`GARUDA_HOME`** (default `~/OneDrive/Desktop/garuda`; override
with the env var):

```
crime_series.csv   incidents_series.csv   alerts.csv
network/<kingpin>.json   phase5_report.json
```

These are regenerable; an external `GARUDA_HOME` keeps them out of the repo (the repo-local
default `data/local/` is git-ignored).

---

## 4. REST contract (AppSail)

| Method | Route | Returns |
|---|---|---|
| GET | `/network/top?n=10&node_type=person` | candidate kingpins by centrality score |
| GET | `/network/rings?min_districts=2&min_incidents=4` | organized cross-district rings (gangs) |
| GET | `/network/{canonical_id}?radius=2&cache=false` | ego-subgraph JSON for the force graph |
| POST | `/network/run` | rebuild graph; report nodes/edges/communities/top |
| POST | `/series/run` `{write, limit}` | link `Crime_Series` + `series_id`; sample |
| POST | `/anomaly/run` `{write}` | flag `Alerts`; sample (sorted by z-score) |

The graph/series/anomaly endpoints return the JSON the **Phase-8** force-graph, series view,
and alert panel will draw. This phase produces the data; the UI is out of scope (P8).

---

## 5. Account-gated (G5 — when the Phase-1 project is live)

Set `GARUDA_BACKEND=zcql`; `shared.store` then reads `Incidents/Entities/Incident_Edges`
and writes back via ZCQL (already implemented, batched):

- `write_crime_series` → `INSERT INTO Crime_Series`
- `write_incident_series` → `UPDATE Incidents SET series_id=…`
- `write_alerts` → `INSERT INTO Alerts`
- `write_network_cache` → cache ego-subgraphs (NoSQL / Cache in prod; local file for the PoC)

Wire `POST /network/run|/series/run|/anomaly/run` into the nightly **Job Scheduling** pool
(Phase 9). Cache hot subgraphs so the live demo is instant.

---

## 6. Gotchas / design notes

- **Kingpin signal in a clique.** The gang co-offends so tightly it forms a near-clique, so
  *betweenness is ~0 for everyone* — nobody bridges. The discriminating signal there is
  **weighted degree (strength)**: the kingpin (in all 10 incidents) scores 31 vs ≤18 for the
  rest. `top_actors` ranks by a normalized **betweenness + strength** blend so it surfaces
  both brokers (loose networks) and prolific co-offenders (cliques).
- **Ring detection isn't Louvain-by-district.** Louvain lumps a loose "background"
  mega-community that touches every district through unrelated members, and the synthetic set
  has many vehicles incidentally reused across 4–5 districts. The real fingerprint is a
  *shared phone/vehicle reused heavily across districts*: `cross_district_rings` anchors on
  link entities (ranked by uses → #distinct shared links → district reach) and de-dupes by
  crew, so the deliberate gang (one phone **and** one vehicle, 10 incidents) tops incidental
  plate reuse (≤5 incidents, one link).
- **Anomaly baseline is robust.** Median + MAD modified z-score (not mean/σ) so the spike
  month doesn't poison its own baseline; gated on z ≥ 3.5 **and** ratio ≥ 2× and a minimum
  baseline, which keeps false positives down while the planted ×3.5–×5 spikes rank top.
- **Betweenness perf.** Computed per connected component (exact for the small components that
  matter; sampled only inside any huge one) — O(V·E) never bites on the full graph.
- **Louvain community count** drifts a little run-to-run (set iteration), but the gang always
  collapses into one community; gates assert membership, not the total count.

---

## 7. Next

Phase 6 (Predictive & Explainable AI): grid×time risk forecasting + SHAP + PAI/PEI, using
these series/anomaly signals as features. Phase 8 renders the network/series/alerts JSON.
