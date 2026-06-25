# GARUDA — Technical Build Workflow (Catalyst-native)
The actual construction sequence. Each stage is independently testable. Commands/SDK calls verified against Catalyst docs (links at bottom). Items marked ⚠️verify = confirm exact field/name in the linked doc before relying on it.

## Architecture decisions that drive the build
- **Node glue → Python brain.** Event functions (ingestion triggers) are **Node.js/Java only**. Heavy ML (resolution, graph, forecast, clustering) runs as a **Python FastAPI app on AppSail**. Node functions call the Python brain over HTTP.
- **Three compute surfaces:** (1) **Advanced I/O functions** (Node) = light REST + auth-gated reads; (2) **Event functions / Circuits** (Node) = ingestion; (3) **AppSail** (Python/FastAPI) = ML + orchestration endpoints.
- **Copilot = hybrid**, not KB-RAG alone (see Stage 5).
- **Scheduling = Job Scheduling**, NOT Cron (Cron is EOL since 30 Apr 2026).

## Repo ↔ Catalyst component layout
```
/garuda
  catalyst.json  .catalystrc          # created by `catalyst init`
  /functions
    /api          # Advanced I/O (Node)  -> REST for frontend
    /ingest-event # Event function (Node) -> Stratus upload handler
    /jobs         # Job function (Node)   -> called by Job Scheduling
  /app            # AppSail Python (FastAPI) = the ML brain
    main.py  requirements.txt  app-config.json
  /client         # React (Vite) build output -> Web Client Hosting
  /data           # local tooling: synthetic generator, gazetteer, geojson (NOT deployed)
  /schema         # table definitions, seed/import scripts
```

---

## STAGE 0 — Bootstrap (½ day)
1. **Console:** create the project (the *first* project must be made in the web console, not CLI). Name it `GARUDA`.
2. **Local CLI:**
```bash
npm install -g zcatalyst-cli
catalyst --version
catalyst login
catalyst init        # select: Serverless functions, CloudScale client, AppSail; associate GARUDA
```
3. **Prove the pipeline:** add a hello-world Advanced I/O function → `catalyst serve` (local) → `catalyst deploy` (deploys to **Development** env). Production is promoted later from the console (requires Catalyst payments enabled).
- **DoD:** dev function URL returns 200.

## STAGE 1 — Data foundation (unblocks everything — do first)
1. **Create Data Store tables** (Console → Cloud Scale → Data Store → Create Table). Tables: `Incidents, Entities, Incident_Edges, Predictive_Risk, MO_Clusters, Crime_Series, Socioeconomic, Geo_Boundaries, Alerts, Review_Queue, Audit_Log`. (Catalyst auto-adds `ROWID, CREATORID, CREATEDTIME, MODIFIEDTIME`.) Table names: alphanumeric + underscore, no leading digit.
2. **Smoke-test ZCQL** in the ZCQL Console:
```sql
SELECT Incidents.Crime_Type, Entities.Value
FROM Incidents
JOIN Incident_Edges ON Incident_Edges.IncidentID = Incidents.ROWID
JOIN Entities ON Entities.ROWID = Incident_Edges.EntityID
LIMIT 20;
```
3. **Load reference data:** upload GeoJSON boundaries + Census CSV to **Stratus**; load lookups into tables.
4. **Synthetic generator** (local Python in `/data`): emit CSVs for incidents/entities/edges with the **planted cross-district network + near-repeat series + anomaly spikes**, mixed IPC/BNS codes, Kannada/English alias variants. Bulk-load via Data Store **Import** (console) or Python SDK bulk write (~50k rows).
- **DoD:** ZCQL aggregations return realistic distributions; planted network is present.

## STAGE 2 — Ingestion pipeline (event-driven)
1. **Stratus:** create bucket `raw-fir`.
2. **Wire the trigger:** Stratus *file-create* event → **Signal** → **Circuit** (multi-step, recommended) or a single **Event function** (Node). Configure the binding in the console (Signals/event config) to point at the bucket.
3. **OCR step** (Node, Zia SDK — Kannada is supported, it covers 10 Indian languages):
```js
const catalyst = require('zcatalyst-sdk-node');
const fs = require('fs');
module.exports = async (event, context) => {
  const app = catalyst.initialize(context);
  const zia = app.zia();
  const ocr = await zia.extractOpticalCharacters(
    fs.createReadStream(localPath),
    { language: 'eng', modelType: 'OCR' }   // returns { confidence, text }
  );
  // -> POST ocr.text to AppSail /extract
};
```
4. **Structured extraction:** Node posts OCR text to AppSail **`/extract`** (Python) → Qwen (QuickML LLM Serving) with a schema-constrained prompt → JSON fields (names, vehicle, weapon, date, place). NER fallback = Zia text analytics.
5. **Geocode** the place name via your gazetteer (AppSail) → lat/long.
6. **Persist:** write to `Review_Queue` with per-field confidences. On reviewer approve → insert into `Incidents` + `Incident_Edges` (ZCQL). Low confidence stays queued (human-in-the-loop).
- **DoD:** drop a sample FIR image into `raw-fir` → a row appears in `Review_Queue`.

## STAGE 3 — ML brain on AppSail (Python/FastAPI) — parallel with Stage 2
1. **Scaffold:**
```bash
catalyst appsail:add        # stack: Python; source dir: /app
```
`requirements.txt`: fastapi, uvicorn, pandas, scikit-learn, lightgbm, networkx, hdbscan, sentence-transformers, splink, shap, statsmodels, zcatalyst-sdk-python.
2. **`app-config.json`** (⚠️verify exact keys + port var in AppSail docs):
```jsonc
{
  "command": "uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}",
  "env_variables": { "ENV": "dev" },
  "memory": 512
}
```
Catalyst injects the listen port via an env var (commonly `X_ZOHO_CATALYST_LISTEN_PORT`) — bind to it.
3. **Init SDK per request** (Python SDK must be initialized with the request object):
```python
import zcatalyst_sdk
from fastapi import FastAPI, Request
app = FastAPI()

@app.middleware("http")
async def attach_catalyst(request: Request, call_next):
    request.state.cat = zcatalyst_sdk.initialize(request)   # ⚠️verify signature
    return await call_next(request)
```
4. **ZCQL from Python:**
```python
zcql = request.state.cat.zcql()
rows = zcql.execute_zcql_query("SELECT * FROM Incidents WHERE District_Code='BLR'")
```
5. **Endpoints:** `/extract`, `/resolve` (splink → Canonical_ID), `/mo-cluster` (embeddings+HDBSCAN → MO_Clusters), `/network/{entityId}` (ZCQL JOIN → networkx centrality/Louvain → force-graph JSON), `/forecast`, `/anomaly`, `/patrol-optimize`, `/copilot`.
6. **Persist derived data:** graph adjacency + embeddings → **NoSQL**; hot aggregations → **Cache**.
7. **Deploy:** `catalyst deploy appsail`. Front it with **API Gateway**.
- **DoD:** `curl <appsail-dev-url>/network/<id>` returns graph JSON.

## STAGE 4 — Predictive model + explainability
1. Build a training table: features per **grid × time-shift** (lagged counts, day-of-week, hour bucket, holiday flag, density, literacy). Export to Stratus/CSV.
2. **Zia AutoML** (console): upload tabular data → pick target → train → deploy → copy the prediction endpoint.
3. **Batch-score** grids nightly (Stage 6 job calls the AutoML endpoint) → write `Predictive_Risk`.
4. **Explainability:** train a **LightGBM mirror** in AppSail → SHAP → `/risk/explain?grid=` returns top drivers for the "why" panel.
5. **Validate:** walk-forward split; compute **PAI/PEI**; store `Backtest_PAI`. Always beat a "last-period hotspot" baseline.

## STAGE 5 — Copilot (HYBRID — this is the correct design)
> KB-RAG alone can't hold 50k FIRs (≤500 KB/doc). Build three layers in the `/copilot` AppSail endpoint:
1. **Structured layer:** NL → filters → ZCQL over `Incidents` (precise: location, vehicle, date, type). Optionally NL→ZCQL via Qwen.
2. **Semantic layer:** embed narratives (sentence-transformers / QuickML) → store vectors in NoSQL → top-k retrieve.
3. **Generation:** call **QuickML LLM Serving (Qwen 2.5-14B)** or the **RAG API** (POST only; OAuth scope `QuickML.deployment.READ`; endpoint from RAG chat → "View API" → Model Details) with retrieved context.
4. **Always return source FIR IDs** (citations). Guardrail prompt: surface records, never assert guilt. Log every query to `Audit_Log`.

## STAGE 6 — Automation & alerts (Job Scheduling, not Cron)
1. **Job Scheduling:** create a **Function/AppSail Job Pool** → create jobs → schedule with a **pre-defined cron**: nightly 02:00 (recompute forecast + anomaly + network), weekly Mon 08:00 (intelligence brief). Dynamic crons via SDK if needed.
2. **Spike alerts:** anomaly job writes `Alerts` → emits a **Signal** → Event function fires **Push Notifications** + **Mail** to the district officer.
3. **Weekly brief:** cron → job → function triggers **SmartBrowz** (headless render of the dashboard → PDF) → store in **Stratus** → **Mail** to DGP.
- **DoD:** manually run the cron once → PDF in Stratus + email received.

## STAGE 7 — Frontend (React → Web Client Hosting)
1. Build React (Vite) so output lands in `/client` (the dir `catalyst init` created).
2. **Auth:** Catalyst **Authentication** via the Web (JS) SDK (embedded/hosted login); gate routes by role (SCRB-admin/district/station).
3. **Data:** Web SDK for simple Data Store reads + auth; call AppSail/Functions ML endpoints via **API Gateway**.
4. **UI:** MapLibre + deck.gl (hotspots/choropleth from `Predictive_Risk` + `Geo_Boundaries`), react-force-graph (`/network`), copilot chat (`/copilot`), review-queue table, SHAP "why" panel, bias panel.
5. **Deploy:** `catalyst deploy` (optionally `--only client`).
- **DoD:** dev hosting URL loads, login works, map + graph render from live data.

## STAGE 8 — Harden & ship
- **API Gateway:** routes + throttling + auth in front of AppSail/Functions.
- **Cache** expensive ZCQL aggregations + graph builds.
- **Governance:** `Audit_Log` middleware on every record read; field-mask victim PII by role.
- **Pipelines:** Git → CI → deploy.
- **Promote dev → production** from console; **Domain Mappings** for custom domain + SSL.
- Secrets live in AppSail `env_variables` / Catalyst — never hardcode OAuth tokens.

---

## Build order / critical path
`0 → 1 → (2 ∥ 3) → 4 → 5 → 6 → 7 → 8`
- Stage 1 (data) unblocks all.
- Stage 3 (AppSail brain) runs in parallel with Stage 2 (ingestion) once tables exist.
- Stage 7 (frontend) can start early against mocked endpoints.

## Source docs (verified)
- Quick Start / CLI: https://docs.catalyst.zoho.com/en/getting-started/quick-start-guide/ · https://docs.catalyst.zoho.com/en/cli/v1/cli-command-reference/
- Data Store + ZCQL: https://docs.catalyst.zoho.com/en/cloud-scale/help/data-store/introduction/ · https://docs.catalyst.zoho.com/en/cloud-scale/help/zcql/introduction/
- AppSail (managed Python): https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/deploy-from-cli/ · https://docs.catalyst.zoho.com/en/serverless/help/appsail/key-concepts/catalyst-configurations/
- Stratus + Signals/Event functions: https://docs.catalyst.zoho.com/en/cloud-scale/help/stratus/introduction/ · https://docs.catalyst.zoho.com/en/signals/help/events/
- Zia OCR (Node): https://docs.catalyst.zoho.com/en/sdk/nodejs/v2/zia-services/ocr/
- QuickML RAG / LLM Serving: https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/rag/ · https://docs.catalyst.zoho.com/en/quickml/help/generative-ai/llm-serving/
- Job Scheduling: https://docs.catalyst.zoho.com/en/job-scheduling/getting-started/quick-start-guide/
