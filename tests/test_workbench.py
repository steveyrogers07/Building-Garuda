"""GARUDA — local Iteration-11 workbench evaluation (no Catalyst).

Checks the investigation-workbench gates:
  - W1  entity dossier: kingpin 360 (appearances, districts, associates incl. the
        shared phone/vehicle); accepts alias entity ids; unknown id -> error.
  - W2  case file: linked cases carry explained reasons (shared phone/vehicle/person,
        series, near-repeat) and gang cases interlink.
  - W3  universal search: plate / person / case / semantic; ethics restricted.
  - W4  governance: victim-only identities masked for analyst in dossier + search,
        visible to admin; suspects always visible.

Run:  python tests/test_workbench.py
Prereqs: python data/generate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))

from engines import workbench as wb          # noqa: E402
from governance import rbac                    # noqa: E402

ADMIN = rbac.Principal(actor="t", role="scrb-admin")
ANALYST = rbac.Principal(actor="t", role="analyst")
ETHICS = rbac.Principal(actor="t", role="ethics")

KINGPIN, PHONE, VEHICLE = "ENT014602", "+916534933629", "KA68MC3164"


def run():
    st = wb.state()
    print(f"workbench state: {len(st['incidents']):,} incidents, "
          f"{len(st['canon_meta']):,} canonical entities (built in {st['built_s']}s)")

    # ---- W1: kingpin dossier ----
    d = wb.dossier(KINGPIN, ADMIN)
    assert d["value"] == "Aayush Zachariah" and d["masked"] is None
    assert d["stats"]["incidents"] >= 9 and len(d["stats"]["districts"]) == 4
    assoc_vals = {a["label"] for a in d["associates"]}
    assert PHONE in assoc_vals and VEHICLE in assoc_vals, "shared phone/vehicle missing"
    assert any(a["type"] == "person" for a in d["associates"])
    assert d["timeline"] and d["guardrail"]
    print(f"  W1 kingpin dossier: {d['stats']['incidents']} incidents, "
          f"districts {d['stats']['districts']}, {len(d['associates'])} associates: OK")

    alias_ok = wb.dossier("ENT000002", ADMIN)          # alias entity -> canonical parent
    assert alias_ok.get("canonical_id") == "ENT000001", "alias did not resolve to canonical"
    assert wb.dossier("ENT_NOPE", ADMIN).get("error") == "not_found"
    print("  W1 alias resolution + not-found: OK")

    # ---- W2: case file linked reasons ----
    c = wb.case_file("INC010002", ADMIN)
    assert not c.get("error") and c["parties"], "case file empty"
    linked_ids = {l["incident_id"] for l in c["linked_cases"]}
    assert "INC010001" in linked_ids, "gang cases not interlinked"
    top = c["linked_cases"][0]
    rtypes = {r["type"] for l in c["linked_cases"] for r in l["reasons"]}
    assert {"shared_phone", "shared_vehicle"} & rtypes, f"no shared-link reasons: {rtypes}"
    assert top["strength"] >= c["linked_cases"][-1]["strength"], "links not ranked"
    print(f"  W2 case INC010002: {len(c['linked_cases'])} linked cases, "
          f"reasons {sorted(rtypes)}: OK")
    assert wb.case_file("INC_NOPE", ADMIN).get("error") == "not_found"

    # ---- W3: universal search ----
    s = wb.search(VEHICLE, ADMIN)
    assert s["groups"]["vehicles"] and s["groups"]["vehicles"][0]["incidents"] == 10
    assert len(s["groups"]["vehicles"][0]["districts"]) == 4
    print(f"  W3 plate search: {s['groups']['vehicles'][0]} ({s['took_ms']}ms)")

    s2 = wb.search("Aayush", ADMIN)
    assert any(p["value"] == "Aayush Zachariah" for p in s2["groups"]["people"])
    s3 = wb.search("INC010001", ADMIN)
    assert s3["groups"]["cases"], "case-id search failed"
    s4 = wb.search("gold chain snatched sped away two-wheeler", ADMIN)
    assert s4["semantic"], "semantic search returned nothing"
    s5 = wb.search(VEHICLE, ETHICS)
    assert s5.get("note") and not s5["groups"]["vehicles"], "ethics not restricted"
    print(f"  W3 person/case/semantic/ethics: OK (semantic top: {s4['semantic'][0]['fir_no']})")

    # ---- W4: masking in dossier + search ----
    victim_cid = next(cid for cid, roles in wb.state()["canon_roles"].items()
                      if roles and roles <= {"victim", "witness"}
                      and wb.state()["canon_meta"][cid]["type"] == "person")
    true_val = wb.state()["canon_meta"][victim_cid]["value"]
    dv_admin = wb.dossier(victim_cid, ADMIN)
    dv_analyst = wb.dossier(victim_cid, ANALYST)
    assert dv_admin["value"] == true_val and dv_admin["masked"] is None
    assert dv_analyst["value"] != true_val and dv_analyst["masked"], "analyst saw victim identity"
    sv = wb.search(true_val.split()[0], ANALYST)
    leaked = [p for p in sv["groups"]["people"] if p["value"] == true_val
              and p["canonical_id"] == victim_cid]
    assert not leaked, "search leaked a victim identity to analyst"
    print(f"  W4 victim masking (dossier '{dv_analyst['value']}' for analyst; search clean): OK")

    # suspects stay visible to analysts (operational)
    dk_analyst = wb.dossier(KINGPIN, ANALYST)
    assert dk_analyst["value"] == "Aayush Zachariah", "suspect wrongly masked"
    print("  W4 suspect visible to analyst (pending-trial framing): OK")

    print("\nPASS")


def test_workbench():
    run()


if __name__ == "__main__":
    run()
