"""GARUDA - intelligence-brief assembly (Phase 9 automation).

Assembles the periodic intelligence brief from the engine outputs (rings, alerts,
series, risk, fairness) into structured sections + printable HTML. In production a
**SmartBrowz** headless render turns `render_html()` into a PDF → Stratus → Mail;
locally we emit the HTML. The brief always carries its source FIRs and a fairness
note (places & times, not people).
"""
from __future__ import annotations

import datetime
import html as _html


def build_brief(scope="STATE", period="", *, stats=None, rings=None, alerts=None,
                series=None, risk=None, fairness=None):
    stats, rings, alerts = stats or {}, rings or [], alerts or []
    series, risk, fairness = series or [], risk or [], fairness or {}

    sec = [{"title": "Situation", "body":
            "%s FIRs tracked · %s active spike alerts · %s organized rings."
            % (stats.get("incidents", "-"), len(alerts), len(rings))}]
    if rings:
        r = rings[0]
        sec.append({"title": "Top organized network", "body":
                    "Kingpin %s - %s members across %s districts (%s). Shared links: %s."
                    % (r.get("kingpin_label"), r.get("persons"), r.get("district_count"),
                       ", ".join(r.get("districts", [])), ", ".join(r.get("shared_links", [])))})
    if alerts:
        sec.append({"title": "Emerging-trend alerts", "items": [a.get("detail") for a in alerts[:5]]})
    if series:
        sec.append({"title": "Active crime series", "items": [
            "%s · %s ×%s (%s..%s)" % (s.get("crime_type"), s.get("district_code"),
                                      s.get("incident_count"), s.get("start_date"), s.get("end_date"))
            for s in series[:5]]})
    if risk:
        sec.append({"title": "Risk forecast (next period)", "items": [
            "%s · %s - %s%%" % (t.get("district_code"), t.get("crime_type"),
                                round((t.get("risk_score") or 0) * 100)) for t in risk[:5]]})
    if fairness:
        sec.append({"title": "Fairness & governance note", "body":
                    "%s of %s wards over-predicted >1.3x (max %.2fx) - flagged for review. "
                    "Forecasts target places & times, never individuals; all reads are audited."
                    % (fairness.get("over_predicted", 0), fairness.get("wards", "-"),
                       float(fairness.get("max_ratio", 0) or 0))})

    return {
        "scope": scope, "period": period or datetime.date.today().isoformat(),
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "classification": "RESTRICTED - for authorized SCRB personnel only",
        "sections": sec,
        "sources": [r.get("kingpin_id") for r in rings[:3] if r.get("kingpin_id")],
    }


def publish_pdf(html_text, name, bucket=None):
    """HTML → PDF via Catalyst SmartBrowz, stored in the Stratus briefs bucket
    (plan §4.9). Account-gated and strictly best-effort: any failure returns
    None and the caller keeps returning HTML, exactly as today.
    Returns {"bucket", "key"} on success."""
    import os
    bucket = bucket or os.environ.get("GARUDA_BRIEFS_BUCKET", "briefs")
    try:
        import zcatalyst_sdk               # deferred (account-gated)
        app = zcatalyst_sdk.initialize()
        pdf = app.smart_browz().convert_to_pdf(html_text)
        body = pdf.content if hasattr(pdf, "content") else pdf
        key = f"{name}.pdf"
        app.stratus().bucket(bucket).put_object(key, body)
        return {"bucket": bucket, "key": key}
    except Exception:                      # noqa: BLE001 - degrade to HTML-only
        return None


def render_html(brief):
    e = _html.escape
    body = []
    for s in brief["sections"]:
        body.append("<h2>%s</h2>" % e(s["title"]))
        if s.get("body"):
            body.append("<p>%s</p>" % e(s["body"]))
        if s.get("items"):
            body.append("<ul>" + "".join("<li>%s</li>" % e(str(i)) for i in s["items"]) + "</ul>")
    return ("<!doctype html><html><head><meta charset='utf-8'><title>GARUDA Brief</title><style>"
            "body{font-family:Arial,Helvetica,sans-serif;color:#0e1626;max-width:760px;margin:28px auto;line-height:1.5}"
            "h1{color:#1e40af;margin-bottom:2px}h2{color:#1e3a8a;border-bottom:1px solid #cbd5e1;padding-bottom:4px;margin-top:22px}"
            ".cls{color:#b45309;font-weight:700}.meta{color:#64748b;font-size:12px}ul{padding-left:18px}</style></head><body>"
            "<h1>GARUDA - Intelligence Brief</h1><p class='cls'>%s</p>"
            "<p class='meta'>Scope: %s · Period: %s · Generated: %s UTC</p>%s"
            "<p class='meta'>Source FIRs / entities: %s</p></body></html>"
            % (e(brief["classification"]), e(brief["scope"]), e(brief["period"]),
               e(brief["generated_at"]), "".join(body), e(", ".join(brief["sources"]) or "-")))
