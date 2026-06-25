# GARUDA — Phase 6 Kickoff (paste into a fresh build chat)

> Fresh build session for **Phase 6** of GARUDA. Read fully, execute step by step, don't jump ahead.

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/Building-Garuda`
- Read: `docs/GARUDA_BLUEPRINT.md` (predictive/§explainability), `docs/PHASE_2_RUNBOOK.md` (data + schema), `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**Dev only, $0**).
- Stack: Node functions · **Python/FastAPI on AppSail** · Data Store (ZCQL) · **Zia AutoML** · LightGBM.

## ✅ Dependency — fully parallel NOW
Depends only on **Phase 2 data** (Incidents + Socioeconomic), which is merged. Can be built immediately, independent of Phases 4/5/7. Use the CSVs / local PoC store (`data/local/`) + `ground_truth.json` (planted anomaly spikes are a sanity check).

## Convention
Pure-Python brain verified locally (no creds/credits) + deferred account-gated section. **Zia AutoML is the Catalyst-native headline; LightGBM is the local mirror for SHAP.** Text business keys. Produce `docs/PHASE_6_RUNBOOK.md`.

## Goal
Backtested, **explainable**, bias-checked **risk forecasting**: per area × time-shift × crime-type risk scores written to `Predictive_Risk`, with SHAP "why" and a fairness audit. **Predict places & times, never individuals.**

## Exit Gate (✅ local · ⧖ live)
- [ ] **G1** `app/engines/forecasting/` builds a feature table (lagged counts per area×time-shift, day-of-week, hour bucket, holiday flag, density/literacy from `Socioeconomic`) from the data. ✅
- [ ] **G2** LightGBM model trained with **walk-forward (temporal) split**; **PAI/PEI** reported and **beats a naive "last-period hotspot" baseline**; PR-AUC for rare classes. ✅
- [ ] **G3** **SHAP** explanations per prediction (`/risk/explain` → top drivers). ✅
- [ ] **G4** **Fairness audit**: predicted-vs-actual rate per ward; flag any ward over-predicted >1.3×. ✅
- [ ] **G5** `Predictive_Risk` populated (grid_id, time_shift, crime_type, risk_probability, model_version, backtest_pai). ⧖
- [ ] **G6** **Zia AutoML** model trained + deployed as the Catalyst-native headline; batch-scored into `Predictive_Risk`. ⧖

## Prerequisites
`pip install lightgbm scikit-learn shap pandas numpy holidays`. Phase 2 outputs present (`python data/generate.py && python data/build_reference.py`).

## Steps
1. **Feature engineering → `app/engines/forecasting/features.py`**: aggregate Incidents to (area_code × time-shift × crime_type); add lagged counts (t-1, t-7, rolling mean), day-of-week, time-of-day bucket, festival/holiday flag, `Socioeconomic` joins (density, literacy, urbanization).
2. **Model → `model.py`**: LightGBM (classification: incident likely / count bucket). **Walk-forward** validation (train past → predict next window; NO random split). Compute **PAI** (top X% area capture) + **PEI**, PR-AUC; compare to baseline.
3. **Explainability → `explain.py`**: SHAP values; `/risk/explain?area=&shift=` returns the top contributing features.
4. **Fairness → `fairness.py`**: predicted vs actual victim-reported rate per ward; disparity report.
5. **Eval → `tests/test_forecasting.py`**: assert PAI/PEI > baseline; report numbers.
6. **Account-gated:** train **Zia AutoML** on the exported feature table (console), deploy, batch-score into `Predictive_Risk` (nightly job in P9).

## Gotchas
Dev only ($0); LightGBM/SHAP run locally (free). **No random splits** (time leakage) — walk-forward only. Use precision/recall + PR-AUC, not accuracy (class imbalance). **Predict places, not people.**

## Out of scope
Network → P5 · copilot → P7 · the map UI → P8 (this phase produces `Predictive_Risk` the map reads).

## When done
`feat/phase-6-predictive` → PR → `main`; write `docs/PHASE_6_RUNBOOK.md`.
