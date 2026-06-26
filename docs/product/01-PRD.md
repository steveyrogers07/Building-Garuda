# GARUDA — Product Requirements Document (PRD)

**Status:** Living · **Owner:** steveyrogers07 · **Context:** Karnataka SCRB · Datathon 2026

---

## 1. Vision & mission

**Vision.** Every FIR registered in Karnataka becomes part of one connected intelligence
fabric — so that an officer in Kolar instantly sees that the chain-snatching in front of them
is the ninth hit of a gang already active in Bengaluru Urban, Ramanagara and Tumakuru.

**Mission.** Give the SCRB an AI layer that turns 10⁵+ siloed records into **explainable,
citable, bias-checked intelligence** — networks, patterns, forecasts and answers — while
upholding due process: *surface and explain, never accuse.*

## 2. Problem statement

Karnataka registers hundreds of thousands of FIRs a year across 31 districts and ~1,000
stations. Today:

- **FIRs are silos.** A case is investigated in the station that registered it. The same
  offender, vehicle or phone recurring across districts is invisible — there is no entity
  resolution and no cross-jurisdiction link analysis.
- **Analysis is manual and reactive.** Crime trends, series and hotspots are discovered after
  the fact, in spreadsheets, by a handful of analysts.
- **Unstructured narrative is wasted.** The richest signal — `BriefFacts` (vehicle descriptions,
  phone numbers, MO) — is free text no system mines.
- **"Predictive policing" is mistrusted** — and rightly, when it is an unexplained black box that
  profiles people. Any system a bureau adopts must be transparent, fair, and human-supervised.

## 3. Goals & success metrics

| Goal | Metric | Target |
|---|---|---|
| Reveal organized crime | Cross-district rings recovered vs ground truth | ≥ planted gang as #1 ring (✅) |
| Resolve entities | Person-resolution precision / recall | ≥ 0.94 / 0.90 (✅ 0.946 / 0.896) |
| Forecast hotspots usefully | PAI vs naive baseline at 10% coverage | beat baseline every fold (✅ 4.08 vs 3.56) |
| Answer trustably | Copilot citation accuracy | ≥ 0.90 (✅ 1.00) |
| Earn trust | % of AI outputs with explanation + citation + audit entry | 100% |
| Operational adoption | Time from FIR → linked-network insight | < 1 min |
| Fairness | Wards over-predicted > 1.3× surfaced for review | 100% surfaced (✅) |

## 4. Personas

| Persona | Role | Goals | Pain today |
|---|---|---|---|
| **ADGP / Director, SCRB** ("Exec") | State oversight | Situational awareness; where to focus; defensible AI | No real-time state view; trust in AI |
| **SP / District head** | District command | District hotspots, gangs, resourcing | Cross-station blindness |
| **SHO / Station officer** | Station ops | Local load, repeat offenders, BOLO hits | Manual registers |
| **Crime Analyst** ("Analyst") | Pattern analysis | Networks, series, forecasts, briefs | Spreadsheets, no tooling |
| **Investigating Officer (IO)** | Case work | Link this case to others; offender dossier | One FIR at a time |
| **Data Steward / Admin** | Data + system | Quality, reference data, users/roles | n/a (new) |
| **Oversight / Ethics officer** | Governance | Audit, fairness, lawful use, PII | No transparency |

## 5. Product principles

1. **Intelligence, not records** — every screen answers "so what / what next," not just "how many."
2. **Surface, never accuse** — outputs are leads with citations; the system never asserts guilt.
3. **Explainable or it doesn't ship** — every score carries its drivers; every answer its sources.
4. **Places & times, not people** — forecasting targets geography/time, with a fairness audit.
5. **Human-in-the-loop** — AI proposes; an officer confirms before anything becomes canonical.
6. **Real-data-ready** — build on the canonical schema; the real KSP extract swaps in via the adapter.
7. **Governed by default** — RBAC, PII masking, and an immutable audit trail are not optional.

## 6. Feature set — epics

Priority: **M**ust / **S**hould / **C**ould / **W**on't-now (MoSCoW). Phase: build sequence.
Modules E1–E8 have engine foundations built (P1–8); E9–E17 are the depth this blueprint adds.

### E1 · Command Dashboard *(M · built P8, deepen)*
Role-tailored landing: situational KPIs, what-needs-attention, active rings/alerts, trend deltas.
- *Exec:* state map, top emerging trends, model-health & fairness banner.
- *District/Station:* local load, repeat offenders, BOLO hits, open series.
- **Stories:** "As an SP, I see my district's emerging spikes and active gangs the moment I log in."
- **AC:** role-specific layout; every KPI links to its drill-down; data freshness shown.

### E2 · Case Intelligence (FIR file) *(M · partial)*
Rich case view per FIR: parties (complainant/victim/accused), sections (Act+Section), MO, geo,
timeline (incident→report→arrest→chargesheet→court), **linked cases**, evidence, status.
- **Stories:** "As an IO, I open a FIR and immediately see every other case it links to and why."
- **AC:** linked-case panel with link reason (shared entity / MO cluster / series); status timeline.

### E3 · Entity Resolution & 360° Dossier *(M · engine built, surface new)*
Canonical person/vehicle/phone profile aggregating **all** appearances across FIRs and roles,
with aliases, associates (co-offender graph), criminal history, recidivism, and a transparent
**risk indicator** (with drivers). POI dossiers, printable.
- **Stories:** "As an analyst, I pull a dossier on a plate and see every incident, associate and district it touches."
- **AC:** one canonical id → all roles/aliases; associates from the network engine; every claim cites a FIR; PII masked by role.

### E4 · Network & Link Analysis (the hero) *(M · built P5, deepen)*
Interactive co-offender graph: centrality (kingpin), Louvain communities, **cross-district rings**,
shared phone/vehicle links, **link prediction** (hidden associates), temporal evolution, expand/
collapse, path-between-two-entities, export.
- **AC:** ego + ring views; node→incidents drill; "show likely-hidden ties"; recovers the planted gang.

### E5 · Crime Pattern & Series *(M · built P5, deepen)*
MO clustering, **crime series** (space-time near-repeat), serial-offender tracking, similar-case
finder ("find cases like this one"), MO signatures, series→case promotion.
- **AC:** series board; "similar cases" on any FIR; recovers the planted MYS burglary series.

### E6 · Geospatial Intelligence *(M · built P8, deepen)*
Hotspot map: choropleth + kernel-density heatmap + pulsing hotspots, **beat/jurisdiction overlays**,
near-repeat victimization, spatio-temporal playback (time slider), crime-corridor detection,
patrol-coverage overlay. MapLibre (no API key) on deploy.
- **AC:** layer toggles; time slider; click district→drill; risk + actual overlays.

### E7 · Predictive Risk & Patrol (ethical) *(M · built P6, deepen)*
Walk-forward risk forecast per area×time×crime-type; **SHAP "why"**; **fairness audit**;
patrol-tasking suggestions (top-N cells to cover) with PAI/PEI; backtest transparency; model card.
- **AC:** risk surface + explanation + fairness panel; "predicts places not people" stated in UI; human approves tasking.

### E8 · Anomaly & Early Warning *(M · built P5, deepen)*
Emerging-trend detection (robust z-score / STL), new-MO emergence, real-time signals → alerts
with severity, baseline, and drill-to-incidents.
- **AC:** ranked alert feed; each alert explains baseline vs observed; one-click to the incidents.

### E9 · Intelligence Copilot *(M · built P7, deepen)*
NL Q&A with **mandatory citations** + guardrails (no guilt, refuse out-of-scope), hybrid
structured+semantic retrieval, **NL→chart**, conversational follow-ups, saved queries, Kannada.
- **AC:** every answer cites FIRs; guilt/out-of-scope refused; "show as chart" works; audit logged.

### E10 · Alerting & Notifications *(S · new)*
Configurable alerts (spike, BOLO match, series growth), channels (in-app, email, push), severity &
escalation, **alert workflow** (acknowledge → assign → resolve), digest scheduling.
- **AC:** rules engine; alert lifecycle states; recipient routing by role/jurisdiction.

### E11 · Watchlists & BOLO *(S · new)*
Be-on-lookout lists for persons/vehicles/phones; **auto-match incoming FIRs** against watchlists;
hit alerts with context; legal-basis field + expiry; audit of who added/why.
- **AC:** add to watchlist from any entity; new-FIR match fires an alert; entries expire; fully audited.

### E12 · Universal Search *(S · new)*
One search across FIRs, entities, vehicles, phones, places — **full-text + structured filters +
semantic**; faceted; saved searches; command palette (⌘K).
- **AC:** sub-second results; facets (district/crime/date/status); semantic match on narrative; deep-linkable.

### E13 · Reporting & Intelligence Briefs *(S · new, P9 hook)*
Auto-generated **daily/weekly intelligence briefs** (PDF) — top trends, new rings, active series,
forecast, fairness note; custom report builder; court-ready case summary; comparison reports.
- **AC:** scheduled brief → PDF in Stratus → mailed; brief cites sources; exportable.

### E14 · Ingestion & Data Quality *(M · built P3, deepen)*
FIR upload (scan/PDF) → **OCR (eng+Kannada)** → structured extraction with confidence →
**human review queue** → promote to canonical. Bilingual NER for vehicle/phone from `BriefFacts`.
Data-quality dashboard; the **real-data adapter**.
- **AC:** low-confidence flagged for review; nothing canonical without approval; adapter swaps real data.

### E15 · Governance, Audit & Compliance *(M · new — trust layer)*
RBAC (state/district/station scopes), **field-level PII masking by role**, immutable **audit log**
of every privileged read/query, data-retention policy, **model cards + fairness dashboard**, lawful-
use attestations, DPDP-Act alignment.
- **AC:** every access logged; PII masked per role; model card per AI feature; ethics officer view.

### E16 · Admin & Configuration *(S · new)*
Users/roles, reference data (Acts, Sections, CrimeHeads, districts, stations), model management
(versions, retrain, thresholds), integrations, system health.
- **AC:** role assignment; reference-data CRUD with audit; model version pinning.

### E17 · Insights & Performance Analytics *(C · new)*
Crime trends over time, **clearance & conviction rates** (from ChargesheetDetails/CaseStatus),
district comparisons, socioeconomic correlation, resource-vs-load analysis.
- **AC:** trend explorer; clearance dashboard; comparison view.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| **Security** | Catalyst Auth; RBAC by jurisdiction; TLS; secrets in env/secret store; no PII in URLs/logs. |
| **Privacy** | DPDP-Act-aligned; field-level PII masking by role; purpose-bound access; retention limits. |
| **Performance** | Dashboard < 1.5s; cached analytics < 300ms; copilot answer < 3s; graph build cached/batch. |
| **Scalability** | 10⁵–10⁶ incidents; batch recompute nightly; betweenness sampled on huge graphs. |
| **Availability** | Dev now; Prod target 99.5%; idempotent ingestion; retries on transient failures. |
| **Usability** | Any core task ≤ 3 clicks from the dashboard; consistent shell; command palette. |
| **Accessibility** | WCAG 2.1 AA; keyboard-complete; contrast ≥ 4.5:1; reduced-motion; screen-reader labels. |
| **Localization** | English + **Kannada** (UI strings, OCR, NER, copilot); locale-aware dates/numbers. |
| **Observability** | Structured logs, request metrics, **model-drift monitoring**, audit trail. |
| **Cost** | Dev runs at **$0** (local CSV / free engines); QuickML LLM serving opt-in for demo only. |

## 8. Ethics, legal & governance (a first-class requirement)

- **Presumption of innocence.** No screen labels anyone "guilty/criminal." Accused = "as recorded
  in FIR, pending investigation/trial." The copilot refuses guilt-determination queries.
- **Fairness.** Forecasts run a per-ward predicted-vs-actual audit; over-predicted wards are flagged,
  not silently acted on. No protected attributes (caste/religion) used as model features.
- **Transparency.** SHAP drivers on every risk score; citations on every answer; published model cards.
- **Accountability.** Immutable audit log; RBAC; human approval before canonical writes or tasking.
- **Data protection.** PII classified and masked by role; minimal retention; lawful-basis fields on watchlists.

## 9. Out of scope / non-goals

Individual-level "threat scores" used for enforcement; automated action without human approval;
facial recognition; predicting *who* will offend; surveillance integrations; any use of
caste/religion/gender as predictive features.

## 10. Assumptions, dependencies, risks

- **Assumption:** real KSP extract matches the documented schema (`docs/DATASET_REAL_SCHEMA.md`).
- **Dependency:** Catalyst Dev project for the account-gated layer (deploy, ZCQL, QuickML).
- **Risk:** vehicle/phone links depend on `BriefFacts` NER (no structured fields in source) →
  *mitigation:* strong bilingual extractor + review queue. · **Risk:** model trust → *mitigation:*
  explainability + fairness + human-in-loop. · **Risk:** scope creep → *mitigation:* MoSCoW + iterations.

## 11. Release roadmap

- **MVP (done, P1–8):** ingestion → engines → console, synthetic, $0, all gates green.
- **V1 — Operational (next):** Entity Dossier, Case Workbench, Universal Search, Alerting,
  Watchlists, Briefs, Governance surfaces; deploy to Catalyst Dev. *(see Impl. Plan)*
- **V2 — Scale & polish:** real-data swap, Kannada end-to-end, mobile/field view, NL→chart, performance.
- **V3 — Institutional:** integrations, advanced patrol optimization, conviction analytics, multi-tenant.

## 12. North Star

**"Minutes from a single FIR to a defensible, cited, cross-jurisdiction intelligence picture —
that a court and an ethics board would both accept."**
