# DEMO SCRIPT & RUNBOOK — 90-second atomic transaction (v2.0, Tamil, verified build)

v2.0 change: everything below is aligned to the **built and verified** slice. Superseded: the Kannada
plan, and the older "3 crates of tomatoes" phrasing. The canonical spoken command is now the 20 கிலோ
line, because that is the exact phrase the shipped audio and the parser are verified against.

> **Command (canonical, crew records this):**
> `நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி`
> → tomato 20 kg × ₹18 = ₹360 · coriander 10 → **6** bunches (rain −40%) × ₹31 = ₹186 · **₹546**
>
> "3 crates" also parses (60 kg) but it breaks the ₹546 story — do not use it on stage.

Ready-to-play backup audio: `ui/assets/command_ta.wav` (synthetic, labelled) and `command_en.wav`.
Regenerate both with `python make_backup_audio.py`.

## 90-Second Pitch Script

**HOOK (0:00–0:20)** — Option B opens, Option A's closing line becomes the demo intro.
> "Lakshmi loses ₹400 every day to spoilage — not because she's inefficient, but because she guesses.
> HarvestWise turns her voice into a restocking order that saves ₹7,200 every month in our pilot model."

**PROBLEM (0:20–0:40)**
> "Perishables have a deadline: too much and it rots, too little and the sale walks away. Her payments
> app tells her what already happened — not what to order tomorrow morning."

**MECHANISM & DEMO (0:40–2:00)** — trigger the Tamil voice note.
- Sarvam transcribes the dialect and extracts the commodities.
- The **deterministic engine** decides quantities; the LLM only understands and explains.
- Cognee supplies her stored facts (rain 78%, coriander rainy-day sales −40%).
- She says **"சரி"** → n8n dispatches to her mandi wholesaler on WhatsApp.
- Stock moves and memory updates, visibly.

Narration discipline: *"the engine decides the number"* — Cognee = remembered facts, n8n = the executor.
When the dispatch record appears, **stop talking for two seconds** and let them read it.

**PAYTM STRATEGIC MOAT (2:00–2:50)**
- **Soundbox:** her briefings and confirmations play on the device she already owns.
- **Lending:** underwriting runs on top-line payment flows; the missing half is procurement rhythm and
  spoilage volatility — exactly the telemetry HarvestWise produces.
- **Monetization:** daily alerts free; automated mandi execution ₹149/month, settlement-linked,
  *subject to Paytm integration approval, simulated in this prototype*.

**CLOSE (2:50–3:00, verbatim)**
> "Most merchant assistants stop at advice. HarvestWise closes the loop between payment data, a
> purchase decision, and the action that protects the merchant's next day of income."

## Live Demo Execution Runbook (<90s)

| Time | Screen | Audio / action | Fail-safe |
|---|---|---|---|
| 0:00–0:15 | Split: dashboard left · n8n canvas right | play the Tamil voice note, **or** click ▶ Cached audio | if mic or STT lags: *"Let me switch to our backup audio so you hear it clearly — the flow is identical either way."* |
| 0:15–0:35 | transcript + intent JSON (`engine: rules+llm`) | point at the entity parse | type the command into the fallback box and press Run |
| 0:35–0:55 | basket card + factor list + "Why this order?" panel | *"the engine recalculates from her own stored history — Cognee remembers, code decides"* | `/reason` (fast) adds a live Sarvam reasoning trace in ~2 s |
| 0:55–1:15 | merchant says **"சரி"** → dispatch panel | show the dispatch record + stock `12 → 32` | "சரி (typed fallback)" button |
| 1:15–1:30 | Inventory & Memory ledger panel + Soundbox briefing | *"order sent, stock moved, memory updated"* | ledger is server-written; it cannot disagree with the screen |

Pre-stage (do this before you walk up): `POST /demo/reset` · run the whole flow once · click
**Reason (Sarvam-105B)** once to pre-warm · play the cached audio once.

## Judge Defense Cheat Sheet

**"Why not just tell her to buy less?"**
> "Advice without execution dies at 4:30 AM. We draft *and dispatch* the revised order to her existing
> wholesaler after her explicit voice approval — the friction between insight and transaction is gone."

**"How do you justify ₹149/month?"**
> "Voice alerts are free and build the daily habit. Pro activates only on opt-in for automated
> reordering — about 2% of the ₹7,200 monthly margin our illustrative model targets preserving. The
> pilot validates the baseline before we charge anyone."

**"Why Cognee instead of vector search?"**
> "Perishables are relational, not lexical: commodity → humidity → her rainy-day UPI velocity → safety
> stock. Vector search retrieves similar text; a knowledge graph resolves this causal chain and shows
> every hop. We can screenshot the recall live."

**"Is this actually an LLM, or is the AI a wrapper?"** *(anticipated after the sponsor deep-dive)*
> "Both, deliberately. Sarvam's model does what language models are good at — understanding Tamil
> speech and speaking back in her register. Quantity decisions are ordinary auditable code, because a
> hallucinated order quantity is a real loss. We can show you the boundary live: `/reason` returns the
> model's reasoning next to the observations the API fetched, and the quantity column always comes from
> the engine."

**"What if the model is slow or down?"**
> "There's a hard wall-clock budget on every call. If it blows, the rules path answers instantly and the
> payload says so — `engine: rules`, with a `fallback_reason`. Nothing in the demo depends on the model
> being fast."

**"You have no real Paytm data"**
> "Correct, and we say so: this prototype runs labelled, Paytm-transaction-shaped seeded data. The
> integration pattern is consent-first inside Paytm's rails — that's what the pilot validates."

## Pending crew decisions & blockers
1. **`TWILIO_WHATSAPP_TO`** → verified recipient in the Twilio console (one-time). Until then dispatch
   records honestly as `skipped`.
2. **Crew-record the Tamil command** for stage; the shipped WAV is a labelled synthetic backup.
3. **Rotate the burned keys** (Sarvam / Cognee / Twilio) — see SECURITY.md.
4. **Import + activate the 3 n8n JSONs** and set their `$env` variables on n8n cloud.
