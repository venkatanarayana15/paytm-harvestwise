# HarvestWise — Finale Scaffold (build-day assembly kit)

Goal: on the 7-hour build day, this repo means INTEGRATE + REHEARSE, not architect.
Scope = frozen vertical slice (knowledge/08): tomato restocking, one voice command, deterministic rec, approval, n8n dispatch, memory update. Everything else is P5 polish — last.

## Structure (as built 2026-09-18)
```
finale/
  api/main.py            FastAPI orchestration (/stt, /intent, /rec, /rec/basket,
                         /approve, /voice/approve, /dispatch, /tts, /memory, /cognee/recall)
                         single-use approval tokens + idempotent dispatch
  engine/restock.py      DETERMINISTIC recommendation: stock-adjusted demand × rain
                         modifier (tomato 1.0, coriander 0.6) — LLM never sets quantity
  data/seed_gen.py       regenerates data/seed.json FROM engine CATALOG (no drift)
  prompts/P1..P4         Sarvam-105B prompts from knowledge/10 (intent, ReAct, explain, dispatch)
  n8n/*.json             importable workflows: briefing / dispatch / daywrap
  cognee/seed_memory.py  merchant causal graph seed (local fallback; cloud via /cognee/recall)
  ui/index.html          single-file demo dashboard — real mic capture (MediaRecorder →
                         /stt), typed fallback, dual-SKU basket, cached-audio slot
  ui/assets/command_ta.wav  crew-recorded Tamil command goes HERE (cached-audio backup)
  test_voice.py          Sarvam TTS/STT pre-test (needs SARVAM_API_KEY)
  FAILPATHS.md           the 7 failure states + expected UI behavior
```

## Run
```
pip install -r requirements.txt
cp .env.example .env            # add SARVAM_API_KEY (STT/TTS), Twilio vars optional
python data/seed_gen.py         # writes data/seed.json (synced from engine)
python cognee/seed_memory.py    # writes cognee/memory.json
python -m uvicorn api.main:app --port 8000
start ui/index.html             # dashboard at file:// — talks to localhost:8000
```
Demo command (deck-consistent): **"நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி"** →
basket: tomato 20 kg × ₹18 = ₹360 · coriander 10→6 bunches (rain −40%) × ₹31 = ₹186 · **₹546**.
Parser also accepts "3 crates tomato" (60 kg) — for the ₹546 story use the 20 கிலோ phrasing.

### WhatsApp (Twilio trial) — one-time crew step
Trial accounts can only message **verified recipients**. Error 572002 means: add the
merchant's number in Twilio Console → Messaging → WhatsApp sandbox settings (verified
"to" + send the sandbox join code from that phone once). Then dispatch shows 201 and the
phone gets the order message. Until then the demo still completes — dispatch is recorded
and the note is visible (labeled fallback, never pretend it sent).

## Build-day protocol (Luma agenda: build 10:00–17:00, demos 18:00–20:00)
- **Hour 0–2:** clone repo · run seed · voice-loop smoke test (STT→intent→TTS <2s) · dashboard shows state
- **Hour 2–5:** wire n8n (import 3 JSONs, point webhooks at your tunnel/local URL) · Cognee seed + live graph · pre-run the dispatch once so execution history has real records
- **Hour 5–7:** noise stress-test (>85% on key terms else simplified phrase) · RECORD BACKUP DEMO NOW (OBS; laptop + phone) · rehearse 3:00 pitch with cheat-sheet · print graph_fallback.svg
- Checkpoints only at T+2h / T+4h / T+6h — otherwise heads-down.

## Non-negotiables on build day (knowledge/08 + 09)
- Data on screen = "Paytm-transaction-shaped seeded demo data" (say it; never imply live Paytm access)
- LLM explains; engine decides; n8n re-validates — never let Sarvam set a quantity
- Billing = simulated ₹149 concept; never "Paytm handles it"
- No new stats, no new Kannada text (fluent speaker only), no new billing mechanics — ledger is law

## Blockers still open (pre-build)
1. Round-1 PDF upload confirmation
2. SARVAM_API_KEY (indus.sarvam.ai free credits) → unblocks test_voice.py
3. Fluent Kannada speaker → writes + records the ONE command (semantic: "Increase tomorrow's tomato order and send it to the wholesaler")
