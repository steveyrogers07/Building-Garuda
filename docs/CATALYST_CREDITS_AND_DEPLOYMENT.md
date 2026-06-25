# GARUDA — Catalyst Credits & Deployment Strategy

How to use your Zoho Catalyst credits so they fuel a smooth **production deployment + live demo** instead of leaking away during the build.

## TL;DR
- **Development environment is FREE.** Credits are consumed **only in Production.**
- So **build everything (Phases 1–9) in Dev → $0 credits.** Credits are *deployment & demo* fuel, not build fuel.
- **Don't claim/activate credits until Phase 10** — the standard grant expires ~60 days from claim.
- The big credit-burners are **always-on** services (QuickML LLM serving, AppSail). Keep them **off except when demoing.**

## 1. How Catalyst billing actually works
- **Two environments:** **Development** (free — nearly all components, up to ~200k API calls/app) and **Production** (billed).
- **Production billing:** pay-as-you-go (postpaid, monthly) or subscription. A **monthly free tier** applies before you're charged/credits are drawn.
- **Credits:** complimentary wallet credits (standard = **$250, valid ~60 days from claim**) are applied automatically to production usage. **Your datathon credit may differ — confirm the exact amount + expiry** in the console.
- **Manage at:** Console → **Settings → Manage Billing** (wallet balance, **Current Usage**, budgets/alerts). Redeem a coupon code (if that's how the credit came) on the Catalyst wallet-credits page.
- **Compute is billed by GB-second (Functions) / GB-minute (AppSail)** = memory × time. → **always-on services cost the most.**

## 2. Credit-conservation rules (mapped to the 10 phases)
| When | Environment | Credits |
|---|---|---|
| **Phases 1–9** (all building + testing, incl. Claude-assisted) | **Development** | **$0** |
| **Phase 10** (promote, custom domain, live demo) | **Production** | credits used here |

- Stay in **Dev** for all iteration. Claude-assisted building does **not** touch credits.
- **Claim the credits only when you start Phase 10**, so the expiry window covers demo day + a buffer.
- Reserve the bulk of credits for the **demo/judging period** + custom domain.

## 3. Credit-burners & how to control them (GARUDA-specific)
| Service | Why it burns | Control |
|---|---|---|
| **QuickML LLM serving (Qwen)** | Served model = continuous compute. Likely your #1 cost. | **Spin up only while demoing the copilot; spin down after.** Prefer on-demand calls. |
| **AppSail (Python ML brain)** | Runs continuously (GB-minute). | Minimal memory/instances; **stop the service when idle.** |
| **Zia AutoML** | Training jobs. | **Train once**; don't retrain in a loop. |
| **Zia OCR / Data Store / Stratus** | Per-call / storage. | Keep synthetic data ~10–20k rows; batch OCR. |
| **Live recompute during demo** | Repeated heavy queries. | **Cache** + **Job Scheduling precompute** → serve stored results on stage (cheaper + faster). |

Set a **budget + alert** in Manage Billing so you're warned before the wallet runs low.

## 4. Claude-assisted building, kept Catalyst-correct
- Use Zoho's official **agent-skills + Zoho MCP** (`github.com/catalystbyzoho/agent-skills`) so Claude generates **deployment-ready** Catalyst code and follows current APIs. (Free — this is about code quality, not credits.)
- Drive each build session from the per-phase briefs: `docs/PHASE_1_KICKOFF.md`, `docs/PHASE_2_KICKOFF.md`, … (one self-contained brief per phase).

## 5. Phase 10 — Go-Live runbook (sequenced to minimize credit burn)

### Pre-flight (still in Dev — $0)
- [ ] Exit gates for Phases 1–9 all green; full **E2E demo flow works in Dev**.
- [ ] **Backup demo video recorded** (in case the live demo fails).
- [ ] Trim **AppSail** memory to the minimum that runs; confirm **Cache** + nightly **Job Scheduling** precompute populate the demo's data.
- [ ] Remove debug logging; finalize env config (no secrets hardcoded — use AppSail `env_variables`).
- [ ] Keep synthetic data at demo-necessary size.

### Promotion (credits start here — do this a day or two before demo, not earlier)
1. [ ] Set up a payment method, then **claim the credits** (this starts the expiry clock — do it now, not weeks earlier).
2. [ ] Set a **budget + alert** in Manage Billing.
3. [ ] **Promote the project to Production** (from the console).
4. [ ] Deploy **client + functions + AppSail** to Production.
5. [ ] Configure **Domain Mappings + SSL** (custom domain).
6. [ ] Load data (or restore precomputed results) into the prod Data Store.
7. [ ] Smoke-test prod URLs (client, `/health`, map, network, copilot) — **but leave QuickML LLM serving OFF** until needed.

### Demo-day ops
- [ ] ~30–60 min before: **spin up QuickML LLM serving** and warm AppSail.
- [ ] During the demo: serve **cached/precomputed** results; copilot live.
- [ ] Immediately after: **spin DOWN LLM serving + AppSail** to stop the meter.

### Post-demo
- [ ] Stop/scale down all always-on services.
- [ ] Check **Current Usage** vs. remaining credits; confirm you're within budget.

## 6. Ongoing monitoring checklist
- [ ] Manage Billing → **Current Usage** checked daily once in Production.
- [ ] Budget alert configured.
- [ ] **Credit expiry date** noted and tracked.

---
**One-line policy:** *Build free in Dev, deploy late, keep the always-on services switched off except when demoing — and you'll never run out of credits mid-judging.*
