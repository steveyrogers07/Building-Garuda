# GARUDA — Iteration 11 (Investigation Workbench) Runbook

> Goal: turn the console from a dashboard into an **object-centric investigation
> workbench** — the Palantir-style loop: *search anything → open its dossier →
> pivot to linked cases → expand the network → ask the copilot* — governed
> end-to-end (RBAC + masking + audit) with the edge cases designed, not ignored.

Branch `feat/iter-11-workbench` (on top of Phase 9). Everything local at **$0**;
same engines deploy to AppSail unchanged.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Workbench engine (dossier / case links / search) | [app/engines/workbench.py](../app/engines/workbench.py) | ✅ |
| Full-column incident fetch | [app/shared/store.py](../app/shared/store.py) `fetch_incidents_full` | ✅ |
| Governed endpoints | [app/routers/analytics.py](../app/routers/analytics.py) `GET /entity/{id}` · `GET /case/{id}` · `GET /search` (+`_authz` 403 mapping) | ✅ |
| Workbench UI (tabs, search, dossier, case file, role switcher) | [client/index.html](../client/index.html) · [client/assets/app.js](../client/assets/app.js) · [client/assets/app.css](../client/assets/app.css) | ✅ |
| Eval | [tests/test_workbench.py](../tests/test_workbench.py) | ✅ all gates green |

**Verified** (`python tests/test_workbench.py` + live HTTP smoke):
- **Dossier** `ENT014602`: 9 incidents · 4 districts · associates incl. the shared phone
  `+916534933629` + vehicle `KA68MC3164`; alias entity-ids resolve to their canonical; unknown → 404.
- **Case** `INC010002`: **9 linked cases with explained reasons** (`shared_phone`,
  `shared_vehicle`, `shared_person`), ranked by evidence strength; the gang FIRs interlink.
- **Search**: plate → the gang vehicle (10 incidents / 4 districts) in **12–13 ms**; person,
  case-id and **semantic narrative** matches work; results ranked by recorded involvement.
- **Governance over HTTP**: district out-of-jurisdiction case → **403**; ethics dossier → **403**;
  victim-only identities masked for analyst in both dossier *and* search (no leak path);
  suspects visible with *pending-trial* framing; every read audited.

## 1. The workbench model

**Objects:** case (FIR) · person · vehicle · phone. Every object is **URL-addressable**
(`#case/INC010002`, `#entity/ENT014602`) and opens as a **workspace tab** (persisted per
session) — an investigation accumulates open objects like an IDE accumulates files.

**Pivots (drill-everywhere):** search result → dossier/case · case party → dossier ·
dossier appearance → case · dossier associate → dossier · linked case → case ·
copilot citation → case · ring row (overview) → kingpin dossier · graph node → dossier.

**The demo loop (start from one plate):**
`Ctrl-K` → type `KA68MC3164` → vehicle dossier (10 incidents, 4 districts) → associate
*Aayush Zachariah* → kingpin dossier → *Ego network* → the gang → linked cases → copilot.

## 2. Linked-case reasoning (why two FIRs connect)

| Reason | Signal | Weight |
|---|---|---|
| `shared_phone` / `shared_vehicle` | same canonical link-entity on both FIRs | 4 |
| `shared_person` | same canonical person | 3 |
| `series` | same detected crime series (near-repeat linkage) | 3 |
| `mo` | same MO cluster (when Phase-4 MO has been run) | 2 |
| `near_repeat` | same district+crime within 2 km / 14 days | 1 |

Reasons stack; links are ranked by total strength and rendered as chips on the case file.

## 3. Governance in the UI (the live demo moment)

The sidebar **role switcher** re-issues every object read with `X-Role`/`X-Scope`:
- `scrb-admin` → full identity; `analyst` → victim/witness masked (`A. M.` + reason badge);
- `district:BNU` → out-of-jurisdiction cases return a designed **403 panel** (not a blank);
- `ethics` → dossiers/cases refused; search restricted with an explanatory note;
- IPC-228A/POCSO identities stay masked for everyone but admin/case-officer.
Switching roles live and watching names redact **is** the governance pitch.

## 4. Edge cases handled (by design)

not-found case/entity → designed error state · 403 → explanation + "switch role to compare" ·
alias id → canonical dossier · victim-only person → masked in dossier *and* search ·
no linked cases → explicit "no shared entities / series / near-repeat" ·
empty search → guidance (Enter → copilot) · <2 chars → hint · offline/API-down → mock
fixtures so the UI never blanks · first network load → progress note (centrality ~1 min) ·
role switch → cached masked payloads invalidated · deep link to any object · tabs survive reload.

## 5. Run it

```bash
python app/run_phase8.py     # serves API + workbench at http://127.0.0.1:9000/ui/
python tests/test_workbench.py
```

## 6. REST contract (workbench)

| Method · Route | Returns |
|---|---|
| `GET /entity/{canonical_or_alias_id}` | dossier: identity+aliases, appearances, associates (weighted), timeline, activity indicators, guardrail |
| `GET /case/{incident_id}` | full FIR + masked parties + linked cases with reasons + timeline |
| `GET /search?q=` | grouped hits (cases/people/vehicles/phones/places) + semantic narrative matches |

All three: principal via `X-Role`/`X-Scope` (Catalyst Auth/Gateway in prod), audited, 403/404 semantics.

## 7. Next

Iteration 12 (watchlists/BOLO, alert workflow, briefs UI) builds directly on these objects;
Phase 10 wires deploy. The dossier's *activity indicators* stay deliberately transparent —
components, never a single "risk score" on a person.
