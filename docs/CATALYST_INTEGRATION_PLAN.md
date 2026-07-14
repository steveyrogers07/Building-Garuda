# GARUDA — Catalyst Integration Plan (organizer-mandated deployment)

> **STATUS (2026-07-12): decisions locked, execution not yet started.** All 4 blocking
> decisions in §7 are answered. Nothing has been run — no `catalyst login`, no
> `catalyst.json`, no code edits from §4 yet. The only thing that has to happen outside
> Claude is `catalyst login` in your own interactive terminal (browser OAuth). **Once
> that's done, tell Claude ("I've logged in" / "continue") and execution resumes at
> §7 step 2** (`catalyst init` → 4.1A → 4.2 → 4.3 → …, full order in §7).
>
> **Organizer rule:** *"Deployment via Catalyst is mandatory for all submissions, without
> exception"* — with a 26-row capability → Catalyst-service mapping table. This document
> maps every row of that table onto GARUDA as built, lists **every code edit required**
> (file-by-file, effort-tagged), and sequences the work so **no feature shipped so far is
> lost or degraded**.
>
> Companion docs (don't duplicate, cross-reference):
> - **When to spend credits** → [CATALYST_CREDITS_AND_DEPLOYMENT.md](CATALYST_CREDITS_AND_DEPLOYMENT.md) (build free in Dev, claim credits at Phase 10, spin down after demo)
> - **Ingestion wiring steps** → [PHASE_3_RUNBOOK.md](PHASE_3_RUNBOOK.md) · **Go-live** → [PHASE_10_KICKOFF.md](PHASE_10_KICKOFF.md)
> - **Data Store DDL** → [../schema/create_tables.md](../schema/create_tables.md) (all 12 tables, console-clickable)

---

## 0. Ground rules (the no-feature-loss contract)

1. **Local mode stays the default.** `python app/run_phase8.py` → `http://127.0.0.1:9000/ui/`
   must keep working exactly as today, from a clean checkout, with zero Catalyst
   dependencies. Every integration below goes behind a switch that already exists or is
   added defaulting OFF: `GARUDA_BACKEND` (`local`|`zcql`), `GARUDA_LOCAL`, `EXTRACTOR`
   (`rules`|`qwen`), `APPSAIL_BASE_URL`, plus new ones named here.
2. **All 9 test suites stay green** after every edit (`python tests/test_*.py` as scripts).
   No test may be weakened to accommodate a Catalyst path; Catalyst-only behavior gets
   *new* assertions or a documented manual gate, never replaces an existing one.
3. **The mock fallback stays.** The React console's `lib/mock.ts` planted-scenario
   fixtures (topbar shows "Mock data") remain the offline safety net for the demo.
4. **Dev = free, Production = credits.** Everything below is wired and tested in the
   Catalyst **Development** environment ($0); promotion to Production follows the credits
   doc's Phase-10 runbook, days before demo, not earlier.

---

## 1. Current state — what is already Catalyst-shaped

GARUDA was architected for this from Phase 1. Inventory of what exists **in the repo now**:

| Piece | Where | State |
|---|---|---|
| AppSail app config (Python 3.11, port binding, 512 MB) | `app/app-config.json` | ✅ ready (`uvicorn main:app --port ${X_ZOHO_CATALYST_LISTEN_PORT}`) |
| AppSail path resolution from a deployed bundle | `app/shared/store.py`, `app/shared/refs.py` | ✅ works from repo root *or* bundle root |
| Data bundling for deploy | `scripts/bundle_data_for_deploy.py` | ✅ one command, re-runnable |
| Python deps manifest | `app/requirements.txt` | ✅ (fastapi, sklearn, networkx, lightgbm, …) |
| Data Store DDL (all 12 tables incl. Officers/Arrests/Case_Sections/Courts) | `schema/create_tables.md` + `schema/canonical_schema.yaml` | ✅ console-clickable |
| Bulk loader CSV → Data Store (validate-gated, batched) | `ingestion/adapter/loader.py` | ✅ (`--dry-run` works locally; live write needs Catalyst context) |
| ZCQL read/write branches for **every** table | `app/shared/store.py` (`GARUDA_BACKEND=zcql`) | ⚠️ written, **unpaginated** (see §4.1) |
| Advanced I/O Node function (health + Review_Queue approve/reject) | `functions/api/` | ✅ written, not deployed |
| Stratus-event ingest function (Stratus → Zia OCR → `/extract` → Review_Queue) | `functions/ingest-event/` (+ `ocr.js` Zia wrapper) | ✅ written, trigger binding pending (Phase 3 runbook) |
| Circuits definition for the same pipeline with retries/dead-letter | `ingestion/circuits/fir_ingest.json` | ✅ documented, build in console |
| QuickML/Qwen schema-constrained extraction prompt + JSON schema | `ingestion/extraction/prompt.md`, `fir_schema.json`; `EXTRACTOR=qwen` in `app/engines/extraction/qwen.py` | ✅ written, off by default |
| Job logic for nightly recompute + weekly brief | `app/automation/jobs.py` | ✅ pure callables, cron-ready |
| Alert → Mail/Push routing envelopes | `app/automation/notify.py` | ✅ envelope built; `dispatch()` is a local stub |
| Brief HTML (SmartBrowz PDF-ready) | `app/automation/briefs.py`, `POST /brief/run` | ✅ returns rendered HTML |
| React SPA production build, relative asset paths | `client-react/` (`vite base: "./"`), served at `/ui/` | ✅ builds in <3s |
| Audit log to Data Store in zcql mode | `store.write_audit_log` | ✅ |

**Not in the repo yet:** a `catalyst.json` project file, any live Catalyst project, auth
integration, Gateway config, Cache/NoSQL/Stratus usage beyond the abstractions noted.

---

## 2. The organizer's 26 rows, mapped to GARUDA

Status legend: **READY** (code exists, wire in console) · **EDIT** (code change needed, itemized in §4)
· **SHOWPIECE** (optional, high judge-value) · **SKIP** (not applicable — justify in submission notes).

| # | Capability | Catalyst service | GARUDA mapping | Status |
|---|---|---|---|---|
| 1 | Serverless functions | **Functions** | `functions/api` (review endpoints), `functions/ingest-event`, `functions/jobs` | READY / EDIT (jobs body §4.8) |
| 2 | Docker deployment | AppSail (OCI) | Not needed — managed runtime chosen | SKIP (justified: Python managed stack) |
| 3 | Full web app, managed runtime | **AppSail** | The FastAPI ML brain (`app/`) — resolution, MO, network, series, anomaly, forecasting, copilot, workbench, district, deadlines | READY (§4.2) |
| 4 | Frontend/SPA | **Web Client Hosting** | `client-react/dist` (login, overview, my-cases, district, absconding, network, map, copilot, case file, dossier, search, audit) | EDIT (API base/CORS §4.3) |
| 5 | Custom domain + SSL | Domain Mappings | `garuda.<team-domain>` | OPTIONAL, last (credits doc §5.5) |
| 6 | Relational DB | **Data Store** | All 12 canonical tables (`schema/create_tables.md`) as system-of-record; Review_Queue; Audit_Log | READY / EDIT (serving strategy §4.1) |
| 7 | Semi-structured data | **NoSQL** | Cached ego-subgraph JSON (`store.write_network_cache` — currently local file "NoSQL/Cache in prod") | EDIT (S, §4.6) |
| 8 | Object storage | **Stratus** | `raw-fir` inbox bucket (scan uploads → ingest event); `briefs` bucket (rendered PDFs); demo FIR samples (`data/fir_samples/`) | READY (bucket creation + upload) |
| 9 | Cache | **Cache** | Cross-restart warm copies of the precomputed JSON (risk top, roster, absconding phase-1, geo aggregates) | EDIT (M, §4.7) |
| 10 | Full-text search in Data Store | Data Store search | Structured arm of `/search` (FIR no / names / plates) — semantic arm stays in-process TF-IDF | OPTIONAL EDIT (§4.11) |
| 11 | Text LLM / RAG | **QuickML (LLM serving)** | (a) Copilot answer generation over the existing hybrid-RAG retrieval + citations; (b) `EXTRACTOR=qwen` messy-FIR extraction — prompt + schema already in `ingestion/extraction/` | SHOWPIECE (§4.12) |
| 12 | No-code ML pipelines | QuickML | Alternative risk pipeline for comparison | SKIP or screenshot-only |
| 13 | AutoML (tabular) | **Zia AutoML** | One-off train on the risk feature table → accuracy comparison slide vs our walk-forward LightGBM+SHAP (keep ours as the product path) | SHOWPIECE (one training run) |
| 14 | OCR etc. | **Zia Services** | FIR scan OCR — `functions/ingest-event/ocr.js` (`zia().extractOpticalCharacters`), Kannada+English | READY (wire trigger) |
| 15 | Voice / translation | Zia Services | **Kannada voice query → copilot** (speech-to-text + translation feeding `/copilot`) — closes the "Kannada is nowhere" gap | SHOWPIECE (§4.13) |
| 16 | PDF / headless browser | **SmartBrowz** | Weekly intelligence brief: `briefs.render_html()` → SmartBrowz → PDF → Stratus | EDIT (S, §4.9) |
| 17 | User auth | **Authentication** | Replace demo header-login for production: Catalyst sign-in → user→role/scope mapping table | EDIT (M, §4.4) |
| 18 | API routing/throttle/auth | **API Gateway** | Front AppSail + Functions; same-origin paths for the SPA; **turn the X-Role demo headers into server-verified claims** | EDIT (M, §4.5) |
| 19 | OAuth to Zoho services | Connections | Only if AppSail calls QuickML/Zia REST directly (SDK inside Catalyst usually suffices) | AS-NEEDED |
| 20 | Cron / scheduled jobs | **Job Scheduling** | Nightly 02:00 recompute (anomaly/risk/network/workbench refresh + cache re-warm), weekly Mon 08:00 brief — logic in `app/automation/jobs.py` | EDIT (S, §4.8) |
| 21 | React to in-project events | **Signals + Event Functions** | FIR scan lands in Stratus → `functions/ingest-event` (written) → Review_Queue. Future: G1 BOLO auto-match on new-FIR insert against the absconding board | READY (bind trigger) / SHOWPIECE (BOLO) |
| 22 | Cross-app event bus | Signals | Alert fan-out: anomaly alert → Signal → notify function | EDIT (S, part of §4.10) |
| 23 | Workflow orchestration | **Circuits** | `ingestion/circuits/fir_ingest.json` — OCR → extract → queue with retries + dead-letter | READY (build in console) |
| 24 | Transactional email | **Mail** | `notify.py` envelopes → Mail send in the notify function (high/medium severity) | EDIT (S, §4.10) |
| 25 | Push notifications | **Push Notifications** | Same envelopes, `high` severity → web push to the console | EDIT (S, §4.10) |
| 26 | CI/CD | **Pipelines** | GitHub repo → run the 9 test scripts → auto-deploy to Dev on green — closes the "no CI" gap | EDIT (S, §4.14) |

**Coverage summary for the submission write-up:** 20+ of 26 rows exercised for real
(2 skipped with stated justification, 3–4 as judged showpieces). That breadth is itself a
scoring asset — cite this table in the submission.

---

## 3. Target production architecture

```
Browser ── Web Client Hosting (client-react/dist, served at /)
   │              │  (same Catalyst origin)
   │              ▼
   └──────► API Gateway ──────────► AppSail  «garuda-brain»  (FastAPI, python_3_11)
                 │                     │  GARUDA_LOCAL unset (no /ui mount)
                 │                     │  reads: bundled CSVs (data/…, §4.1 option A)
                 │                     │  writes: Data Store (audit, review, alerts)
                 │                     │  in-process _Lazy caches + warm() on boot
                 │
                 ├────► Functions «api»          (Review_Queue approve/reject)
                 ├────► Functions «jobs»         (Job Scheduling → nightly/weekly)
                 └────► Functions «ingest-event» (Stratus Signal → Zia OCR → /extract)

Data Store (12 tables + Review_Queue + Audit_Log)     Stratus (raw-fir, briefs)
Cache (precomputed JSON segments)                      NoSQL (ego-graph cache)
QuickML (Qwen: copilot answers / messy-FIR extraction) Zia (OCR, voice, translate)
SmartBrowz (brief HTML → PDF)                          Mail / Push (alert routing)
Pipelines (CI on the GitHub repo)                      Job Scheduling (cron)
```

Key property: **the SPA and the API share one origin behind the Gateway**, so
`lib/api.ts`'s `API = ""` same-origin contract keeps working in production exactly as it
does locally — no CORS, no client rewrite (fallback edit in §4.3 if Gateway routing turns
out not to give same-origin paths on your plan).

---

## 4. The edit list (all code changes, phased)

Effort: **S** ≤ 1h · **M** ≈ half day · **L** ≈ 1 day+. Every item states its feature-loss risk.

### P0 — mandatory to submit (deployable end-to-end in Dev)

**4.0 Catalyst project skeleton — S**
- `catalyst login` → `catalyst init` in the repo root (or a `deploy/` wrapper folder if init
  insists on scaffolding): register **AppSail** app pointing at `app/` (config exists),
  **Web Client Hosting** pointing at `client-react/dist`, **Functions** from `functions/*`.
- Commit the generated `catalyst.json` / `.catalystrc`. Add `app/data/` (the bundle copy)
  to `.gitignore` if not already.
- *Console:* create the project once, note `PROJECT_ID`/domain. **Verify current CLI
  command names in the console docs — they shift between Catalyst versions.**
- Feature risk: none (additive files).

**4.1 Data serving strategy — decision + S/M**
Two options; **Option A recommended**:
- **A (recommended): bundled-CSV serving, Data Store as system-of-record.**
  Run `python data/generate.py` → `python scripts/bundle_data_for_deploy.py` →
  `catalyst deploy`. AppSail serves all reads from the bundled CSVs through the existing
  mtime-cached store (today's measured 7–145 ms endpoints, zero per-request DB cost).
  Data Store holds the same rows (loaded once via `ingestion/adapter/loader.py` or console
  Import) as the durable system-of-record for **writes**: Review_Queue inserts,
  Audit_Log, alert rows — which already go to Data Store under zcql-write paths.
  *Edit (S):* split the backend switch into `GARUDA_READ_BACKEND` / `GARUDA_WRITE_BACKEND`
  in `app/shared/store.py` (default both `local`; prod sets writes→`zcql`). Mechanical:
  the read fns branch on one var, write fns on the other.
- **B: full ZCQL serving.** Honest blocker: `store._zcql_rows` does **no pagination** and
  ZCQL caps rows per query (~300/page — verify the current cap); a naive
  `GARUDA_BACKEND=zcql` flip silently truncates the 10,130-row corpus and every
  engine's numbers change. *Edit (M–L):* add LIMIT/OFFSET pagination loops to every zcql
  read + a read-through in-process cache so engines don't re-query per request. Only worth
  it if judges explicitly require reads-from-DB; Option A keeps Data Store genuinely used
  (row 6) without the perf/correctness risk.
- Feature risk: A = none (serving path unchanged). B without pagination = **silent data loss** — do not flip without the edit.

**4.2 AppSail deploy — S**
- Pre-deploy: `python scripts/bundle_data_for_deploy.py` (bundles `data/synthetic`,
  `reference`, `gazetteer` into `app/data/`).
- In production do **not** set `GARUDA_LOCAL=1` (that flag only mounts the local `/ui`
  static serving; prod SPA lives on Web Client Hosting).
- `app/app-config.json`: raise `memory` 512 → **1024 MB** first deploy (LightGBM training in
  `warm()` + pandas + networkx headroom; measure in Dev, trim down per credits doc).
  Add env: `GARUDA_WRITE_BACKEND=zcql` (after 4.1A), `ENV=prod`.
- Health probe: `/health` exists. Note `warm()` runs in a **background thread** at startup
  (main.py), so the instance binds the port immediately — first requests may be slow for
  ~1–2 min while caches build (same as local). Job-scheduled re-warm covers restarts (§4.8).
- Feature risk: none.

**4.3 SPA on Web Client Hosting — S (+ contingency M)**
- `npm run build` → deploy `client-react/dist` as the web client. `vite base: "./"` already
  makes assets relative.
- Router uses `HashRouter` → no server-side rewrite rules needed for deep links.
- **Same-origin check:** if Gateway serves the SPA and `/stats`, `/case/*`, … on one origin
  (target architecture §3), **no client edit is needed**. If your plan's Gateway can't route
  both, contingency edit (M): `lib/api.ts` — `const API = import.meta.env.VITE_API_BASE ?? ""`,
  and add gated CORS in `app/main.py` (`CORSMiddleware` enabled only when
  `GARUDA_CORS_ORIGINS` env is set). Defaults keep today's behavior byte-identical.
- *Dev-only bug found during this review (fix regardless):* `client-react/vite.config.ts`
  `API_ROUTES` proxy list is missing **`/district`, `/officers`, `/officer`, `/absconding`**
  — `npm run dev` (port 5173) silently falls back to mock data for District Command,
  My Cases, and the Absconding Board. Add the four routes. (S; local run_phase8 flow is
  unaffected, which is why it wasn't caught.)
- Feature risk: none; mock fallback still covers brain-unreachable.

**4.4 Authentication (row 17) — M**
- Console: enable Catalyst **Authentication** (email or Zoho sign-in) for the web client.
- New Data Store table `Console_Users` (`email`, `role`, `scope`, `officer_id?`) mapping
  verified identities to GARUDA's RBAC roles — the demo's 5 personas become 5 seeded rows.
- Frontend (`pages/Login.tsx`, `lib/roles.ts`): when `window.catalyst` (embedded auth SDK)
  is present, authenticate through Catalyst and fetch the principal from a new
  `GET /whoami`; when absent (local dev), fall back to today's demo login untouched.
  Keep the role-switcher visible in demo builds — it *is* the governance demo.
- Backend (`routers/analytics.py` `get_principal`): accept the Gateway/Auth-injected user
  (header set server-side, see 4.5) and look up role/scope from `Console_Users`; fall back
  to `X-Role`/`X-Scope` **only when `ENV != prod`**.
- Feature risk: none locally (fallback path); prod gains real auth.

**4.5 API Gateway (row 18) — M, console-heavy**
- Define routes: `/*` → Web Client Hosting; `/stats|/network/*|/case/*|…` → AppSail;
  `/review/*` → `functions/api`. Enable throttling (e.g., 60 rpm/user) on the heavy
  endpoints (`/copilot`, `/risk/run`, `/brief/run`).
- **Security payoff:** today `X-Actor/X-Role/X-Scope` are client-supplied (a deliberate demo
  affordance). Behind the Gateway, strip inbound `X-Role`/`X-Scope` headers and inject the
  authenticated user id; AppSail resolves role/scope from `Console_Users` (4.4). Document
  this in the submission's security section — judges notice header-trust.
- Feature risk: none locally (no gateway there); this is the single most important
  production-hardening item.

### P1 — high-value breadth, wire after P0 works in Dev

**4.6 NoSQL ego-graph cache (row 7) — S**
- `store.write_network_cache()` already isolates the write ("NoSQL/Cache in prod; local
  file for the PoC"). Add a zcql-mode branch writing the payload to a Catalyst **NoSQL**
  table keyed by `canonical_id`; add `read_network_cache()` used by `GET /network/{id}?cache=true`.
- Feature risk: none (local file path stays default).

**4.7 Catalyst Cache for precomputed JSON (row 9) — M**
- Purpose: survive AppSail restarts/scale-out without re-running `warm()`'s heavy builds,
  and let the nightly job (§4.8) publish fresh results the serving instance picks up.
- Add `app/shared/kvcache.py`: `get(key)` / `put(key, json, ttl)` — Catalyst Cache segment
  when the SDK context exists, in-process dict locally. Wrap the **outputs** (not the
  builders) of: `_risk_rows(top)`, `_ROSTER_CACHE`, `_ABSCONDING_CACHE` phase-1,
  `geo_districts`, `stats`. `_Lazy` in-process caches stay (they're the L1; Cache is L2).
- Feature risk: none (L2 only engages under Catalyst).

**4.8 Job Scheduling (row 20) — S code + console**
- Implement `functions/jobs/index.js` (folder exists, empty): a thin Job-function that
  POSTs to AppSail admin endpoints — nightly: `/anomaly/run`, `/risk/run`, `/network/run`,
  workbench refresh; weekly: `/brief/run` (+ SmartBrowz step §4.9). Logic/ordering already
  in `app/automation/jobs.py` — keep orchestration Python-side by adding one AppSail
  endpoint `POST /jobs/nightly` that internally runs `jobs.nightly_recompute([...])` and
  returns the per-task report; the Node job function then only makes one call.
- Console: two schedules (02:00 IST nightly, Mon 08:00 IST weekly) targeting the job function.
- Feature risk: none.

**4.9 SmartBrowz brief PDF (row 16) — S**
- `POST /brief/run` already returns rendered HTML (`briefs.render_html`). Add
  `?pdf=true` path: call SmartBrowz (HTML→PDF) via SDK/REST, store the PDF in Stratus
  `briefs/` bucket, return the object URL. Local fallback: return HTML as today.
- Feature risk: none.

**4.10 Signals → Mail + Push (rows 21/22/24/25) — S/M**
- `notify.dispatch()` is an explicit stub ("account-gated"). Implement the prod arm:
  AppSail (or the nightly job) raises a Catalyst **Signal** per high-severity alert; a small
  event function consumes it and sends **Mail** (all severities ≥ medium) and **Push**
  (high) using the envelope fields already produced by `notification_for()`.
- Keep `dispatch()` returning the would-send envelope locally — `tests/test_governance.py`
  asserts the routing rules and must stay green.
- Feature risk: none.

**4.11 Data Store full-text search (row 10) — OPTIONAL S**
- The structured arm of `/search` (FIR no, names, plates, phones) can additionally query
  Data Store's search API in zcql mode. The in-process index is already fast and the
  semantic arm must stay local (TF-IDF) — do this only for service-breadth credit.
- Feature risk: none if kept behind `GARUDA_READ_BACKEND=zcql`.

**4.14 Pipelines CI (row 26) — S, closes a known gap**
- Console: connect the GitHub repo (`Building-Garuda`), pipeline = `pip install -r
  app/requirements.txt` → `python data/generate.py` → run the 9 test scripts → (on green,
  optionally) auto-deploy AppSail to **Dev**. This converts the "8 solid suites but no CI"
  Tier-5 gap into a mandate-table row.
- Feature risk: none.

### P2 — showpieces (judge-visible AI breadth; spin up only while demoing)

**4.12 QuickML / Qwen (row 11) — M each, biggest credit burner (see credits doc §3)**
- **(a) Messy-FIR extraction:** everything exists — `EXTRACTOR=qwen`, prompt
  (`ingestion/extraction/prompt.md`), schema validation + one retry. Edit: point
  `app/engines/extraction/qwen.py` at the QuickML-served endpoint (env
  `QUICKML_ENDPOINT`/`QUICKML_KEY` via **Connections** if REST). Demo: upload a messy
  scan → watch it land in Review_Queue with per-field confidence.
- **(b) Copilot generative answers:** keep the existing hybrid retrieval + citations +
  guardrails exactly as-is; add an answer-composer step that passes the retrieved,
  already-cited context to Qwen with a "cite-only-provided-FIRs, never assert guilt"
  system prompt; env `COPILOT_LLM=quickml` (default off → today's templated answers).
  The guardrail tests in `tests/test_copilot.py` must pass in **both** modes.
- Feature risk: none while flags default off; **operationally**: spin the served model up
  30–60 min before demo, down right after (credits doc demo-day ops).

**4.13 Zia voice — Kannada copilot (row 15) — M**
- Frontend: mic button on the Copilot page → Zia speech-to-text (Kannada) → Zia
  translation KN→EN → existing `/copilot` → answer (optionally translated back EN→KN).
- Directly answers the "built for Karnataka but English-only" critique with the demo's
  best 30 seconds. Degrades cleanly: without the SDK the mic button hides.
- Feature risk: none.

**4.15 Zia AutoML comparison (row 13) — S, one run**
- Export the risk feature table (`fc.build_feature_table`) to CSV → one AutoML training
  in the console → screenshot metrics beside our walk-forward LightGBM+SHAP+fairness
  numbers in the submission ("we validated against AutoML; kept the explainable model").
  No code path changes; train once (credits doc: don't loop).

**4.16 Review UI (supports rows 1/21/23) — OPTIONAL M**
- The human-in-the-loop endpoints exist (`functions/api/review.js`) but the React console
  has no Review page. If demoing live ingestion end-to-end, add `pages/Review.tsx`
  (pending list → approve/reject) under the Govern nav group. Otherwise demo via the
  existing endpoints + Data Store console view.

---

## 5. Efficiency & performance on Catalyst (why this plan is also the fast one)

- **Serving reads from bundled CSVs (4.1A)** keeps today's measured latencies (7 ms
  roster, 9–43 ms absconding, sub-150 ms worklist) and today's `_Lazy`+mtime caches —
  per-request ZCQL would add network hops, the 300-row pagination problem, and API-call
  spend, for zero user-visible gain on a 10k-row corpus.
- **Keep `warm()` + background thread** (already in `app/main.py`): instance binds the
  port instantly, heavy builds (LightGBM, graph, TF-IDF, roster, absconding) happen off
  the request path. Add the **nightly re-warm** (4.8) so a restarted instance never faces
  a stampede, and **Cache L2** (4.7) so restarts pick up precomputed JSON instead of
  rebuilding.
- **Memory:** start AppSail at 1024 MB, watch the console metrics during a Dev demo run,
  then trim (billing is GB-minute — right-sizing is the biggest lever after keeping
  services off when idle, per the credits doc).
- **Bundle hygiene:** `bundle_data_for_deploy.py` copies only `synthetic`/`reference`/
  `gazetteer`. Ensure `data/local/` (generated alerts/briefs), `__pycache__`, and
  `client-react/node_modules` are excluded from any deploy zip.
- **Demo-day pattern:** precompute via the nightly job → serve cached results on stage →
  only `/copilot` (and voice) does live inference. This is both the cheapest and the
  most reliable stage behavior.

## 6. Feature-preservation checklist (run after every P-phase)

| Feature (as shipped today) | Proof it still works |
|---|---|
| Login + 5 role personas + live role switch | manual: each preset renders its scoped view |
| Overview / Alerts / Risk + fairness | `test_forecasting.py`, `test_network.py` + UI smoke |
| District Command (clearance, backlog, leaderboard) | `test_district.py` |
| **My Cases** (deadline clock, district→officer picker, RBAC) | `test_field_officer.py` F1–F4, F6 + SHO/SP role smoke |
| **Absconding Board** (person-grouped, filters, RBAC) | `test_field_officer.py` F5 + ethics-403 smoke |
| Case File (deadline badge, timeline, linked cases, masking) | `test_workbench.py`, F6 |
| Network reveal / Hotspot map / Universal search / Copilot guardrails | `test_network.py`, `test_copilot.py` + UI smoke |
| Governance: RBAC, masking, audit trail | `test_governance.py` |
| Ingestion: extract→confidence→review gating | `test_ingestion_pipeline.py` |
| Offline mock fallback ("Mock data" badge) | stop the brain, reload the SPA |

Rule of thumb: **every edit in §4 lands behind a default-off switch, so this table is
provable locally at any commit** — Catalyst adds surface area, never replaces the core.

## 7. Sequencing & decisions needed from you

1. **Now (Dev, $0):** 4.0 → 4.1A → 4.2 → 4.3 (+ the vite proxy fix) → smoke the Dev URLs.
   This alone satisfies "deployed via Catalyst" (rows 3, 4, 6, 8, 14, 21, 23 wired).
2. **Then (still Dev):** 4.4, 4.5 (auth + gateway), 4.8, 4.9, 4.10, 4.14. → 20+ rows covered.
3. **Pick showpieces by remaining runway:** voice-Kannada (4.13) and Qwen copilot (4.12b)
   have the highest demo value per hour; AutoML (4.15) is a one-hour slide win.
4. **Production promotion:** strictly per the credits doc — claim credits days before the
   demo, promote, load data, smoke, keep QuickML/AppSail off until ~an hour before stage.

### Decisions — LOCKED (2026-07-12)

| Decision | Choice |
|---|---|
| (a) Data serving strategy | **Option A** — bundled CSV reads + Data Store for writes (§4.1). Not Option B (ZCQL pagination gap). |
| (b) Auth depth | **Catalyst auth + visible role-switcher stays** (§4.4). The switcher is kept in demo builds — it's the governance demo. |
| (c) P2 showpieces | **Kannada voice → copilot only** (§4.13). Qwen/QuickML generative copilot (§4.12b) and Zia AutoML (§4.15) are explicitly **not** in scope for this pass — revisit only if runway remains after P0+P1+4.13. |
| (d) Custom domain | **No** — ship on the default Catalyst domain, skip Domain Mappings entirely. |

### Where execution actually stopped

Nothing has been run yet — this whole plan is still unexecuted. The one thing checked:
`catalyst --version` → `1.26.1` (CLI installed), `catalyst project:list` → **not logged in**,
no `catalyst.json` in the repo. `catalyst login` was attempted once and confirmed it needs
a **real interactive terminal** — it prompts `Allow Catalyst to collect CLI error reporting
information? (Y/n)` and then drives a browser-based OAuth sign-in. That can't run through
an automated/non-interactive shell, and it shouldn't be — it's the user's own Zoho
credentials/consent screen.

**To resume, in order:**
1. **You:** open your own terminal (not through Claude) and run `catalyst login`. Complete
   the browser sign-in.
2. **Claude, from here:** `catalyst init` in the repo root (4.0) — register AppSail → `app/`,
   Web Client Hosting → `client-react/dist`, Functions → `functions/*`. Commit the generated
   `catalyst.json`.
3. Then the code edits with no login dependency, in order: **4.1A** (split
   `GARUDA_READ_BACKEND`/`GARUDA_WRITE_BACKEND` in `app/shared/store.py`) → **4.2** (bundle
   data, bump `app/app-config.json` memory to 1024 MB, add `ENV=prod`/
   `GARUDA_WRITE_BACKEND=zcql` env) → **4.3** (add `/district`, `/officers`, `/officer`,
   `/absconding` to the `vite.config.ts` dev proxy list — a real bug found during this
   review, independent of deployment; also confirm same-origin once the Gateway routes are live).
4. Then **4.4/4.5** (Console_Users table + Login.tsx/get_principal wiring; API Gateway
   routing + header-trust hardening) — both need the live Catalyst project from step 2.
5. Then **4.8/4.9/4.10/4.14** (Job Scheduling, SmartBrowz PDF, Signals→Mail/Push, Pipelines CI).
6. Then **4.13** (Kannada voice → copilot) as the one committed showpiece.
7. **Production promotion** only in the final days before demo, per
   [CATALYST_CREDITS_AND_DEPLOYMENT.md](CATALYST_CREDITS_AND_DEPLOYMENT.md) — claim credits,
   promote, load data, smoke test, keep QuickML/AppSail off until ~1h before stage.

Say "I've logged in" (or just "continue") in a new message whenever you're ready, and
execution picks up at step 2 above.
