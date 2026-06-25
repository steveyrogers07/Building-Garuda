# GARUDA — Phase 10 Kickoff (paste into a fresh build chat) — TEST · DEPLOY · DEMO

> Fresh build session for **Phase 10** of GARUDA. Read fully, execute step by step. This is the integration + go-live phase — **one owner, near the end.**

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/Building-Garuda`
- Read: `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**follow the Phase 10 go-live runbook there to the letter**), `docs/GARUDA_DATA_READINESS.md` (the swap rehearsal), all `PHASE_*_RUNBOOK.md`.
- Stack: everything; **Pipelines** (CI), **Domain Mappings** (SSL).

## ⧖ Dependency — needs ALL prior phases
Integration phase. Requires Phases 1–9 merged. One person owns it; deploy to Production **late** (a day or two before demo) to conserve credits.

## Convention
This is where credits are finally spent — **claim them now, not earlier** (~60-day expiry). Produce `docs/PHASE_10_RUNBOOK.md`.

## Goal
A **tested, production-deployed, demo-ready** submission with a backup video and a clean report.

## Exit Gate
- [ ] **G1** Test suite: **unit** (per engine), **integration** (ingest→promote pipeline; AppSail endpoints), **E2E** (the full demo flow); **load-test** the demo path.
- [ ] **G2** **Real-data swap rehearsal:** run the `GARUDA_DATA_READINESS.md` runbook on a real-shaped sample → prove the adapter works (column-map only).
- [ ] **G3** Promote Dev → **Production** (console); deploy client + functions + AppSail; **Domain Mappings + SSL** (custom domain).
- [ ] **G4** Data loaded / precomputed results restored in prod; smoke-test prod URLs (**LLM serving still OFF**).
- [ ] **G5** **3.5-min demo recorded + backup video**; slides + report + README finalized (data lineage + ethics note).
- [ ] **G6** Submission checklist green (≥10 Catalyst services used; metrics on a slide; responsible-AI panel; auto-PDF brief; copilot citations).

## Steps
1. **Tests:** consolidate `tests/` (unit/integration/e2e); add load-test of the demo path; fix the red.
2. **Swap rehearsal:** create a `column_map.ksp-style.yaml`, run the adapter on a renamed sample, confirm validation + load (proves dataset-readiness).
3. **Promote (credits start):** set payment method, **claim credits**, set a budget+alert; promote project to Production.
4. **Deploy:** `catalyst deploy`; configure **Domain Mappings + SSL**.
5. **Data:** load/restore precomputed `Predictive_Risk`/`MO_Clusters`/`Crime_Series`/graph; smoke-test (keep **LLM serving OFF** until demo).
6. **Demo:** rehearse the script (ingest → map → **network reveal** → why/SHAP → copilot → brief); **record the backup video**; ~30–60 min pre-demo, spin **up** LLM serving + warm AppSail; spin **down** right after.
7. **Package:** slides, report, README (data lineage + ethics), architecture + runtime diagrams.

## Gotchas
Follow the credits doc's go-live sequence exactly (claim late, LLM serving up only for demo, down after). **Live demos die — the backup video is mandatory.** Promote late to conserve credits.

## When done
`feat/phase-10-deploy` → PR → `main`; write `docs/PHASE_10_RUNBOOK.md`; submit. 🏁
