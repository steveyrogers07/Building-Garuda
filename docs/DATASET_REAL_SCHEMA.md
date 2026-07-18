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
| `Incidents.case_category` **[BUILT]** | `CaseMaster.CaseCategoryID` → `CaseCategory.LookupValue` (FIR/UDR/PAR/Zero-FIR) |
| `Incidents.gravity` **[BUILT]** | `CaseMaster.GravityOffenceID` → `GravityOffence.LookupValue` (Heinous/Non-Heinous) |
| `Incidents.officer_id` → `Officers` **[BUILT]** | `CaseMaster.PolicePersonID` → `Employee` (narrowed to Rank/Designation/posting — see `schema/canonical_schema.yaml`) |
| `Chargesheets` (`cs_id, incident_id, cs_date, cs_type, officer_id`) **[BUILT]** | `ChargesheetDetails` (CSID, csdate, cstype A/B/C, PolicePersonID) |
| `Arrests` (`arrest_id, incident_id, entity_id, event_type, event_date, district_code, court_id, io_officer_id, is_accused, is_complainant_accused`) **[BUILT]** | `ArrestSurrender` (→ Accused via `inv_arrestsurrenderaccused`, IOID→Employee, CourtID, IsAccused, IsComplainantAccused) |
| `Case_Sections` (`incident_id, act_code, section_code, section_order, act_order`) **[BUILT]** | `ActSectionAssociation` → `Act.ActCode` + `Section.SectionCode` (one-to-many, ActOrderID/SectionOrderID) |
| `Incidents.incident_to_date` / `info_received_ps_date` **[BUILT]** | `CaseMaster.IncidentToDate` / `InfoReceivedPSDate` |
| `Incidents.court_id` + `Courts` (`court_id, name, district_code, state_code`) **[BUILT]** | `CaseMaster.CourtID` → `Court` (also referenced by `Arrests.court_id`) |
| `Incident_Edges.is_police` **[BUILT]** | `Victim.VictimPolice` (meaningful only when `role == victim`) |
| `Officers.kgid/dob/blood_group/appointment_date` **[BUILT]** | `Employee.KGID/EmployeeDOB/BloodGroupID/AppointmentDate` |
| `Case_Status` (`status_code, status_name`) **[BUILT]** | `CaseStatusMaster` — reference-only; `Incidents.status` stays denormalized text |
| `Crime_Head_Sections` (`crime_head, act_code, section_code`) **[BUILT]** | `CrimeHeadActSection` — reference map, derived from crime_types + companions |
| `Incidents.crime_no` / `case_no` **[BUILT 2026-07-17]** | `CaseMaster.CrimeNo`/`CaseNo` in the organizer's exact 18-digit format (1 category + 4 district + 4 unit + 4 year + 5 serial; separate serial per station × category × year). Searchable via `/search` (any ≥6-digit fragment); shown on the CaseFile register head |
| `Incident_Edges` role `complainant` **[BUILT 2026-07-17]** | `ComplainantDetails` (one-to-many off CaseMaster; ~60% of complainants are the victim filing their own FIR). Masked like victims (`masking.VICTIM_ROLES`) |
| `Units` (`unit_id, unit_name, unit_type, parent_unit, district_code, district_num, station_code, lat, long`) **[BUILT 2026-07-17]** | `Unit` + `UnitType` — the station/office hierarchy (self-referencing `parent_unit`); its numeric ids are the CrimeNo segments; centroids power `/geo/stations` drill-down |

## Deliberately not modeled (decisions, not gaps)

| Organizer column/table | Why excluded |
|---|---|
| `ComplainantDetails.OccupationID/ReligionID/CasteID` (+ their master tables) | **Ethics/fairness by design**: GARUDA profiles places and times, never communities. Caste/religion-keyed analytics in a policing tool invites the exact bias the fairness audit exists to catch. Stated in the submission. |
| `Accused.PersonID` (A1/A2 per-case ordering) | Per-case display ordering, not a global identity — entity resolution supersedes it |
| `State` master / `Employee.PhysicallyChallenged/GenderID` | Single-state deployment; HR attributes with no analytical surface |
| `Rank`/`Designation`/`UnitType` as separate masters | Flattened to text on `Officers`/`Units` — lookup tables with stable vocabularies |
| `Inv_OccuranceTime` (1:1 off CaseMaster) | Flattened into `Incidents.occurred_at/incident_to_date/lat/long` |
| `inv_arrestsurrenderaccused` junction | Flattened: one `Arrests` row per (incident, entity) |

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
4. **Legal sections** come from `ActSectionAssociation` (many per case) — **[BUILT]** the
   `Case_Sections` table now retains every act+section (`section_order` 1 = the
   primary/most-serious, which is what `ipc_bns_code` continues to hold).
5. **Geo:** `latitude`/`longitude` are present on `CaseMaster` → our geocoder is a fallback,
   not the primary path, on real data.
6. **Outcomes** (`ChargesheetDetails`, `CaseStatus`) — **[BUILT]** the District Command Card
   (blueprint §B1, `app/engines/district.py`) computes clearance rate = A / (A+B+C) from
   `Chargesheets.cs_type` per district, plus backlog aging and an officer leaderboard, via
   `GET /district/{code}/command` and `GET /district/rank`. **[BUILT]** `ArrestSurrender` is
   modeled as `Arrests` — the statutory chargesheet-deadline tracker and absconding board
   ([08 — Field-Officer Intelligence §1/§6/§9](product/08-FIELD-OFFICER-INTELLIGENCE.md))
   now have their event source.

## Adapter checklist (Phase-2 column-map, when the extract lands)
Run `docs/GARUDA_DATA_READINESS.md` runbook → set the column-map to the table above →
`python ingestion/adapter/validate.py` → load → re-run the engine tests. No engine code changes.
