# GARUDA — The 10-Phase Build Plan
Execute phase by phase. **Do not start a phase until the previous phase's EXIT GATE is green.** Each gate is itself a test, so the product is continuously verified and ends fully deployable. Everything is built against synthetic data first (see GARUDA_DATA_READINESS.md), so the real KSP dataset slots in without breaking the march.

**Parallel-friendly:** Phase 2 unblocks everything · Phase 8 (frontend) can start on mocked endpoints during Phases 4–7 · Phase 6 can run alongside Phase 5.
**Tracks:** A = Data/Backend · B = AI/ML · C = Frontend · D = Pitch/Governance.

---

## PHASE 1 — Foundation & Project Setup
**Goal:** a deployable, authenticated, empty Catalyst project with CI.
- [ ] Create the Catalyst project in the web console (first project must be console-created).
- [ ] Install CLI, `catalyst login`, `catalyst init` (Functions + Client + AppSail).
- [ ] Set up Git repo with the component layout; configure **Pipelines** CI (push → deploy).
- [ ] Configure **Authentication** + roles (SCRB-admin / district / station); gate a test route.
- [ ] Create **Stratus** buckets (`raw-fir`, `reports`, `artifacts`), **Cache** namespace, env config (all params config-driven).
- [ ] Deploy a hello-world function + blank client to Dev.
**Catalyst:** Functions, Authentication, Web Client Hosting, Stratus, Cache, Pipelines.
**Test:** hit the dev URL; login works; CI deploys on push.
**EXIT GATE:** ✅ blank app live on Catalyst Dev, login works, CI green.

## PHASE 2 — Data Layer & Synthetic Dataset
**Goal:** canonical schema + 50k synthetic rows + the swap-ready adapter.
- [ ] Create canonical **Data Store** tables (Incidents, Entities, Incident_Edges + derived).
- [ ] Build the **synthetic generator** → canonical schema + realistic patterns + planted network/series/anomalies.
- [ ] Build the **adapter/loader** (source → column-map config → validate → canonical → bulk insert).
- [ ] Build the **profiling/EDA notebook** + **validation gate** script.
- [ ] Load IPC↔BNS map, Karnataka GeoJSON, Census, gazetteer.
- [ ] Bulk-import ~50k rows; run ZCQL smoke tests (JOINs, aggregations).
**Catalyst:** Data Store (ZCQL), Stratus.
**Test:** adapter loads a sample CSV end-to-end; validation gate passes; ZCQL returns sane distributions.
**EXIT GATE:** ✅ 50k rows queryable via ZCQL; adapter + validation working.

## PHASE 3 — Ingestion & Extraction Pipeline
**Goal:** a scanned FIR becomes a structured, review-gated record automatically.
- [ ] Wire `raw-fir` upload → **Signal** → **Circuit**/Event function (Node).
- [ ] OCR step (**Zia OCR** Node SDK; `eng` + Kannada) → text.
- [ ] Structured extraction via AppSail `/extract` (Qwen) → JSON fields + NER.
- [ ] Geocode place → lat/long; write to **Review_Queue** with field confidences.
- [ ] Review/approve flow → insert into Incidents + Incident_Edges (human-in-loop).
**Catalyst:** Stratus, Signals + Event Functions, Circuits, Zia OCR, AppSail.
**Test:** upload a sample scanned FIR → row in Review_Queue → approve → lands in Incidents.
**EXIT GATE:** ✅ FIR upload → review queue → Incidents, end-to-end.

## PHASE 4 — Entity Resolution & Enrichment (the heart)
**Goal:** fragmented mentions collapse into canonical people; MO signatures formed.
- [ ] Stand up **AppSail FastAPI** (app-config.json, Python SDK per-request init).
- [ ] `/resolve`: normalize + transliterate (Kannada↔Eng) + blocking + `splink` → Canonical_ID.
- [ ] `/mo-cluster`: embeddings + structured MO features → HDBSCAN → MO_Clusters.
- [ ] Geocoding service + gazetteer integration.
- [ ] Persist resolved entities + MO signatures to Data Store / NoSQL.
**Catalyst:** AppSail, Data Store, NoSQL.
**Test:** unit-test resolution on labeled synthetic alias pairs (precision/recall); recovers planted links.
**EXIT GATE:** ✅ aliases merged @ measured precision; MO clusters formed.

## PHASE 5 — Core Analytics Engines (Network + Series + Anomaly) ★
**Goal:** the hero — siloed FIRs become a visible criminal network.
- [ ] `/network/{id}`: ZCQL JOIN → networkx (betweenness, Louvain, link prediction) → force-graph JSON.
- [ ] Crime-series linkage (MO + space-time near-repeat) → Crime_Series.
- [ ] `/anomaly`: STL + EWMA/CUSUM → Alerts.
- [ ] Store graph adjacency/embeddings in **NoSQL**; **Cache** hot results.
- [ ] Verify the planted cross-district network is recovered.
**Catalyst:** AppSail, NoSQL, Cache, Data Store.
**Test:** the planted network reveals correctly; anomalies + series detected on synthetic data.
**EXIT GATE:** ✅ hero network reveal works end-to-end.

## PHASE 6 — Predictive & Explainable AI
**Goal:** backtested, explainable, bias-checked risk forecasting.
- [ ] Build grid×time-shift training table; export to Stratus.
- [ ] Train **Zia AutoML** (target → deploy → endpoint).
- [ ] LightGBM mirror in AppSail → SHAP → `/risk/explain`.
- [ ] Walk-forward backtest; compute **PAI/PEI**, PR-AUC; store Backtest_PAI.
- [ ] Fairness audit: predicted-vs-actual disparity per ward.
**Catalyst:** Zia AutoML, AppSail, Data Store, Stratus.
**Test:** backtest beats naive baseline; SHAP explanations render; bias check passes/flagged.
**EXIT GATE:** ✅ risk scores + PAI/PEI + SHAP available.

## PHASE 7 — Intelligence Copilot (Hybrid RAG)
**Goal:** plain-English Q&A over the data with citations and guardrails.
- [ ] Embed narratives → vector store (NoSQL); set up **QuickML** KB / LLM serving (Qwen 2.5-14B).
- [ ] `/copilot`: NL→ZCQL filters + vector retrieval + Qwen generation.
- [ ] Mandatory source-FIR **citations**; guardrail prompt (no guilt assertions); log to Audit_Log.
- [ ] (Optional) NL→chart.
**Catalyst:** QuickML, AppSail, Data Store, NoSQL.
**Test:** battery of sample queries; measure citation accuracy; guardrail refusals work.
**EXIT GATE:** ✅ NL query → correct filtered results + cited answer.

## PHASE 8 — Frontend / Visualization Platform
**Goal:** the whole product is usable in a browser.
- [ ] React app shell + Auth (role-gated routes).
- [ ] Map (MapLibre + deck.gl): choropleth + pulsing hotspots.
- [ ] Network graph (react-force-graph) from `/network` with drill-down.
- [ ] Copilot chat UI, review-queue UI, SHAP "why" panel, bias panel, dashboards.
- [ ] Wire to AppSail/Functions via **API Gateway**; build → client → deploy.
**Catalyst:** Web Client Hosting, API Gateway, Authentication.
**Test:** every view renders from live (synthetic) data; demo flow clickable end-to-end.
**EXIT GATE:** ✅ all core views live and interactive.

## PHASE 9 — Automation, Governance & Hardening
**Goal:** the proactive loop + production-grade safety.
- [ ] **Job Scheduling**: job pool + crons (nightly recompute, weekly brief).
- [ ] Anomaly → **Signal** → **Push** + **Mail** alerts.
- [ ] **SmartBrowz** weekly PDF brief → Stratus → **Mail**.
- [ ] Governance: audit-log middleware, field-level PII masking by role, RBAC enforcement.
- [ ] API Gateway throttling; Cache expensive ops; retries/idempotency on ingestion.
**Catalyst:** Job Scheduling, Signals, Push, Mail, SmartBrowz, API Gateway, Cache.
**Test:** a spike fires a real alert; scheduled brief emails a PDF; RBAC + audit verified.
**EXIT GATE:** ✅ alerts + scheduled briefs + RBAC/audit working.

## PHASE 10 — Testing, Deployment & Demo
**Goal:** a tested, production-deployed, demo-ready submission.
- [ ] Test suite: unit (engines) + integration (pipeline) + E2E (demo flow); load-test the demo path.
- [ ] **Real-data swap rehearsal:** run the data-arrival runbook on a sample to prove the adapter.
- [ ] Promote Dev → **Production** (console); **Domain Mappings** + SSL.
- [ ] Record the 3.5-min demo + **backup video**; finalize slides + report + README (data lineage + ethics).
- [ ] Final submission checklist pass.
**Catalyst:** Pipelines, Domain Mappings, (all).
**Test:** full E2E green; production URL loads; adapter proven on a real-shaped sample.
**EXIT GATE:** ✅ production URL on custom domain + backup video + submission package complete.

---

### How to use this
1. Work top to bottom; one phase at a time; don't skip a gate.
2. If multiple people: parallelize per the note above, but each track still respects its own gates.
3. When the real dataset arrives (any phase ≥2): run the readiness runbook, adjust the adapter column-map, re-run — no engine changes.
4. Keep the synthetic planted-network scenario as the guaranteed demo even if real data lacks clean links.
