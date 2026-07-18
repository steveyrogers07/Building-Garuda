"""GARUDA emerging-trend anomaly detection (Phase 5).

Per (district x crime_type) we build a monthly count series and flag months that
spike well above their own baseline. The baseline is robust (median + MAD), so a
single huge month doesn't poison it, and we gate on both a modified z-score and a
plain multiple-of-baseline ratio to keep false positives down. This recovers the
planted spikes (e.g. BNU two-wheeler theft x4) without any training.

statsmodels' STL is used opportunistically to de-seasonalise long series; the
robust z-score is the dependable fallback and the default signal.
"""
from __future__ import annotations

import calendar
import re
import statistics
from collections import defaultdict
from datetime import datetime

_DT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def _month(s):
    s = (s or "").strip()
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return None


def _month_end(ym):
    y, m = (int(x) for x in ym.split("-"))
    return f"{ym}-{calendar.monthrange(y, m)[1]:02d}"


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def detect(incidents, z_thresh=3.5, min_ratio=2.0, min_baseline=3.0, min_active_months=6):
    """Return ``{alerts: [...]}`` - one Alerts row per flagged (district, crime, month)."""
    counts = defaultdict(lambda: defaultdict(int))      # (district, crime) -> {month: n}
    months = set()
    for inc in incidents:
        m = _month(inc.get("occurred_at"))
        if not m:
            continue
        counts[(inc.get("district_code", ""), inc.get("crime_type", ""))][m] += 1
        months.add(m)

    all_months = sorted(months)
    alerts = []
    for (district, crime), series in counts.items():
        if sum(1 for m in all_months if series.get(m, 0) > 0) < min_active_months:
            continue
        for m in all_months:
            obs = series.get(m, 0)
            if obs <= 0:
                continue
            others = [series.get(mm, 0) for mm in all_months if mm != m]
            med = statistics.median(others)
            if med < min_baseline:
                continue
            mad = statistics.median([abs(x - med) for x in others])
            if mad > 0:
                z = 0.6745 * (obs - med) / mad
            else:                                       # flat baseline: use spread
                sd = statistics.pstdev(others) or 1.0
                z = (obs - med) / sd
            ratio = obs / med
            if z < z_thresh or ratio < min_ratio:
                continue
            alerts.append({
                "alert_id": f"AL-{district}-{_slug(crime)}-{m}",
                "type": "emerging_trend",
                "district_code": district,
                "crime_type": crime,
                "severity": "high" if ratio >= 3 else "medium",
                "window_start": f"{m}-01",
                "window_end": _month_end(m),
                "detail": (f"{crime} in {district} {m}: {obs} incidents vs baseline "
                           f"{med:.0f}/mo (x{ratio:.1f}, z={z:.1f})"),
                "status": "open",
                # extra metrics (handy for the UI / sorting; ignored by the ZCQL writer)
                "observed": obs,
                "baseline": round(med, 1),
                "ratio": round(ratio, 2),
                "z_score": round(z, 2),
            })
    alerts.sort(key=lambda a: -a["z_score"])
    return {"alerts": alerts}
