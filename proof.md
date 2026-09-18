# 🏆 PROOF.md — Round 1 Submission Evidence Pack

> **Team Sairam** (Venkata Narayana G V · Malaravan P) · **HarvestWise** · Track 1: Merchant Growth AI

> ⚠️ **Addendum (2026-09-18, post-shortlist).** This file is the historical evidence pack for the
> **submitted Round 1 deck** and its contents remain an accurate record of that submission. One row is
> now out of date: §6 said "`finale/` today holds planning docs only and zero code files" — that was
> true at submission time and is no longer. The finale slice is now built and verified (83/83 battery,
> dashboard renders end-to-end); see `finale/IMPROVEMENTS.md` for the audit and `STATUS.md` for state.
> Do not re-export or alter the submitted PDF.
> **Artifact:** `deck/HarvestWise_Round1_PaytmHackathon.pdf` (1.41 MB · 10 pages · 1280×720 CSS / 960×540 pt · valid PDF header · re-exported 2026-09-13 18:51 after humanize pass, CreationDate D:20260913132147+00'00')
> One file that proves, line by line, that our submission meets the Round 1 criteria and survives credibility probing.

## 📊 Status dashboard

| Area | Status |
|---|---|
| 7/7 required sections present | ✅ Complete (+2 value-add slides) |
| Slide integrity (overflow / placeholders / banned phrases) | ✅ Zero issues, 3 consecutive passes |
| Numbers (verified vs labeled) | ✅ Ledger-clean — see §3 |
| Full-deck accuracy audit (652 lines read) | ✅ Judge-safe — see §5 |
| Build-day feasibility | ⚠️ Feasible **iff** scaffold pre-built — see §6 |
| Portal upload | ⬜ **OPEN — gates everything** |

**Contents:** [1. Criteria audit](#1--round-1-criteria-audit) · [2. Verification log](#2--verification-log) · [3. Credibility ledger](#3--credibility-ledger-extract) · [4. Decision trail](#4--decision-trail) · [5. Deep accuracy audit](#5--deep-accuracy-audit-full-deck-read) · [6. Feasibility audit](#6--build-day-feasibility-audit) · [7. Open items](#7--open-items)

---

## 1. Round-1 criteria audit

| # | Required section | Our slide(s) | Coverage | Shortlist strength |
|---|---|---|---|---|
| 1 | Title Slide | S1 — HarvestWise, tagline, Track 1 chip, Team Sairam + members, pipeline strip (WhatsApp→Sarvam→Cognee→n8n→Mandi) | Complete | High — sponsor stack on slide 1 is a pattern interrupt |
| 2 | Problem Statement | S3 — Lakshmi story (labeled representative persona), 3 pain cards, cost strip (₹3,500 × ~30% − salvage = ₹400/day), city model (~₹175 Cr/yr) | Complete | High — visceral + every number labeled |
| 3 | Proposed Solution | S4 (Observe→Predict→Act→Learn loop) + S5 (day-in-life demo flow) | Complete, doubled | Highest — closed-loop execution is the wedge |
| 4 | Technology / Tech Stack | S6 — 5 layers, one-job-per-tool, guardrails bar, sandbox-labeled data | Complete | High — each sponsor does named work |
| 5 | USP | S7 — 4-row comparison table (dashboards/chatbots/Soundbox/ERP) + moat line | Complete | High — contrast format built for 60-second judging |
| 6 | Impact & Benefits | S8 — waterfall (₹21,000 → +₹7,200 → ₹28,200, +34%, 30 selling days), assumptions footnote, Paytm-level wins, directional KPIs | Complete | High — dual-level impact (merchant P&L + Paytm flywheel) |
| 7 | Business Model | S9 — Seed free / Pro ₹149 (proposed + simulated) / platform revenues + flywheel strip | Complete | High — Soundbox-rail billing + lending telemetry |

> Value-add beyond requirements: S2 (opportunity framing, verified Paytm scale) + S10 (roadmap + team + close). Ten slides total — standard length, no bloat.

## 2. Verification log

| Check | Method | Result | When |
|---|---|---|---|
| Slide overflow (all 10 slides) | DOM audit: scrollHeight + per-element bounds vs slide box | **Zero overflow, 3 consecutive passes** (incl. post-edit re-verification) | 2026-09-11 → 2026-09-13 |
| Banned-phrase scan | Deck-wide text scan vs ledger 09 banned list (IMDb, blooms/florist, Q1 2025, "Paytm handles it", ₹450 variant, collision counts) | **Clean** | 2026-09-12, 2026-09-13 |
| Placeholder scan | `[TEAM NAME]`, `[Member N]`, APMC attributions | **Zero remaining** (APMC ×2 removed in final pre-upload pass) | 2026-09-13 |
| Team identity | Slides 1 & 10 contain Team Sairam + both member names | **Present** | 2026-09-13 |
| PDF integrity | Header bytes `%PDF`, page-object count, file size | **Valid · 10 pages · 1.27 MB** | 2026-09-13 14:52 |
| Accuracy pass (pre-upload) | 30-selling-day basis fix (₹21,000 → +₹7,200 → ₹28,200, +34%); Sarvam ASR 12→22+ langs; live DOM 10/10 clean zero-overflow; PDF re-exported via Edge headless | **Clean** | 2026-09-13 17:58 |
| Grammar pass | 2 fixes (S5 "3 crates of tomatoes", "vs last week"); automated scan found no other real errors; DOM re-checked 10/10; PDF re-exported | **Clean** | 2026-09-13 18:22 |
| Humanize pass (tone) | 7 micro-edits (em-dash/inversion smoothing, de-symmetrized S4 strip, dropped boastful absolute "is the only one that" from S7, "derisks"→"de-risks" ×2, unit-economics line to prose); numbers/structure/layout untouched; DOM re-checked 10/10 clean; PDF re-exported 18:51, CreationDate D:20260913132147+00'00' | **Clean** | 2026-09-13 18:51 |

## 3. Credibility ledger extract

### ✅ VERIFIED (safe to state, sourced)
- 30M+ merchants in Paytm ecosystem — Paytm blog, 2025
- 1.57 Cr merchant device subscriptions — Q Jun-2026 earnings coverage
- ~8 Cr monthly transacting users — Jun-2026 quarter disclosures
- ₹92,651 Cr/yr post-harvest losses; F&V 49.9M tonnes/yr (largest share) — NABCONS study for MoFPI, PIB PRID 2151371
- Soundbox subscription ≈ 60% EBITDA margins; device base = credit-distribution pipeline — BofA Global Research, Mar 2026
- Merchant lending = Paytm FY26 growth priority; distribution revenue +34% YoY to ₹672 Cr (Q3 FY26) — Paytm earnings
- 60 lakh+ street vendors, India — PM SVANidhi / MoHUA

### 🧮 ILLUSTRATIVE MODEL (labeled as such in deck footnotes — pilot validates)
- ₹3,500/day working capital · ~30% unsold band (est.) · ₹400/day net loss after salvage · ≈₹12,000/mo · up to ~30% of take-home
- 12,000 Bengaluru vegetable vendors = **working estimate** (never attributed to APMC/Paytm surveys)
- City math: 12,000 × ₹400 × 365 ≈ ₹175 Cr/yr · 60% recovery = ₹240/day ≈ ₹7,200/mo/vendor ≈ ₹105 Cr/yr preserved
- Waterfall: ₹21,000 base → +₹7,200 → ₹28,200 (+34%, 30-selling-day basis) · evening kept ₹1,940 · demo order ₹546 · +8% GMV **target**

### 🔶 PROPOSED + SIMULATED (never "Paytm handles it")
- Pro ₹149/mo via settlement-linked micro-deduction — subject to Paytm integration approval; simulated in prototype

### 🏷️ LABELED, NEVER LIVE
- Lakshmi = representative persona · demo data = Paytm-transaction-shaped seeded data · weather source = IMD

### ❌ BANNED (never in our materials)
40% loss claim · 5–15% retail range · 68% NASSCOM / 72% voice / 89% spikes · ₹450/day variant · "₹1.8 Cr" math · collision counts & rankings · Q1 2025 · florist artifacts · "Paytm handles it" · live-data implication.

## 4. Decision trail

1. **Track 1** — only track deploying all three team strengths with zero missing capabilities; only track making all three sponsors load-bearing; brief literally says *"recommending or **executing**"* (our closed loop lives in that word); judges' own P&L is merchants. Tracks 2/3 rejected on domain deficit, demo physics, and integration-access risk (full analysis: knowledge/02).
2. **Wedge, not generic copilot** — perishable restocking where advice rots tonight; white space verified (voice-AI vendors serve call centers; street-vendor projects stop at forecasting).
3. **Demo language Tamil** — crew-native (Tamil/Telugu/English team); zero external dependency; Bengaluru-market authentic; language-agnostic loop portable to Kannada (deck slide 5 shows Kannada product story — Q&A line owned).
4. **Architecture moat** — deterministic engine decides quantities; LLM understands + explains; Cognee stores causal facts; n8n executes after voice approval. Narration never blurs these boundaries.
5. **Dual-SKU command** (3 crates tomato + 10→6 coriander, deck-consistent numbers) — crew sign-off pending; fallback = tomato-only slice.
6. **Terminology law** — ₹3,500/day = working capital (legitimate) · ₹7,200/mo = preserved margin, illustrative (never "working capital") · bands are est., never "verified".

---

## 5. Deep accuracy audit (full deck read, 2026-09-13)

> ✅ **Verdict: judge-safe.** All 652 lines of `deck.html` read fresh. Zero fabrications, zero banned claims, all recomputed arithmetic exact, labels everywhere the doctrine requires.

| Slide | Claim checked | Result |
|---|---|---|
| S1 | Team/event names, pipeline order, "dispatches to wholesaler" | ✅ Clean — no factual claims beyond identity |
| S2 | 30M+ / 1.57 Cr / 8 Cr + "Paytm blog & investor disclosures, 2025–26" footnote | ✅ All in-ledger, sourced on-slide |
| S2 | "Paytm's own AI (ARMS) optimizes merchant lifecycle internally" | ✅ In knowledge/03 from company statements; reasonable characterization, low risk |
| S3 | City math ₹400×12,000×365 = ₹175.2 Cr, labeled "Modeled… baseline validated in pilot" | ✅ Exact + labeled |
| S3 | Persona labeled, 12,000 as "(working est.)", cost strip footnote "illustrative model" | ✅ Doctrine-compliant |
| S4 | IMD (not IMDb), consent-labeled signals, voice-approval gate, Soundbox briefing as proposal | ✅ Clean |
| S5 | Seed-style story numbers (₹18/kg, ₹546 order, ₹1,940 kept); "n8n gate: nothing moves without her yes" | ✅ Narrative-level, doctrine-consistent |
| S6 | STT/TTS language counts, guardrails, "seeded data (labeled as such)", no APMC attributions | ✅ Clean (STT "12" understates verified 22+ — modesty, not a violation) |
| S7 | Competitor characterizations, moat line (no invented stats) | ✅ Rhetoric within scan support; "only one" flagged as watch-item for Q&A, not a deck change |
| S8 | Waterfall adds exactly (21,000+7,200=28,200; +34.3%≈+34%); KPIs recompute exactly (105.1 / 175.2 Cr); "target +8% GMV" labeled | ✅ Exemplary footnotes |
| S9 | Billing "proposed… subject to approval; simulated"; "80%+ SaaS margin" as projection (unattributed, standard) | ✅ Compliant |
| S10 | Roadmap in Months 1–3/4–6 (no banned timelines); team + 500-merchant ask | ✅ Clean |

### ⚠️ Nits found (reported honestly — none block upload)

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | ~~Day-basis mix (26d base vs 30d uplift)~~ → **RESOLVED 2026-09-13 17:58** | Was low — fixed because user requested max accuracy | Model re-based on **30 selling days** (₹21,000 + ₹7,200 = ₹28,200, +34%); footnote, waterfall bars, DECK-COPY synced; live DOM re-verified; PDF re-exported + re-certified |
| 2 | STT "12 Indic languages" vs verified 22+ | Negligible — understates capability | **Fixed pre-upload** → "ASR · 22+ Indic languages" (ledger 09.30, docs.sarvam.ai) |
| 3 | S7 "the only one that…" absolute | Low — scan-supported rhetoric | Q&A watch-item, no deck change |

## 6. Build-day feasibility audit

> ⚠️ **Verdict: feasible — but only pre-built, not invented on the day.** `finale/` today holds planning docs only (README, requirements, FAILPATHS, DEMOSCRIPT) and **zero code files**. The ~7-hour build day fits integration + rehearsal, not architecture.

| Demo promise (S5/S10) | Exists today | Still to build | Est. |
|---|---|---|---|
| Deterministic rec engine (velocity×decay×rain→qty, validation, idempotency) | ❌ spec only (08/10) | `engine/` (~150 lines) | 2–3h |
| FastAPI orchestration (state/intent/recommend/approve/dispatch) | ❌ | `api/main.py` (~200 lines) | ~2h |
| Seed dataset (90d × 2 merchants, Paytm-shaped) | ❌ | `data/seed_gen.py` (~120 lines) | ~1.5h |
| Prompts P1–P4 as `.txt` | ❌ (live in knowledge/10) | copy + trim | 30 min |
| n8n 3 workflows (briefing/dispatch/daywrap) | ❌ | JSONs + WhatsApp-sandbox wiring — **highest-risk item** (fallback: local responder, in runbook) | 2h + contingency |
| Cognee seed + live graph (static PNG fallback) | ❌ | `seed_memory.py` + annotated SVG | 1.5h |
| Single-file dashboard UI | ❌ | `ui/index.html` (~250 lines) | 2h |
| Sarvam voice loop <2s | ❌ | **Blocked: API key + Tamil WAV** (both open) | 1h once unblocked |
| Backup recording + rehearsal | — | Build-day scheduled | 1.5h |

## 7. Open items

- [ ] **Portal upload confirmation (+ screenshot) — HIGHEST LEVERAGE, gates everything**
- [ ] SARVAM_API_KEY → unblocks test_voice.py
- [ ] Tamil command drafted + recorded WAV (crew-native)
- [ ] Dual-SKU sign-off
- [ ] Slide-5 Tamil switch — gated on WAV + pre-upload state; Q&A line covers the seam meanwhile
- [ ] Post-shortlist deck touch-ups (nit #1 day-basis alignment, STT "22+", NOT before upload)
