# 11 — MENTOR DEEP PLAYBOOK (the veteran material behind Hermes)

Reference ammunition for the Mentor agent. Sources: hackathon-judging research, Paytm context (knowledge/01-03), our own project history. Coaching judgments are marked [CJ] — they are pattern-knowledge, not verified facts; the Mentor must never present them as data.

## A. Judge-rubric model (internal scoring, never show judges)
Score 1-10, fix anything below 7:
1. **Problem clarity** — tired judge restates it in one sentence after slide 3?
2. **Demo irrefutability** — a visible action ends the "does it work?" debate (n8n node pulsing, dispatch record, memory write)?
3. **Sponsor integrity** — Sarvam/n8n/Cognee each do NAMED, MEANINGFUL work (not logo slides)?
4. **Paytm nativeness** — GMV/retention/underwriting/Soundbox tie-in explicit?
5. **Credibility** — every number verified (09) or labeled illustrative?
6. **Memory** — will judges still describe us at dinner tonight? (one-line hook + one demo moment + one number)
[CJ] Research on judging: novelty ~33%, impact ~25%, feasibility ~17%, presentation ~25% — but a SINGLE live failure can outweigh everything; hence backup-first culture. Judges see 20-40 pitches; recall collapses to hooks and moments.

## B. Demo-day choreography (the 3:00 flow, mapped to seconds)
- **0:00-0:20 HOOK — two options, crew's call (G5 decision):**
  - Option A (locked 08 script): "A vegetable vendor doesn't lose money because she lacks analytics. She loses money when tomorrow's tomatoes are ordered using yesterday's guess. HarvestWise listens in her language, understands her recent Paytm sales and stock, and — after her approval — sends the right restocking order to the wholesaler."
  - Option B (money-first hook — sharper at grabbing judge attention): "Lakshmi loses ₹400 every day to tomato spoilage — not because she's inefficient, but because she guesses. HarvestWise turns her voice into a restocking order that saves ₹7,200 every month." (Numbers are ledger-safe: ₹400/day & ₹7,200/mo are labeled illustrative in the deck; the spoken pitch may use the model per 09 as long as any follow-up attributes it as the pilot model.)
  - Coaching call: **Option B opens, Option A's closing line becomes the demo intro.** Crew decides at rehearsal — both are memorized.
- **BACKUP DEMO SCOPE = one verifiable causal chain in <90 seconds (atomicity over perfection):** Kannada voice command → Sarvam STT → LLM intent → n8n WhatsApp order dispatch → Cognee graph update (rain alert + velocity → action) → simulated settlement deduction. If this flows with transparent causality, the technical bar is cleared; everything else is narrative.
- **0:20-0:40 PROBLEM:** perishable time pressure; too much = waste, too little = missed sale; payment data tells what happened, not what to do next.
- **0:40-2:00 LIVE FLOW (the vertical slice):** screen shows sales+inventory → speak tested Kannada command → transcription+intent visible → deterministic rec appears → Cognee explanation visible → "ಸರಿ" approval → n8n canvas executing → dispatch record + inventory update → bulbul:v3 voice reply. Every step = one sentence narration; never two people narrate [CJ].
- **2:00-2:25 ARCHITECTURE:** one sentence per sponsor tool (08 boundaries).
- **2:25-2:50 BUSINESS/PILOT:** vendors-first wedge; pilot metrics (stockouts, spoilage, margin, time saved); Rs 149 concept labeled as simulated [billing rule].
- **2:50-3:00 CLOSE (verbatim):** "Most merchant assistants stop at advice. HarvestWise closes the loop between payment data, a purchase decision, and the action that protects the merchant's next day of income."
- **Roles [CJ]:** one driver (demo), one narrator (pitch), one wing (timing + judge reading). Swap nothing mid-pitch.

## C. Backup & AV protocol (Ranked failure risks)
1. **WiFi/LAN dies** → local 60s screencast `HarvestWise_Backup.mp4` on laptop AND phone, tested volume [CJ: #1 killer at in-person hackathons]. Swap-script (say it calmly, keep narrating): "Let me switch to our backup audio so you hear it clearly — the flow is identical either way." A seamless swap reads as professionalism; never apologize twice.
2. **STT accent failure** → pre-recorded clean Kannada WAV + on-screen transcript; simplify live phrase to the 4-word version; English fallback command.
3. **Cognee graph fails/ugly** → static annotated PNG (Vendor→Product→Trigger→Action→Outcome, 5 nodes, each labeled with its fact). Attempt live first, switch without apology: "Here's the same graph."
4. **n8n timeout live** → pre-run the workflow once before stage; show the execution history pane — real records beat live risk [CJ].
5. **Sarvam API latency spike** → pre-warmed session; bulbul:v3 streamed; if >5s once, switch to backup immediately — never let the room watch a spinner [CJ: 2 spinners = perceived broken].
6. **Slide disaster** → deck is a PDF; present from it if HTML dies.

## D. Pitch cadence & delivery [CJ]
- Speak at ~150 wpm, drop to ~130 for the impact numbers; silence-beat 1s after "yesterday's guess."
- The demo moment is THE moment: when the dispatch record appears, stop talking for 2 seconds. Let them read it.
- Never read slides; slides = evidence, voice = story.
- Rehearse the 3:00 eleven times: three alone, three to team, three on camera, twice on stage-conditions (standing, timer visible).

## E. Countdown triage matrix (Mentor's default answer-shaper)
| Time | Everything else is optional except |
|---|---|
| >72h | strategy depth, experiments, alternatives analysis |
| 24-72h | only moves protecting the demo slice (08 acceptance criterion) |
| <24h | end-to-end demo works + backup recorded + failure paths tested |
| <2h | rehearse, hydration, laptop charged, backup on phone; NO new code |
| Post-Round-1 (shortlist wait) | prep finale per 08/10; do NOT touch the submitted PDF |

## F. Judge Q&A — hostile variants & control lines (extensions of 07)
- "Why not just WhatsApp + ChatGPT?" → "That's advice without arithmetic. Our quantities come from a deterministic engine over her own Paytm-shaped velocity, shelf-life and IMD rain — and n8n executes only after her voice approval. A chatbot can't dispatch an order, and we can prove it live."
- "What if the vendor can't read?" → "She never has to. Voice in, voice out; the Soundbox reads the briefing aloud."
- "How do you know vendors will trust it?" → trust ladder [CJ]: tips first (no action) → recommendations with receipts (weekly money-saved scorecard) → approved dispatch (one-tap undo). Trust is earned in the memory graph, not claimed in a slide.
- "You have no real Paytm data" → "Correct, and we say so: this prototype runs labeled, Paytm-transaction-shaped seeded data. The integration pattern is consent-first inside Paytm's rails — that's exactly what the pilot validates." (Honesty as a weapon [CJ].)
- "Can this scale beyond vegetables?" → wedge-then-platform line (07), never "all 30M merchants."
- **The "Paytm-native test" (apply to every business claim):** would a Paytm PM nod "this fits our roadmap"? Frame the underwriting story viscerally: **"HarvestWise provides the procurement telemetry lenders lack — turning restocking behavior into causal, auditable signals for underwriting. This isn't competing with Paytm; it's building the merchant-facing layer your lending roadmap needs."** (Vyapar-TrustNet is Paytm's internal credit-scoring effort — we are the missing merchant-facing signal layer, not a rival.)

## G. Team command patterns (Mentor behavior)
- Decisions, not options: "Do X because Y. Change trigger: Z."
- One owner + one deadline per action.
- Panic protocol: shrink the next step to 15 minutes.
- Energy protection: no all-nighters inside 24h of pitch [CJ: sleep > polish].
- Meeting discipline [CJ]: build day = 3 checkpoints only (T+2h core loop, T+4h dispatch, T+6h dress rehearsal), otherwise heads-down.

## H. Anti-hallucination drills (Mentor self-tests)
Before any material answer touching numbers: recompute the chain (e.g., 12,000 x 400 x 365 = 1.752B = ~175 Cr — check the ledger's version, not memory). If a "fact" arrives without a file or fresh web check, it goes to the team as [Unverified] with a verification step. The banned list (09) is reflexive, not deliberative.
