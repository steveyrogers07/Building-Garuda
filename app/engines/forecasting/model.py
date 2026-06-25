"""GARUDA risk-forecasting model (Phase 6): LightGBM + walk-forward + PAI/PEI.

Trains a gradient-boosted classifier to predict whether each (area x day x
crime_type) cell will see an incident, validated with an **expanding walk-forward
(temporal) split** — never a random split, which would leak the future. Reports
PR-AUC (the positive class is rare) plus the hotspot-policing metrics PAI and PEI,
and compares against a naive "recently-hot" persistence baseline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import average_precision_score

MODEL_VERSION = "lgbm-p6-v1"
BASELINE_COL = "roll_28"          # naive "recently-hot" persistence predictor

_PARAMS = dict(objective="binary", n_estimators=300, learning_rate=0.05,
               num_leaves=31, min_child_samples=50, subsample=0.8,
               colsample_bytree=0.8, n_jobs=-1, verbose=-1)


def fit(train, features, params=None):
    m = lgb.LGBMClassifier(**{**_PARAMS, **(params or {})})
    m.fit(train[features], train["y"])
    return m


def _score(m, df, features):
    return m.predict_proba(df[features])[:, 1]


def pai_pei(df, score_col, coverage=0.10):
    """Hotspot capture if we flag the top `coverage` fraction of cells by score.
    PAI = (crime captured / total) / (cells flagged / total). PEI = PAI / PAI_best."""
    d = df.sort_values(score_col, ascending=False)
    total, ncells = d["count"].sum(), len(d)
    flagged = max(1, int(round(coverage * ncells)))
    if total <= 0:
        return {"pai": 0.0, "pei": 0.0, "capture": 0.0, "coverage": coverage}
    captured = d["count"].iloc[:flagged].sum()
    best = df.sort_values("count", ascending=False)["count"].iloc[:flagged].sum()
    pai = (captured / total) / (flagged / ncells)
    pai_best = (best / total) / (flagged / ncells)
    return {"pai": round(pai, 3), "pei": round(pai / pai_best, 3) if pai_best else 0.0,
            "capture": round(captured / total, 3), "coverage": coverage}


def walk_forward(t, features, n_folds=3, coverage=0.10):
    """Expanding-window temporal CV over the tail of the series."""
    days = np.sort(t["date"].unique())
    n = len(days)
    # test windows tile the last 45% of the timeline into n_folds slices
    edges = [int(n * f) for f in np.linspace(0.55, 1.0, n_folds + 1)]
    folds = []
    for k in range(n_folds):
        ts, te = days[edges[k]], days[min(edges[k + 1], n - 1)]
        train = t[t["date"] < ts]
        test = t[(t["date"] >= ts) & (t["date"] <= te)].copy()
        if test.empty or train["y"].sum() == 0:
            continue
        m = fit(train, features)
        test["score"] = _score(m, test, features)
        folds.append({
            "test_start": str(pd.Timestamp(ts).date()),
            "test_end": str(pd.Timestamp(te).date()),
            "n_test": int(len(test)), "positives": int(test["y"].sum()),
            "pr_auc": round(average_precision_score(test["y"], test["score"]), 4),
            "pr_auc_base": round(average_precision_score(test["y"], test[BASELINE_COL]), 4),
            "model": pai_pei(test, "score", coverage),
            "baseline": pai_pei(test, BASELINE_COL, coverage),
        })
    return {"folds": folds, "summary": _summary(folds), "base_rate": round(t["y"].mean(), 4)}


def _summary(folds):
    if not folds:
        return {}
    avg = lambda f: round(float(np.mean([x[f] for x in folds])), 4)
    return {
        "pr_auc": avg("pr_auc"),
        "pr_auc_base": avg("pr_auc_base"),
        "pai": round(float(np.mean([x["model"]["pai"] for x in folds])), 3),
        "pai_base": round(float(np.mean([x["baseline"]["pai"] for x in folds])), 3),
        "pei": round(float(np.mean([x["model"]["pei"] for x in folds])), 3),
        "capture": round(float(np.mean([x["model"]["capture"] for x in folds])), 3),
        "capture_base": round(float(np.mean([x["baseline"]["capture"] for x in folds])), 3),
    }


def forecast_next(t, features, model):
    """Score the most recent day as the current risk surface (one row per
    area x crime_type) — what Predictive_Risk / the map shows."""
    last = t["date"].max()
    cur = t[t["date"] == last].copy()
    cur["risk_score"] = _score(model, cur, features)
    cur = cur.sort_values("risk_score", ascending=False).reset_index(drop=True)
    cur["rank"] = cur.index + 1
    return cur, last
