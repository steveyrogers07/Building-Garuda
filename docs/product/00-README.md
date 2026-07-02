# GARUDA — Product & Engineering Blueprint

> AI Crime-Intelligence Platform for the **Karnataka State Crime Records Bureau (SCRB)** ·
> Datathon 2026 · built on **Zoho Catalyst**.
>
> This folder is the **source-of-truth specification** for what GARUDA *is* and where it is
> going — written so the product can be deepened iteration over iteration into a genuinely
> deployable, operationally-useful system, not a demo dashboard.

## Why GARUDA wins (the thesis)

Most teams will build a **dashboard over FIR statistics** — charts of counts by district and
crime type. That is a *report*, not *intelligence*. GARUDA is built on six differentiators
that map directly to what a State Crime Records Bureau actually needs:

| # | Differentiator | What it means | Most teams |
|---|---|---|---|
| 1 | **Records → Intelligence** | A full pipeline: ingest → resolve entities → build networks → forecast → answer in natural language. | Stop at counts/charts |
| 2 | **The network reveal** | Siloed FIRs across districts collapse into one visible gang — kingpin, crew, the reused burner phone/number-plate crossing jurisdictions. | No cross-FIR linkage |
| 3 | **Responsible AI by design** | SHAP explanations, fairness/bias audits, mandatory citations, guardrails ("never asserts guilt"), audit log, RBAC, PII masking. | Black-box outputs |
| 4 | **Real-data-ready** | A canonical schema + adapter that maps to the *actual* KSP FIR schema (`CaseMaster`…), built synthetic-first so the real extract slots in with no engine change. | Hard-coded to sample data |
| 5 | **End-to-end & deployed** | OCR ingestion → review → analytics → console, all on Catalyst at **$0 dev**. | Notebook-only |
| 6 | **Human-in-the-loop** | Predicts *places & times, never people*; review queues; analyst confirms before canon. | Automated "predictive policing" with no guardrails |

The product is opinionated about one thing above all: in a justice context, an AI system must
**surface and explain, never accuse**. That posture is a feature, and it is wired through every
layer.

## Document map

| Doc | Purpose | Read if you are… |
|---|---|---|
| [01 — PRD](01-PRD.md) | Product requirements: vision, personas, the full feature set (17 modules), NFRs, ethics, roadmap. | deciding *what* to build |
| [02 — TRD](02-TRD.md) | Technical requirements: architecture, engines, APIs, security, ML specs, deployment. | deciding *how* to build |
| [03 — App Flow](03-APP-FLOW.md) | Information architecture + 14 end-to-end user flows with states. | designing journeys |
| [04 — UI/UX Design](04-UI-UX-DESIGN.md) | Design system + 22-screen inventory + interaction/data-viz/a11y specs. | designing screens |
| [05 — Backend Schema](05-BACKEND-SCHEMA.md) | Canonical + derived data model, source mapping, storage strategy, data dictionary. | modeling data |
| [06 — Implementation Plan](06-IMPLEMENTATION-PLAN.md) | What's built (P1–8), gap analysis, prioritized backlog, the next iterations. | planning work |
| [07 — Intelligence Blueprint](07-INTELLIGENCE-BLUEPRINT.md) | The master capability catalogue (~60 features, A–K) to make it police-grade intelligent + Catalyst-native; triages the "17 enterprise ideas"; prioritized hackathon tiers + the 5 "wow" moments. | deciding what makes it *win* |

## Current state vs the vision

**Built and verified (Phases 1–8, all gate-tested in this repo):** Catalyst scaffold · canonical
data layer + 50k synthetic generator · FIR OCR→extract→review ingestion · entity resolution + MO
fingerprinting · **co-offender network / crime-series / anomaly** engines · **explainable risk
forecasting** (LightGBM + SHAP + fairness) · **hybrid-RAG copilot** (citations + guardrails) ·
the **intelligence console** SPA.

**The vision (this blueprint):** turn those engines into a complete operational product — case
workbench, 360° entity dossiers, universal search, watchlists/BOLO, real-time alerting,
auto-generated intelligence briefs, governance/audit surfaces, and role-tailored command
dashboards — so a real analyst can run an investigation end-to-end, defensibly.

> **How to use this:** each iteration, pull the highest-value item from
> [06 — Implementation Plan](06-IMPLEMENTATION-PLAN.md), implement it against the PRD acceptance
> criteria + the schema, and update the relevant doc. Keep the thesis above as the tie-breaker for
> every product decision.
