"""GARUDA — local Phase-9 governance evaluation (no Catalyst).

Checks the locally-buildable Phase-9 exit gates:
  - G4  field-level PII masking by role; statutory hard-masking for IPC 228A / POCSO;
        suspects framed ("pending trial"), never masked.
  - G5  RBAC jurisdiction filtering + action authorization; every read audited.
  - automation: intelligence-brief assembly + alert→notification routing.

Run:  python tests/test_governance.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from automation import briefs, notify          # noqa: E402
from governance import audit as gaudit, masking, rbac   # noqa: E402
from shared import store                         # noqa: E402

SYN = REPO / "data" / "synthetic"


def run():
    edg = pd.read_csv(SYN / "incident_edges.csv", dtype=str, keep_default_na=False)
    iid = edg[edg["role"] == "victim"]["incident_id"].iloc[0]
    inc = store.fetch_incident(iid)
    parties = store.fetch_incident_parties(iid)
    victim = next(p for p in parties if p["role"] == "victim" and p["type"] == "person")
    suspect = next((p for p in parties if p["role"] == "suspect" and p["type"] == "person"), None)
    dist, stn = inc["district_code"], inc["station_code"]
    print(f"case {iid} · district {dist} · victim '{victim['value']}'")

    def vic(masked):
        return next(p for p in masked if p["entity_id"] == victim["entity_id"])["value"]

    # ---- G4a: ordinary crime — own jurisdiction + admin see; analyst + others masked ----
    def M(role, scope=None, crime="Theft"):
        return masking.mask_parties(parties, role, scope, crime_type=crime, district=dist, station=stn)
    assert vic(M("scrb-admin")) == victim["value"], "admin must see victim"
    assert vic(M("district", dist)) == victim["value"], "own-district must see victim"
    assert vic(M("analyst")) != victim["value"], "analyst must be masked"
    assert vic(M("district", "ZZZ")) != victim["value"], "other district must be masked"
    print("  G4a ordinary-crime victim masking: OK")

    # ---- G4b: IPC 228A / POCSO — masked for ALL except admin / case-officer ----
    assert vic(M("district", dist, "Rape")) != victim["value"], "228A: even own-district masked"
    assert vic(M("analyst", None, "Rape")) != victim["value"]
    assert vic(M("scrb-admin", None, "Rape")) == victim["value"], "admin sees protected (audited)"
    assert vic(M("case-officer", None, "Rape")) == victim["value"]
    print("  G4b IPC-228A / POCSO hard-masking: OK")

    # ---- suspects: framed, never masked ----
    if suspect:
        ms = masking.mask_party(suspect, "analyst", None, dist, stn, "Theft")
        assert ms["value"] == suspect["value"] and "pending" in ms.get("note", ""), "suspect framing"
        print("  suspect framing (not masked, 'pending trial'): OK")

    # ---- G5: RBAC jurisdiction filter + authorization ----
    rows = store.fetch_incidents_copilot()
    assert len(rbac.jurisdiction_filter(rows, rbac.Principal(role="scrb-admin"))) == len(rows)
    dfil = rbac.jurisdiction_filter(rows, rbac.Principal(role="district", scope=dist))
    assert dfil and all(r["district_code"] == dist for r in dfil), "district filter leaks"
    print(f"  G5 jurisdiction filter: district {dist} sees {len(dfil)}/{len(rows)} incidents")

    for role, act, res in [("ethics", "read", "incident_pii"), ("analyst", "write", "canonical")]:
        try:
            rbac.authorize(rbac.Principal(role=role), act, res)
            raise AssertionError(f"{role} {act} {res} should be denied")
        except PermissionError:
            pass
    print("  G5 authorization denials (ethics/PII, analyst/write): OK")

    # ---- audit: every governed read writes a log entry ----
    before = len(store.read_audit_log(1000000))
    gaudit.record(rbac.Principal(actor="tester", role="district", scope=dist),
                  "read", "Incident:" + iid, "test")
    assert len(store.read_audit_log(1000000)) == before + 1, "audit entry not written"
    print("  audit trail (+1 entry on read): OK")

    # ---- automation: brief assembly ----
    brief = briefs.build_brief(
        "STATE", stats={"incidents": 10130},
        rings=[{"kingpin_label": "Aayush Zachariah", "kingpin_id": "ENT014602", "persons": 5,
                "district_count": 4, "districts": ["BNU", "RMN", "TMK", "KLR"],
                "shared_links": ["+916534933629", "KA68MC3164"]}],
        alerts=[{"detail": "BNU two-wheeler theft x4", "severity": "high",
                 "district_code": "BNU", "crime_type": "Two-wheeler theft", "alert_id": "AL1"}],
        series=[{"crime_type": "House burglary", "district_code": "MYS", "incident_count": 6,
                 "start_date": "2024-05-12", "end_date": "2024-05-26"}],
        risk=[{"district_code": "BNU", "crime_type": "Theft", "risk_score": 0.42}],
        fairness={"over_predicted": 4, "wards": 31, "max_ratio": 1.61})
    html = briefs.render_html(brief)
    assert brief["sections"] and "ENT014602" in brief["sources"] and "<h1" in html
    print(f"  brief assembly: {len(brief['sections'])} sections, {len(html)} bytes HTML: OK")

    # ---- automation: alert → notification routing ----
    n = notify.notification_for({"district_code": "BNU", "severity": "high",
                                 "crime_type": "Two-wheeler theft", "detail": "x4", "alert_id": "AL1"})
    assert n["channels"] == ["push", "mail"] and n["district_code"] == "BNU" and n["priority"] == 1
    nmed = notify.notification_for({"district_code": "MYS", "severity": "medium", "crime_type": "Theft"})
    assert nmed["channels"] == ["mail"], "medium alert should be mail-only"
    print("  alert routing (high -> push+mail, medium -> mail): OK")

    print("\nPASS")


def test_governance():
    run()


if __name__ == "__main__":
    run()
