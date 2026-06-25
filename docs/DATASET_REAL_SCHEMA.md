# GARUDA — Real Dataset Schema (organizer-provided)

> Source of truth for the **real-data swap**: the Karnataka Police Department's
> official **Police FIR System — ER Diagram** (confidential), provided by the
> Datathon organizers. PDF: [`docs/Police_FIR_ER_Diagram.pdf`](Police_FIR_ER_Diagram.pdf).
> We build/verify on synthetic data (Phase 2 generator) today; when the real
> extract arrives, the Phase-2 adapter's column-map targets the columns below —
> **no engine changes** (the whole point of the canonical schema).

## Source tables (relational, SQL Server-style)

**`CaseMaster`** — the FIR spine (one row per case). Key columns:
`CaseMasterID` (PK), `CrimeNo`, `CaseNo`, `CrimeRegisteredDate`,
`IncidentFromDate`/`IncidentToDate`, `InfoReceivedPSDate`, `latitude`, `longitude`,
`BriefFacts` (Nvarchar(Max) — the narrative), and FKs:
`PolicePersonID`→Employee, `PoliceStationID`→Unit, `CaseCategoryID`→CaseCategory,
`GravityOffenceID`→GravityOffence, `CrimeMajorHeadID`→CrimeHead,
`CrimeMinorHeadID`→CrimeSubHead, `CaseStatusID`→CaseStatusMaster, `CourtID`→Court.

**Parties (all FK → `CaseMaster.CaseMasterID`, one-to-many):**
- `ComplainantDetails` — ComplainantName, AgeYear, GenderID, + OccupationID/ReligionID/CasteID.
- `Victim` — VictimName, AgeYear, GenderID, VictimPolice.
- `Accused` — AccusedName, AgeYear, GenderID, `PersonID` (sort label A1, A2, …).
- `ArrestSurrender` — arrest/surrender events → Accused (via junction `inv_arrestsurrenderaccused`), Officer (IOID→Employee), Court, State/District.

**Legal classification:**
- `ActSectionAssociation` (FK CaseMaster) → `Act.ActCode` + `Section.SectionCode` (the IPC/BNS/NDPS sections invoked).
- `Act`, `Section` (Section FK→Act). `CrimeHead` (major head e.g. "Crimes Against Body") → `CrimeSubHead` (e.g. Murder, Robbery). `CrimeHeadActSection` maps heads ↔ act-sections.

**Masters / lookups:** `CaseCategory` (FIR/UDR/PAR/Zero-FIR), `GravityOffence`
(Heinous/Non-Heinous), `CaseStatusMaster`, `Court`, `State`, `District`, `Unit`
(police station; self-referencing `ParentUnit`), `UnitType`, `Rank`, `Designation`,
`Employee` (officers), `CasteMaster`, `ReligionMaster`, `OccupationMaster`.
`ChargesheetDetails` (CSID, csdate, cstype A=Chargesheet/B=False/C=Undetected).
`Inv_OccuranceTime` — 1:1 with CaseMaster (occurrence time/location).

## `CrimeNo` format (decodable keys, no joins needed)

`1 Case-Category + 4 District + 4 Unit(Station) + 4 Year + 5 Serial` (18 digits).
Example `104430006202600001` → category `1` (FIR), district `0443`, station `0006`,
year `2026`, serial `00001`. (UDR=3, Zero-FIR=8, PAR=4.) `CaseNo` = last 9 digits.

## Mapping → our canonical schema (`schema/canonical_schema.yaml`)

| Canonical (ours) | Real source |
|---|---|
| `Incidents.incident_id` | `CaseMaster.CaseMasterID` (business key: `CrimeNo`) |
| `Incidents.fir_no` | `CaseMaster.CrimeNo` |
| `Incidents.occurred_at` | `CaseMaster.IncidentFromDate` (→`IncidentToDate`) |
| `Incidents.reported_at` | `CrimeRegisteredDate` / `InfoReceivedPSDate` |
| `Incidents.district_code` | decode `CrimeNo` digits 2–5, or `Unit→District` |
| `Incidents.station_code` | `PoliceStationID` (`Unit.UnitID`) |
| `Incidents.crime_type` | `CrimeSubHead.CrimeHeadName` (+ `CrimeHead` group) |
| `Incidents.ipc_bns_code` | `ActSectionAssociation` (`Act.ActCode`+`Section.SectionCode`) |
| `Incidents.lat` / `long` | `latitude` / `longitude` |
| `Incidents.mo_text` / `address_text` | `BriefFacts` |
| `Incidents.status` | `CaseStatusMaster.CaseStatusName` |
| `Entities` (person) + `Incident_Edges` | `Complainant`/`Victim`/`Accused` rows → role = complainant/victim/suspect; `value`=Name, `age`=AgeYear, `gender`=GenderID |

## Implications for our pipeline (important)

1. **No structured phone/vehicle in the source.** There are no phone/vehicle tables —
   they live inside `BriefFacts` free text. Our **co-offender network's shared
   phone/vehicle links depend on the Phase-3 NER/extraction** over `BriefFacts`. This is
   the single biggest dependency for the hero reveal on real data; keep the extractor
   strong (and bilingual — narratives may be Kannada).
2. **Accused/Complainant/Victim are the structured persons** → resolve to canonical
   entities (Phase 4); `Accused.PersonID` (A1/A2…) is per-case ordering, not a global id.
3. **Crime type is a two-level hierarchy** (`CrimeHead`→`CrimeSubHead`). Map our 16
   synthetic crime types onto `CrimeSubHead`; keep the head for rollups.
4. **Legal sections** come from `ActSectionAssociation` (many per case) — our single
   `ipc_bns_code` should become the primary/most-serious section, with the rest retained.
5. **Geo:** `latitude`/`longitude` are present on `CaseMaster` → our geocoder is a fallback,
   not the primary path, on real data.
6. **Outcomes available** (`ChargesheetDetails`, `ArrestSurrender`, `CaseStatus`) — future
   signal for Phase 6 (detection/clearance) and Phase 9 governance.

## Adapter checklist (Phase-2 column-map, when the extract lands)
Run `docs/GARUDA_DATA_READINESS.md` runbook → set the column-map to the table above →
`python ingestion/adapter/validate.py` → load → re-run the engine tests. No engine code changes.
