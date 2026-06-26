# GARUDA — Implementation Plan

**Companion to:** [01-PRD](01-PRD.md) · `docs/GARUDA_10_PHASE_PLAN.md` (the original build march).
This plan takes GARUDA from the **built MVP (P1–8)** to the **operational product (V1)** in the PRD.

---

## 1. What's built (Phases 1–8 — all gate-tested in this repo)

| Phase | Delivered | Gate |
|---|---|---|
| 1 Foundation | Catalyst scaffold (Functions/Client/AppSail), runbook | ✅ |
| 2 Data layer | canonical schema, 50k synthetic generator, adapter, ground truth | ✅ |
| 3 Ingestion | FIR OCR→extract→confidence→**review queue** | ✅ |
| 4 Resolution | entity resolution (P/R 0.95/0.90) + MO fingerprinting | ✅ |
| 5 Network ★ | co-offender graph, **cross-district rings**, series, anomaly | ✅ gang/series/spikes recovered |
| 6 Predictive | LightGBM walk-forward (PAI 4.08>3.56), **SHAP**, **fairness** | ✅ |
| 7 Copilot | hybrid RAG, **citations**, guardrails (100% citation acc.) | ✅ |
| 8 Frontend | dark SOC **console** SPA (overview/network/map/copilot/alerts) | ✅ live |

**Foundation strengths:** the hard ML is done and explainable; the canonical+adapter design is
real-data-ready; everything runs at $0 locally.

## 2. Gap analysis (MVP → "genuinely useful")

The console today is a strong *demo* but thin on *operational workflow*. The gaps that separate it
from a tool an analyst uses daily:

| Gap | Impact | Closes with |
|---|---|---|
| No **entity dossier** (360° view) | can't investigate a person/vehicle/phone | E3 |
| No **case file / linked cases** | FIRs still feel siloed in the UI | E2 |
| No **universal search** | can't find a specific case/entity fast | E12 |
| Alerts not **actionable** (no workflow) | alerts are read-only | E10 |
| No **watchlists/BOLO** | can't operationalize "look out for X" | E11 |
| No **briefs/reports** | no shareable output | E13 |
| Governance not **surfaced** (audit/RBAC/model cards) | trust story not visible | E15 |
| Not **deployed**; Kannada not end-to-end | demo-only; half the real narratives | P9/P10, V2 |
| Static SPA limits **complex stateful UI** | dossier/workbench need richer state | refactor decision |

## 3. Prioritized backlog (MoSCoW)

**Must (V1):** E3 Dossier · E2 Case file + linked cases · E12 Universal search · E10 Alert workflow ·
E15 Governance surfaces (audit/RBAC/model cards) · deploy to Catalyst Dev (P9/P10 account-gated).
**Should (V1.5):** E11 Watchlists/BOLO · E13 Briefs (Job Scheduling + SmartBrowz + Mail) · E6 map
layers + time slider · E9 NL→chart + saved queries.
**Could (V2):** Kannada end-to-end · mobile/field view · E17 clearance/conviction analytics · patrol
optimization · React/Vite rebuild.
**Won't-now:** individual threat scoring, integrations, multi-tenant.

## 4. Roadmap (iterations)

- **Iteration 9 — Governance & Automation** *(= Phase 9)*: Job Scheduling (nightly recompute, weekly
  brief), anomaly→Signal→Push/Mail, SmartBrowz PDF brief, **audit-log middleware + PII masking + RBAC
  enforcement**, API-Gateway throttling, Cache hot ops. → surfaces E15, lights up E10/E13.
- **Iteration 10 — Deploy & Demo** *(= Phase 10)*: bundle reference data into `app/` (deploy fix),
  test suite (unit/integration/e2e/load), **real-data swap rehearsal**, Dev→Prod + Domain Mappings,
  record demo + backup video, submission package.
- **Iteration 11 — Investigate (V1 depth):** **E3 Dossier**, **E2 Case file + linked cases**,
  **E12 Universal search**. *(highest user value; details below)*
- **Iteration 12 — Operationalize:** **E11 Watchlists/BOLO**, **E13 Briefs builder**, **E10 alert
  rules**, map layers/time-slider.
- **Iteration 13 — Trust & locale (V2):** Kannada end-to-end (OCR/NER/copilot/UI), model cards UI,
  fairness trends, mobile/field view.

## 5. Next iteration in detail (Iteration 11 — the value unlock)

> Goal: an analyst can investigate a **person/vehicle/phone** and a **case** end-to-end, with every
> link explained and cited. Build server-first (engines exist), then surface.

**E3 · Entity Dossier**
- *Backend:* `GET /entity/{canonical_id}` → identity + aliases (resolution), appearances-by-role
  (Edges⋈Incidents), associates (network ego), districts/timeline, linked vehicles/phones,
  risk indicator + drivers. New `Entity_Canonical`/`Entity_Alias` (Schema §5). PII masking by role.
- *Frontend:* Dossier screen (#7); "open dossier" from any entity/node/citation; PDF export.
- *AC:* one canonical id → all roles/aliases; associates from the graph; every claim cites a FIR;
  masked per role. *Tests:* `tests/test_dossier.py` (kingpin dossier shows 10 incidents, 4 districts,
  4 associates, shared phone+vehicle).

**E2 · Case file + linked cases**
- *Backend:* `GET /case/{incident_id}` → full FIR + parties + sections + MO + geo + timeline +
  **linked cases** (`Case_Link`: shared entity / mo_cluster / series / near-repeat, with reason+score).
- *Frontend:* Case File screen (#5) with linked-cases panel.
- *AC:* every link shows its reason; status timeline; "ask copilot about this case."

**E12 · Universal search**
- *Backend:* `GET /search?q=&type=&filters` → fuse full-text (Incidents/Entities) + structured filters
  + semantic (reuse copilot TF-IDF/embeddings); facets; ⌘K.
- *Frontend:* Search screen (#15) + command palette.
- *AC:* sub-second; facets; semantic match on narrative; deep-linkable.

**Work breakdown (Iteration 11):** store helpers (dossier/case/search reads) → 3 engines/aggregators
→ 3 endpoints → 3 screens + command palette → tests → runbook. ~ the size of one prior phase.

## 6. Technical debt & refactors

- **Deploy:** bundle `data/reference` + `data/gazetteer` into `app/` (or load from Data Store/Stratus)
  — else `refs.py` `FileNotFoundError` in prod. *(blocker for Iteration 10)*
- **Fold legacy `fix/phase-3-hardening` fixes** (confidence-gate `crime_type`, phone regex) into the
  new repo's phase-3 lineage. *(known, from old repo)*
- **Auth/RBAC:** the console uses an auth stub; wire Catalyst Web SDK + jurisdiction scoping (Iter 9).
- **SPA scale:** static SPA is right for the demo; when dossier/workbench state grows, evaluate a
  React/Vite rebuild (the API + design tokens port directly). Decision gate at Iteration 11.
- **Vectors:** copilot TF-IDF is fine at 10⁴; move embeddings to NoSQL/FAISS for 10⁶ (V2).
- **Map:** swap the SVG symbol map for **MapLibre** + real polygons on deploy.

## 7. Testing & QA strategy

| Level | Coverage | Tooling |
|---|---|---|
| Unit | each engine vs ground truth (`tests/test_{network,forecasting,copilot,resolution,mo}.py`) ✅ | pytest |
| Integration | ingestion→canonical→engines pipeline | pytest + fixtures |
| E2E | demo flow (ingest→map→network→why→copilot→brief) clickable | preview/Playwright on deploy |
| Load | demo path + dashboard under concurrency | k6/locust |
| **Fairness** | per-ward disparity gate in CI | the fairness audit |
| **Security** | RBAC scope tests, PII-masking tests, ZCQL injection tests | pytest |
| Real-data | adapter rehearsal on a real-shaped sample | the readiness runbook |

**Quality gates (CI):** all engine tests green · fairness audit runs · no PII in logs · adapter
validates. Definition of done: feature meets its PRD acceptance criteria + has a test + a runbook note.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `BriefFacts` NER weak on real/ Kannada data → network degrades | strong bilingual extractor + review queue; dossier/network gracefully handle missing links |
| AI trust / adoption | explainability + fairness + citations + human-in-loop, surfaced in UI (E15) |
| Scope creep across 17 modules | MoSCoW + iteration boundaries; ship vertical slices |
| Deploy reference-data bug | fix in Iteration 10 before Prod |
| Solo throughput | per-iteration vertical slices; reuse engines (the hard part is done) |

## 9. Datathon submission criteria (definition of "winning")

A judge should see, in one demo: **(1)** a scanned FIR become a structured record (ingestion HIL);
**(2)** siloed FIRs collapse into a **cross-district gang** with a named kingpin and a reused
burner phone (the reveal); **(3)** an **explained, fair** risk forecast; **(4)** a **cited,
guard-railed** natural-language answer; **(5)** the **governance** story (audit, RBAC, PII, model
cards) — all **deployed** and **real-data-ready**. That combination — *intelligence + responsibility
+ deployability* — is the moat. This blueprint is the path to make every one of those a deep,
operational feature rather than a demo tile.
