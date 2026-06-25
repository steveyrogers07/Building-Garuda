# app/ — The ML Brain (AppSail · Python/FastAPI) — Track B · Phases 4–7

The Python service where all heavy ML lives, deployed on **Catalyst AppSail** (managed Python runtime). Exposes HTTP endpoints consumed by the Node functions and the frontend (via API Gateway).

## Layout
- `routers/` — FastAPI routers, one per endpoint group.
- `engines/` — the actual algorithms:
  - `resolution/` — entity resolution (normalize + transliterate + blocking + `splink` → `Canonical_ID`). **Phase 4**
  - `mo_clustering/` — MO fingerprinting (embeddings + structured features → HDBSCAN → `MO_Clusters`). **Phase 4**
  - `network/` — co-offender graph (networkx: betweenness, Louvain, link prediction). **Phase 5 ★ hero**
  - `forecasting/` — predictive risk (Zia AutoML + LightGBM mirror + SHAP). **Phase 6**
  - `anomaly/` — emerging-trend detection (STL + EWMA/CUSUM → `Alerts`). **Phase 5/6**
  - `patrol/` — patrol/resource optimization (max-coverage over risk grid). **Phase 9 (differentiator)**
  - `copilot/` — hybrid RAG: NL→ZCQL filters + vector retrieval + QuickML (Qwen) generation with citations. **Phase 7**
- `shared/` — Catalyst SDK init, ZCQL helpers, config, caching.

## Endpoints
`/extract /resolve /mo-cluster /network/{id} /forecast /risk/explain /anomaly /patrol-optimize /copilot`

## Run / deploy
`app-config.json` sets the uvicorn start command, env vars, memory. Init the Python SDK **per request** (`zcatalyst_sdk.initialize(request)`). Deploy with `catalyst deploy appsail`. See [../docs/GARUDA_BUILD_WORKFLOW.md](../docs/GARUDA_BUILD_WORKFLOW.md) Stage 3.
