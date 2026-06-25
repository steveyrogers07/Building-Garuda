# GARUDA — Phase 1 Kickoff (paste this into a fresh build chat)

> You are starting a fresh build session for **Phase 1** of Project GARUDA. Read this whole brief, then help me execute Phase 1 step by step. Do **not** jump ahead to later phases.

## Project context (so you understand cold)
We're building **Project GARUDA** — an AI-driven crime-analytics & visualization platform for the **Karnataka State Police / SCRB**, for **Datathon 2026**. **Mandatory deploy target: Zoho Catalyst.**

- **GitHub repo (already scaffolded with folders + docs + diagrams):** https://github.com/steveyrogers07/Building-Garuda
- **Local clone:** `C:\Users\hp\OneDrive\Desktop\acadflip\Building-Garuda`
- **Full design lives in the repo's `docs/`:** `GARUDA_BLUEPRINT.md` (what & why), `GARUDA_BUILD_WORKFLOW.md` (Catalyst-native build steps), `GARUDA_10_PHASE_PLAN.md` (the gated plan), `GARUDA_DATA_READINESS.md` (dataset readiness). Read `GARUDA_BUILD_WORKFLOW.md` Stage 0 for more detail on this phase.

**Locked stack:** React + Vite + TS on Catalyst **Web Client Hosting**; **Node** serverless functions (glue/REST); **Python/FastAPI** ML on **AppSail**; **Data Store** (ZCQL); **QuickML** (Qwen 2.5-14B) for RAG; **Zia** for OCR; **Zia AutoML** for tabular.

**Critical Catalyst facts (don't get these wrong):**
- File Store, Event Listeners, and Cron are **END-OF-LIFE (30 Apr 2026)** → use **Stratus**, **Signals + Event Functions**, and **Job Scheduling** instead.
- The **first Catalyst project must be created in the web console**, not the CLI.
- **Event functions are Node/Java only**; all heavy Python ML lives on **AppSail**.

We work in **10 gated phases**. This is **Phase 1 (Foundation) only**. No data model, no ingestion, no ML, no real UI yet — just a deployable, authenticated, empty project with CI.

---

## Phase 1 — Goal
A deployable, authenticated, empty Catalyst project wired to this repo, with hello-world stubs that prove each component deploys, storage + cache provisioned, auth working, and CI set up.

## Phase 1 — Exit Gate (done when ALL are true)
- [ ] Catalyst project exists; CLI logged in and linked to the repo (`catalyst.json` present).
- [ ] **Functions** deploy; a hello-world Advanced I/O endpoint returns `200` (`/health`) on the Dev URL.
- [ ] **Client** deploys; a placeholder page loads on the Web Client Hosting Dev URL.
- [ ] **AppSail** Python hello-world deploys and responds (de-risks the trickiest deploy early).
- [ ] **Authentication** enabled; sign up / sign in works; a test route is login-gated; roles defined (SCRB-admin / district / station).
- [ ] **Stratus** buckets created: `raw-fir`, `reports`, `artifacts`; one **Cache** segment created.
- [ ] **Pipelines** CI connected (push → auto-deploy to Dev) — or the manual `catalyst deploy` flow documented if CI is deferred.

## Prerequisites
- Node 18+, Python 3.11, Git installed.
- A Zoho Catalyst account (free dev tier is fine).
- `npm install -g zcatalyst-cli` → verify `catalyst --version`.
- *(Commands are shell-agnostic; on Windows use PowerShell or Git Bash.)*

## Steps

### 1. Create the project (web console — required first)
Go to the Catalyst console → create a new project named **GARUDA**. (The first project cannot be created from the CLI.)

### 2. Log in & initialize the CLI inside the repo
```
cd Building-Garuda
catalyst login
catalyst init
```
When prompted: select components **Functions + Client + AppSail**; associate with the **GARUDA** project; Functions language **Node.js**; AppSail stack **Python**; give the client a package name. This creates `catalyst.json` + `.catalystrc`.
> ⚠️ The repo already has `client/`, `functions/`, `app/` folders with READMEs. Reconcile whatever `catalyst init` generates so those folders stay aligned (point AppSail's source dir at `app/`). Don't delete the existing per-folder README files.

### 3. Hello-world Function (Advanced I/O, Node)
Add a function under `functions/api` that returns `{ "status": "ok" }` on `GET /health`. (See the Catalyst "Working with Functions" docs for the exact add command.) Test locally with `catalyst serve`.

### 4. Minimal Client
Ensure the client has an `index.html` that loads (a "GARUDA — coming soon" placeholder is fine; the real React app is Phase 8).

### 5. Minimal AppSail (Python/FastAPI) — de-risk early
In `app/` add `main.py` (FastAPI with a `/health` route), `requirements.txt` (`fastapi`, `uvicorn`), and `app-config.json`.
```
catalyst appsail:add        # stack: Python, source dir: app
catalyst deploy appsail
```
`app-config.json` startup command example: `uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}`
> Bind to the port Catalyst injects via an env var (commonly `X_ZOHO_CATALYST_LISTEN_PORT` — confirm the exact name in the AppSail docs).

### 6. Authentication
Enable Authentication in the console; configure sign-up/sign-in. Define roles/segments: **SCRB-admin, district, station**. Wire the Catalyst Web (JS) SDK login in the client and gate one test route.

### 7. Storage & Cache
Console → **Stratus**: create buckets `raw-fir`, `reports`, `artifacts`. Console → **Cache**: create a segment (e.g., `aggregations`).

### 8. CI (Pipelines)
Connect this GitHub repo to **Catalyst Pipelines** for auto-deploy to Dev on push. If Pipelines is blocked, document the manual `catalyst deploy` flow and move on — don't let CI block the gate.

### 9. Deploy & verify
```
catalyst deploy
```
Open the Dev URLs and confirm: client placeholder loads · function `/health` returns 200 · AppSail `/health` responds · login works.

## Gotchas
- First project = console only; production promotion later needs Catalyst payments enabled (Dev is enough now).
- Never hardcode secrets — use AppSail `env_variables`.
- Keep functions thin (Node); heavy ML is Phase 4 on AppSail.

## Out of scope for Phase 1 (resist these — they're later phases)
Data Store tables & synthetic data → Phase 2 · ingestion/OCR → Phase 3 · ML engines → Phases 4–7 · real React UI → Phase 8.

## When Phase 1 is done
Commit & push, tick the exit-gate checklist above, then start **Phase 2 — Data Layer & Synthetic Dataset** (see `docs/GARUDA_10_PHASE_PLAN.md`).
