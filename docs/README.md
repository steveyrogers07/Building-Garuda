# docs/

All planning and design documents for Project GARUDA. **Start here, in this order:**

1. **[GARUDA_BLUEPRINT.md](GARUDA_BLUEPRINT.md)** — the master design: concept, winning thesis, 6-layer architecture, Catalyst service map, decided tech stack, database schema, per-engine ML methodology, governance/ethics, demo script, judging strategy, risks.
2. **[GARUDA_10_PHASE_PLAN.md](GARUDA_10_PHASE_PLAN.md)** — the gated execution plan (Phase 1 → 10) with subtasks, services, tests, and exit gates. **This is what you work through day to day.**
3. **[GARUDA_BUILD_WORKFLOW.md](GARUDA_BUILD_WORKFLOW.md)** — the Catalyst-native build steps with literal CLI/SDK commands (verified against Zoho docs).
4. **[GARUDA_DATA_READINESS.md](GARUDA_DATA_READINESS.md)** — how to be ready for the real KSP dataset (canonical data contract, adapter pattern, intake questions, "day the data arrives" runbook).

## diagrams/
- `architecture.svg` — 6-layer system architecture mapped to Catalyst services
- `runtime-flow.svg` — how a single FIR flows Ingest → Resolve → Analyze → Act
- `ten-phase-roadmap.svg` — the 10-phase march with exit gates
- `data-readiness.svg` — the adapter pattern (swap the data, not the code)
- `feature-priority.svg` — what to build vs. what to pitch
