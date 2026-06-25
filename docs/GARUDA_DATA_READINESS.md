# GARUDA — Data-Readiness Plan
How to build the whole platform NOW, before the real KSP dataset arrives, so that integrating it later is a mapping change — not a rebuild.

## Principle: build data-agnostic behind an adapter
- Develop against **synthetic data shaped like the expected KSP schema**.
- Put every format-specific detail (column names, encodings, joins) in **one loader module** (`/ingestion/adapter`).
- Everything downstream (engines, models, frontend) reads only the **canonical schema**.
- When real data lands: rewrite the **column-map config**, run profiling + validation, reload. Nothing else changes.

## The canonical data contract (build against this)
Required = the hero/core needs it. Optional = enrich if present, else fallback.

| Canonical field | Type | Required? | Fallback if missing |
|---|---|---|---|
| incident_id / fir_no | string | required | generate surrogate key |
| occurred_at (date+time) | datetime | required | use report date; flag low confidence |
| district_code | string | required | map from station; else "unknown" |
| station_code | string | optional | district-level only |
| crime_type | string | required | map from IPC/BNS code |
| ipc_bns_code | string | optional | infer from crime_type text |
| lat / long | float | optional | **geocode** from address/area via gazetteer |
| address_text / area | string | optional | district centroid |
| status | string | optional | "unknown" |
| mo_text / narrative | text | optional (boosts MO + copilot) | structured features only |
| person.name | string | optional (**enables network hero**) | fall back to crime-series linkage |
| person.role | enum(suspect/victim/witness) | optional | infer from column context |
| person.age / gender | — | optional | omit from socio features |
| phone / vehicle | string | optional (**strong link signals**) | rely on name + MO |
| property_value / weapon | — | optional | omit |

Canonical tables stay as defined in the blueprint: `Incidents`, `Entities`, `Incident_Edges`, plus derived (`MO_Clusters`, `Crime_Series`, `Predictive_Risk`, `Alerts`, `Review_Queue`, `Audit_Log`, `Socioeconomic`, `Geo_Boundaries`).

## What the real KSP dataset probably looks like (so the synthetic mimics it)
- **Most likely record-level** (incidents + accused + victims), CCTNS-style: FIR no, dates, district, police station, crime head / IPC-BNS sections, location text, investigation status; accused with name/age/gender/address; victim (often masked) with age/gender; possibly property/weapon/MO notes; Kannada + English text (Unicode).
- **Possibly aggregated** (NCRB/open-data style): counts by district × crime-type × period — no individuals.
- Build the synthetic generator to emit the **record-level** contract (richest case), but keep an **aggregated fallback path** in the adapter.

## Prepare NOW — checklist (no data required)
1. ☐ Lock the canonical schema in Catalyst Data Store.
2. ☐ Build the **synthetic generator** → emits the canonical contract + realistic patterns + the planted cross-district network/series/anomalies.
3. ☐ Build the **adapter/loader**: source file → column-map (config) → validate → canonical → bulk insert. Make the column-map a JSON/YAML config, not code.
4. ☐ Build a **profiling/EDA notebook** that runs on *any* incoming file: row counts, dtypes, % missing, cardinality, date range, district coverage, candidate join keys, likely PII columns.
5. ☐ Build a **validation gate**: schema check, null/required checks, duplicate FIRs, invalid dates/coords, code-mapping coverage, encoding check.
6. ☐ Build **all engines + frontend against the synthetic data** so the whole thing works end-to-end before real data.
7. ☐ Prepare the **IPC↔BNS mapping table** and the **Karnataka gazetteer + GeoJSON** for geocoding.
8. ☐ **Parameterize** district list, crime types, grid size, time bins via config — never hardcode.

## The day the dataset arrives — runbook
1. **Profile** (30–60 min): run the EDA notebook → learn granularity, fields, missingness, joins.
2. **Answer the intake questions** (below).
3. **Map**: fill in the adapter's column-map config (source → canonical).
4. **Validate**: run the gate on a sample; triage issues.
5. **Load**: adapter → Data Store (sample first, then full).
6. **Re-point** engines from synthetic → real (one flag); re-run entity resolution, MO clustering, forecasts, network build, anomaly scan.
7. **Sanity-check + tune** thresholds (resolution confidence, cluster sizes, forecast backtest).
8. **Demo decision**: if real data has clean person links, demo the hero on it; if not, run hotspots/trends/forecast on real data and keep the **synthetic planted-network** for the relational reveal — disclosed as a representative scenario.

## Dataset intake questions (answer first)
- Granularity: record-level (incident/person) or **aggregated counts**?
- Person identifiers linking offenders/victims across FIRs? → decides if the **network hero** works on real data.
- Geospatial: lat/long, or only district/station/address? → geocoding need.
- Temporal: occurrence date/time present? what range?
- Codes: IPC, BNS, or NCRB categories? mapping needed?
- PII: real names/victims present? → masking obligations (228A/POCSO).
- Format/size/encoding (Excel/CSV; Kannada Unicode)?
- Join keys between incident / offender / victim tables?

## Contingency — what each data shape means for the hero
| Real data shape | Hero becomes |
|---|---|
| Person-level links present | Full **co-offender network** (best case) |
| Incident-level only | **MO fingerprinting + crime-series linkage** |
| Aggregated only | **Forecasting + anomaly**; keep synthetic for the network demo |
