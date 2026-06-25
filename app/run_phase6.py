"""GARUDA — Phase 6 local runner (no Catalyst account needed).

Builds the risk feature table, backtests the LightGBM forecaster walk-forward,
writes the current risk surface + fairness audit to local storage, and prints the
summary:

    predictive_risk.csv   fairness.csv   phase6_report.json

Local storage defaults to  ~/OneDrive/Desktop/garuda  (override with GARUDA_HOME).
The engine here is exactly what deploys to AppSail; only the storage is local.

    python app/run_phase6.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

if "GARUDA_HOME" not in os.environ:
    os.environ["GARUDA_HOME"] = str(Path.home() / "OneDrive" / "Desktop" / "garuda")
HOME = Path(os.environ["GARUDA_HOME"])
HOME.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO / "app"))

from engines import forecasting as fc          # noqa: E402
from shared import store                         # noqa: E402


def main():
    print("GARUDA Phase 6 -> local storage:", HOME)
    inc = store.fetch_incidents_p5()
    socio = store.fetch_socioeconomic()
    t, feats = fc.build_feature_table(inc, socio)
    print("feature table: %d rows (area x crime x day), %d features, positive %.2f%%"
          % (len(t), len(feats), 100 * t["y"].mean()))

    # ---- walk-forward backtest ----
    wf = fc.walk_forward(t, feats, n_folds=3)
    s = wf["summary"]
    print("\nbacktest (walk-forward, flag top 10% cells):")
    print("  PAI    %.2f  vs baseline %.2f" % (s["pai"], s["pai_base"]))
    print("  PEI    %.2f" % s["pei"])
    print("  PR-AUC %.3f vs baseline %.3f  (base rate %.2f%%)"
          % (s["pr_auc"], s["pr_auc_base"], 100 * wf["base_rate"]))
    print("  capture %.0f%% vs baseline %.0f%% of crime in the flagged 10%%"
          % (100 * s["capture"], 100 * s["capture_base"]))

    # ---- final model + current risk surface ----
    model = fc.fit(t, feats)
    cur, last = fc.forecast_next(t, feats, model)
    period = str(__import__("pandas").Timestamp(last).date())
    print("\ntop forecast risk for %s:" % period)
    for _, r in cur.head(5).iterrows():
        print("    %-4s %-20s risk %.3f" % (r["area_code"], r["crime_type"], r["risk_score"]))

    # ---- explain the #1 cell ----
    top = cur.iloc[[0]]
    drivers = fc.shap_drivers(model, top[feats].to_numpy(dtype=float), feats, top=6)
    print("  why #1: " + ", ".join("%s %s" % (d["feature"], d["direction"]) for d in drivers))

    # ---- fairness audit ----
    samp = t.sample(min(40000, len(t)), random_state=0).copy()
    samp["score"] = model.predict_proba(samp[feats])[:, 1]
    fair_df, fair_sum = fc.fairness_audit(samp, "score")
    print("\nfairness: %d wards, %d over-predicted >1.3x (max ratio %.2f)"
          % (fair_sum["wards"], fair_sum["over_predicted"], fair_sum["max_ratio"]))

    # ---- write artifacts ----
    booster = getattr(model, "booster_", model)
    contrib = booster.predict(cur[feats].to_numpy(dtype=float), pred_contrib=True)
    rows = []
    for i, (_, r) in enumerate(cur.reset_index(drop=True).iterrows()):
        vals = contrib[i][:-1]
        drv = [feats[j] for j in (abs(vals)).argsort()[::-1][:3]]
        rows.append({"grid_id": r["area_code"], "district_code": r["area_code"],
                     "crime_type": r["crime_type"], "period": period,
                     "risk_score": round(float(r["risk_score"]), 4), "rank": int(r["rank"]),
                     "top_drivers": json.dumps(drv), "model_version": fc.MODEL_VERSION,
                     "backtest_pai": s["pai"]})
    store.write_predictive_risk(rows)
    store._write_out_csv("fairness.csv", fair_df.to_dict("records"),
                         list(fair_df.columns))
    (HOME / "phase6_report.json").write_text(json.dumps(
        {"period": period, "metrics": s, "base_rate": wf["base_rate"],
         "model_version": fc.MODEL_VERSION, "fairness": fair_sum,
         "top_risk": rows[:10]}, indent=2), encoding="utf-8")

    print("\nwrote to", HOME)
    for name in ("predictive_risk.csv", "fairness.csv", "phase6_report.json"):
        print("   ", name)
    print("done.")


if __name__ == "__main__":
    main()
