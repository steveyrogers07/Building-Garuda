"""GARUDA copilot - natural language -> structured query (Phase 7).

Rules/regex parser (no credits) that turns a plain-English question into safe,
parameterized filters over Incidents: district, crime_type, vehicle plate, phone,
date range, time-of-day. The residual text feeds the semantic retriever. An
optional Qwen path (QuickML) can replace this behind EXTRACTOR=qwen, mirroring the
Phase-3 pattern; the rule parser is the $0 default.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

# crime-type synonyms -> canonical label (the canonical set is supplied at runtime)
_CRIME_SYNONYMS = {
    "chain snatch": "Chain snatching", "snatching": "Chain snatching",
    "bike theft": "Two-wheeler theft", "two wheeler": "Two-wheeler theft",
    "two-wheeler": "Two-wheeler theft", "scooter theft": "Two-wheeler theft",
    "motorcycle theft": "Two-wheeler theft", "burglary": "House burglary",
    "housebreaking": "House burglary", "break-in": "House burglary",
    "car theft": "Motor vehicle theft", "vehicle theft": "Motor vehicle theft",
    "fraud": "Cheating", "cyber": "Cybercrime", "kidnap": "Kidnapping",
}

VEHICLE_RE = re.compile(r"\bKA[\s-]?\d{1,2}[\s-]?[A-Z]{1,2}[\s-]?\d{1,4}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?91[\s-]?)?[6-9]\d{9}\b")
ISO_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
MONTH_YEAR_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(20\d{2})\b", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
# guilt-determination guardrail (refuse) - NOT generic investigative retrieval
_GUILT_RE = re.compile(
    r"\b(guilty|culprit|the criminal|did (he|she|they|\w+) (commit|do it)|"
    r"is \w+ (a criminal|the offender)|convict\b|should be punished|prove .* guilt)\b",
    re.I)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _esc(v):
    return str(v).replace("'", "''")


def parse_query(text, districts, crime_types, data_max=None):
    """districts: {name_lower: code}; crime_types: iterable of canonical labels.
    Returns a filters dict (+ guardrail flag)."""
    q = " " + _norm(text) + " "
    f = {"raw": text}

    code = None
    for name, c in sorted(districts.items(), key=lambda kv: -len(kv[0])):
        if name and name in q:
            code = c
            break
    if code is None:
        for alias, c in (("bangalore", "BNU"), ("bengaluru", "BNU"), ("blr", "BNU")):
            if alias in q:
                code = c
                break
    if code:
        f["district_code"] = code

    # longest match wins so "two-wheeler theft" beats the substring "theft"
    ct = next((c for c in sorted(crime_types, key=len, reverse=True) if c.lower() in q), None)
    if ct is None:
        ct = next((canon for syn, canon in _CRIME_SYNONYMS.items()
                   if syn in q and canon in crime_types), None)
    if ct:
        f["crime_type"] = ct

    v = VEHICLE_RE.search(text)
    if v:
        f["vehicle"] = re.sub(r"[\s-]", "", v.group(0).upper())
    p = PHONE_RE.search(text)
    if p:
        f["phone"] = p.group(0)

    df_, dt_ = _parse_dates(text, q, data_max)
    if df_:
        f["date_from"] = df_
    if dt_:
        f["date_to"] = dt_

    hf, ht = _parse_time_of_day(q)
    if hf is not None:
        f["hour_from"] = hf
    if ht is not None:
        f["hour_to"] = ht

    f["guilt_query"] = bool(_GUILT_RE.search(text))
    return f


def _month_end(y, m):
    import calendar
    return f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def _parse_dates(text, q, data_max):
    isos = ["-".join(t) for t in ISO_RE.findall(text)]
    if "between" in q and len(isos) >= 2:
        return isos[0], isos[1]
    if any(w in q for w in (" after ", " since ", " from ")) and isos:
        return isos[0], None
    if any(w in q for w in (" before ", " until ", " till ")) and isos:
        return None, isos[0]
    my = MONTH_YEAR_RE.search(text)
    if my:
        mon = _MONTHS.index(my.group(1).lower()[:3]) + 1
        yr = int(my.group(2))
        return f"{yr}-{mon:02d}-01", _month_end(yr, mon)
    if len(isos) == 1:
        return isos[0], isos[0]
    m = re.search(r"last\s+(\d+)\s+(day|week|month)", q)
    if m and data_max:
        n = int(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2)]
        start = (datetime.strptime(data_max, "%Y-%m-%d") - timedelta(days=n)).strftime("%Y-%m-%d")
        return start, data_max
    yr = YEAR_RE.search(text)
    if yr:
        return f"{yr.group(1)}-01-01", f"{yr.group(1)}-12-31"
    return None, None


def _to24(hour, ampm):
    h = int(hour) % 12
    return h + 12 if ampm.lower() == "pm" else h


def _parse_time_of_day(q):
    m = re.search(r"\bafter\s+(\d{1,2})\s*(am|pm)\b", q)
    if m:
        return _to24(m.group(1), m.group(2)), None
    m = re.search(r"\bbefore\s+(\d{1,2})\s*(am|pm)\b", q)
    if m:
        return None, _to24(m.group(1), m.group(2))
    for word, (a, b) in {"midnight": (0, 4), "night": (20, 5), "morning": (5, 12),
                         "afternoon": (12, 17), "evening": (17, 21)}.items():
        if word in q:
            return a, b
    return None, None


def to_zcql(f, limit=200):
    """Parameterized ZCQL SELECT for the prod path (transparency + audit)."""
    where = []
    if f.get("district_code"):
        where.append("district_code = '%s'" % _esc(f["district_code"]))
    if f.get("crime_type"):
        where.append("crime_type = '%s'" % _esc(f["crime_type"]))
    if f.get("date_from"):
        where.append("occurred_at >= '%s'" % f["date_from"])
    if f.get("date_to"):
        where.append("occurred_at <= '%s 23:59:59'" % f["date_to"])
    sql = ("SELECT incident_id, fir_no, occurred_at, district_code, crime_type, "
           "ipc_bns_code, mo_text, source_fir_url FROM Incidents")
    if where:
        sql += " WHERE " + " AND ".join(where)
    return sql + " LIMIT %d" % limit
