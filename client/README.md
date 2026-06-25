# client/ — Frontend SPA (Track C · Phase 8)

React + Vite + TypeScript + Tailwind single-page app, deployed to **Catalyst Web Client Hosting**. Talks to the backend (Node functions + AppSail) through the **API Gateway**, and uses the Catalyst Web (JS) SDK for **Authentication** (role-gated: SCRB-admin / district / station).

## Subfolders
- `public/` — static assets.
- `src/components/` — shared UI components.
- `src/pages/` — route-level screens (dashboard, district drill-down, review queue).
- `src/map/` — MapLibre GL + deck.gl layers (choropleth, pulsing hotspots from `Predictive_Risk` + `Geo_Boundaries`).
- `src/graph/` — react-force-graph network view (from the AppSail `/network/{id}` endpoint), with drill-down & community highlighting.
- `src/copilot/` — natural-language copilot chat UI (calls `/copilot`, renders answers **with FIR citations**).
- `src/api/` — typed client for backend endpoints.

## Key screens to build
Map + hotspots · network graph · copilot chat · **review-queue UI** (human-in-the-loop) · SHAP "why" panel · fairness/bias panel · dashboards.

## Dev
`npm create vite@latest` (React+TS) here, build into the Catalyst client dir, `catalyst deploy`. Develop against **mocked endpoints** early (Phases 4–7 produce the real ones).
