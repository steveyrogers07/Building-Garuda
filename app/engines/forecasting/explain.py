"""GARUDA risk explainability (Phase 6) — SHAP via LightGBM TreeSHAP.

Uses LightGBM's native `pred_contrib=True` (exact TreeSHAP) so every risk score
comes with its top contributing drivers — no extra `shap` dependency. Powers
`/risk/explain`: "why is this area x time x crime-type risky?".
"""
from __future__ import annotations

import numpy as np


def shap_drivers(model, X_row, feature_names, top=8):
    """Top SHAP drivers for a single prediction.

    X_row: 1-row array/DataFrame in `feature_names` order.
    Returns rows {feature, value, shap} sorted by |contribution| (log-odds)."""
    booster = getattr(model, "booster_", model)
    X = np.asarray(X_row, dtype=float)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    contrib = booster.predict(X, pred_contrib=True)[0]   # n_features + 1 (last = base)
    vals = contrib[:-1]
    order = np.argsort(np.abs(vals))[::-1][:top]
    return [{"feature": feature_names[i], "value": round(float(X[0][i]), 4),
             "shap": round(float(vals[i]), 4),
             "direction": "raises" if vals[i] > 0 else "lowers"} for i in order]
