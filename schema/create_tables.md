# GARUDA — Create the Data Store tables (Phase 2, Step 1)

Source of truth: [`canonical_schema.yaml`](canonical_schema.yaml). This is the
human-clickable version for the **Catalyst Console → Cloud Scale → Data Store →
Create Table**. (Catalyst Data Store table/column creation is a console operation;
the SDK writes *rows*, not schema. `ingestion/adapter/loader.py` loads rows once the
tables below exist.)

**Every table also auto-gets** `ROWID`, `CREATORID`, `CREATEDTIME`, `MODIFIEDTIME` —
don't add those. Table names: alphanumeric + underscore, no leading digit.

**FK note:** a Catalyst ForeignKey stores the referenced row's `ROWID`, which isn't
known at CSV time and can't be set by console Import. So `Incident_Edges` join columns
are **Text business keys** (`incident_id`, `entity_id`) referencing the business keys in
`Incidents`/`Entities`. ZCQL joins use those (see [smoke tests](#zcql-smoke-tests)).

---

## Create these first — CORE (Phase 2 populates them)

### Incidents
| Column | Type | Null? |
|---|---|---|
| incident_id | Text | no (unique) |
| fir_no | Text | no |
| occurred_at | DateTime | no |
| reported_at | DateTime | yes |
| district_code | Text | no |
| station_code | Text | yes |
| crime_type | Text | no |
| ipc_bns_code | Text | yes |
| lat | Decimal | yes |
| long | Decimal | yes |
| address_text | Text | yes |
| mo_text | Text | yes |
| status | Text | yes (denormalized from Case_Status.status_name) |
| case_category | Text | yes (FIR/UDR/PAR/Zero-FIR — CaseMaster.CaseCategoryID) |
| gravity | Text | yes (Heinous/Non-Heinous — CaseMaster.GravityOffenceID) |
| officer_id | Text | yes (→ Officers.officer_id — CaseMaster.PolicePersonID) |
| incident_to_date | DateTime | yes (CaseMaster.IncidentToDate) |
| info_received_ps_date | DateTime | yes (CaseMaster.InfoReceivedPSDate) |
| court_id | Text | yes (→ Courts.court_id — CaseMaster.CourtID, set once trial-eligible) |
| mo_cluster_id | Text | yes (Phase 4) |
| series_id | Text | yes (Phase 5) |
| source_fir_url | Text | yes |
| confidence | Decimal | yes |
| created_by | Text | yes |

### Entities
| Column | Type | Null? |
|---|---|---|
| entity_id | Text | no (unique) |
| canonical_id | Text | no |
| type | Text | no (person/vehicle/phone) |
| value | Text | no |
| alias_of | Text | yes |
| age | Int | yes |
| gender | Text | yes |
| match_confidence | Decimal | yes |

### Incident_Edges
| Column | Type | Null? |
|---|---|---|
| incident_id | Text | no (→ Incidents.incident_id) |
| entity_id | Text | no (→ Entities.entity_id) |
| role | Text | no (suspect/victim/witness/vehicle_used/phone_used) |
| edge_weight | Decimal | yes |
| evidence_type | Text | yes |
| is_police | Boolean | yes (Victim.VictimPolice — meaningful only when role = victim) |

### Socioeconomic
| Column | Type | Null? |
|---|---|---|
| area_code | Text | no (unique) |
| population | Int | yes |
| density | Decimal | yes |
| literacy | Decimal | yes |
| urbanization | Decimal | yes |

### Geo_Boundaries
| Column | Type | Null? |
|---|---|---|
| area_code | Text | no (unique) |
| level | Text | no (state/district/taluk) |
| polygon | Text | no (GeoJSON geometry as string) |

### Officers
*(organizer schema: Employee, narrowed to what the platform needs)*
| Column | Type | Null? |
|---|---|---|
| officer_id | Text | no (unique) |
| name | Text | no |
| rank | Text | yes (Constable..DySP) |
| designation | Text | yes (Investigating Officer/SHO/...) |
| district_code | Text | yes |
| unit_code | Text | yes (station) |
| kgid | Text | yes |
| dob | Date | yes |
| blood_group | Text | yes |
| appointment_date | Date | yes |

### Chargesheets
*(organizer schema: ChargesheetDetails — the clearance/conviction signal, blueprint §B1)*
| Column | Type | Null? |
|---|---|---|
| cs_id | Text | no (unique) |
| incident_id | Text | no (→ Incidents.incident_id) |
| cs_date | Date | yes |
| cs_type | Text | no (A=Chargesheet / B=False Case / C=Undetected) |
| officer_id | Text | yes (→ Officers.officer_id) |

### Arrests
*(organizer schema: ArrestSurrender, joined to Accused via inv_arrestsurrenderaccused)*
| Column | Type | Null? |
|---|---|---|
| arrest_id | Text | no (unique) |
| incident_id | Text | no (→ Incidents.incident_id) |
| entity_id | Text | no (→ Entities.entity_id — the accused) |
| event_type | Text | no (arrest/surrender) |
| event_date | Date | no |
| district_code | Text | yes |
| court_id | Text | yes (→ Courts.court_id — production court) |
| io_officer_id | Text | yes (→ Officers.officer_id) |
| is_accused | Boolean | yes (primary vs co-accused) |
| is_complainant_accused | Boolean | yes (rare cross-role/false-case signal) |

### Case_Sections
*(organizer schema: ActSectionAssociation → Act.ActCode + Section.SectionCode, one-to-many)*
| Column | Type | Null? |
|---|---|---|
| incident_id | Text | no (→ Incidents.incident_id) |
| act_code | Text | no (IPC/BNS/IT_ACT) |
| section_code | Text | no |
| section_order | Int | no (1 = primary/most serious, matches Incidents.ipc_bns_code) |
| act_order | Int | no (orders the ACT, distinct from section_order) |

### Courts
*(organizer schema: Court)*
| Column | Type | Null? |
|---|---|---|
| court_id | Text | no (unique) |
| name | Text | no |
| district_code | Text | yes |
| state_code | Text | yes |

### Case_Status
*(organizer schema: CaseStatusMaster — reference-only; Incidents.status denormalizes status_name)*
| Column | Type | Null? |
|---|---|---|
| status_code | Text | no (unique) |
| status_name | Text | no |

### Crime_Head_Sections
*(organizer schema: CrimeHeadActSection — the 2-level crime classification's reference map)*
| Column | Type | Null? |
|---|---|---|
| crime_head | Text | no |
| act_code | Text | no |
| section_code | Text | no |

---

## Create now but leave EMPTY — DERIVED (filled in later phases)

Create with the columns in [`canonical_schema.yaml`](canonical_schema.yaml); do **not**
populate in Phase 2.

- **MO_Clusters** (Phase 4) · **Crime_Series** (Phase 5) · **Predictive_Risk** (Phase 6)
  · **Alerts** (Phase 5/6) · **Review_Queue** (Phase 3) · **Audit_Log** (Phase 9)

---

## Load order

Tables must exist before loading. Then load with the adapter (parents before edges):

```bash
python ingestion/adapter/loader.py --source data/synthetic/incidents.csv      --map ingestion/adapter/column_map.synthetic.yaml --table Incidents
python ingestion/adapter/loader.py --source data/synthetic/entities.csv       --map ingestion/adapter/column_map.synthetic.yaml --table Entities
python ingestion/adapter/loader.py --source data/synthetic/incident_edges.csv --map ingestion/adapter/column_map.synthetic.yaml --table Incident_Edges
python ingestion/adapter/loader.py --source data/reference/socioeconomic.csv  --map ingestion/adapter/column_map.synthetic.yaml --table Socioeconomic
python ingestion/adapter/loader.py --source data/reference/geo_boundaries.csv --map ingestion/adapter/column_map.synthetic.yaml --table Geo_Boundaries
```

(Reference CSVs: `census_2011.csv` is mapped to `Socioeconomic`; `geo_boundaries.csv`
to `Geo_Boundaries`. The loader writes in batches and respects `--limit` for dev-tier
row quotas.)

---

## ZCQL smoke tests

```sql
SELECT COUNT(ROWID) FROM Incidents;
SELECT crime_type, COUNT(ROWID) FROM Incidents GROUP BY crime_type;

-- JOIN on business keys (matches how the loader writes the data)
SELECT Incidents.crime_type, Entities.value
FROM Incidents
JOIN Incident_Edges ON Incident_Edges.incident_id = Incidents.incident_id
JOIN Entities       ON Entities.entity_id = Incident_Edges.entity_id
LIMIT 20;

-- Planted network: the shared phone/vehicle should link incidents across >=3 districts.
-- Use the values printed in data/synthetic/ground_truth.json (network.shared_phone / shared_vehicle).
SELECT DISTINCT Incidents.district_code
FROM Incidents
JOIN Incident_Edges ON Incident_Edges.incident_id = Incidents.incident_id
JOIN Entities       ON Entities.entity_id = Incident_Edges.entity_id
WHERE Entities.value = '<shared_phone_from_ground_truth>';
```
