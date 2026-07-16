# GARUDA — your minimal console checklist (click-follow, ~25 min once)

You do NOT need to understand the schema. Zoho only lets a logged-in human
create *containers* (tables, buckets, segments); the app fills and uses them
by itself afterwards. Everything below is one-time.

Console: https://console.catalyst.zoho.in → project **Garuda-system** →
environment **Development** (top-right switcher — NOT "project rainfall").

## Step 1 — create 19 empty tables (Cloud Scale → Data Store → Create Table)

Create each table below by name, then add its columns — the exact column
names/types to copy are in [schema/create_tables.md](../schema/create_tables.md)
(each table is a small copy-paste list; skip ROWID etc., Catalyst adds those).
Just names first, in this order:

Incidents · Entities · Incident_Edges · Case_Sections · Arrests ·
Chargesheets · Officers · Courts · Case_Status · Crime_Head_Sections ·
Socioeconomic · Geo_Boundaries · Console_Users · MO_Clusters · Crime_Series ·
Predictive_Risk · Alerts · Review_Queue · Audit_Log

(The last 6 stay empty — the app writes into them at runtime.)

## Step 2 — create 2 buckets (Cloud Scale → Stratus)

`raw-fir` and `briefs`. Defaults are fine.

## Step 3 — enable Cache (Cloud Scale → Cache)

Just enable it / open it once so the default segment exists. Nothing to configure.

## Step 4 — deploy the functions (your terminal, one command)

    cd C:\Users\hp\Desktop\garuda3
    catalyst deploy --only functions

## Step 5 — Job Scheduling (Serverless → Job Scheduling)

1. Create a **Function Job Pool** (defaults fine).
2. Create job `garuda-nightly`, target = function `jobs`, param `kind=nightly`,
   cron daily **02:00 IST**.
3. Create job `garuda-weekly`, target = function `jobs`, param `kind=weekly`,
   cron Monday **08:00 IST**.

## Step 6 — tell Claude "console done"

The app then finishes the rest ITSELF — no ds:import needed:

- `GET  /admin/provision`       → shows anything you missed
- `POST /admin/provision/load`  → bulk-loads all 13 data tables from the CSVs
                                  already bundled inside the deployment
- Claude verifies, flips `GARUDA_WRITE_BACKEND=zcql` + `GARUDA_NOTIFY=catalyst`,
  you run one final `catalyst deploy appsail --name garuda-brain`.

## Later (separate sittings, also guided)

- **Authentication** (enable email sign-in) + **API Gateway** (routing/throttle)
  — the real-login hardening.
- **Pipelines** (connect the GitHub repo — CI + auto-deploy).
- **Circuits** (bind `ingestion/circuits/fir_ingest.json`) + the Stratus
  trigger on `raw-fir` → live FIR-scan ingestion.
