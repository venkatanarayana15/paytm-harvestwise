# DEMO SCRIPT & RUNBOOK — 90-second atomic transaction (v1.1, Tamil primary)

v1.1 change: DEMO LANGUAGE = TAMIL (crew-fluent: Tamil/Telugu/English; no external speaker dependency). English fallback unchanged. Crew drafts the Tamil command natively — semantic intent: "3 crates of tomatoes, 10 bunches of coriander for tomorrow morning." All Kannada text below is superseded; kept where noted for reference only. Deck slide 5 shows Kannada — Q&A answer: "The loop is language-agnostic across Sarvam's 22 Indic languages. Our crew speaks Tamil natively and Bengaluru's produce markets are full of Tamil-speaking vendors — first working demo runs Tamil; the same loop ports to Kannada."

Corrections applied to external draft (2026-09-12): market consistency (Kalasipalya, matches deck) · deck-aligned demo numbers (3 crates/10→6 coriander, per deck slide 5) · role boundaries preserved (Sarvam extracts · ENGINE calculates · Cognee supplies stored facts · n8n executes) · "preserved margin (illustrative)" not "working capital" · no 4x-fee billing gate · ₹240/day chain consistency · decay multiplier = documented seed constant. Crew sign-off required on the dual-SKU deviation from 08's tomato-only freeze (coaching call: adopt; fallback slice = tomato-only).

## 90-Second Pitch Script

**HOOK (0:00–0:20)**
"At 4:30 AM at Kalasipalya mandi, Lakshmi spends ₹3,500 on fresh produce based entirely on yesterday's sales. By 3:00 PM, an unpredicted thunderstorm clears the street. By 9:00 PM, she dumps ₹400 worth of rotting tomatoes. That ₹400 isn't lost because she can't sell — it's lost because she's forced to guess. HarvestWise turns her one voice note into an executed restocking order — preserving ₹7,200 of margin every month in our illustrative pilot model."
*(If a judge probes the number: "₹400/day baseline loss, 60% recovery target — the pilot validates the baseline.")*

**MECHANISM & DEMO (0:20–0:55)**
"She doesn't type, open an app, or read English. Watch the live loop:
[Trigger TAMIL voice note — crew-written & recorded]
She says: [CREW TO RECORD — Tamil semantic: '3 crates of tomatoes, 10 bunches of coriander for tomorrow morning.']
Sarvam transcribes the dialect and extracts the commodity entities.
Now the reasoning layer: Cognee surfaces her stored facts — 78% afternoon rain probability, and her rainy-day coriander sales history down ~40%. The deterministic engine recalculates: six bunches of coriander, not ten. Tomatoes hold — they still sell in rain.
(Implemented 2026-09-18: rain_modifier 0.6 on coriander, 1.0 on tomato, in engine/restock.py — the screen now matches this narration exactly: tomato 20 kg ₹360 + coriander 6 bunches ₹186 = ₹546.)
n8n takes the approved order and dispatches it to her mandi wholesaler on WhatsApp."
*(Narration discipline: the ENGINE decides the number — say it that way. Cognee = her remembered facts. n8n = the executor.)*

**PAYTM STRATEGIC MOAT (0:55–1:30)**
"Where does this sit in Paytm's ecosystem?
Soundbox: her morning briefing and order confirmation play as audio through the Soundbox she already owns.
Lending: underwriting today runs on top-line payment flows. The missing half is procurement rhythm, input costs, spoilage volatility — HarvestWise produces exactly that telemetry, making vendors like Lakshmi underwritable for Paytm Merchant Loans.
Monetization: daily alerts are free. Automated mandi execution is ₹149/month — a settlement-linked mechanism, subject to Paytm integration approval, simulated in this prototype."

## Live Demo Execution Runbook (<90s)

| Time | Main screen | Audio/action | Fail-safe checkpoint |
|---|---|---|---|
| 0:00–0:15 | Split: WhatsApp Web (left) · n8n Canvas (right) | Play TAMIL voice note: [CREW-RECORDED WAV — semantic: "3 crates tomatoes, 10 bunches coriander, tomorrow morning"] | If mic latency spikes → "Play Cached Audio" button on test harness. Swap line: "Let me switch to our backup audio so you hear it clearly — the flow is identical either way." |
| 0:16–0:35 | n8n webhook node flashes green; Sarvam extraction node shows entities: {"tomato": "3 crates", "coriander": "10 bunches"} | Point at entity parse | Payload tab pre-rendered in browser. |
| 0:36–0:55 | Engine output + Cognee facts panel: [rain 78%] + [rainy-day coriander sales −40%] → recalc: coriander 10 → 6 | "The engine recalculates from her own stored history — Cognee remembers, code decides." | Static JSON log tab open in secondary window. Numbers now verified live in engine: 20kg×₹18 + 6×₹31 = ₹546. |
| 0:56–1:15 | Wholesaler chat receives order: "3 crates Tomato, 6 bunches Coriander — ₹546. Approve?" → voice "ಸರಿ" → dispatch confirmation | Show voice approval + dispatch record | Local simulated WhatsApp responder ready. |
| 1:16–1:30 | Simulated merchant dashboard: "Day's spoilage risk: ₹240 preserved (model)" · "HarvestWise Pro: ₹149/mo — settlement-linked (simulated)" | Close on lending-telemetry line | Dashboard labeled "Paytm-transaction-shaped seeded demo data." |

Seed constants (documented, engine-traceable — no improvised numbers): rain 78% · rainy-day coriander −40% (her 90-day history) · decay multiplier for coriander at 85% humidity: 2.0x (documented in engine/catalog.py) · revised coriander: 6 bunches · order total ₹546 (matches deck slide 5).

## Judge Defense Cheat Sheet

**"Why not just tell her to buy less?"**
"Advice without execution dies at 4:30 AM. Her wholesaler runs on fast-moving WhatsApp lists — by drafting and dispatching the revised order to her existing agent after her approval, we remove the friction between the insight and the transaction."

**"How do you justify ₹149/month from micro-merchants?"**
"Seed tier — voice demand warnings — is free, building the daily habit. Pro activates only on opt-in for automated reordering: ₹149 is ~2% of the ₹7,200 monthly margin our illustrative model targets preserving. The pilot validates the baseline before we charge anyone anything."

**"Why Cognee instead of standard vector search / RAG?"**
"Perishables are relational, not lexical: commodity → humidity threshold → her rainy-day UPI velocity → safety stock. Vector search retrieves similar text; a knowledge graph resolves this causal chain — and shows you exactly *why* the order changed, every hop traceable."

## Pending crew decisions & blockers
1. Sign-off: dual-SKU demo command (recommended: yes; fallback slice = tomato-only)
2. Fluent Kannada speaker validates + records the ONE command (semantic: "3 crates of tomatoes, 10 bunches of coriander tomorrow morning") — non-negotiable, no AI-generated speech
3. SARVAM_API_KEY → unlocks test_voice.py
4. Round-1 PDF upload confirmation
