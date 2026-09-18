# DECK COPY — HarvestWise (Round 1)

Slide-by-slide copy of `deck.html` / `HarvestWise_Round1_PaytmHackathon.pdf`.
Edit here or in deck.html, then re-export PDF (see readme).

## S1 · Title — HarvestWise
- Tagline: Voice-first autonomous restocking for India's street merchants.
- Pipeline: WhatsApp/Soundbox → Sarvam Indic Voice AI → Cognee Knowledge Graph → n8n Orchestrator → Mandi Wholesaler
- Hook: "Lakshmi sells vegetables in Bengaluru. Paytm made her a merchant — nothing made her a restocker. HarvestWise listens, predicts spoilage, recalculates her order and dispatches it to her mandi wholesaler — without asking her to type a single word."
- Fill in: TEAM NAME + members — DONE: Team Sairam · Venkata Narayana G V · Malaravan P

## S2 · Opportunity — "Paytm made them merchants. Nobody made them restockers."
- 30M+ merchants · 1.57 Cr device subs · 8 Cr MTU (Paytm disclosures 2025-26)
- Locked layer: the 4:30 AM stocking decision runs blind; Paytm ARMS is internal-only; merchant-facing layer = next growth phase.
- Why now: Sarvam + n8n + Cognee matured together.

## S3 · Problem — "Her inventory rots. Her margin goes with it."
- Lakshmi story (representative persona, labeled) — Kalasipalya 4:30 AM, ₹3,500, 3 PM storm, ₹400 dumped
- 25–35% daily spoilage · 4:30AM↔3PM signal disconnect · tools need literacy/dry hands/downtime
- Cost strip: ₹3,500 × ~30% unsold − salvage = ₹400/day ≈ ₹12,000/mo ≈ up to 30% of take-home
- City line (model): 12,000 vendors × ₹400 × 365 ≈ ₹175 Cr/yr spoilage losses; drives "meter baddi" debt. Baseline validated in pilot.

## S4 · Solution — restocking loop: Observe → Predict → Act → Learn
- Observe: UPI velocity (consent), IMD rain, festivals, mandi rates, decay tables
- Predict: spoilage & demand in her words
- Act: recalc order (10→6 bundles), voice-approve, dispatch to wholesaler
- Learn: what worked and why → next week starts from evidence
- No new app: WhatsApp voice + Soundbox briefing; "Chatbots advise. We finish the job."

## S5 · Experience/demo script (times)
- 6:30 AM briefing (WhatsApp + Soundbox) · 9:14 she orders in Kannada (3 crates tomatoes, 10 coriander) · 11:02 recalc to 6 bundles + approval + dispatch · 8:30 PM zero waste, ₹1,940 kept, "+₹4,100 this week", logged to memory.

## S6 · Tech stack — one job each
- Experience: WhatsApp BA API, Soundbox, Business with Paytm
- Intelligence: Sarvam saaras:v3 STT / sarvam-30b LLM / bulbul:v3 TTS
- Decision core: Cognee memory graph, decay tables, cold-start patterns
- Orchestration: n8n briefing/order-dispatch/approval-gate workflows
- Data: Paytm signals (consent), IMD, mandi feeds (sandbox for MVP)
- Guardrails: DPDP-aligned, federated, human approval, undoable, audited.

## S7 · USP table
Rows: input modality / decision intelligence / workflow completion / hardware tie-in.
Cols: traditional tools vs generic chatbots vs HarvestWise (voice-native, causal graph, closed-loop dispatch, Soundbox briefing). MOAT: memory graph × vernacular closed loop × Paytm-native distribution.

## S8 · Impact — "Waste is her biggest expense. We give 60% of it back."
- Waterfall: ₹21,000 base + ₹7,200 preserved = ₹28,200 (+34%) — illustrative, 30-selling-day basis
- Paytm wins: Soundbox upgraded to assistant · +8% GMV target · underwriting telemetry for Merchant Loans · mission story
- KPIs: ₹7,200/vendor/mo · ₹105+ Cr/yr city-wide · vs ₹175+ Cr current loss

## S9 · Business model
- Seed ₹0 (alerts, habit, zero CAC) · Pro ₹149/mo (autonomous restocking, P&L voice audit) — settlement-linked micro-deduction PROPOSED, subject to Paytm integration approval, simulated in prototype · Platform: supplier take-rate, credit distribution, anonymized demand curves (DPDP)
- Wedge → platform: perishable carts → kirana fresh → 30M merchants.

## S10 · Roadmap & close
- Now/finale MVP · Months 1–3: 500-merchant pilot (KR Market, Russell Market, Madivala) · Months 4–6: Paytm for Business API + Soundbox rail · Beyond: restocking layer + credit
- Close: "Every morning at 4:30, India's merchants guess. From tomorrow, they guess with a copilot." + Ask: 500-merchant pilot.

## Finale note (per knowledge/08 doctrine — SUPERSEDES the 4-command demo idea)
Demo = ONE vertical slice: tomato restocking; ONE crew-written TAMIL command + ONE English fallback (supersedes earlier Kannada plan — crew-fluent; see DEMOSCRIPT v1.1); deterministic rec engine (LLM never picks quantities); Cognee shows causal graph + answers "why 20 kg?"; n8n dispatches; 3-min pitch script in 08.
- [x] TEAM NAME + member names (S1, S10): Team Sairam — Venkata Narayana G V · Malaravan P
- [ ] Re-export PDF after any edit
- [ ] Upload to portal "Round 1 / Rounds" section (retry after 2–3 hrs if locked)
- [ ] File name: HarvestWise_Round1_PaytmHackathon.pdf (1.3 MB, 10 pages, 1280×720)

## Queued micro-fixes for NEXT re-export only (do NOT re-export for these alone)
- [x] APMC-source softening ×2 — APPLIED 2026-09-13 in final pre-upload pass ("public daily price feeds", "mandi logistics planning")
- [ ] Slide 5 title + bubbles switch to Tamil ONLY when crew command is recorded AND pdf not yet uploaded; otherwise leave deck, use Q&A line.
4. Terminology law (unchanged): ₹3,500/day stock budget = "working capital" (legitimate use) · ₹7,200/mo = "preserved margin, illustrative" (NEVER "working capital") · 25–35% band = est./illustrative, never "verified".
