"""GARUDA — dataset profiling helpers (used by profile.ipynb).

Runs on ANY tabular file: shape, dtypes, missingness, cardinality, date ranges,
district coverage, candidate join keys, likely-PII columns. This is the FIRST thing
to run when the real KSP dataset arrives (see docs/GARUDA_DATA_READINESS.md), to learn
its granularity/fields/joins before filling in the adapter's column map.
"""
from __future__ import annotations

import warnings

import pandas as pd


def _to_dt(s):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(s, errors="coerce")

PII_NAME_HINTS = ("name", "phone", "mobile", "email", "address", "aadhaar", "aadhar",
                  "victim", "accused", "complainant", "dob", "father", "guardian")
PHONE_RE = r"(?:\+?91[\-\s]?)?[6-9]\d{9}"
EMAIL_RE = r"[^@\s]+@[^@\s]+\.[^@\s]+"
AADHAAR_RE = r"\b\d{4}\s?\d{4}\s?\d{4}\b"


def _is_datetime_col(s, thresh=0.8):
    nonempty = s[s.astype(str).str.strip() != ""]
    if len(nonempty) == 0:
        return False
    return _to_dt(nonempty).notna().mean() >= thresh


def missingness(df):
    return (df.apply(lambda s: (s.astype(str).str.strip() == "").mean()) * 100).round(1).sort_values(ascending=False)


def cardinality(df):
    return df.nunique().sort_values(ascending=False)


def date_ranges(df):
    out = {}
    for c in df.columns:
        if _is_datetime_col(df[c]):
            dt = _to_dt(df[c])
            out[c] = (str(dt.min()), str(dt.max()), int(dt.notna().sum()))
    return out


def district_coverage(df):
    for c in df.columns:
        if "district" in c.lower():
            return c, df[c].value_counts()
    return None, None


def candidate_join_keys(df):
    n = len(df)
    keys = []
    for c in df.columns:
        nu = int(df[c].nunique())
        ratio = nu / n if n else 0
        if ratio > 0.9 or c.lower().endswith(("_id", "_no", "id", "code")):
            keys.append((c, nu, round(ratio, 3)))
    return keys


def likely_pii(df):
    flagged = {}
    for c in df.columns:
        reasons = []
        if any(h in c.lower() for h in PII_NAME_HINTS):
            reasons.append("name-hint")
        sample = df[c].astype(str).head(2000)
        if sample.str.contains(PHONE_RE, regex=True, na=False).any():
            reasons.append("phone-like")
        if sample.str.contains(EMAIL_RE, regex=True, na=False).any():
            reasons.append("email-like")
        if sample.str.contains(AADHAAR_RE, regex=True, na=False).any():
            reasons.append("aadhaar-like")
        if reasons:
            flagged[c] = reasons
    return flagged


def full_report(df, name="dataset"):
    print(f"=== PROFILE: {name} ===")
    print(f"shape: {df.shape[0]:,} rows x {df.shape[1]} cols\n")
    print("missing % (top 20):")
    print(missingness(df).head(20).to_string(), "\n")
    print("cardinality (top 20):")
    print(cardinality(df).head(20).to_string(), "\n")
    dr = date_ranges(df)
    print("date-like columns:")
    for c, (a, b, n) in dr.items():
        print(f"  {c}: {a} -> {b}  ({n:,} parsed)")
    if not dr:
        print("  none")
    print()
    col, vc = district_coverage(df)
    if col is not None:
        print(f"district coverage via '{col}': {vc.shape[0]} distinct")
        print(vc.head(10).to_string(), "\n")
    print("candidate join keys (near-unique or *_id/_no/code):")
    for c, nu, r in candidate_join_keys(df):
        print(f"  {c}: nunique={nu:,} ratio={r}")
    print()
    pii = likely_pii(df)
    print("LIKELY PII columns (mask per IPC 228A / POCSO before sharing):")
    for c, reasons in pii.items():
        print(f"  {c}: {', '.join(reasons)}")
    if not pii:
        print("  none detected")
