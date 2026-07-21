"""Gates for the district action card (engines/actions.py).

Run:  python tests/test_actions.py

  - AC1  every recommendation carries priority (1..n contiguous), severity,
         action, why, sources; ordering is severity-ranked (high before
         medium before info).
  - AC2  the deadline directive's count equals an independent recomputation
         (sum of roster `urgent` for that district's officers).
  - AC3  the anomaly directive appears exactly for districts with a
         current-window alert, and quotes that alert's observed/baseline.
  - AC4  the absconding directive's numbers equal the district-filtered board
         summary.
  - AC5  the clearance directive appears iff the district is below the state
         median clearance rate.
  - AC6  empty inputs produce the single no-directives card, never a crash.
  - AC7  hotspot() only reports bands with enough mass and only stations from
         the requested district.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from engines import actions as act                      # noqa: E402
from engines import deadlines as dl                     # noqa: E402
from engines import district as de                      # noqa: E402
from engines.anomaly import detect as detect_anomalies  # noqa: E402
from shared import store                                # noqa: E402


def run():
    incidents = store.fetch_incidents_full()
    chargesheets = store.fetch_chargesheets()
    officers = store.fetch_officers()
    arrests = store.fetch_arrests()

    codes = sorted({r["district_code"] for r in incidents if r.get("district_code")})
    cards = de.rank_districts(codes, incidents, chargesheets, officers)
    by_code = {c["district_code"]: c for c in cards}
    alerts = detect_anomalies(store.fetch_incidents_p5())["alerts"]
    roster = dl.officers_roster(incidents, officers, arrests, chargesheets)["officers"]
    absc_state = dl.absconding_people(
        incidents, arrests, chargesheets, store.fetch_edges_p5(), store.fetch_entities_p5())

    med = act._median([c.get("clearance_rate") for c in cards])
    alert_districts = {a["district_code"] for a in alerts}
    print(f"actions: {len(codes)} districts, {len(alerts)} alerts "
          f"({len(alert_districts)} districts), state median clearance {med:.0%}")

    sev_rank = {"high": 0, "medium": 1, "info": 2}
    checked_anom = checked_dead = checked_absc = 0
    for code in codes:
        summary = dl.absconding_board_from(absc_state, district=code, limit=1)["summary"]
        res = act.district_actions(
            code, card=by_code[code], all_cards=cards, alerts=alerts,
            risk_rows=[], roster=roster, absconding_summary=summary,
            incidents=incidents)
        recs = res["recommendations"]

        # AC1 - shape + ordering
        assert recs, f"{code}: empty recommendations"
        assert [r["priority"] for r in recs] == list(range(1, len(recs) + 1)), \
            f"{code}: priorities not contiguous"
        ranks = [sev_rank[r["severity"]] for r in recs]
        assert ranks == sorted(ranks), f"{code}: severity ordering broken"
        for r in recs:
            assert r["action"] and r["why"] is not None and isinstance(r["sources"], list)

        # AC2 - deadline count == independent roster recomputation
        urgent = sum(o["urgent"] for o in roster if o["district_code"] == code)
        dead = [r for r in recs if "deadlines" in r["sources"]]
        if urgent:
            assert len(dead) == 1 and str(urgent) in dead[0]["action"], \
                f"{code}: deadline rec missing/incorrect ({urgent} urgent)"
            checked_dead += 1
        else:
            assert not dead, f"{code}: deadline rec with zero urgent cases"

        # AC3 - anomaly rec quotes the current-window alert
        mine = [a for a in alerts if a["district_code"] == code]
        anom = [r for r in recs if "anomaly" in r["sources"]]
        if mine:
            latest = max(a["window_end"] for a in mine)
            top = max((a for a in mine if a["window_end"] == latest),
                      key=lambda a: a["ratio"])
            assert anom, f"{code}: alert present but no anomaly directive"
            assert any(str(top["observed"]) in r["why"] for r in anom), \
                f"{code}: anomaly why does not quote observed count"
            checked_anom += 1
        else:
            assert not anom, f"{code}: anomaly rec without an alert"

        # AC4 - absconding numbers match the board summary
        bolo = [r for r in recs if "absconding" in r["sources"]]
        if summary.get("heinous_people"):
            assert len(bolo) == 1 and str(summary["heinous_people"]) in bolo[0]["action"]
            assert str(summary["people"]) in bolo[0]["why"]
            checked_absc += 1
        else:
            assert not bolo

        # AC5 - clearance directive iff below state median, and the sentence it
        # prints must be literally true at the precision it prints
        cr = by_code[code].get("clearance_rate")
        clr = [r for r in recs if "district" in r["sources"] and "clearance" in r["why"]]
        if cr is not None and round(cr * 100) < round(med * 100):
            assert clr, f"{code}: below median ({cr:.0%} < {med:.0%}) but no audit rec"
        else:
            assert not clr, f"{code}: audit rec at/above median"
        for r in clr:
            a, b = re.findall(r"(\d+)%", r["why"])[:2]
            assert int(a) < int(b), f"{code}: contradictory clearance text: {r['why']}"

    assert checked_anom and checked_dead and checked_absc, \
        "gates never exercised - dataset lost its planted signals?"
    print(f"  AC1 shape+ordering ok across {len(codes)} districts")
    print(f"  AC2 deadline counts verified in {checked_dead} districts")
    print(f"  AC3 anomaly directives verified in {checked_anom} districts")
    print(f"  AC4 absconding numbers verified in {checked_absc} districts")
    print(f"  AC5 clearance-vs-median rule verified in {len(codes)} districts")

    # AC6 - empty inputs: one info card, no crash
    empty = act.district_actions(
        "XX", card={"clearance_rate": None, "outcomes": {}, "backlog_aging": 0,
                    "backlog_threshold_days": 90},
        all_cards=[], alerts=[], risk_rows=[], roster=[],
        absconding_summary={}, incidents=[])
    assert len(empty["recommendations"]) == 1
    assert empty["recommendations"][0]["severity"] == "info"
    print("  AC6 empty-input card ok (single info directive)")

    # AC7 - hotspot integrity
    code = max(codes, key=lambda c: by_code[c]["total_incidents"])
    spot = act.hotspot(incidents, code)
    assert spot is not None and spot["count"] >= 3
    stations = {r.get("station_code") for r in incidents
                if r.get("district_code") == code}
    assert spot["station_code"] in stations
    assert act.hotspot([], code) is None
    print(f"  AC7 hotspot ok ({code}: {spot['band']} around {spot['station_code']}, "
          f"n={spot['count']})")

    print("ALL ACTION-CARD GATES PASSED")


if __name__ == "__main__":
    run()
