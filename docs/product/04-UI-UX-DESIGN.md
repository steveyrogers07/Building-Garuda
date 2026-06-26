# GARUDA — UI/UX Design Document

**Companion to:** [03-App-Flow](03-APP-FLOW.md) · implemented base: `client/assets/app.css`
(design system), `client/index.html` (shell). Design intelligence sourced from the **ui-ux-pro-max**
skill (`--design-system` for "government crime-intelligence command centre").

---

## 1. Design philosophy

A **security-operations console**, not a marketing dashboard. Calm, dark, data-dense, authoritative;
every pixel earns its place. Three rules: (1) **information density without clutter** — group with
whitespace and rule lines, not boxes-in-boxes; (2) **the data is the hero** — restrained chrome,
vivid only where data demands attention (alerts, the kingpin, hotspots); (3) **legible under
pressure** — tabular figures, high contrast, predictable layout an officer can scan in seconds.

## 2. Design system (tokens)

| Token group | Values |
|---|---|
| **Surfaces (dark)** | bg `#080d18` · surface `#0e1626` · surface-2 `#131d31` · elevated `#18233c` |
| **Lines** | border `#22304e` · soft `#1a2740` · grid `rgba(120,150,200,.05)` |
| **Text** | primary `#e8eef9` · muted `#94a3bd` · faint `#5d6c89` (all AA on bg) |
| **Brand** | primary `#3b82f6` / deep `#1e40af` · **accent (amber)** `#f9a825` / `#d97706` |
| **Status** | ok `#22c55e` · warn `#f59e0b` · danger `#ef4444` · info `#38bdf8` (+ soft fills) |
| **Type** | **Fira Code** (headings, labels, data, numerals — tabular) · **Fira Sans** (body) |
| **Scale** | 9.5/11/12.5/14/16/21/30 px · weights 400/500/600/700 |
| **Radius** | sm 7 · md 10 · lg 14 |
| **Spacing** | 4/8 rhythm; section tiers 16/24/32 |
| **Elevation** | one shadow scale (`0 2px 8px` + `0 12px 32px` @ 28-35% black) + a primary "glow" for focus |
| **Motion** | 150–300ms; ease-out enter / ease-in exit; pulse for hotspots; reduced-motion disables all |

Light theme is a defined variant (the source palette is light-first); dark is the default operations
mode. Both must be contrast-tested independently.

## 3. Layout system

- **App shell:** fixed 248px sidebar + main (sticky 60px topbar + scrolling content, max-width 1500).
- **Grids:** 12-col fluid; KPI auto-fit `minmax(190px,1fr)`; two-pane (list + detail) for investigate
  views; full-bleed stage for graph/map.
- **Breakpoints:** 1440 / 1280 / 1024 / 768 / 375. ≥1024 sidebar persistent; <1024 off-canvas with a
  hamburger (field/mobile). No horizontal scroll.

## 4. Component catalog

KPI card · panel/card (header+body) · status badge & dot · button (primary/ghost) · filter chip ·
data table (sortable, hover-row, tabular nums) · list row (lead icon + title + meta + end) · bar /
sparkline · **graph stage** (canvas + legend + detail panel + tooltip) · **map stage** (SVG bubbles +
legend + drill panel) · **chat** (message, citation card, guardrail strip, composer) · timeline ·
empty/skeleton/error states · command palette · toast. Icons: **one stroke SVG set** (Lucide-style
sprite), 24px tokenized, never emoji.

## 5. Screen inventory (22)

> Each: **purpose · key components · layout · primary action.** ★ = built (Phase 8).

1. **Login** — auth + role. Centered card on the grid field; Catalyst Web SDK; jurisdiction shown after.
2. **Command Dashboard (Exec)** ★ — situational read. KPIs · state map · emerging-trends list · new-rings list · model/fairness banner. *Action:* drill any tile.
3. **Command Dashboard (District/Station)** — local read. District KPIs · local hotspots · repeat-offenders · BOLO hits · open series.
4. **Cases (FIR list)** — triage. Filter bar (district/crime/section/date/status) · sortable table · saved views. *Action:* open case.
5. **Case File** — one FIR, fully. Header (CrimeNo/status/gravity) · parties (complainant/victim/accused) · sections (Act+Section) · MO + BriefFacts · mini-map · **timeline** · **linked-cases panel (with reason)** · evidence/chargesheet. *Action:* open linked / dossier / "ask copilot."
6. **Entities list** — people/vehicles/phones. Type tabs · search · table (appearances, districts, last seen). *Action:* open dossier.
7. **Entity Dossier (360°)** — the POI view. Identity + aliases · appearances-by-role table · **associates mini-graph** · districts/timeline · linked vehicles/phones · **risk indicator + drivers** · actions (watchlist, PDF). PII masked by role.
8. **Network Explorer** ★ — the hero. Ring/actor selector · **force-graph stage** (size=strength, color=community, kingpin ring) · node detail panel · "likely-hidden ties" · path-between · export. *Action:* drill node → incidents.
9. **Crime Series & Patterns** — series board. Series cards (crime, district, window, count, method) · open → map+timeline · "similar cases" finder. *Action:* confirm/promote series.
10. **Hotspot Map** ★ — geospatial. Layer toggles (choropleth/heatmap/hotspots/beats/risk-vs-actual) · **time slider** · district drill panel · legend. *Action:* district → drill / tasking.
11. **Risk Forecast** — predictive. Risk table/surface · **SHAP "why" panel** · **fairness panel** (ward ratios, flags) · patrol-tasking suggestion · model-version + backtest note. *Action:* approve tasking (human-in-loop).
12. **Copilot** ★ — NL intelligence. Thread (cited answers, guardrail strip) · example chips · composer · saved queries · NL→chart. *Action:* ask; click citation → case.
13. **Alerts Center** ★ — operations. Ranked alert feed (severity, baseline vs observed, z) · workflow controls (ack/assign/resolve) · rules editor. *Action:* triage.
14. **Watchlists / BOLO** — lookout. Lists by type · add (legal basis + expiry) · **hit log** with case context. *Action:* add / act on hit.
15. **Universal Search** — find anything. Big search + facets (entity/case/vehicle/phone/place) · semantic + structured results, grouped. *Action:* open result.
16. **Review Queue** ★(P3) — ingestion HIL. Extraction cards · **per-field confidence** (low highlighted) · correct + approve. *Action:* promote to canonical.
17. **Briefs & Reports** — output. Scheduled briefs list · on-demand builder (scope/time) · PDF preview · recipients. *Action:* generate/send.
18. **Audit Log** — governance. Filterable table (actor/role/action/resource/time) · export. Read-only.
19. **Model Cards & Fairness** — trust. Per-model card (purpose, data, metrics, limits, last-trained) · fairness trends. Read-only for ethics.
20. **Data Quality** — stewardship. Completeness/confidence by field/district · extraction error rates · adapter status.
21. **Admin** — config. Users/roles/scopes · reference-data CRUD · model management · system health.
22. **Settings** — per-user. Theme, language (EN/Kannada), notification channels, density.

## 6. Data-visualization guidelines

- **Network:** node size = weighted degree (involvement), color = community, amber ring = kingpin,
  edge width = co-occurrence; hover highlights neighborhood; never rely on color alone (also size/label).
- **Map:** proportional symbols at real centroids (gazetteer polygons are coarse); intensity scale
  blue→amber→red; top hotspots pulse; time slider for spatio-temporal; **MapLibre** base on deploy.
- **Charts (Recharts/SVG):** trend→line, comparison→bar, distribution→horizontal bar; tabular nums;
  legends + tooltips; no pie >5 cats; gridlines low-contrast; **table alternative** for a11y.
- **Risk/fairness:** bars with ratio labels; over-threshold bars use danger; show the baseline.
- **Citations:** always a card with `fir_no`, crime, district, date, snippet — clickable to the case.

## 7. Interaction & motion

Drill-down everywhere; filter chips with smooth count updates; selection highlights linked data
across panels; ⌘K command palette; "ask-about-this" affordances. Motion conveys cause→effect only:
stagger lists 30–50ms, fade views, pulse live hotspots, scale-press on cards; exits faster than
enters; **all animation off under `prefers-reduced-motion`**.

## 8. Accessibility (WCAG 2.1 AA)

Contrast ≥ 4.5:1 (verified on dark); visible focus rings; full keyboard nav incl. graph/map (arrow to
traverse nodes, table fallback); aria-labels on icon buttons; `aria-live` for alerts/toasts; logical
heading order; color never the sole signal; reduced-motion + dynamic type honored; touch targets ≥44px.

## 9. Localization

EN + **Kannada** (UI strings via i18n, OCR + NER + copilot bilingual); Fira fonts cover Latin, a
Kannada-capable face (e.g. Noto Sans Kannada) loads for `kn`; locale-aware dates/numbers; never
truncate Kannada (it grows) — wrap + tooltip.

## 10. States (every screen)

Loading → skeleton/shimmer with expected time · Empty → guidance + example/action · Error → cause +
retry · Permission → "request access" · Stale → "as of <time>" + recompute. No silent blanks.

## 11. Field / mobile

Responsive console for officers in the field: bottom nav (≤5), card-first layout, larger targets,
offline-tolerant reads (cached dossier/BOLO), one-handed copilot. Sensitive PII gated behind re-auth
on small screens.
