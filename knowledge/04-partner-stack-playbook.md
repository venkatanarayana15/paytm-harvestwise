# 04 — Partner Stack Playbook (Sarvam + n8n + Cognee)

Why the deck (and finale build) must visibly use all three: they are the organizers' partners; solutions that showcase their stack get sponsor-judge attention and credits.

## Sarvam AI — India's sovereign AI platform (sarvam.ai, API hub: indus.sarvam.ai) — CORRECTED 2026-09-12 (web-verified, see knowledge/09)
- STT: **saaras:v4** = latest (adds Global English, 24 languages, 5 output modes); **saaras:v3** = default & recommended (22-23 Indic languages); **saaras:v3-realtime** = WebSocket endpoint, server-side endpointing, lower latency — use for the <2s demo loop; batch /speech-to-text endpoint also available
- Chat LLM: **Sarvam-105B** (chat completion, deep Indic reasoning). (Earlier "sarvam-30b" note: superseded — use 105B unless docs say otherwise at build time)
- TTS: **bulbul:v3** — natural voices in 11 Indic languages, 30+ voices, streamed or batch
- Extras: Mayura translation/transliteration (22+ langs) · Sarvam Vision document digitization · document translation (23 langs) · dubbing with voice cloning
- Platform: SOC 2 Type II, ISO 27001, DPDP-compliant; median latency <100ms; 10B+ tokens served; rate-limit + pricing pages live on docs.sarvam.ai; MCP server at docs.sarvam.ai/_mcp/server; Python SDK `pip install sarvamai`
- Voice agents exist as reference patterns (cart-recovery nudge, EMI reminder, appointment booking)
- HarvestWise use: merchant speaks (Kannada/Hindi/...) -> saaras STT (test v3 vs v4 realtime) -> Sarvam-105B reasoning + JSON tool-calls -> bulbul:v3 voice reply. LLM understands + explains; code decides quantities/money.

## n8n — workflow automation + AI agent orchestration (n8n.io)
- Node-based visual automation; 400-1,000+ integrations (400+ safe claim); AI agent nodes, LangChain integration; custom JS/Python code nodes; self-hostable
- Backed: $2.5B valuation Series C (Accel, NVIDIA), #1 on GitHub JavaScript Rising Stars 2025 (+112k stars)
- HarvestWise use: the "act" layer — scheduled 6:30 AM briefing workflow; supplier-order placement via WhatsApp; price-update actions; human-in-the-loop approval nodes before any money moves; fallback/escalation branches

## Cognee — open-source agent memory / knowledge graphs (cognee.ai)
- 30.6k GitHub stars; 5M+ SDK runs/month; MCP server; per-agent memory + custom ontologies; trusted by engineers at Apple/Microsoft/PayPal (and production case studies: Bayer, Knowunity)
- HarvestWise use: per-merchant knowledge graph — what this merchant sells, festival patterns, monsoon behavior, supplier reliability, which recommendations worked; federated/anonymized cross-merchant patterns give cold-start recommendations (Lee 2021 pattern)

## Integration sketch (for tech slide + finale build)
Experience: WhatsApp Business API (voice notes) + optional dashboard inside "Business with Paytm"
  |
Intelligence: Sarvam ASR -> Sarvam-2B LLM (reasoning, JSON tool-calls) -> Sarvam TTS
  |
Orchestration & Memory: n8n (agent workflow, integrations, approval gates) + Cognee (merchant memory graph)
  |
Data: Paytm settlement/sales signals (sandbox/synthetic for MVP), weather API, festival calendar, mandi price feeds
  |
Guardrails: consent-first, DPDP-aligned, human approval for every money action, federated learning (patterns shared, raw data never)

## Finale MVP plan (day-of, ~7 hrs)
1. Synthetic merchant dataset (2 vendors x 90 days of item-level sales)
2. n8n workflow #1: 6:30 AM briefing (weather + festival + history -> Sarvam -> voice note out via WhatsApp)
3. n8n workflow #2: conversational agent (ASR in, LLM + Cognee memory, tool: supplier order)
4. n8n workflow #3: day-wrap summary + weekly learning note into Cognee
5. Demo script: one phone, one voice note, one executed order, one memory callback ("last Tuesday you ignored the rain tip and lost Rs 400 — want the plan this week?")
