# data/ — Synthetic dataset & reference data (Phase 2)

Local tooling (not deployed). Lets us build the entire platform **before** the real KSP dataset arrives.

## Subfolders
- `synthetic/` — the **synthetic data generator** (Python). Emits the canonical schema with realistic patterns (crime-type mix, time-of-day, festival/payday spikes, mixed IPC/BNS codes, Kannada/English alias variants) **plus a planted cross-district network + near-repeat series + anomaly spikes** for the demo's "aha". Output CSVs are git-ignored.
- `gazetteer/` — Karnataka place-name → lat/long lookup for geocoding.
- `reference/` — district/taluk **GeoJSON** boundaries, Census 2011 demographics, **IPC↔BNS** offense mapping table.
- `notebooks/` — the **profiling/EDA notebook** (runs on *any* incoming file: row counts, dtypes, % missing, cardinality, date range, join keys, likely PII) and the **validation gate**.

## When the real data arrives
Run the profiling notebook → answer the intake questions → update `ingestion/adapter/` column-map → re-run. See the data-readiness runbook.
