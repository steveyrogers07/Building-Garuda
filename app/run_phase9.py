"""GARUDA — Phase 9 local runner: the proactive loop + governance, at $0.

Runs the nightly recompute (network / series / anomaly / forecast refresh),
assembles & renders the weekly intelligence brief, routes spike alerts to
notifications, and demonstrates field-level PII masking by role — all locally.
The Catalyst triggers (Job Scheduling cron, Signal -> Push/Mail, SmartBrowz PDF)
are the account-gated wiring documented in the runbook.

    python app/run_phase9.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if "GARUDA_HOME" not in os.environ:
    os.environ["GARUDA_HOME"] = str(Path.home() / "OneDrive" / "Desktop" / "garuda")
HOME = Path(os.environ["GARUDA_HOME"])
HOME.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO / "app"))

import pandas as pd                                          # noqa: E402
from engines import forecasting as fc, network as net       # noqa: E402
from engines.anomaly import detect                           # noqa: E402
from engines.series import link_series                       # noqa: E402
from automation import briefs, jobs, notify                  # noqa: E402
from governance import audit as gaudit, masking, rbac        # noqa: E402
from shared import store                                     # noqa: E402


def main():
    print("GARUDA Phase 9 -> local storage:", HOME)
    inc = store.fetch_incidents_p5()
    state = {}

    def job_network():
        a = net.analyze(inc, store.fetch_entities_p5(), store.fetch_edges_p5())
        state["rings"] = net.cross_district_rings(a["graph"], a["communities"], top=5)
        return "%d nodes, %d cross-district rings" % (a["graph"].number_of_nodes(), len(state["rings"]))

    def job_anomaly():
        state["alerts"] = detect(inc)["alerts"]
        return "%d alerts" % len(state["alerts"])

    def job_series():
        state["series"] = link_series(inc)["series"][:5]
        return "top %d series kept" % len(state["series"])

    def job_forecast():
        t, feats = fc.build_feature_table(inc, store.fetch_socioeconomic())
        m = fc.fit(t, feats)
        cur, _ = fc.forecast_next(t, feats, m)
        state["risk"] = [{"district_code": r["area_code"], "crime_type": r["crime_type"],
                          "risk_score": float(r["risk_score"])} for _, r in cur.head(5).iterrows()]
        samp = t.sample(min(40000, len(t)), random_state=0).copy()
        samp["score"] = m.predict_proba(samp[feats])[:, 1]
        state["fairness"] = fc.fairness_audit(samp, "score")[1]
        return "risk surface + fairness audit computed"

    report = jobs.nightly_recompute([("network", job_network), ("anomaly", job_anomaly),
                                     ("series", job_series), ("forecast", job_forecast)])
    print("\nnightly recompute (%.1fs):" % report["_duration_s"])
    for name in ("network", "anomaly", "series", "forecast"):
        r = report[name]
        print("   %-9s %s" % (name, r["result"] if r["ok"] else "ERROR " + r["error"]))

    def _write(html):
        p = HOME / "intelligence_brief.html"
        p.write_text(html, encoding="utf-8")
        return str(p)

    out = jobs.weekly_brief(
        lambda: briefs.build_brief("STATE", stats={"incidents": len(inc)}, rings=state.get("rings"),
                                   alerts=state.get("alerts"), series=state.get("series"),
                                   risk=state.get("risk"), fairness=state.get("fairness")),
        briefs.render_html, _write)
    print("\nweekly brief: %d sections -> %s" % (len(out["brief"]["sections"]), out["written"]))

    notifs = notify.notifications_for_alerts(state.get("alerts", []), severity_min="high")
    print("\nalert dispatch (%d high-severity; Signal/Push/Mail send is account-gated):" % len(notifs))
    for n in notifs[:4]:
        print("   [%s] %-34s -> %s (%s)" % (n["severity"], n["title"], n["to"], "+".join(n["channels"])))

    edg = pd.read_csv(REPO / "data" / "synthetic" / "incident_edges.csv", dtype=str, keep_default_na=False)
    iid = edg[edg["role"] == "victim"]["incident_id"].iloc[0]
    case, parties = store.fetch_incident(iid), store.fetch_incident_parties(iid)
    vic = next(p for p in parties if p["role"] == "victim" and p["type"] == "person")

    def see(role, scope=None, crime=None):
        mp = masking.mask_parties(parties, role, scope, crime_type=crime or case["crime_type"],
                                  district=case["district_code"], station=case["station_code"])
        return next(p for p in mp if p["entity_id"] == vic["entity_id"])["value"]

    print("\ngovernance - victim identity on FIR %s (%s, %s):" % (iid, case["crime_type"], case["district_code"]))
    print("   scrb-admin       :", see("scrb-admin"))
    print("   district (%-4s)   :" % case["district_code"], see("district", case["district_code"]))
    print("   analyst          :", see("analyst"))
    print("   station (other)  :", see("station", "XX99"))
    print("   IF IPC-228A/POCSO: district ->", see("district", case["district_code"], "Rape"),
          "| admin ->", see("scrb-admin", None, "Rape"))
    gaudit.record(rbac.Principal(actor="run_phase9", role="scrb-admin"), "read", "Incident:" + iid, "phase9-demo")
    print("\naudit entries on file:", len(store.read_audit_log(1000000)))
    print("done.")


if __name__ == "__main__":
    main()
