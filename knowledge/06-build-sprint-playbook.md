# 06 — Finale Build Sprint Playbook (partner-stack specifics)

## Sarvam API specifics (indus.sarvam.ai, free ~Rs 1,000 credits on signup)
- STT: model `saaras:v3` — real-time Indic transcription (Hindi, Kannada, Tamil, +9). Handle noisy backgrounds (street demos!) — test with cart-side audio.
- LLM: `sarvam-30b` / `sarvam-105b` — business reasoning; prompt for intent+entity extraction from vernacular queries, JSON tool-calls, anti-hallucination (ground every number in provided data).
- TTS: model `bulbul:v3` — natural Indic voices. Target <2s voice-to-voice latency (judge favorite).
- Python SDK: `pip install sarvamai`; audio -> base64 -> API call.

## n8n (use for ~80% of logic — replaces backend code)
- Webhook trigger from our voice backend -> Sarvam nodes -> branches.
- Workflows to build: (1) 6:30 AM briefing (weather+IMD mock, festival, history -> voice out), (2) order recalc + dispatch to wholesaler via WhatsApp, (3) day-wrap P&L + memory write, (4) payment-reminder flow with Paytm links.
- Human-approval node before any money action.

## Cognee (memory + wow-factor)
- `cognee.add()` merchant context (sales trends, khata/credit ledger, supplier reliability).
- `cognee.search()` for grounded recall; show LIVE knowledge-graph visualization in demo: Vendor -> Tomato -> DemandSpike -> MonsoonAlert. Judges love the graph.
- Khata voice logging: "Ramesh ko ₹450 ka aata udhar diya" -> parsed -> graph -> n8n WhatsApp reminder with Paytm link.

## 3-day pre-finale sprint
- Day 1: voice pipeline STT->LLM->TTS in Kannada/Hindi, <2s latency.
- Day 2: n8n fetch synthetic Paytm data -> Cognee store -> voice-triggered action executes.
- Day 3: record 60-sec backup screen-capture; rehearse 3-min pitch (hook 30s / demo 60s / impact 60s / CTA 30s).

## Judge psychology & avoidances
- Lead with WHO it's for, not tech depth. Real grounded data (synthetic-but-labeled for MVP). Dead-simple interaction.
- NO dashboard-first pitch (action > analytics). NO English-only demo (Bengaluru = Kannada wins). NO over-engineering (1 working voice query > 5 broken features). NO cold open (practice the 30-sec hook).
- Winner profile: "Solves a problem I've seen on my street corner, and it works in my language."

## Current deck numbers (locked after technical review — keep consistent)
- Rs 3,500 avg daily working capital; 25–35% spoilage band; Rs 400/day net loss after evening salvage (~Rs 12,000/mo); ~30% of household take-home.
- City math: 12,000 vendors × Rs 400 × 365 = Rs 175+ Cr/yr; 60% recovery = Rs 240/day ≈ Rs 7,200/mo/vendor ≈ Rs 105+ Cr/yr preserved.
- Take-home model: Rs 18,200 base (~20% margin) + Rs 7,200 preserved = Rs 25,400 (+40%). Label illustrative; 60% reduction is the pilot metric to validate.
- Pricing: Seed free; Pro Rs 149/mo via settlement micro-deductions; platform: supplier take-rate + credit distribution + anonymized demand curves (DPDP-compliant).
- Tool roles: Sarvam = Indic speech layer (saaras/bulbul); Cognee = causal knowledge graphs (decay tables × rain × UPI velocity); n8n = event-driven orchestration to mandi wholesalers; Soundbox = morning briefing loudspeaker.
- Weather source: IMD (India Meteorological Department) — never "IMDb".
