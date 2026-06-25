# GARUDA — Phase 1 (Foundation) Execution Runbook

> Goal: a deployable, authenticated, **empty** Catalyst project wired to this repo,
> with hello-world stubs proving each compute surface deploys, storage + cache
> provisioned, auth working, and CI set up. **No data model, ingestion, ML, or real
> UI yet** — those are Phases 2–8.

This runbook is split into **what is already done in the repo** (code/config Claude
prepared and verified locally) and **what only you can do** (anything that touches
your Zoho Catalyst account: console, browser OAuth login, deploys). Work top to
bottom; each step maps to an exit-gate item.

All work is on branch **`feat/phase-1-foundation`** — `main` is untouched.

---

## 0. Status snapshot

**Verified tooling on this machine**

| Tool | Required | Found |
|---|---|---|
| Node | 18+ | v24.14.1 ✅ |
| npm | — | 11.11.0 ✅ |
| Python | 3.11 | 3.11.9 ✅ |
| Git | — | 2.52.0 ✅ |
| Catalyst CLI | latest | 1.26.1 ✅ (installed this session) |

**Code/config already in the repo (locally syntax-checked + behaviour-tested)**

- `functions/api/` — Advanced I/O Node function. `GET /health` → `{"status":"ok",…}`
  (tested: returns **200**; unknown paths → 404). Files: `catalyst-config.json`
  (`type: advancedio`, `stack: node18`), `index.js`, `package.json`.
- `client/` — minimal placeholder that loads, plus the auth wiring:
  `index.html` (landing), `login.html` (hosted-login embed), `protected.html`
  (login-gated test route), `main.js` / `main.css` / `config.js`, `client-package.json`.
- `app/` — AppSail FastAPI hello-world: `main.py` (`/health`, `/`),
  `requirements.txt` (fastapi, uvicorn), `app-config.json`
  (binds **`X_ZOHO_CATALYST_LISTEN_PORT`**, `stack: python_3_11`, `memory: 512`).

**What needs YOUR Catalyst account (cannot be automated from here)**

Creating the project (console only), `catalyst login` (browser OAuth), `catalyst init`,
enabling Authentication, creating Stratus buckets / Cache, connecting Pipelines, and
running deploys. Steps below give the exact commands and what to verify.

---

## 1. Exit gate (tick when ALL true)

- [ ] **G1** Catalyst project exists; CLI logged in & linked (`catalyst.json` present).
- [ ] **G2** Functions deploy; hello-world `/health` returns **200** on the Dev URL.
- [ ] **G3** Client deploys; placeholder page loads on the Web Client Hosting Dev URL.
- [ ] **G4** AppSail Python hello-world deploys & `/health` responds.
- [ ] **G5** Authentication enabled; sign up/in works; the test route is login-gated;
      roles defined (SCRB-admin / district / station).
- [ ] **G6** Stratus buckets `raw-fir`, `reports`, `artifacts` created; one Cache segment created.
- [ ] **G7** Pipelines CI connected (push → auto-deploy to Dev), **or** manual
      `catalyst deploy` documented and working.

---

## 2. Create the project — **console only** (→ G1)

The *first* project in an org must be created in the web console; the CLI cannot create it.

1. Go to the Catalyst console → **Create Project**.
2. Name it exactly **`GARUDA`**.
3. You'll land in the **Development** environment. That's all we need for Phase 1
   (promoting to Production later requires Catalyst payments enabled — not now).

---

## 3. Link the CLI: `login` + `init` (→ G1)

Run these from the repo root (`Building-Garuda`). The CLI was slow
on its very first invocation in this environment (one-time) — that's normal.

```bash
catalyst login          # opens a browser OAuth flow — approve with your Zoho account
catalyst init           # interactive; see the choices below
```

**`catalyst init` choices**

- Components: select **Functions**, **Client**, **AppSail** (space to toggle).
- Associate project: pick **GARUDA**.
- Functions stack: **Node.js**.
- AppSail stack: **Python** (point its source at **`app/`** — see §5; init may defer
  AppSail to `appsail:add`, which is fine).

**Reconcile with the existing folders** (the repo is already scaffolded):

- The CLI discovers components by marker files that are **already present**:
  `functions/api/catalyst-config.json`, `client/client-package.json`,
  `app/app-config.json`. So your stubs should be picked up as-is.
- If `init` offers to **create a sample** function/client or to **overwrite** an
  existing file, choose **No / keep existing** — don't clobber the prepared stubs.
  (If you accidentally overwrite, `git checkout -- <file>` restores it.)
- If init creates an extra throwaway function dir (e.g. `functions/function1`), delete
  that dir; keep `functions/api`.
- **Do not delete** the per-folder `README.md` files or the `.gitkeep`s in folders
  reserved for later phases.
- After init you'll have a generated **`catalyst.json`** (project id/name/domain) and
  **`.catalystrc`**. These are git-ignored-sensitive only for secrets; `catalyst.json`
  itself is safe to commit. Confirm it names project **GARUDA** with your real id.

> `catalyst.json` is generated — don't hand-write it. It should reference your project
> id; the component dirs are found via their marker files above.

---

## 4. Local smoke test before deploying (optional but recommended) (→ G2)

```bash
catalyst serve          # serves functions + client locally
```

- Function: hit the local Advanced I/O URL the CLI prints, path **`/api/health`**
  (Advanced I/O routes are served under the function name). Expect
  `{"status":"ok","service":"garuda-api",…}`.
- Client: open the local hosting URL → the GARUDA placeholder should render. The
  "Auth SDK" line will say *not loaded* until §6 — that's expected locally.

> AppSail isn't part of `catalyst serve` the same way; test it after deploy (§5), or
> run it directly: `cd app && pip install -r requirements.txt && uvicorn main:app --port 9000`,
> then open `http://localhost:9000/health`.

---

## 5. AppSail: add + deploy (→ G4)

`app/` already has `main.py`, `requirements.txt`, and a prepared `app-config.json`.

```bash
catalyst appsail:add    # name it e.g. garuda-ml ; source dir: app ; stack: Python
```

When prompted for the **Python runtime**, the CLI lists what the server currently
offers (candidates: `python_3_9` / `python_3_10` / `python_3_11`). **Pick the closest
to 3.11** and make sure `app/app-config.json`'s `"stack"` matches the exact string the
prompt used. If `appsail:add` asks to overwrite `app-config.json`, you can say **No**
(keep the prepared one) as long as the `stack` value matches.

Prepared `app/app-config.json` (keys verified against the CLI):

```json
{
  "command": "uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT}",
  "build_path": ".",
  "stack": "python_3_11",
  "env_variables": { "ENV": "dev" },
  "memory": 512,
  "scripts": {}
}
```

- `X_ZOHO_CATALYST_LISTEN_PORT` is the port Catalyst injects — **confirmed** from the
  CLI source. The command must bind it (it does).
- Dependency install: the managed Python runtime installs `requirements.txt` on the
  build side. **Do not** vendor packages locally on Windows (`pip install -t .`) — that
  bundles Windows wheels (e.g. pydantic-core) that won't run on Catalyst's Linux. If a
  deploy ever reports missing `fastapi`/`uvicorn`, tell me and I'll add a Linux-safe
  build script instead.

Deploy just AppSail:

```bash
catalyst deploy --only appsail        # or: catalyst deploy appsail
```

Verify: open the AppSail Dev URL shown in the console + `/health` →
`{"status":"ok","service":"garuda-appsail",…}`.

---

## 6. Authentication + roles + gated route (→ G5)

1. **Console → Authentication →** enable it. Configure the hosted/embedded login and
   add yourself as a user so you can sign in.
2. **Roles:** create **`SCRB-admin`**, **`district`**, **`station`** (role-based PII
   masking is wired later in Phase 9; for now we just need the roles to exist and login
   to work).
3. **Web SDK snippet:** the client pages load the Catalyst Web SDK from a placeholder
   CDN tag:
   ```html
   <script src="https://static.zohocdn.com/catalyst/sdk/js/4.5.0/catalyst-web-sdk.min.js"></script>
   ```
   Copy the **exact** SDK `<script>` + embed code from **Console → Authentication →
   Get Started / Embed**, and replace that tag in `client/index.html`,
   `client/login.html`, `client/protected.html` if the version differs. The SDK API
   names used in `client/main.js` (`auth.signIn`, `auth.isUserAuthenticated`,
   `auth.signOut`) are stable across v4.
4. **Test the gate** (after the client is deployed, §8):
   - Visit `protected.html` **signed out** → it must redirect to `login.html`.
   - Sign in → `protected.html` shows your user object + a Sign out button. ✅ G5.

---

## 7. Stratus buckets + Cache segment (→ G6)

**Console → Stratus →** create three buckets (lowercase, hyphen-safe names):

- `raw-fir` — incoming scanned FIR uploads (Phase 3 ingestion trigger source).
- `reports` — generated PDFs / intelligence briefs (Phase 9).
- `artifacts` — model artifacts, exports, GeoJSON/Census reference data (Phases 2/6).

**Console → Cache →** create one segment named **`aggregations`** (hot ZCQL
aggregations / graph builds are cached here from Phase 5).

> Reminder: **File Store, Event Listeners, and Cron are EOL (30 Apr 2026)** — we use
> **Stratus**, **Signals + Event Functions**, and **Job Scheduling** instead.

---

## 8. CI (Pipelines) or manual deploy (→ G7)

**Preferred — Pipelines:** Console → **Pipelines** → connect the GitHub repo
`steveyrogers07/Building-Garuda` → set it to deploy the working
branch to the **Development** environment on push.

> Tip: point CI at `feat/phase-1-foundation` (or merge it to `main` first, your call —
> Claude will not touch `main` without you asking). Keep secrets out of git; use
> AppSail `env_variables` / Catalyst env for tokens.

**Fallback — manual deploy** (documented = also satisfies G7):

```bash
catalyst deploy                 # deploys functions + client + appsail to Dev
# or scope it:
catalyst deploy --only client
catalyst deploy --only functions
catalyst deploy --only appsail
```

---

## 9. Deploy & verify everything (→ G2,G3,G4)

```bash
catalyst deploy
```

Then verify each surface on the **Dev** URLs (exact hostnames appear in the console
after deploy):

| Gate | Check | Expected |
|---|---|---|
| G2 | `GET https://<project-dev-host>/server/api/health` | `200` `{"status":"ok",…}` |
| G3 | open `https://<project-dev-host>/` | GARUDA placeholder renders |
| G4 | `GET https://<appsail-dev-host>/health` | `{"status":"ok","service":"garuda-appsail"}` |
| G5 | `…/protected.html` signed out → login; signed in → user shown | gate works |

`curl` example for G2:

```bash
curl -i https://<project-dev-host>/server/api/health
```

---

## 10. Verified facts & gotchas (don't relearn these the hard way)

- **First project = console only.** CLI can't create the first project in an org.
- **Listen port:** AppSail injects **`X_ZOHO_CATALYST_LISTEN_PORT`** (confirmed in CLI
  source `serve/server/lib/appsail/index.js`). Bind to it.
- **Function type/stack:** Advanced I/O is `type: "advancedio"`; valid Node stacks are
  `node16|node18|node20|node22` (we use `node18`).
- **AppSail Python runtime** string is `python_3_x` — confirm the exact token from the
  `appsail:add` prompt and match it in `app-config.json`.
- **Don't vendor Python deps on Windows** for AppSail (wrong-platform wheels). Let the
  managed runtime install `requirements.txt`.
- **Prod promotion** (later) needs Catalyst **payments enabled**. Dev is free and is
  all Phase 1 needs.
- **Never hardcode secrets.** Use AppSail `env_variables` / Catalyst env, never git.
- **Keep functions thin** — push real computation to AppSail (`app/`).
- **EOL services:** File Store / Event Listeners / Cron (30 Apr 2026) → Stratus /
  Signals + Event Functions / Job Scheduling.

---

## 11. When Phase 1 is green

1. Tick all of §1 (G1–G7).
2. Commit on `feat/phase-1-foundation`, push, open a PR into `main` (your call to merge).
3. Ask for the **Phase 2 brief** (synthetic data generator + adapter + Data Store
   schema — the part that makes the platform dataset-ready).

> Golden rule: do not start Phase 2 until this exit gate is green.
