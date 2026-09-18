# 02 — Track Decision & Positioning

## Comparison (from literature review + judging analysis)
| Criterion | T1 Merchant Growth | T2 Financial Journeys | T3 Autonomous Teammates |
|---|---|---|---|
| Evidence strength | High (AI copilots lift SME sales 15-25%, largest gains for low-capability merchants — Pangkey 2026) | High (claims cycle -22-30%, 40-70% routine-task automation — Sikarwar 2025, Sudabathula 2025) | Medium (agents beat chatbots on multi-step work — Rai 2026; governance is make-or-break — Pothukuchi 2026) |
| Build difficulty (24h) | Low-Medium | Medium (legacy backend integration) | Medium-High (API sprawl, guardrails) |
| Judge appeal | High — relatable, visual, demo-friendly | High but abstract; regulated domain | Very high IF tightly scoped; vague agents = red flag |
| Our team fit | LLM+agents, full-stack, design — all three strengths map to a copilot product | weaker domain fit | possible but riskier |

## Decision: Track 1
Wedge: perishable-goods micro-merchants (vegetables & fruits first; flowers, milk, eggs, street food next).
Rationale:
1. Sharpest pain in Paytm's 30M+ merchant long tail: daily stock literally rots; forecasting = survival math
2. "Perishable + time-sensitive" makes AI value obvious in one sentence; generic "merchant copilot" pitches will be common in this track — the niche is the differentiation
3. Voice-first vernacular (Sarvam) is THE unlock for this segment: literacy, 12-hour stall days, no dashboards
4. Perfect stage for the three partner tools (see 04)
5. Expansion story to 30M merchants keeps the TAM big: wedge first, category by category

## Risks & mitigations
- "Too small a niche?" -> Position as wedge: perishables first (highest pain), then all merchant categories; Paytm-native from day one
- "Crowded track?" -> Differentiate on: voice-first (not dashboard), closed-loop execution (not advice), per-merchant memory graph (not generic chat), waste-to-wealth framing (money saved = money earned)
- "No access to real Paytm data?" -> Hackathon MVP uses synthetic settlement data in sandbox; production design is consent-first inside Paytm's rails; judges care that the integration pattern is realistic
- Fabricated-stats risk: use only sourced anchors (see 03) + clearly-labeled illustrative model for unit economics

## Product one-liner
HarvestWise — the voice-first AI growth copilot for India's perishable-goods merchants. Merchants speak; it predicts, acts, and remembers — in their language, on the phone they already use.
