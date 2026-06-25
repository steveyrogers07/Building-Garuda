# functions/ — Catalyst Serverless (Node.js) — Track A · Phases 3, 9

Lightweight Node functions. **Event functions are Node/Java only** (not Python) — so this is the *glue* that reacts to events and calls the Python ML brain in `app/`.

## Subfolders
- `api/` — **Advanced I/O** function(s): REST endpoints for the frontend (auth-gated reads, simple CRUD via ZCQL). Heavy ML is proxied to AppSail.
- `ingest-event/` — **Event function**: triggered by a **Signal** when a file lands in the `raw-fir` Stratus bucket. Runs OCR (Zia), calls AppSail `/extract`, geocodes, writes to `Review_Queue`. (Phase 3)
- `jobs/` — **Job functions**: targets for **Job Scheduling** crons — nightly recompute (forecast/anomaly/network) and the weekly intelligence brief. (Phase 9)

## Notes
- Init the SDK with the function context: `const app = catalyst.initialize(context)`.
- Query the Data Store with ZCQL via the Node SDK.
- Keep these thin; push real computation to `app/` (AppSail).
