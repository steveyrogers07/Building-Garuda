# GARUDA — Phase 8 (Frontend / Intelligence Console) Runbook

> Goal: the usable product in a browser — overview, the **network reveal**, the
> hotspot map, the copilot, and alerts/risk — one continuous demo story, wired to
> the live AppSail analytics API.

Build-side is done & locally verified (branch `feat/phase-8-frontend`); the live
**API-Gateway + Web-Client-Hosting deploy** is the deferred section. Everything local
runs at **$0** (no Catalyst account): the SPA is served by the same FastAPI process that
exposes the engines.

---

## 0. What's built

| Area | Files | Notes |
|---|---|---|
| Console shell + views | [client/index.html](../client/index.html) | sidebar nav, topbar, 5 views, inline SVG icon sprite (no emoji) |
| Design system | [client/assets/app.css](../client/assets/app.css) | dark SOC theme, Fira Code + Fira Sans, blue+amber+status, data-dense |
| Force graph (hero) | [client/assets/graph.js](../client/assets/graph.js) | self-contained canvas force-sim; size=strength, colour=community, kingpin ring |
| App / router / views | [client/assets/app.js](../client/assets/app.js) | overview, network, map, copilot, alerts; live API + mock fallback |
| Server (read endpoints) | [app/routers/analytics.py](../app/routers/analytics.py) | `GET /stats`, `GET /geo/districts` for the dashboard + map |
| Local serving | [app/main.py](../app/main.py) | `GARUDA_LOCAL=1` mounts the SPA at `/ui/` |
| Launcher | [app/run_phase8.py](../app/run_phase8.py) | one command → console + live API |

### Design system (credit: `ui-ux-pro-max` skill)
Generated via the skill's `--design-system` for "government crime-intelligence command
centre", then applied as a **dark** variant:
- **Style:** Data-Dense Dashboard (KPI cards, grid, max data visibility).
- **Palette:** blue primary `#1E40AF`/`#3B82F6` + **amber** accent `#D97706` + status
  green/amber/red, on dark slate surfaces.
- **Type:** **Fira Code** (data/labels, tabular figures) + **Fira Sans** (body).
- Anti-AI-generic: bespoke SOC aesthetic, SVG icons (no emoji), real data density,
  tabular numerals, considered spacing — not default Tailwind/Bootstrap.

### Stack decision
A **dependency-free static SPA** (HTML + CSS + vanilla JS) served by the local FastAPI,
**not** React+Vite+deck.gl. Rationale: zero npm/build risk, instant, offline-capable, and a
hand-crafted design system reads less "AI-templated" than default React output. The map is
an **inline-SVG proportional-symbol map** from the real district centroids (the gazetteer
polygons are coarse rectangles, so bubbles look better than a polygon choropleth); the
network is a **hand-rolled canvas force graph**. The API contract + design tokens port
directly to a React/Vite rebuild later if desired.

---

## 1. Exit gates

| Gate | What | Status |
|---|---|---|
| **G1** | SPA shell + role-gated nav across views | ✅ (auth stub; Catalyst SDK in deploy) |
| **G2** | Map: district load + pulsing hotspots; click → drill-down | ✅ (live `/geo/districts`) |
| **G3** | Network graph from `/network/{id}`: kingpin emphasised, communities coloured, click → details | ✅ live |
| **G4** | Copilot chat → `/copilot` with FIR citations + guardrail | ✅ live |
| **G5** | Alerts feed, risk leaderboard + SHAP "why", fairness panel | ✅ live |
| **G6** | Deployed via API Gateway; loads on Web Client Hosting URL | ⧖ account-gated |

**Verified locally:** `/stats`, `/geo/districts`, `/network/rings`, `/network/{kingpin}`,
`/copilot` all return live data; the SPA renders every view (overview KPIs, the gang
force-graph auto-selecting kingpin *Aayush Zachariah*, the map, copilot citations + the
guilt/out-of-scope refusals). A latent Phase-5 bug (`/network/rings` passed a removed
`min_persons` arg) was found and fixed here.

---

## 2. Run it ($0, no Catalyst)

```bash
python app/run_phase8.py        # then open http://127.0.0.1:9000/ui/
```

First run auto-generates the synthetic dataset. The engines build + cache on first hit per
view (network graph ~3s, risk model ~20s, copilot index ~1s), then stay instant.

**Demo flow:** Overview (KPIs + rings + alerts) → *Open network reveal* → click the kingpin
→ Hotspot Map → Copilot ("two-wheeler theft in BNU in March 2025") → Alerts & Risk
(spikes + SHAP "why" + fairness).

## 3. API consumed (same-origin local; API Gateway in prod)

`GET /stats` · `GET /geo/districts` · `GET /network/rings` · `GET /network/{canonical_id}`
· `POST /copilot` · `POST /anomaly/run` · `GET /risk/top` · `GET /risk/fairness`. Each view
falls back to embedded mock fixtures (mirroring the planted scenario) if an endpoint is
unavailable, so the UI always renders.

## 4. Account-gated (G6 — when the project is live)

- Replace the auth stub with the **Catalyst Web SDK** login; gate routes by role
  (SCRB-admin / district / station).
- Point the API client at the **API Gateway** base instead of same-origin; `catalyst deploy`
  the SPA to **Web Client Hosting**.
- Fold the existing Phase-3 `client/review.html` review queue in as a sixth view.

## 5. Gotchas

- MapLibre/Google Maps intentionally avoided — the SVG symbol map needs no key, no network,
  and renders the actual district centroids.
- The canvas force graph runs a cooling `requestAnimationFrame` loop; it interrupts cleanly
  on view change (`graph.stop()`).
- Reduced-motion is respected (animations disabled under `prefers-reduced-motion`).
- Asset cache-busting: bump the `?v=` on the script tags when shipping changes.

## 6. Next

Phase 9 (automation/governance) + Phase 10 (deploy). On deploy, the same SPA loads from Web
Client Hosting and reaches the engines through the API Gateway — no frontend rewrite.
