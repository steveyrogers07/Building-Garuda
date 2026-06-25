# GARUDA — Phase 8 Kickoff (paste into a fresh build chat)

> Fresh build session for **Phase 8** of GARUDA. Read fully, execute step by step, don't jump ahead.

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/Building-Garuda`
- Read: `docs/GARUDA_BLUEPRINT.md` (§ visualization), the diagrams in `docs/diagrams/`, `docs/PHASE_3_RUNBOOK.md` (existing `client/review.html` review UI + functions/api REST contract), `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**Dev only, $0**).
- Stack: **React + Vite + TS + Tailwind** on **Web Client Hosting** · MapLibre GL + deck.gl · react-force-graph · Recharts.

## ✅ Dependency — start NOW on mocked endpoints
Can begin immediately. Build against **mock JSON** matching each engine's output, then swap to live endpoints as P5/P6/P7 land. The P3 `client/review.html` review queue already exists — fold it into the SPA.

## Convention
Frontend in `client/`; calls AppSail/Functions via **API Gateway** (or same-origin `/server`); **Authentication** via the Catalyst Web SDK, role-gated (SCRB-admin/district/station). Produce `docs/PHASE_8_RUNBOOK.md`.

## Goal
The usable product: maps, the network reveal, the copilot, dashboards — the one continuous demo story in a browser.

## Exit Gate (✅ local/mock · ⧖ live)
- [ ] **G1** React SPA shell + role-gated auth; nav across views. ✅
- [ ] **G2** **Map** (MapLibre + deck.gl): district choropleth + **pulsing hotspots** from `Predictive_Risk` + `Geo_Boundaries`; click district → drill-down. ✅(mock)
- [ ] **G3** **Network graph** (react-force-graph) from `/network/{id}`: kingpin node enlarged (centrality), communities colored, click → incidents/MO. ✅(mock)
- [ ] **G4** **Copilot chat** UI (calls `/copilot`, renders answer **with FIR citations**). ✅(mock)
- [ ] **G5** **Review queue** (extend `client/review.html`), **SHAP "why" panel**, **fairness/bias panel**, dashboards. ✅(mock)
- [ ] **G6** Wired to live endpoints via API Gateway; `catalyst deploy`; loads on the Dev hosting URL. ⧖

## Prerequisites
Node 18+. `npm create vite@latest` (React+TS) into `client/` (preserve the existing `review.html`/config). Mock fixtures for each endpoint.

## Steps
1. **Scaffold** React+Vite+TS+Tailwind in `client/`; set up `src/api/` typed client + **mock fixtures** (network, hotspots, copilot, risk).
2. **Auth:** Catalyst Web SDK login; gate routes by role.
3. **Map view** (`src/map/`): MapLibre base + deck.gl layers (choropleth, hotspot pulse); legend; time-shift selector.
4. **Network view** (`src/graph/`): react-force-graph; size by centrality, color by community; side panel for node details.
5. **Copilot** (`src/copilot/`): chat with streamed answer + **clickable FIR citations**.
6. **Panels:** review queue, SHAP "why", fairness, summary dashboards (Recharts).
7. **Integrate:** replace mocks with live API Gateway calls as engines land; `catalyst deploy`.

## Gotchas
Dev only ($0). Develop against **mocks** so you're not blocked on P5/6/7. MapLibre needs no API key (don't use Google Maps). Keep the demo flow (ingest → map → network reveal → why → copilot → brief) clickable end-to-end.

## Out of scope
The engines themselves (P5/6/7) — this phase visualizes their outputs.

## When done
`feat/phase-8-frontend` → PR → `main`; write `docs/PHASE_8_RUNBOOK.md`.
