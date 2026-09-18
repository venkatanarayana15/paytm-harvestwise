# REHEARSAL TIMING — second-by-second stage plan (stepper-UI edition)

Companion to `DEMOSCRIPT.md` (the words live there; this file is the clock).
Built on **measured** latencies from the 2026-09-18 verification runs — see the
budget table below. Print this. Keep it on the laptop lid.

The new dashboard shows a **5-step stepper** at the top:
`1 🎙 STT → 2 🧮 Recommend → 3 ✅ Approve → 4 📤 Dispatch → 5 🧠 Memory`
amber = running · green = done. **The stepper is your teleprompter** — every beat
below is keyed to a step changing color.

## Measured latency budget (2026-09-18, real runs)

| Call | Measured | Budgeted here | If it exceeds |
|---|---|---|---|
| `/intent` (rules+llm) | 1.2–3.8 s | 5 s | keep talking; it cannot hang (8 s hard cap → rules path) |
| `/rec/basket` | <0.5 s | 1 s | instant — never the bottleneck |
| `/tts` + playback | ~2–4 s incl. audio | 8 s | template ask already on screen; read it aloud yourself |
| `/explain` uplift | 1.2–3.8 s | (runs *after* TTS) | silent fallback — nobody notices |
| `/dispatch` ×2 (n8n round-trip each) | **~4 s total** | 8 s | narrate the n8n canvas while it lands |
| Cognee recall | **11–17.5 s** | 20 s | fill with the moat story (beat 7) |
| `/reason` fast | 1.5 s | 3 s | deterministic trace still renders |

**Total demo: 90 s planned / 135 s worst-case with all fillers spoken.**

---

## THE RUN (T = seconds on stage clock)

### PRE (before walking up, ~3 min, off-stage)
- [ ] `curl -s http://127.0.0.1:8000/health` → ok · `seeded` · `finish_reason: stop`
- [ ] Click **↺ Reset demo state** → stepper all gray, tomato 12 kg
- [ ] Click **Reason** once (pre-warm), then **↺ Reset** again
- [ ] Phone: WhatsApp sandbox re-joined THIS MORNING (checklist 1.4)
- [ ] Browser at 100% zoom, n8n Executions tab ready on the projector source 2

### 0:00–0:20 — HOOK (stepper: all gray — that's the point)
> "Lakshmi loses ₹400 every day to spoilage — not because she's inefficient, but
> because she guesses. HarvestWise turns her voice into an executed restocking
> order. Watch the five steps at the top light up."

**Point at the gray stepper.** "Five steps: hear, decide, approve, execute, remember."

### 0:20–0:30 — FIRE THE COMMAND
- Click **▶ Cached audio** (or live mic). Step 1 → **amber**.
- T+2s: transcript appears. Step 1 → **green**. Step 2 → **amber**.

**Say while it runs:** "She said *tomorrow 20 kilos tomato, 10 bunches coriander* — in Tamil."

### 0:30–0:45 — THE DECISION (Step 2 green)
Basket renders: 20 kg tomato ₹360 · coriander 10→**6** · ₹546 banner.

> "The engine — ordinary auditable code, not the language model — sets every
> quantity. Rain is 78% tomorrow; coriander loses 40% of its sales on rainy
> days, so it trimmed 10 bunches to 6. That's ₹186 saved from rotting."

**Do not skip the 10→6. That single number is the whole thesis.**

### 0:45–0:55 — THE GATE (Step 3 amber → green)
Click **✅ சரி (typed fallback)** — or say it live via mic.

> "Nothing moves until *she* says yes. Her voice is the payment authorization."

### 0:55–1:10 — DISPATCH (Step 4 → amber)
Click **Dispatch**. **Measured ~4s — this is a talking beat, not a pause:**

> "The order goes to n8n — which re-validates every field independently — then
> to her wholesaler on WhatsApp."

Step 4 → **green**. n8n panel shows `"dispatched"`, ledger shows `12 → 32`.
**STOP TALKING FOR TWO SECONDS. Let them read the ledger.**
Phone buzzes on the projector mic if you're lucky — acknowledge it: "and her phone just got the order."

### 1:10–1:25 — MEMORY (Step 5 green)
> "Stock moved 12 to 32. The system remembers why — next underwriting decision
> sees procurement rhythm, not just payment flows."

### 1:25–1:30 — CLOSE (verbatim from DEMOSCRIPT)
> "Most merchant assistants stop at advice. HarvestWise closes the loop between
> payment data, a purchase decision, and the action that protects the merchant's
> next day of income."

---

## BUFFER BEATS (only if something above ran long)

**Beat 7 — Cognee recall (20s filler).** Click **Recall from Cognee** the moment the
close ends. While it runs (11–17s): "And it's not a vector database — perishables
are *causal*: commodity → humidity → her rainy-day UPI velocity. The graph answers
'why 20 kilos' from her own stored facts." (Answer lands ~15s. Read one line from it.)

**Beat 8 — Reason.** If a judge asks "is the AI just a wrapper?": click **Reason**
→ 1.5s → point at the screen: "observations on the left — all fetched by the API;
reasoning on the right — and the quantity column still says *deterministic engine*."

## FAIL-SAFE MAP (what you say when the screen disagrees)

| Failure | Your line (calm) | Action |
|---|---|---|
| Step 1 stuck amber >8s | "Let me use our backup audio — the flow is identical." | typed fallback box → Run |
| TTS silent | Read the template ask from the basket card yourself | none — /explain still uplifts silently |
| Dispatch >8s, step 4 amber | "While n8n executes — note the ledger hasn't moved yet. *That's* the approval gate." | wait to 20s, then: reset + rerun during Q&A |
| Phone doesn't buzz | Don't mention the phone. The record + ledger carry the demo | check `twilio_status` only if asked |
| Cognee recall errors | "Cloud's shy right now — this is the labeled local fallback, same graph." | the fallback SVG renders; move on |
| Any crash | "The engine is deterministic — let me show the audit trail instead." | open `dispatch_record.json` |

## DRILL SCHEDULE (build day, hour 5–7)

1. **Run 1** — full script, out loud, timed. Nobody stops you. Record video.
2. **Run 2** — inject one fail-safe (Mute TTS). Speaker must land the swap line <5s.
3. **Run 3** — full run, <100s, from cold browser + fresh reset.
4. **Checkpoint:** stepper hit green on all 5 steps every run? Sum of demo ≤ 135s worst case?
5. Post-run: `POST /demo/reset`, clear stepper — laptop is stage-ready.
