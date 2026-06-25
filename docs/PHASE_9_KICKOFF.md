# GARUDA — Phase 9 Kickoff (paste into a fresh build chat)

> Fresh build session for **Phase 9** of GARUDA. Read fully, execute step by step, don't jump ahead.

## Context
**GARUDA** — AI crime-analytics for Karnataka SCRB, Datathon 2026, on Zoho Catalyst.
- Repo: https://github.com/steveyrogers07/Building-Garuda · Local: `…/Building-Garuda`
- Read: `docs/GARUDA_BLUEPRINT.md` (§ governance, automation), `docs/CATALYST_CREDITS_AND_DEPLOYMENT.md` (**Job Scheduling NOT Cron; LLM serving OFF except demo**), the P1–3 runbooks (Stratus, functions, Signals).
- Stack: **Job Scheduling** · **Signals + Event Functions** · **Push** · **Mail** · **SmartBrowz** · API Gateway · Cache · Auth.

## Dependency — config in parallel, wire after engines
The governance layer (audit/RBAC/masking, Cache, throttling) can be built anytime. The scheduled recompute + alerts **wire to the P4/P5/P6 engines**, so finish those (or stub them) before the live cron/alert tests.

## Convention
Most pieces testable in Dev; this phase touches a few production-ish services — still **keep QuickML LLM serving OFF**. Produce `docs/PHASE_9_RUNBOOK.md`.

## Goal
The proactive loop + production-grade safety: nightly recompute, real-time spike alerts, scheduled intelligence brief, and full governance (audit, PII masking, RBAC).

## Exit Gate (✅ local · ⧖ live)
- [ ] **G1** **Job Scheduling** job pool + pre-defined crons: **nightly recompute** (resolution/MO/forecast/anomaly/network refresh) + **weekly brief**. ⧖
- [ ] **G2** Anomaly job writes `Alerts` → emits a **Signal** → Event Function sends **Push + Mail** to the district officer. ⧖
- [ ] **G3** **SmartBrowz** renders the dashboard → PDF → **Stratus** → **Mail** to the DGP (weekly). ⧖
- [ ] **G4** **Audit_Log middleware** on every record read; **field-level PII masking** by role (victim masking — IPC 228A / POCSO). ✅(logic) / ⧖(enforced)
- [ ] **G5** **RBAC** enforced (SCRB-admin/district/station); **API Gateway** throttling; **Cache** wraps expensive engine outputs; ingestion is idempotent + retried. ✅/⧖

## Prerequisites
Engines from P4–P6 available (or stubbed). Catalyst project (P1) live for the account-gated wiring.

## Steps
1. **Scheduling:** create a Function/AppSail **Job Pool**; pre-defined crons — nightly 02:00 batch (`/resolve/run`,`/mo/run`,`/forecast`,`/anomaly`,`/network/run`), weekly Mon 08:00 brief. (Dynamic crons via SDK if needed.)
2. **Alerts:** anomaly run → write `Alerts` → emit **Signal** → Event Function → **Push Notification** + **Mail**.
3. **Brief:** cron → job → function triggers **SmartBrowz** (headless render of dashboards) → PDF → Stratus → **Mail**.
4. **Governance:** Audit_Log middleware (who read what); role-based **field masking** of victim PII; enforce **RBAC** on every API; **API Gateway** throttling; **Cache** the hot aggregations/subgraphs; idempotency + retries on ingestion.
5. **Verify:** manually fire the cron once → recompute runs; trip a synthetic spike → Push+Mail arrive; weekly PDF emailed; confirm a `station` role can't read masked victim fields.

## Gotchas
**Job Scheduling, not Cron** (Cron is EOL). Keep **LLM serving OFF** (precompute via the nightly job; cache for the demo). Most of this is testable in Dev; mind credits once anything runs in Production (see the credits doc).

## Out of scope
The engines (P4–6) and UI (P8) — this phase automates + secures them.

## When done
`feat/phase-9-hardening` → PR → `main`; write `docs/PHASE_9_RUNBOOK.md`.
