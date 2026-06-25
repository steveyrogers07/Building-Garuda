# GARUDA — Phase 6 (Predictive & Explainable Risk) Runbook

> Goal: backtested, **explainable**, bias-checked **risk forecasting** — per
> area × day × crime-type risk scores with SHAP "why" and a fairness audit,
> written to `Predictive_Risk`. **Predict places & times, never individuals.**

Same split as P2–P5: the **build-side brain is done & locally verified** (branch
`feat/phase-6-predictive`); the **account-gated** Zia AutoML headline + ZCQL write-back is a
deferred section. Everything local runs at **$0** — LightGBM + TreeSHAP, no credits.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| Feature engineering | [app/engines/forecasting/features.py](../app/engines/forecasting/features.py) | dense area×day×crime grid · leakage-safe lags (t-1,t-7) + rolling means · calendar (dow/month/weekend/holiday) · socio joins |
| Model + backtest | [app/engines/forecasting/model.py](../app/engines/forecasting/model.py) | LightGBM · **walk-forward** temporal CV · PAI/PEI + PR-AUC vs naive baseline |
| Explainability | [app/engines/forecasting/explain.py](../app/engines/forecasting/explain.py) | **TreeSHAP** via LightGBM `pred_contrib` (no `shap` dep) → top drivers |
| Fairness | [app/engines/forecasting/fairness.py](../app/engines/forecasting/fairness.py) | per-ward predicted-vs-actual; flag over-prediction >1.3× |
| Data access | [app/shared/store.py](../app/shared/store.py) | `fetch_socioeconomic` + `write_predictive_risk` (CSV ↔ ZCQL) |
| AppSail endpoints | [app/routers/analytics.py](../app/routers/analytics.py) | `POST /risk/run`, `GET /risk/top`, `/risk/explain`, `/risk/fairness` |
| Local runner | [app/run_phase6.py](../app/run_phase6.py) | backtest → write `predictive_risk.csv`/`fairness.csv` to `GARUDA_HOME` |
| Eval | [tests/test_forecasting.py](../tests/test_forecasting.py) | asserts model beats baseline (PAI + PR-AUC) |

**Verified locally** (`python tests/test_forecasting.py`), 271,312 cells (31 districts ×
16 crime-types × 547 days), positive rate **3.49%**:

- **Walk-forward (3 temporal folds, flag top 10% of cells):**
  - **PAI 4.08** vs naive baseline **3.56** · **PEI 0.41**
  - **PR-AUC 0.158** vs baseline **0.123** (≈4.5× the 3.49% base rate)
  - captures **41%** of crime in the flagged 10% of cells (baseline 36%) — beats baseline on **every** fold.
- **SHAP** (`/risk/explain`): each score decomposed into drivers (e.g. `roll_28`, `population`,
  `crime_code`, `urbanization`, `dow`).
- **Fairness:** 31 wards audited; **4 over-predicted >1.3×** (max 1.61×) — flagged for review.

---

## 1. Exit gates

| Gate | What | Status |
|---|---|---|
| **G1** | feature table (lagged counts + calendar + socio) | ✅ local |
| **G2** | LightGBM, walk-forward split; PAI/PEI + PR-AUC beat naive baseline | ✅ local |
| **G3** | SHAP per prediction (`/risk/explain` → top drivers) | ✅ local |
| **G4** | fairness audit per ward; over-prediction flag | ✅ local |
| **G5** | `Predictive_Risk` populated via ZCQL | ⧖ account-gated |
| **G6** | Zia AutoML model trained + deployed (Catalyst-native headline) | ⧖ account-gated |

---

## 2. Method (and why)

- **Unit:** (district × day × crime-type). District is the finest unit the gazetteer carries;
  swap in ward/grid when finer data arrives — no model change. Target `y` = an incident of
  that type occurs that day (the rare positive class → PR-AUC, not accuracy).
- **No leakage:** every predictor uses only the past — lags shifted ≥1, rolling means
  `shift(1).rolling(...)`. Validation is **walk-forward** (train past → predict the next
  window), **never** a random split.
- **Baseline:** a naive "recently-hot" persistence predictor (28-day trailing rate). The
  gate is that the model **beats** it on PAI and PR-AUC — it does, on every fold.
- **PAI / PEI:** PAI = (crime captured / total) ÷ (cells flagged / total) at 10% coverage;
  PEI = PAI ÷ best-achievable PAI. These are the standard hotspot-policing metrics.
- **SHAP via LightGBM** `pred_contrib` (exact TreeSHAP) — explanations with no extra dep.
- **Fairness:** predicted risk vs actual offense rate per ward; a ward predicted materially
  hotter than reality (>1.3×) is flagged so the model can't quietly over-police an area.

---

## 3. Run it locally ($0, no Catalyst)

```bash
python data/generate.py && python data/build_reference.py   # data + Census socio
python tests/test_forecasting.py     # gate test (beats baseline)
python app/run_phase6.py             # backtest + write artifacts to GARUDA_HOME
```

Outputs land in `GARUDA_HOME` (default `~/OneDrive/Desktop/garuda`):
`predictive_risk.csv`, `fairness.csv`, `phase6_report.json`.

## 4. REST contract (AppSail)

| Method | Route | Returns |
|---|---|---|
| POST | `/risk/run` `{write}` | backtest metrics + write `Predictive_Risk`; top cells |
| GET | `/risk/top?n=20` | current highest-risk area × crime-type cells |
| GET | `/risk/explain?area=BNU&crime_type=Theft` | SHAP drivers for that forecast |
| GET | `/risk/fairness` | per-ward predicted-vs-actual bias report |

`Predictive_Risk` columns: `grid_id, district_code, crime_type, period, risk_score, rank,
top_drivers (JSON), model_version, backtest_pai`. The Phase-8 map reads this.

## 5. Account-gated (G5/G6 — when the project is live)

- `GARUDA_BACKEND=zcql` → `write_predictive_risk` batches `INSERT INTO Predictive_Risk`.
- **Zia AutoML** (G6): export the feature table to Stratus, train/deploy an AutoML model in
  the console as the Catalyst-native headline, batch-score into `Predictive_Risk` from the
  nightly **Job Scheduling** pool (Phase 9). The LightGBM model stays as the local/SHAP mirror.

## 6. Gotchas / notes

- **No random splits** (time leakage) — walk-forward only; all lags/rolls are shift-≥1.
- **Use PR-AUC, not accuracy** — the positive class is ~3.5% (predicting "always quiet"
  scores 96% accuracy and is useless).
- **SHAP without the `shap` package** — LightGBM `booster_.predict(X, pred_contrib=True)` is
  exact TreeSHAP; keeps the deploy light.
- **Fairness is a report, not a hard gate** — it surfaces over-predicted wards (4 here) for a
  human to review, rather than silently "correcting" them.
- Census reference (`data/reference/census_2011.csv`) is the socio source locally; the
  `Socioeconomic` Data Store table is the prod source (`GARUDA_BACKEND=zcql`).

## 7. Next

Phase 7 (Intelligence Copilot / RAG) and Phase 8 (the map UI that renders `Predictive_Risk`).
