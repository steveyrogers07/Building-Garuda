# PROJECT GARUDA — Master Blueprint
**AI-Driven Crime Analytics & Visualization Platform for the Karnataka State Crime Records Bureau (SCRB)**
Datathon 2026 · mandatory deploy on Zoho Catalyst · this is the final, locked workflow architecture.

> **GARUDA** = the eagle that sees the whole field from above. The platform gives the SCRB a single state-wide eye over crime that today is scattered across station-level Excel sheets.
> *(Backronym for the deck, optional: **G**eospatial **A**nalytics & **R**elational **U**nderstanding for **D**ecisive **A**ction.)*

---

## 0. The 10-second pitch
> *"We don't just visualize crime — we **connect** it, **explain** it, and **forecast** it. GARUDA turns thousands of isolated, hand-written FIRs into a live organized-crime network and a next-week risk forecast for every district — all queryable in plain English, and built to be trusted by police."*

## 1. The winning thesis (why this beats the field)
1. Most teams will build "a map + charts + a chatbot." The brief's *deepest* pain is **data silos hiding criminal networks** — so our **hero** is turning fragmented FIRs into a connected network via **entity resolution + MO fingerprinting**, something Excel physically cannot do.
2. We win the "AI rigor" axis with **explainability (SHAP), proper temporal backtesting, and reported hotspot metrics (PAI/PEI)** instead of a black box.
3. We win the "maturity / domain" axis with **fairness, privacy, human-in-the-loop, and IPC→BNS / CCTNS awareness** — the things government-domain judges probe and that almost no datathon team addresses.

## 2. Product concept — four questions an analyst actually asks
| Lens | Question | Engine | The visible "wow" |
|---|---|---|---|
| **WHO** ★ hero | Who is connected to whom? | Entity resolution + co-offender graph + MO fingerprinting | "5 FIRs across 3 districts = one network; here's the kingpin." |
| **WHERE** | Where is risk concentrated / emerging? | Predictive hotspots (backtested) | Map that pulses red where next week deviates from baseline. |
| **WHY** | Why here? | Socio-economic model + SHAP | "High-risk *because* recent spike + payday + festival + lighting." |
| **WHAT-NEXT** | What's abnormal right now? | Anomaly / emerging-trend | Real-time alert when a category spikes past its own seasonal norm. |
| **Copilot** (glue) | — | QuickML RAG (Qwen 2.5-14B) + hybrid retrieval | Plain-English question → map + network + cited answer. |

## 3. System architecture — 6 layers
1. **Ingest & Extract** — Stratus upload → Signal → Event Function → Zia OCR → Qwen structured extraction + NER → **human review queue**.
2. **Resolve & Enrich** *(the heart)* — entity resolution, geocoding (Karnataka gazetteer), MO fingerprinting.
3. **Analyze** — predictive (fair + backtested), network (centrality / community / link-prediction), anomaly / emerging-trend, crime-series linkage.
4. **Act** — patrol/resource optimization, real-time alerts, scheduled intelligence briefs.
5. **Interface** — map, force-graph, copilot (RAG + citations), dashboards, Kannada/voice (stretch).
6. **Govern** *(cross-cutting)* — RBAC + field masking, audit log, bias monitor, model-drift watch.

*(See the runtime data-flow diagram in chat: how one FIR travels Ingest → Resolve → Analyze → Act.)*

## 4. Catalyst service map — FINAL (deprecation-corrected)
> ⚠️ **As of 30 Apr 2026, Catalyst File Store, Event Listeners, and Cron are END-OF-LIFE.** The official datathon capability table still lists "Cron" — it is **stale**. Use the right-hand column below. New Catalyst projects can't even see the dead services.

| Capability | Service (USE THIS) | Do NOT use |
|---|---|---|
| Object storage (raw FIRs, PDFs, model artifacts) | **Stratus** | ~~File Store~~ |
| React SPA hosting | **Web Client Hosting** | — |
| Backend API logic | **Serverless Functions** (Node, Advanced I/O) | — |
| Heavy Python ML runtime | **AppSail** (managed runtime, FastAPI) | — |
| Relational DB + full-text search | **Data Store** | — |
| Graph adjacency / embeddings / flexible tags | **NoSQL** | — |
| Cache (hot aggregations) | **Cache** | — |
| Tabular risk model (no-code) | **Zia AutoML** | — |
| OCR / NER / text analytics | **Zia Services** | — |
| LLM serving + RAG knowledge base | **QuickML** (Qwen 2.5-14B; 7B-VL for doc images) | — |
| React-on-event (file upload, DB insert) | **Signals + Event Functions** | ~~Event Listeners~~ |
| Multi-step ingestion orchestration | **Circuits** | — |
| Scheduled jobs (nightly recompute, weekly brief) | **Job Scheduling** | ~~Cron~~ |
| PDF / screenshot report generation | **SmartBrowz** | — |
| Transactional email (briefs) | **Mail** | — |
| Spike alerts | **Push Notifications** | — |
| Login / roles | **Authentication** | — |
| Routing / throttling / auth in front of functions | **API Gateway** | — |
| Custom domain + SSL | **Domain Mappings** | — |
| CI/CD | **Pipelines** | — |

*You will genuinely use ~14 Catalyst services — say this out loud to judges.*

## 5. Tech stack — DECIDED (no menus)
| Area | Choice | Why |
|---|---|---|
| Frontend | **React + Vite + TypeScript + Tailwind** | Fast, standard, deploys to Web Client Hosting. |
| Maps | **MapLibre GL JS + deck.gl** | Open, no API key, GPU layers for heatmaps/hexbins. |
| Network graph | **react-force-graph** | Canvas/WebGL, handles 1000s of nodes. |
| Charts | **Recharts / ECharts** | Quick dashboards. |
| Backend API | **Catalyst Serverless (Node.js)** behind **API Gateway + Auth** | Native, light. |
| ML service | **Python 3.11 + FastAPI on AppSail** | Where the real ML lives. |
| ML libs | pandas, scikit-learn, **LightGBM**, **networkx**, **hdbscan**, **sentence-transformers**, **splink** (entity resolution), **shap**, **statsmodels** (STL), **geopandas** | Battle-tested. |
| Tabular model | **Zia AutoML** (headline, Catalyst-native) + a **LightGBM mirror** for SHAP | AutoML for the requirement; LightGBM for explainability depth. |
| LLM / RAG | **QuickML RAG (Qwen 2.5-14B)** | Native, no external key, satisfies the "LLM/RAG" requirement. |

## 6. Data strategy — generate it (this resolves the granularity risk)
Real KSP data is sensitive and you won't get it clean. **Generate a realistic synthetic Karnataka dataset** — and because *we* generate it, we **guarantee** the entity-level richness the network hero needs.
- **Volume:** ~50,000 incidents, ~15,000 entities (persons/vehicles/phones), 31 districts (Bengaluru as a commissionerate), 3–4 years.
- **Realism:** crime-type mix (two-wheeler theft, chain-snatching, burglary, etc.), time-of-day & day-of-week patterns, festival/payday spikes, **mixed IPC + BNS section codes**, Kannada + English names with alias/spelling variants.
- **Planted patterns (for the demo "aha"):** (a) one **organized network spanning 3+ districts** linked by a shared phone + vehicle + identical MO — invisible in any single sheet; (b) a **near-repeat burglary series**; (c) 2–3 **anomalous spikes**.
- **Enrichment:** Census 2011 ward demographics, Karnataka district/taluk **GeoJSON boundaries**, a **place-name gazetteer** for geocoding, a holiday calendar.
- **Tooling:** Python (Faker + custom generators). *Talking point: synthetic data is itself privacy-positive — we never touch real victim PII.*

## 7. Database schema (Catalyst Data Store)
- **`Incidents`**: `IncidentID, FIR_No, Date_Time, Lat, Long, District_Code, Station_Code, Crime_Type, IPC_BNS_Code, MO_Cluster_ID, Series_ID, Source_FIR_URL, Confidence, Status, Created_By`
- **`Entities`**: `EntityID, Canonical_ID, Type(Person/Vehicle/Phone), Value, Alias_Of, Match_Confidence`
- **`Incident_Edges`**: `IncidentID, EntityID, Role(Suspect/Victim/Witness/Asset), Edge_Weight, Evidence_Type`
- **`Predictive_Risk`**: `Grid_ID, Time_Shift, Crime_Type, Risk_Probability, Model_Version, Backtest_PAI`
- **`MO_Clusters`**: `MO_Cluster_ID, Signature, Top_Terms, Example_IncidentIDs`
- **`Crime_Series`**: `Series_ID, Crime_Type, Span_Districts, IncidentIDs`
- **`Socioeconomic`**: `Area_Code, Population, Density, Literacy, Urbanization, ...`
- **`Geo_Boundaries`**: `Area_Code, Level(District/Taluk/Station), Polygon`
- **`Alerts`**: `AlertID, Area_Code, Crime_Type, Baseline, Observed, Z_Score, Created_At, Acknowledged_By`
- **`Review_Queue`**: `DocID, Stratus_Key, Extracted_JSON, Field_Confidences, Reviewer, State`
- **`Audit_Log`**: `LogID, User, Action, RecordID, Field, Timestamp`

## 8. The engines — methodology (input → method → validation → DoD)

**8.1 Ingestion & Extraction** — *Input:* scanned/photographed FIR or Excel. *Method:* Stratus upload → Signal → Event Function → Zia OCR → Qwen constrained extraction (schema-mapped JSON) + NER (names/vehicles/weapons) → confidence gate → Review Queue. Orchestrated by **Circuits**; idempotent + retried. *Validate:* field-level extraction accuracy; % auto vs. queued. *DoD:* drop a scanned FIR → reviewed row in Data Store.

**8.2 Entity Resolution (★ heart)** — *Input:* raw entity mentions. *Method:* normalize + transliterate (Kannada↔English) → blocking → probabilistic record linkage (`splink`) + phonetic matching tuned for Indian names → `Canonical_ID`. *Validate:* precision/recall on a labeled sample. *DoD:* "Ravi Kumar / Ravi K / R. Kumar" collapse to one person with a confidence score.

**8.3 MO Fingerprinting & Crime-Series** — *Input:* narrative text + structured MO features (time, weapon, target, entry). *Method:* embeddings (sentence-transformers) + structured features → HDBSCAN clusters = MO signatures; link incidents into **series** by MO + space-time proximity (near-repeat). *Validate:* silhouette + manual spot-check; recovers the planted series. *DoD:* unsolved crime shows "matches MO signature of cluster #/offender X."

**8.4 Spatiotemporal Predictive** — *Input:* historical incidents + socio-economic, by grid × time-shift. *Method:* Zia AutoML (headline) + LightGBM mirror; features = lagged counts, day/time, holiday, density. **Predict places/times, never individuals.** *Validate:* **walk-forward** split, **PAI/PEI**, **PR-AUC** for rare classes, beat a "last-period hotspot" baseline. *DoD:* heatmap with backtest numbers on the slide.

**8.5 Network / Link Analysis** — *Input:* resolved entities + edges. *Method:* `networkx` — **betweenness** (brokers/kingpins), **Louvain** communities (gangs), **link prediction** (hidden ties). Store adjacency in NoSQL. *Validate:* recovers planted network; link-prediction precision@k. *DoD:* clickable force-graph, kingpin auto-enlarged, cross-district links highlighted.

**8.6 Anomaly & Emerging-Trend** — *Input:* per-area per-type time series. *Method:* STL decomposition + EWMA/CUSUM control charts → spike flags → **Signals → Push/Mail**. *Validate:* detects planted spikes, low false-positive rate. *DoD:* a spike triggers a real push alert + red pulse on map.

**8.7 Prescriptive — Patrol Optimization** *(differentiator)* — *Input:* predicted risk surface + N patrol units. *Method:* greedy/ILP max-coverage over high-risk cells given unit capacity & travel. *DoD:* "Deploy your 5 units to zones A,B,C → covers 41% of predicted risk."

**8.8 Copilot (RAG)** — *Input:* NL query. *Method:* **hybrid retrieval** — text-to-SQL for structured filters (location/vehicle/date) fused with QuickML RAG vector search over narratives → rerank → Qwen answer **with mandatory source-FIR citations**. Guardrails: surfaces records, never asserts guilt; every query audit-logged. *Validate:* answer faithfulness + citation accuracy. *DoD:* "chain-snatching, blue Pulsar, South Bengaluru, after 8pm" → correct filtered results + citations.

## 9. Governance, ethics, privacy (bake in from day 1)
- **Predict places & times, never people.** No individual "criminality scores."
- **Bias audit panel:** predicted vs. victim-reported rate per ward; flag any ward over-predicted >1.3×.
- **PII & law:** mask victim identity by default (IPC 228A / its BNS successor; POCSO for minors); field-level RBAC (SCRB-admin / district / station); full **audit log**.
- **IPC→BNS taxonomy:** unified offense mapping across the 2024 legal transition.
- **Human-in-the-loop:** every AI output is a *reviewable lead*, not a verdict.
- **Ecosystem framing:** position as an analytics layer over **CCTNS/ICJS**.

## 10. Feature manifest
**① CORE (must build):** entity resolution · MO fingerprinting · co-offender network ★ · predictive + backtest · anomaly/trend alerts · explainability (SHAP) · OCR + review queue · synthetic + planted data · RAG with citations.
**② DIFFERENTIATORS (build if time):** fairness/bias audit · privacy + RBAC + audit log · patrol optimization · cross-jurisdiction linkage · data-quality/under-reporting dashboard.
**③ PITCH AS VISION (say, don't build):** what-if simulation · Kannada + voice copilot · animated network evolution · model-drift monitor · offline-first field app.
> **Rule: finish ALL of ① before touching ②. A complete ①-only demo beats a half-built ①+② demo.**

## 11. 21-day execution roadmap (3–4 person team; compress for 14, extend for 28)
**Tracks:** A = Data/Backend · B = AI/ML · C = Frontend · D = Pitch/Governance.

| Phase | Days | Goal & key tasks | Gate / milestone |
|---|---|---|---|
| **0 Setup** | 1–2 | Catalyst project, Auth+roles, repo, Pipelines CI, Data Store schema, Stratus buckets, GeoJSON+Census loaded | Deployed blank app + login works |
| **1 Data + Spine** | 3–6 | **D:** generate synthetic dataset incl. planted network. **A:** Circuits ingestion (Stratus→Signal→OCR→Qwen→Review→DB). **B:** entity resolution. **C:** descriptive dashboard + district choropleth | 🎯 **Full skeleton live on Catalyst by Day 6** |
| **2 Intelligence** | 7–14 | **B:** MO clustering, network+centrality, AutoML+SHAP+**backtest**, anomaly→Signals→Push. **C:** force-graph, pulsing map, "why" panel, review-queue UI. **A:** Job Scheduling nightly recompute, Cache | Hero reveal works end-to-end (Day ~12) |
| **3 Copilot+Act+Polish** | 15–19 | **B/A:** RAG copilot w/ citations, patrol optimization, SmartBrowz brief→Mail. **D:** bias panel, metrics, demo script. **C:** polish | Copilot answers w/ citations; PDF brief emailed |
| **4 Harden+Pitch** | 20–21 | Domain Mappings+SSL, load-test demo path, **record backup video**, finalize slides+report | Submission-ready |

**If solo / 2-person:** drop Track D's stretch items, cut ② entirely, keep ① core + one map + the hero + the backup video.

## 12. Repo structure & key APIs
```
/garuda
  /web            # React SPA (Web Client Hosting)
  /functions      # Catalyst Serverless (Node) — API + event functions
  /ml             # FastAPI on AppSail (resolution, graph, forecast, anomaly, optimize)
  /ingestion      # Circuits steps + OCR/Qwen extraction
  /data           # synthetic generator, gazetteer, GeoJSON, Census
  /schema         # Data Store DDL, seed scripts
  /docs           # this blueprint, slides, demo script
```
**Core API endpoints:** `POST /ingest`, `GET /incidents?filters`, `GET /hotspots?area&shift`, `GET /network/:entityId`, `GET /risk?grid`, `GET /anomalies`, `POST /patrol/optimize`, `POST /copilot/query`, `GET /report/:district` (→ SmartBrowz PDF).

## 13. Metrics to report (put on a slide)
| Component | Metric | Credible claim |
|---|---|---|
| OCR+extract | field accuracy; % auto vs. review | "84% auto, 16% to review" |
| Entity resolution | precision/recall | "1,240 aliases → 380 persons @ 0.92 precision" |
| Predictive | **PAI/PEI** vs baseline; PR-AUC | "Top 5% area captured 38% vs 11% baseline" |
| Copilot | citation accuracy | "96% answers cite the correct FIR" |
| Fairness | predicted-vs-actual disparity | "No ward over-predicted >1.3×" |

## 14. Demo script (~3.5 min, scene by scene)
1. **Hook (20s):** "Today this is 4 Excel files in 4 stations. Watch." 
2. **Ingest (30s):** upload a scanned FIR → OCR + review queue → row appears.
3. **Map (30s):** district map, a zone **pulses red** (emerging trend).
4. **Hero (60s):** click the zone → **the 3-district network resolves**; kingpin by betweenness; "these looked unrelated in Excel."
5. **Why (25s):** SHAP panel explains the risk drivers.
6. **Copilot (30s):** type a plain-English query → cited answer + filtered map.
7. **Act (25s):** patrol recommendation + auto-PDF brief emailed.
8. **Close (20s):** "Connect, explain, forecast — and built to be trusted: places not people, every lead human-reviewed." 
> **Record this as a video before demo day. Live demos die.**

## 15. Pitch & judging strategy
Likely axes: Innovation · Technical depth · Impact/relevance · Working demo · Sponsor-tech (Catalyst) · Presentation.
- **Innovation/depth:** entity resolution + MO + network + backtest + patrol optimization.
- **Impact:** maps to every bullet in the brief; CCTNS framing.
- **Catalyst:** the ~14-service map (and the deprecation catch).
- **Presentation:** one continuous story (§14), metrics slide (§13), roadmap slide (Tier ③).
**Slide order:** Problem → Live demo → Architecture → How the AI works (with metrics) → Responsible AI → Catalyst-native → Roadmap → Team.

## 16. Risk register & contingencies
| Risk | Mitigation |
|---|---|
| OCR weak on Kannada/handwriting | Review queue + confidence gate; demo on a clean-ish sample; report honest accuracy |
| Live demo fails | **Pre-recorded backup video** + screenshots |
| Catalyst quota/latency | Precompute & **Cache**; nightly **Job Scheduling** batch, not on-demand |
| RAG hallucination | Hybrid retrieval + mandatory citations + "no fabricated links" guardrail |
| Scope creep | Tier rule: ① fully before ② |
| Real data unavailable | Synthetic dataset (already the plan) |

## 17. Edge-case checklist
Handwritten/Kannada FIRs · ambiguous geocoding · class imbalance (rare crimes) · duplicate FIRs for one event · sparse rural districts (fall back to district level) · cold-start new crime types · IPC↔BNS code split · low-connectivity stations (queue uploads) · victim-PII masking.

## 18. Submission checklist (definition of done)
☐ Live Catalyst URL (custom domain) ☐ Hero network reveal works end-to-end ☐ ≥10 Catalyst services used ☐ Backtest metrics on a slide ☐ Responsible-AI panel ☐ Auto-generated PDF brief ☐ Copilot with citations ☐ 3.5-min backup video ☐ Architecture + runtime-flow diagrams ☐ README with data lineage + ethics note.
