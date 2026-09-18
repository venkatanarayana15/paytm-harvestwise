# 08 — AUTHORITATIVE FINALE DOCTRINE (supersedes over-scoped parts of 06 & 07)

Mentor verdict accepted in full. The winning version is SMALLER and more defensible.
Central principle: **Do not build an AI that tells a merchant what might help. Build a trustworthy system that helps make ONE high-value decision and completes the next operational step.**

## Product definition (locked)
"HarvestWise is a vernacular voice agent for vegetable vendors that turns Paytm sales signals and local demand context into an approved, executable restocking order."
- NOT "AI business partner" (too broad — that's the generic 450's category)
- Positioning: Track 1 category, Track 3 execution discipline (Signal → Decision → Approval → Execution → Outcome memory)
- Lakshmi = clearly-labeled representative persona

## Scope freeze — acceptance criterion (one page, memorize)
Given a seeded merchant dataset, a tested voice command must produce:
1. A validated restocking recommendation
2. Merchant approval (voice)
3. An n8n workflow execution
4. A dispatch record
5. A visible memory/inventory update
EVERYTHING OUTSIDE THIS = OPTIONAL.

## Live demo = ONE vertical slice (kill the 3-command script)
- ONE problem: tomato restocking
- ONE voice command: approve a quantity change — **TAMIL, crew-written & crew-validated (crew languages: Tamil/Telugu/English — no external speaker dependency)**; Telugu alternate if bulbul:v3 Telugu voice verifies; ONE fallback English command. (Supersedes earlier Kannada plan; crew cannot natively validate Kannada.)
- Language Q&A (deck slide 5 says Kannada): "The loop is language-agnostic across Sarvam's 22 Indic languages. Our crew speaks Tamil natively, and Bengaluru's produce markets are full of Tamil-speaking vendors — so our first working demo runs Tamil. The same loop is portable to Kannada."
- ONE causal explanation: sales velocity + weather + stock
- ONE n8n execution: dispatch the order
- ONE visible outcome: order status + memory update
All else (Soundbox, settlement, WhatsApp multi-flow, multi-language) = supporting slides/roadmap only.

## Architecture (responsibility boundaries)
Prompt-level contract for the LLM is fully specified in **knowledge/10-prompt-engineering-react-cot.md** (CoT intent extraction → ReAct loop over tool observations → vernacular explanation → deterministic dispatch guard). Rule: LLM reasons & explains; the engine decides; n8n re-validates.
```
React/Vite mobile UI
  → FastAPI orchestration (auth, validation, intent normalization, state)
      → Sarvam STT (saaras:v3)
      → Intent/parameter extraction (LLM — language only)
      → DETERMINISTIC restocking engine (ordinary code: velocity, inventory, shelf-life, weather modifier)
      → Cognee (entities, relationships, outcome memory)
      → n8n webhook (validate order → create PO → wholesaler message → inventory update → status)
      → Sarvam TTS (bulbul:v3)
```
- LLM NEVER decides quantities or calls unrestricted tools. It understands + explains.
- Structured action schema (intent/product/qty/supplier/reasons[]/requires_confirmation) + validation: product exists, qty within limits, supplier known, budget within threshold, merchant approved.
- Numbers/quantities/money/authorization = deterministic code. Language = LLM.

## Cognee = causal memory (not chat history)
Show:
```
Lakshmi ─ sells → Tomato
   ├─ recent sales velocity → +18%
   ├─ current stock → 12 kg
   ├─ expected rain → high
   ├─ shelf-life → 2 days
   └─ recommendation → order 20 kg ─ approved & dispatched
```
Must answer "Why did you recommend 20 kg?" from stored facts + deterministic calc — never LLM-invented. Fallback: static PNG of this graph if live graph fails; attempt live first.

## Pitch (3:00 total)
- 0:00–0:20 OPEN: "A vegetable vendor doesn't lose money because she lacks analytics. She loses money when tomorrow's tomatoes are ordered using yesterday's guess. HarvestWise listens in her language, understands her recent Paytm sales and stock, and — after her approval — sends the right restocking order to the wholesaler."
- 0:20–0:40 PROBLEM: perishable time pressure; too much = waste, too little = missed sale; payment data tells what happened, not what to do next
- 0:40–2:00 LIVE FLOW: sales+inventory view → Kannada command → transcription+intent → deterministic rec → Cognee explanation → approve → n8n executing → dispatch+inventory → Sarvam voice reply
- 2:00–2:25 ARCHITECTURE: each sponsor tool in ONE sentence
- 2:25–2:50 BUSINESS/PILOT: vegetable vendors first (loss is immediate/measurable); pilot measures stockouts, spoilage, margin, time saved; then fresh-goods expansion
- 2:50–3:00 CLOSE: "Most merchant assistants stop at advice. HarvestWise closes the loop between payment data, a purchase decision, and the action that protects the merchant's next day of income."

## Failure paths to test (before backup recording)
Unclear speech · unknown product · ambiguous quantity · duplicate approval · n8n failure · slow Sarvam · missing inventory. Each needs a clear UI state — graceful, not crash.

## 24-hour blocks
1. Freeze scope (acceptance criterion above)
2. Build vertical slice (seeded "Paytm-transaction-shaped demo data" — NEVER imply it's live Paytm data)
3. Test failure paths
4. Record backup demo (voice→transcript→rec→Cognee→n8n→dispatch→voice reply; local + phone copies)
5. Rehearse: user/problem/action/sponsor-integration/pilot-metric — each in one sentence

## Credibility rules (NON-NEGOTIABLE)
- NEVER quote collision counts, rankings, "top 5%", "already won" to judges — internal hypotheses only. Say instead: "Merchant copilots are a crowded category, so we deliberately focus on one urgent workflow: autonomous restocking for perishable vendors."
- Billing = concept: "₹149/mo via settlement-linked mechanism, subject to Paytm integration approval; simulated in this prototype." Never "Paytm handles it."
- All impact math = "illustrative model… baseline validated in pilot." Never cite Paytm surveys/Karnataka APMC without holding the exact source.
- Never claim Paytm APIs/nodes exist unless confirmed; never imply mock data is live data.

## Priority order (if time runs short)
P1 end-to-end execution → P2 grounded calculation → P3 real sponsor integration → P4 failure handling → P5 polish (settlement sim, multi-language, graph animation, analytics, extra categories LAST).
