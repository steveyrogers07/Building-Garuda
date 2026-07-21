# GARUDA
### Crime intelligence for the Karnataka State Crime Records Bureau
**Datathon 2026 submission · built on Zoho Catalyst**

**Live:** https://garuda-brain-50044039193.development.catalystappsail.in/ui/
**Demo sign-in:** `garudaadmin` / `datathon26` (pick any clearance tier on the login screen)
**Repository:** https://github.com/steveyrogers07/Building-Garuda

---

## 1. What GARUDA is

An SCRB analyst has FIRs. What they do not have is the connective tissue between them:
that the chain-snatching in Bengaluru Urban and the one in Mysuru share a phone number,
that a district's clearance rate quietly fell below the state median two months ago, that
four wards are about to see a burglary spike.

GARUDA reads a FIR corpus and produces that connective tissue, then puts it behind
role-based access with every read audited. It surfaces and explains records. It never
asserts guilt, and it never predicts people.

The product is one console with a single spine: **FIR corpus → entity resolution → MO
fingerprinting → co-offender network → hotspot and forecast → prioritised district
directives → governed, audited access.**

---

## 2. What it actually does

| Capability | What a judge sees |
|---|---|
| **Operations Overview** | 10,155 FIRs, 14,624 resolved entities, 31 districts, cross-district rings and live anomaly signals with z-scores |
| **Network Reveal** | Co-offender graph: rings surfaced by shared phones and vehicles, spanning up to 8 districts, click through to a kingpin dossier |
| **District Command** | Per-district picture fusing anomaly, hotspot, clearance, absconding and forecast |
| **District Action Card** | Prioritised, sourced directives. Every sentence cites the record or metric that produced it |
| **Copilot** | Natural-language query over the corpus, returning cited FIR numbers and incident IDs. Kannada voice input supported |
| **Absconding Board** | Ranked absconding accused with last-known linkage |
| **Hotspot Map** | Spatiotemporal concentration by station and ward |
| **Universal Search** | FIR numbers, names, phones, plates across the corpus |
| **Audit Log** | Every governed read, with actor, role, resource and timestamp |

**Forecasting** is `lgbm-p6-v1`: LightGBM, walk-forward validated, with a published model
card. It forecasts **places and times, never people.** A fairness audit runs alongside it
and currently flags 4 of 31 wards for over-prediction review. That flag is shown in the
product, not buried.

---

## 3. Governance is the differentiator

Most crime-analytics demos show capability. The reason this one is built around access
control is that a real SCRB deployment fails on governance long before it fails on
modelling.

Three things are enforced **server-side**, not in the UI:

1. **Role-based access.** Five clearance tiers. The audit log is restricted to
   `scrb-admin` and `ethics`; analyst, district and station roles are refused.
2. **Jurisdiction gates.** A district officer scoped to Bengaluru Urban sees only
   Bengaluru Urban FIRs. A station officer reading a case outside their station is
   refused with `outside your jurisdiction`.
3. **PII masking at the API boundary.** Victim, complainant and witness identities are
   reduced to initials for roles without clearance, so raw PII never leaves the brain.
   Statutory hard-masking for IPC 228A and POCSO is implemented and config-driven.

The role switcher in the console is not a mock. Switching tiers changes what the server
returns. Section 7 shows how to verify all of this from a terminal in under a minute.

**Ethical posture, stated plainly.** Suspects are annotated *as recorded in the FIR,
pending investigation or trial*, never as guilty. The forecast model targets places and
times. The fairness audit is surfaced, not hidden. The audit log is not optional.

---

## 4. Architecture on Catalyst

```
                    React SPA (/ui/)  ── served same-origin by AppSail
                            │
                    AppSail · FastAPI ML brain
                            │
    ┌───────────┬───────────┼───────────┬────────────┬───────────┐
 Data Store   Cache      NoSQL       Stratus     Functions   Job Scheduling
 20 tables   warm      EgoGraph     raw-fir    ingest-event    nightly 02:00
 15,903 rows payloads    Cache       briefs        jobs        weekly Mon 08:00
```

**Serving strategy, stated honestly.** Catalyst **Data Store is the system of record for
writes**: the audit log and the anomaly engine's alerts are written there through ZCQL,
and both grow during ordinary use. The analytical **reads are served from the corpus
bundled into the deployment**, because re-querying a relational store per request is the
wrong shape for graph and time-series work that is expensive exactly once and cheap
thereafter. Cache and a deploy-time warm payload hold the precomputed results.

---

## 5. Catalyst service coverage

Against the organizer's 26 capability rows. Status is reported strictly: **Live** means a
judge can verify it against the running deployment right now.

| # | Capability | Service | Status | Evidence / justification |
|---|---|---|---|---|
| 1 | Serverless functions | **Functions** | **Live** | `ingest-event`, `jobs` deployed. `api` written, not deployed |
| 2 | Docker deployment | AppSail (OCI) | Skipped, justified | Managed Python 3.11 runtime chosen instead. Container image adds no capability here |
| 3 | Full web app | **AppSail** | **Live** | The FastAPI brain. All analytics endpoints |
| 4 | Frontend / SPA | Web Client Hosting | **Live via AppSail** | React SPA served same-origin at `/ui/` so it calls the API without CORS or a second origin |
| 5 | Custom domain + SSL | Domain Mappings | Not attempted | Cosmetic for evaluation |
| 6 | Relational DB | **Data Store** | **Live** | 20 tables, 15,903 rows. System of record for writes |
| 7 | Semi-structured data | **NoSQL** | **Live** | `EgoGraphCache` holds ego-subgraph JSON |
| 8 | Object storage | **Stratus** | **Live** | `raw-fir` (scan inbox) and `briefs` buckets |
| 9 | Cache | **Cache** | **Live** | Warm copies of precomputed analytics. Segment reachable |
| 10 | Full-text search | Data Store search | Not attempted | In-process TF-IDF serves the semantic arm of `/search` |
| 11 | Text LLM / RAG | QuickML | Not attempted | See note below. The copilot is deterministic by design |
| 12 | No-code ML pipelines | QuickML | Skipped, justified | Duplicates the walk-forward LightGBM path already shipped with a model card |
| 13 | AutoML (tabular) | Zia AutoML | Not attempted | Comparison run, not a product path |
| 14 | OCR | Zia Services | Code present, not wired | `functions/ingest-event/ocr.js` written for Kannada and English. Stratus trigger not bound |
| 15 | Voice / translation | Zia Services | **Shipped in product, not via Zia** | Kannada voice query works. Catalyst Zia has no speech-to-text, verified against the SDK, so the browser Web Speech API provides the transcript and `engines/copilot/kannada.py` normalizes Kannada to the English tokens the retriever keys on |
| 16 | PDF / headless browser | SmartBrowz | Blocked by platform | Confirmed unavailable at this project tier. The weekly brief renders as HTML instead, and the status endpoint reports the limitation honestly rather than failing silently |
| 17 | User auth | **Authentication** | **Implemented, deliberately gated** | See §6 |
| 18 | API routing / throttle | **API Gateway** | **Implemented, deliberately gated** | Per-IP sliding-window rate limiting is live in the app. Gateway claim verification ships gated with §6 |
| 19 | OAuth to Zoho services | Connections | Not needed | The in-project SDK covers every call made |
| 20 | Cron / scheduled jobs | **Job Scheduling** | **Live** | `garudanightly` 02:00 recompute, `garudaweekly` Mon 08:00 brief |
| 21 | React to in-project events | Signals + Event Functions | Code present, not wired | `functions/ingest-event` written. Stratus trigger not bound |
| 22 | Cross-app event bus | Signals | Not attempted | |
| 23 | Workflow orchestration | Circuits | Definition present, not built | `ingestion/circuits/fir_ingest.json` defines OCR → extract → queue with retries and dead-letter |
| 24 | Transactional email | Mail | Not attempted | `automation/notify.py` produces the envelopes. Send not wired |
| 25 | Push notifications | Push | Not attempted | Same envelopes |
| 26 | CI/CD | Pipelines | Not attempted | 10 test suites run locally and gate the work. See §9 |

**Tally: 9 services live and independently verifiable, 2 implemented and deliberately
gated, 4 skipped or blocked with stated reasons, 3 built but not wired, 8 not attempted.**

We have reported this strictly rather than counting partial credit. Nine Catalyst services
carrying real traffic, provable by a judge in a terminal, is the claim we are prepared to
defend.

**On row 11, deliberately.** The copilot resolves natural language through a deterministic
parser and a TF-IDF retriever, and every answer cites the FIR numbers it came from. For a
police records system this is a feature, not a shortfall: an analyst can trace any answer
back to the record that produced it, and the system cannot hallucinate a suspect. Adding
generative phrasing on top would be a small change and a large increase in what has to be
audited.

---

## 6. The authentication decision

Production authentication is **implemented and intentionally not switched on.**

Under `ENV=prod`, `get_principal` in `app/routers/analytics.py` trusts only the
Gateway-injected `X-Garuda-User` header, which the API Gateway strips from inbound traffic
and re-injects server-side after Catalyst verifies the sign-in. Role and scope are then
resolved from the `Console_Users` table. The code path is complete and reviewable.

It is gated because in production mode every request without that header is refused with a
hard 401. A judge opening the link would be locked out and would need a provisioned
account to see anything at all.

We chose an evaluator who is inside the product in five seconds, with a role switcher that
demonstrates the access control live, over a configuration flag nobody can see. This is a
deliberate, documented trade-off, not an unfinished edge.

---

## 7. Verify our claims yourself

Every governance claim in §3 is checkable from a terminal. `BASE` is the deployment URL.

**Role-based access** on the audit log:
```bash
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Role: scrb-admin' $BASE/audit   # 200
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Role: ethics'     $BASE/audit   # 200
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Role: analyst'    $BASE/audit   # 403
```

**Jurisdiction filtering** returns only in-scope districts:
```bash
curl -s -H 'X-Role: district' -H 'X-Scope: BNU' "$BASE/governed/incidents?limit=3"
curl -s -H 'X-Role: district' -H 'X-Scope: MYS' "$BASE/governed/incidents?limit=3"
```

**A station officer is refused a case outside their station:**
```bash
curl -s -H 'X-Role: station' -H 'X-Scope: RMN03' $BASE/case/INC000001/parties
# {"detail":"outside your jurisdiction"}
```

**PII masking changes what the server returns:**
```bash
curl -s -H 'X-Role: scrb-admin' $BASE/case/INC000001/parties   # full name
curl -s -H 'X-Role: analyst'    $BASE/case/INC000001/parties   # initials, masked: "jurisdiction"
```

**Catalyst services are genuinely in use, not merely provisioned:**
```bash
curl -s -H 'X-Role: scrb-admin' $BASE/admin/provision
# 20 tables, 15,903 rows, cache_segment_reachable: true
curl -s -H 'X-Role: scrb-admin' "$BASE/audit?limit=5"
```
The audit log grows as you read. It stood at 6 rows early in development and is at 29 now,
written to Data Store through ZCQL by ordinary use. The `Alerts` table holds 12 rows the
anomaly engine wrote on its own schedule, unprompted.

**Measured response times on the deployed instance, warm** (2026-07-21, across two runs):
`/stats` 0.27-0.30s · `/geo/districts` 0.26-0.37s · `/network/rings` 0.28s · `/risk/top`
0.28-0.31s · `/audit` 0.31-0.33s · `/copilot` 0.40s · `/officers` 0.40-0.42s ·
`/district/BNU/command` 0.45-0.52s · `/absconding` 0.50-0.55s. The District Action Card is
the heaviest screen at 0.76-1.68s, because it fuses anomaly, hotspot, clearance,
absconding and forecast in one pass. Everything else answers in well under a second.

---

## 8. Honest limitations

- **The corpus is synthetic**, generated to the organizer's ER schema: 10,155 FIRs across
  31 districts, 2024-01-01 to 2025-06-30. Every name, phone and plate is fabricated. No
  real FIR data was used, which is also why none of this required a data-sharing approval.
- **Statutory 228A and POCSO masking cannot be demonstrated on this data.** The rule is
  implemented and config-driven, but the synthetic corpus contains none of the protected
  crime types, so the path cannot fire. Jurisdiction-based masking is fully demonstrable
  and is what §7 exercises.
- **Authentication runs in demo mode.** See §6. In this mode the API is open, which is the
  cost of an evaluator being able to click straight in.
- **SmartBrowz is unavailable at this project tier**, so the weekly brief renders as HTML
  rather than PDF. The status endpoint says so rather than failing quietly.
- **Reads are served from the bundled corpus, not Data Store.** See §4.

---

## 9. Engineering

**Tests.** 10 suites, all green, run as scripts:
```
python tests/test_{actions,district,governance,workbench,field_officer,
                   network,copilot,forecasting,arrests_sections,p2_fields}.py
```
`test_actions.py` gates acceptance criteria AC1 through AC7 for the District Action Card.
One rule the suites encode, learned the hard way: **a comparison that gets printed must be
evaluated at the precision it prints.** A directive once rendered "clearance rate 72% is
below the state median 72%" because it compared raw floats. A test now parses the
percentages back out of the rendered sentence and fails the build if the sentence
contradicts itself, so a wording regression breaks CI rather than reaching a judge.

**Availability.** AppSail idle-stops the container, and this submission is a link opened at
an unpredictable moment, so the cold path was measured rather than assumed. Boot to first
byte is about 11 seconds. The background warm-up that builds the co-offender graph, the
LightGBM walk-forward model and the TF-IDF index then runs for roughly 3 minutes.

That warm-up window is covered by design: analytics results are baked into the deployment
at build time, so from the first second the container is up, every endpoint serves correct
precomputed data at full speed while the live rebuild proceeds behind it. A visitor
arriving mid-warm sees no difference, which is the whole point of baking them.

An external monitor pings `/keepalive` every five minutes so even the 11-second boot is
absorbed by a robot rather than an evaluator. The endpoint reports `uptime_seconds` and
`warmed`, which makes a container recycle observable after the fact instead of a matter of
guesswork. It caught a genuine idle-stop during final verification, which is precisely the
event it exists to make visible.

---

## 10. Taking this to real KSP data

GARUDA reads through an adapter, so the corpus is swappable rather than baked in.

1. **Column mapping.** A `column_map.ksp.yaml` binds real KSP column names to the internal
   contract. The pattern is already proven in the codebase: Catalyst reserves `long`, so
   `provision.COLUMN_ALIASES` remaps the coordinate column at the Data Store boundary while
   every local read path keeps its original name.
2. **Unstructured extraction.** The real schema has **no structured phone or vehicle
   columns**. Those entities live in the `BriefFacts` narrative text, so the entity arm
   switches from column reads to NER over that field. The extraction scaffolding, prompt
   and schema validation with retry already exist in `ingestion/extraction/`.
3. **Governance binds harder, not softer.** `PROTECTED_CRIMES` is config, not code. The
   moment real data carries sexual-offence or POCSO crime types, IPC 228A masking engages
   with no code change. This is why the rule was built before there was data to trigger it.

---

## 11. Reference

| | |
|---|---|
| Live console | https://garuda-brain-50044039193.development.catalystappsail.in/ui/ |
| Demo sign-in | `garudaadmin` / `datathon26` |
| Repository | https://github.com/steveyrogers07/Building-Garuda |
| Catalyst project | `Garuda-system`, India DC |
| Integration plan | `docs/CATALYST_INTEGRATION_PLAN.md` (the 26-row mandate) |
| Schema | `schema/create_tables.md` · `docs/DATASET_REAL_SCHEMA.md` |
| Intelligence design | `docs/product/07-INTELLIGENCE-BLUEPRINT.md` |
| Field officer design | `docs/product/08-FIELD-OFFICER-INTELLIGENCE.md` |
