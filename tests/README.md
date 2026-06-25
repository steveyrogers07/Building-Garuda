# tests/ — Quality gates (Phase 10 + continuous)

Each of the 10 phases has an **exit gate** that is itself a test — so quality is verified continuously, not just at the end. This folder holds the automated suite.

## Subfolders
- `unit/` — per-engine tests: entity-resolution precision/recall on labeled synthetic pairs; MO cluster sanity; anomaly detection on planted spikes; copilot citation accuracy.
- `integration/` — pipeline tests: Stratus upload → OCR → extract → Review_Queue → Incidents; AppSail endpoints against the Data Store.
- `e2e/` — the full demo flow (ingest → map → network reveal → why → copilot → brief), plus a load test of the demo path.

## Key metrics to assert (see the blueprint)
Entity-resolution precision · forecast **PAI/PEI** vs. baseline + PR-AUC · copilot citation accuracy · fairness disparity per ward.

## Real-data swap rehearsal (Phase 10)
Run the data-readiness runbook on a real-shaped sample to prove the adapter works before the real dataset is integrated.
