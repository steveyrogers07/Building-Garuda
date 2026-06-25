"""GARUDA risk-forecasting features (Phase 6).

Aggregates Incidents to a dense (area x day x crime_type) grid and builds
leakage-safe predictors: lagged counts (t-1, t-7), trailing rolling means
(7/28-day, all shifted by 1 so the current day is never seen), calendar signals
(day-of-week, month, weekend, holiday) and per-area socio-economic context
(population/density/literacy/urbanization from the Census reference).

Spatial unit = district (`area_code` = `district_code`) — the finest unit the
synthetic gazetteer carries; swap in ward/grid when finer data arrives, no model
change. Predicts PLACES x TIMES x crime-type, never individuals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = ["lag_1", "lag_7", "roll_7", "roll_28", "dow", "month", "is_weekend",
            "is_holiday", "population", "density", "literacy", "urbanization",
            "log_pop", "crime_code"]
KEYS = ["area_code", "crime_type", "date"]


def _holiday_dates(years, subdiv="KA"):
    try:
        import holidays as _H
        return set(_H.India(subdiv=subdiv, years=list(years)).keys())
    except Exception:                       # pragma: no cover - holidays optional
        return set()


def build_feature_table(incidents, socio):
    """incidents: rows with district_code, occurred_at, crime_type.
       socio: rows with area_code, population, density, literacy, urbanization.
    Returns (table, FEATURES) — one row per (area_code, crime_type, day)."""
    df = pd.DataFrame(incidents).copy()
    df["occurred_at"] = pd.to_datetime(df["occurred_at"], errors="coerce")
    df = df.dropna(subset=["occurred_at"])
    df["date"] = df["occurred_at"].dt.floor("D")
    df["area_code"] = df["district_code"].astype(str)
    df["crime_type"] = df["crime_type"].astype(str)

    counts = (df.groupby(["area_code", "crime_type", "date"])
                .size().rename("count").reset_index())

    soc = pd.DataFrame(socio).copy()
    soc["area_code"] = soc["area_code"].astype(str)
    for c in ["population", "density", "literacy", "urbanization"]:
        soc[c] = pd.to_numeric(soc.get(c), errors="coerce")

    # dense grid: every area x crime_type x day in the observed span
    areas = sorted(set(df["area_code"]) | set(soc["area_code"]))
    crimes = sorted(df["crime_type"].unique())
    days = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    grid = pd.MultiIndex.from_product([areas, crimes, days], names=KEYS).to_frame(index=False)

    t = grid.merge(counts, on=KEYS, how="left")
    t["count"] = t["count"].fillna(0).astype(int)
    t["y"] = (t["count"] > 0).astype(int)

    # leakage-safe history per (area, crime_type)
    t = t.sort_values(KEYS).reset_index(drop=True)
    grp = t.groupby(["area_code", "crime_type"], sort=False)["count"]
    t["lag_1"] = grp.shift(1)
    t["lag_7"] = grp.shift(7)
    t["roll_7"] = grp.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    t["roll_28"] = grp.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    for c in ["lag_1", "lag_7", "roll_7", "roll_28"]:
        t[c] = t[c].fillna(0.0)

    # calendar
    t["dow"] = t["date"].dt.dayofweek
    t["month"] = t["date"].dt.month
    t["is_weekend"] = (t["dow"] >= 5).astype(int)
    hol = _holiday_dates(t["date"].dt.year.unique())
    t["is_holiday"] = t["date"].dt.date.isin(hol).astype(int)

    # socio-economic context
    t = t.merge(soc[["area_code", "population", "density", "literacy", "urbanization"]],
                on="area_code", how="left")
    for c in ["population", "density", "literacy", "urbanization"]:
        t[c] = t[c].fillna(t[c].median())
    t["log_pop"] = np.log1p(t["population"])
    t["crime_code"] = t["crime_type"].astype("category").cat.codes

    return t, FEATURES
