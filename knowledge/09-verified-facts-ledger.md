# 09 — VERIFIED FACTS LEDGER (single source of truth — anti-hallucination)

Every judge-facing or deck-facing number/API/claim must come from the VERIFIED list.
Anything else must be labeled or cut. Web-verified 2026-09-12.

## ✅ VERIFIED (safe to state, with source)
| Fact | Source |
|---|---|
| India loses ₹92,651 Cr/yr in post-harvest agri losses (54 crops, ref year 2020-22) | NABCONS study for MoFPI; PIB press release PRID 2151371; mofpi.gov.in study report |
| Fruits & vegetables account for 49.9M tonnes of post-harvest waste annually — largest share | Same NABCONS/MoFPI study |
| Paytm ecosystem: 30M+ merchants | Paytm blog (QR & Soundbox), 2025 |
| 1.57 Cr merchant device subscriptions (Soundbox/PoS) | Paytm Q ending Jun-2026 earnings coverage |
| ~8 Cr monthly transacting users (Jun-2026 quarter) | Paytm quarterly disclosures |
| Soundbox subscription = cross-sell anchor (loans, insurance, marketing) | YourStory, Nov 2025 |
| Paytm invests in merchant-lifecycle AI (ARMS) + fraud AI (Pi); AI Router (2026); Perplexity partnership (Feb 2025) | Company statements / press |
| Hackathon: Round 1 = 7-section PPT (PDF) per organizer instructions; partners n8n/Sarvam/Cognee; finale = in-person Bengaluru | Official track doc + organizer message |
| Prior edition: 4,767-team shortlist funnel; ₹1L prize pool; teams up to 3 | Luma page + participant LinkedIn posts (context only) |
| Sarvam STT: **Saaras v4** = latest (adds Global English, 24 langs, 5 output modes); **saaras:v3** = default/recommended (22-23 Indic langs); **saaras:v3-realtime** = WebSocket, lower latency, server-side endpointing | docs.sarvam.ai (models/saaras), Pipecat integration docs |
| Sarvam chat LLM: **Sarvam-105B** (chat completion, deep Indic reasoning) | docs.sarvam.ai homepage |
| Sarvam TTS: **bulbul:v3**, 30+ voices, streamed or batch | docs.sarvam.ai |
| Sarvam extras: Mayura translation/transliteration (22+ langs), Sarvam Vision doc digitization, Python SDK `sarvamai`, MCP server at docs.sarvam.ai/_mcp/server, rate limits + pricing pages on docs | docs.sarvam.ai |
| n8n: visual workflow + AI agent nodes, LangChain integration, 400+ integrations, self-hostable, human-approval patterns | n8n.io + Wikipedia |
| Cognee: open-source agent memory / knowledge graphs, 30.6k stars, MCP server, per-agent memory, custom ontologies | cognee.ai + GitHub |
| 60 lakh+ street vendors in India (PM SVANidhi survey basis) | MoHUA / PM SVANidhi (commonly cited) |
| Soundbox subscription model ≈ 60% EBITDA margins; device base deepens engagement, "natural pipeline for credit distribution" | BofA Global Research report, Mar 2026 (via Money.rediff/YourStory) |
| Paytm merchant payments hardware moat: 1.44 Cr paid device subs, 85%+ Soundbox category share; enables financial-services distribution flywheel | BofA / strategy coverage, Mar 2026 |
| Financial services distribution revenue grew 34% YoY to ₹672 Cr (Q3 FY26), driven by merchant loan distribution | Paytm Q3 FY26 earnings release |
| Merchant lending = stated growth priority (more lending partners, scale merchant lending) | Paytm FY26 strategy coverage |
| Competitive scan (Sep 2026): voice-AI vendors (Sarvam, Vernacular.ai, Gnani, Skit, Bolna etc.) target enterprise call-center workloads; open-source street-vendor projects (e.g., SVDP) do demand FORECASTING = advice; no found product does closed-loop vernacular restocking EXECUTION for street merchants | Web scan this session |
| Sarvam saaras:v3 STT supports 22-23 Indic languages (incl. Tamil, Telugu, Kannada); bulbul:v3 TTS covers 11 Indic languages (Tamil confirmed on docs.sarvam.ai; Telugu voice — quick-check docs before relying on it) | docs.sarvam.ai, checked this session |
| Crew languages: Tamil + Telugu + English (native). Demo language = TAMIL (crew-written/validated command + English fallback). Bengaluru produce-market authenticity: Tamil-speaking vendors common at Kalasipalya/Madivala [coaching judgment based on market composition] | Team input, Sep 2026 |

## 🧮 MODEL / ILLUSTRATIVE (must be labeled "illustrative model / pilot metric to validate")
- Vendor economics: ₹3,500/day working capital · 25–35% unsold band (est.) · ₹400/day net loss after salvage · ≈₹12,000/mo · up to ~30% of take-home
- City math: 12,000 vendors × ₹400 × 365 ≈ ₹175 Cr/yr; 60% recovery = ₹240/day = ₹7,200/mo/vendor ≈ ₹105 Cr/yr
- Take-home waterfall: ₹18,200 → +₹7,200 → ₹25,400 (+40%)
- 12,000 Bengaluru vegetable vendors = working estimate (needs pilot citation; do NOT attribute to APMC/Paytm surveys)
- ₹149/mo Pro tier; settlement-linked micro-deduction = PROPOSED mechanism, "subject to Paytm integration approval; simulated in prototype"
- +8% GMV target per merchant = pilot target, not a claim

## ❌ BANNED (never state — unverified, fabricated, or judge-facing poison)
- "40% of produce lost" (not in fetched NABCONS sources — do not use)
- "5–15% retail-level spoilage, NABCONS stage-wise" (not directly verified)
- 68% NASSCOM · 72% voice-preference · 89% waste-spike stats (fabricated earlier — purged)
- ₹450/day variant · "₹1.8 Cr" city math (incoherent — replaced)
- Collision counts (600 teams / 450 generic / <5 teams) — internal hypotheses only; to judges say: "merchant copilots are a crowded category, so we deliberately focus on one urgent workflow"
- Any "top 5% / already won" certainty claims
- "Paytm handles it" (billing) · implying Paytm settlement APIs/nodes exist without confirmation
- IMDb weather (it's IMD) · florist/blooms/temple artifacts · "Q1 2025" timelines
- Presenting seeded demo data as live Paytm data

## Unknown → protocol
If a fact is not in this ledger: say "unverified", then either (a) check knowledge/ files, (b) run a web search, or (c) label as assumption with a validation plan. NEVER guess.
