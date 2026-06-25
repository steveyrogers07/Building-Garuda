"""GARUDA risk fairness audit (Phase 6).

Bias guardrail for predictive policing: per ward (district here — the finest unit
available), compare the model's mean predicted risk against the actual offense
rate. A ward whose predicted risk runs materially hotter than reality (ratio >
threshold) is over-policed by the model and is flagged for review. Keeps the
system honest about disproportionately targeting any area.
"""
from __future__ import annotations

import pandas as pd


def fairness_audit(scored, score_col="score", ward_col="area_code", flag_ratio=1.3):
    """scored: rows with ward_col, `score_col` (predicted prob) and `y` (actual).
    Returns (report_df, summary)."""
    g = (pd.DataFrame(scored)
         .groupby(ward_col)
         .agg(predicted=(score_col, "mean"), actual=("y", "mean"),
              cells=("y", "size"))
         .reset_index())
    # ratio of predicted risk to actual offense rate (1.0 == calibrated)
    g["ratio"] = g["predicted"] / g["actual"].replace(0, pd.NA)
    g["over_predicted"] = g["ratio"] > flag_ratio
    g = g.sort_values("ratio", ascending=False, na_position="last").reset_index(drop=True)
    for c in ["predicted", "actual", "ratio"]:
        g[c] = g[c].astype(float).round(4)
    summary = {
        "wards": int(len(g)),
        "over_predicted": int(g["over_predicted"].sum()),
        "flag_ratio": flag_ratio,
        "max_ratio": float(g["ratio"].max(skipna=True)) if len(g) else 0.0,
        "flagged_wards": g.loc[g["over_predicted"], ward_col].tolist(),
    }
    return g, summary
