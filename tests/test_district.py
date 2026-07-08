"""GARUDA — District Command Card evaluation (no Catalyst).

Checks the district-command gates (blueprint §B1/§B2 — the clearance/conviction
rate computed from the organizer schema's ChargesheetDetails.cs_type, which sits
unused in the raw data until this aggregation):
  - D1  every district's outcomes (A/B/C) sum to its chargesheet count; clearance
        rate = A / (A+B+C), in [0, 1].
  - D2  total_incidents matches a direct count for that district; open+disposed==total.
  - D3  officer leaderboard is scoped to the district and sorted by case count.
  - D4  rank_districts covers every district exactly once, sorted by clearance rate
        (districts with no outcomes yet sort last, not crash).

Run:  python tests/test_district.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from engines import district  # noqa: E402
from shared import store  # noqa: E402


def run():
    incidents = store.fetch_incidents_full()
    chargesheets = store.fetch_chargesheets()
    officers = store.fetch_officers()
    assert incidents and chargesheets and officers, "run data/generate.py first"

    codes = sorted({r["district_code"] for r in incidents if r.get("district_code")})
    print(f"district command: {len(codes)} districts, {len(incidents):,} incidents, "
          f"{len(chargesheets):,} chargesheets, {len(officers)} officers")

    # ---- D1/D2: single-district card is internally consistent ----
    code = codes[0]
    card = district.command_card(code, incidents, chargesheets, officers)
    direct_total = sum(1 for r in incidents if r["district_code"] == code)
    assert card["total_incidents"] == direct_total
    assert card["open"] + card["disposed"] == card["total_incidents"]
    outcomes = card["outcomes"]
    assert sum(outcomes.values()) == card["outcomes_total"]
    if card["outcomes_total"]:
        assert 0.0 <= card["clearance_rate"] <= 1.0
        assert abs(card["clearance_rate"] - outcomes["A"] / card["outcomes_total"]) < 1e-3
    else:
        assert card["clearance_rate"] is None
    print(f"  D1/D2 {code}: {card['total_incidents']} incidents, "
          f"clearance={card['clearance_rate']}, backlog={card['backlog_aging']}")

    # every chargesheet for this district's incidents is accounted for
    inc_ids = {r["incident_id"] for r in incidents if r["district_code"] == code}
    direct_cs = sum(1 for c in chargesheets if c["incident_id"] in inc_ids)
    assert card["outcomes_total"] == direct_cs

    # ---- D3: officer leaderboard scoped + sorted ----
    if card["top_officers"]:
        assert all(o["cases"] >= 1 for o in card["top_officers"])
        cases_sorted = [o["cases"] for o in card["top_officers"]]
        assert cases_sorted == sorted(cases_sorted, reverse=True)
        for o in card["top_officers"]:
            assert o["clearance_rate"] is None or 0.0 <= o["clearance_rate"] <= 1.0
    print(f"  D3 top officer: {card['top_officers'][0] if card['top_officers'] else None}")

    # ---- D4: ranking covers every district exactly once ----
    ranked = district.rank_districts(codes, incidents, chargesheets, officers)
    assert len(ranked) == len(codes)
    assert {c["district_code"] for c in ranked} == set(codes)
    rates = [c["clearance_rate"] for c in ranked if c["clearance_rate"] is not None]
    assert rates == sorted(rates, reverse=True)
    print(f"  D4 ranked {len(ranked)} districts; top clearance "
          f"{ranked[0]['district_code']}={ranked[0]['clearance_rate']}")

    print("ALL DISTRICT-COMMAND GATES PASSED")


if __name__ == "__main__":
    run()
