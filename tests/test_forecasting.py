"""GARUDA — local Phase-6 forecasting evaluation (no Catalyst).

Builds the risk feature table and checks the Phase-6 exit gates:
  - G1  feature table builds (lagged counts + calendar + socio-economic).
  - G2  LightGBM, walk-forward (temporal) split: PAI/PEI + PR-AUC beat the naive
        "recently-hot" persistence baseline.
  - G3  SHAP drivers return for a prediction (/risk/explain).
  - G4  fairness audit runs per ward (predicted-vs-actual; over-prediction flag).

Run:  python tests/test_forecasting.py
Prereqs: python data/generate.py && python data/build_reference.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))     # AppSail-style imports

from engines import forecasting as fc      # noqa: E402

SYN = REPO / "data" / "synthetic"
REF = REPO / "data" / "reference"


def run():
    inc = pd.read_csv(SYN / "incidents.csv", dtype=str, keep_default_na=False).to_dict("records")
    socio = pd.read_csv(REF / "census_2011.csv", dtype=str, keep_default_na=False).to_dict("records")

    # ---- G1: feature table ----
    t, feats = fc.build_feature_table(inc, socio)
    print(f"feature table: {len(t):,} rows (area x crime x day)  "
          f"features={len(feats)}  positive rate={t['y'].mean():.3%}")
    assert len(t) > 0 and set(feats).issubset(t.columns), "feature table malformed"

    # ---- G2: walk-forward, beat baseline ----
    res = fc.walk_forward(t, feats, n_folds=3, coverage=0.10)
    s = res["summary"]
    print(f"\nwalk-forward ({len(res['folds'])} folds, flag top 10% cells):")
    for f in res["folds"]:
        print(f"  {f['test_start']}..{f['test_end']}  "
              f"PR-AUC {f['pr_auc']} vs base {f['pr_auc_base']}  |  "
              f"PAI {f['model']['pai']} vs base {f['baseline']['pai']}  "
              f"(capture {f['model']['capture']:.0%} vs {f['baseline']['capture']:.0%})")
    print(f"  MEAN: PR-AUC {s['pr_auc']} vs base {s['pr_auc_base']}  |  "
          f"PAI {s['pai']} vs base {s['pai_base']}  |  PEI {s['pei']}  "
          f"(base rate {res['base_rate']:.3%})")
    assert s["pai"] > s["pai_base"], "model PAI does not beat the naive baseline"
    assert s["pr_auc"] > s["pr_auc_base"], "model PR-AUC does not beat the baseline"
    assert s["pr_auc"] > res["base_rate"], "model no better than random (PR-AUC <= base rate)"

    # ---- final model for G3/G4 ----
    model = fc.fit(t, feats)
    cur, last = fc.forecast_next(t, feats, model)
    print(f"\nrisk surface for {str(pd.Timestamp(last).date())}: top cell -> "
          f"{cur.iloc[0]['area_code']} / {cur.iloc[0]['crime_type']} "
          f"(risk {cur.iloc[0]['risk_score']:.3f})")

    # ---- G3: SHAP drivers ----
    top_row = cur.iloc[[0]][feats].to_numpy()
    drivers = fc.shap_drivers(model, top_row, feats, top=6)
    print("top drivers:", ", ".join(f"{d['feature']}({d['direction']})" for d in drivers))
    assert drivers and "shap" in drivers[0], "no SHAP drivers returned"

    # ---- G4: fairness audit ----
    scored = t.sample(min(40000, len(t)), random_state=0).copy()
    scored["score"] = model.predict_proba(scored[feats])[:, 1]
    rep, fsum = fc.fairness_audit(scored, "score")
    print(f"fairness: {fsum['wards']} wards, {fsum['over_predicted']} over-predicted "
          f">1.3x (max ratio {fsum['max_ratio']:.2f})")
    assert fsum["wards"] > 0, "fairness audit produced no wards"

    print("\nPASS")


def test_forecasting():
    run()


if __name__ == "__main__":
    run()
