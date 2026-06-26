# GARUDA — Phase 9 (Automation, Governance & Hardening) Runbook

> Goal: the **proactive loop** (nightly recompute, spike alerts, scheduled brief) +
> **production-grade safety** (audit, RBAC, field-level PII masking, cache,
> idempotency). The trust layer the product blueprint leans on.

Same split as P2–P8: the **governance + automation logic is built and locally verified**
(branch `feat/phase-9-hardening`); the **Catalyst triggers/dispatch** (Job Scheduling cron,
Signal→Push/Mail, SmartBrowz PDF, API-Gateway throttling) are the deferred account-gated wiring.
Everything local runs at **$0**.

---

## 0. What's built (locally verified)

| Area | Files | Status |
|---|---|---|
| RBAC (roles, scopes, jurisdiction filter, authorization) | [app/governance/rbac.py](../app/governance/rbac.py) | ✅ |
| PII masking (victim/witness by role; **IPC 228A / POCSO** hard-mask) | [app/governance/masking.py](../app/governance/masking.py) | ✅ |
| Audit trail | [app/governance/audit.py](../app/governance/audit.py) + `store.read/write_audit_log` | ✅ |
| Intelligence-brief assembly + HTML render | [app/automation/briefs.py](../app/automation/briefs.py) | ✅ (SmartBrowz→PDF ⧖) |
| Alert → notification routing | [app/automation/notify.py](../app/automation/notify.py) | ✅ (Signal/Push/Mail send ⧖) |
| Scheduled-job orchestration | [app/automation/jobs.py](../app/automation/jobs.py) | ✅ (cron trigger ⧖) |
| TTL cache | [app/shared/cache.py](../app/shared/cache.py) | ✅ (Catalyst Cache ⧖) |
| Governed API + parties/audit/brief reads | [app/routers/analytics.py](../app/routers/analytics.py) | ✅ |
| Local runner | [app/run_phase9.py](../app/run_phase9.py) | ✅ |
| Eval | [tests/test_governance.py](../tests/test_governance.py) | ✅ all gates green |

**Verified** (`python tests/test_governance.py`, and `python app/run_phase9.py`):
- **Masking** on FIR `INC000003` (district BNR): admin & owning-district see "Ekalinga Sandal";
  analyst & out-of-jurisdiction station see "E. S."; under **IPC-228A/POCSO** even own-district is
  masked, only admin sees the identity. Suspects are framed ("pending trial"), never masked.
- **RBAC:** a `district:BNR` principal sees 247 / 10,130 incidents; `ethics` is denied incident PII;
  `analyst` is denied canonical writes.
- **Automation:** nightly recompute refreshed network/series/anomaly/forecast; weekly brief = 6
  sections → `intelligence_brief.html`; 6 high-severity alerts → push+mail notifications.
- **Audit:** every governed read appends to `Audit_Log`.

---

## 1. Exit gates

| Gate | What | Status |
|---|---|---|
| **G1** | Job Scheduling job pool + crons (nightly recompute, weekly brief) | ✅ logic / ⧖ cron |
| **G2** | anomaly → `Alerts` → Signal → Push + Mail to district officer | ✅ routing / ⧖ send |
| **G3** | SmartBrowz dashboard → PDF → Stratus → Mail (weekly) | ✅ brief+HTML / ⧖ render+mail |
| **G4** | Audit_Log on every read; **field-level PII masking** (228A/POCSO) | ✅ |
| **G5** | RBAC enforced; API-Gateway throttling; Cache hot ops; ingestion idempotent | ✅ / ⧖ gateway |

---

## 2. Governance model

- **Roles → scopes:** `scrb-admin` (state) · `district:<code>` · `station:<code>` · `analyst`
  (read-all, **PII-masked**) · `case-officer` (assigned) · `ethics` (audit/fairness/model-cards only).
- **Jurisdiction filter:** every incident list is filtered to the principal's scope
  (`rbac.jurisdiction_filter`); district/station out-of-jurisdiction reads are `403`.
- **PII masking (`masking.mask_parties`)** at the API boundary (never in the store):
  - victim/witness person → initials (`A. Z.`), age dropped; phone → `●●●●●●1234`.
  - visible only to admin + the incident's own district/station (analysts always masked).
  - **IPC 228A (sexual offences) / POCSO (minors):** identity withheld from *everyone* except
    `scrb-admin` / `case-officer`, regardless of jurisdiction (`PROTECTED_CRIMES`, config-driven).
  - suspects/accused are **never** masked but annotated "as recorded, pending investigation/trial."
- **Audit (`audit.record`):** `{log_id, actor, role, action, resource, query, ts, ip}` per privileged
  read → `Audit_Log`; readable only by admin/ethics via `GET /audit`.

## 3. The proactive loop (automation)

- **Nightly recompute** (`jobs.nightly_recompute`): refresh resolution/MO/network/series/anomaly/
  forecast; results cached. Triggered by **Job Scheduling** 02:00 in prod; `run_phase9.py` locally.
- **Spike alerts** (`notify`): anomaly `Alerts` → `notification_for` (recipient by district, severity
  → channels) → **Signal → Event Function → Push + Mail** (send is account-gated).
- **Weekly brief** (`briefs`): assemble sections (situation, top ring, alerts, series, forecast,
  fairness note) → `render_html` → **SmartBrowz** PDF → Stratus → **Mail** to the DGP.

## 4. REST contract (governed)

| Method · Route | Auth | Returns |
|---|---|---|
| `GET /governed/incidents` | any (scope-filtered) | incidents in the caller's jurisdiction (audited) |
| `GET /case/{id}/parties` | not ethics; in-jurisdiction | FIR parties with victim/witness PII masked by role |
| `GET /audit` | admin / ethics only | recent audit entries |
| `POST /brief/run` | scheduled/admin | assembled intelligence brief + HTML size |

Principal is supplied via `X-Actor` / `X-Role` / `X-Scope` headers locally; the **Catalyst Web SDK +
API Gateway** provide it in prod. Example:
`curl -H "X-Role: station" -H "X-Scope: BNU03" /case/INC000003/parties` → victim masked.

## 5. Account-gated wiring (when the Dev project is live)

1. **Job Scheduling:** create a Job Pool; pre-defined crons → call `nightly_recompute` tasks (02:00)
   and `weekly_brief` (Mon 08:00). (Dynamic crons via SDK if needed.) **Not the EOL Cron service.**
2. **Signals + Event Functions:** anomaly job emits a Signal on new `Alerts`; the event function calls
   **Push** + **Mail** with the `notify` envelope.
3. **SmartBrowz:** headless-render the dashboard/brief HTML → PDF → **Stratus** → **Mail**.
4. **API Gateway:** enforce auth + **throttling**; map `/v1/*` to the AppSail brain.
5. **Cache:** back `shared/cache.py` keys with the Catalyst **Cache** service (hot rings/risk/stats).
6. **Idempotency/retries:** ingestion dedupes by `source_fir_url`; promote is INSERT-OR-REPLACE on the
   business key; circuit steps retry → dead-letter.

## 6. Gotchas / notes

- **Job Scheduling, not Cron** (Cron is EOL). · **Keep QuickML LLM serving OFF** — the nightly job
  precomputes and the demo reads from cache. · Mask at the **API boundary**, never store masked data.
- **Even admin access to 228A/POCSO identity is audited** — transparency over convenience.
- **No protected attributes** (caste/religion/gender) are ever used as model features (see Phase 6).
- The nightly recompute is the slow path (forecast training ~minutes on the full set) — that is by
  design for a batch job; reads stay sub-second off the cache.

## 7. Next

Phase 10 (testing, deploy, demo) wires these to the live Catalyst services and promotes Dev→Prod.
The product blueprint's Iteration 11 (Dossier/Case-file/Search) consumes this governance layer.
