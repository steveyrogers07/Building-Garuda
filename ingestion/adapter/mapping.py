"""GARUDA adapter — source -> canonical mapping (format-specific logic lives here).

Reads a source file + a column-map config and produces a canonical DataFrame.
Pure (no Catalyst SDK), so it's reusable by loader.py, validate.py and the
profiling notebook. Swapping datasets = swapping the column-map, not this code.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

ADAPTER_DIR = Path(__file__).resolve().parent
REPO_ROOT = ADAPTER_DIR.parent.parent
SCHEMA_PATH = REPO_ROOT / "schema" / "canonical_schema.yaml"


def load_column_map(map_path, table):
    m = yaml.safe_load(Path(map_path).read_text(encoding="utf-8"))
    if table not in m:
        raise KeyError(f"table '{table}' not in column map {map_path}. "
                       f"Available: {list(m.keys())}")
    return m[table]


def read_source(path):
    """Read any CSV as strings (we control coercion ourselves), UTF-8, NA-safe."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")


def _coerce(series, transform):
    if transform == "datetime":
        dt = pd.to_datetime(series, errors="coerce")
        return dt.dt.strftime("%Y-%m-%d %H:%M:%S").where(dt.notna(), "")
    if transform == "int":
        n = pd.to_numeric(series, errors="coerce")
        return n.map(lambda x: "" if pd.isna(x) else str(int(x)))
    if transform == "float":
        n = pd.to_numeric(series, errors="coerce")
        return n.map(lambda x: "" if pd.isna(x) else float(x))
    return series.astype(str).str.strip()


def map_to_canonical(df, table_map):
    """Return (canonical_df, missing) where missing = [(canonical, source), ...]."""
    fields = table_map["fields"]
    out = pd.DataFrame(index=df.index)
    missing = []
    for canon, spec in fields.items():
        spec = spec or {}
        src = spec.get("source", canon)
        if src in df.columns:
            out[canon] = _coerce(df[src], spec.get("transform"))
        else:
            out[canon] = ""
            missing.append((canon, src))
    return out, missing
