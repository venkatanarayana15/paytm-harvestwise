# Failure paths — test ALL before recording the backup (doctrine 08)
# Demo language: TAMIL primary (crew-fluent), English fallback.
#
# Every row below is now observable in code, not aspirational. The "verified" column
# says how we know (battery check, measured value, or labelled API field).

| # | Trigger | System response (Tamil) | UI / API state | Status |
|---|---|---|---|---|
| 1 | STT unclear / low confidence | "சரியாகக் கேட்கவில்லை, தயவுசெய்து மீண்டும் சொல்லுங்கள்." | transcript shows "(unclear)" + mic re-arms | designed |
| 2 | Unknown product | list catalog in her language: "தக்காளி, கொத்தமல்லி, வெங்காயம் — எது?" | `intent: out_of_scope`, `products: {}` | ✅ verified (`400 unknown product`) |
| 3 | Ambiguous quantity ("send more") | asks "எத்தனை கிலோ?" — NEVER guesses | `products: {tomato: null}`, `clarification_needed: true` | ✅ verified (ambiguous + Kannada cases) |
| 4 | Duplicate approval | idempotency: "இந்த ஆர்டர் ஏற்கனவே அனுப்பப்பட்டது." | `duplicate_ignored`, no second order | ✅ verified — **and now survives a server restart** (tokens persisted) |
| 5 | n8n timeout/failure | "இணைப்பில் பிரச்சினை — ஒரு நிமிடத்தில் மீண்டும் முயற்சிக்கவும்." retry ×1 → queue to morning briefing | `record.n8n = "failed"` + `n8n_error`; **the order is still recorded and inventory/memory still update** | designed |
| 6 | Slow Sarvam (>5s once) | switch to typed-transcript fallback + say the swap line | no spinner >3s | designed |
| 7 | Engine-vs-observation anomaly | "நாளை மீண்டும் பார்ப்போம்" + Cognee logs it | `needs_human_review: true`, no dispatch | designed |
| 8 | **WhatsApp recipient not configured** | *(no false claim of a send)* | `twilio_status: "skipped"` + plain-language note. Previously it posted to `+919999999999` → 422 / code 572002 while looking successful | ✅ verified (battery) |
| 9 | **LLM slow / dead / returns nothing** | rules path answers instantly | `engine: "rules"`, `source: "template-fallback"`, `fallback_reason` explains why; `GET /llm/diag` shows `finish_reason` | ✅ verified (8 s budget; deep model returns `length` if under-budgeted) |
| 10 | **Grounding gate trips** | deterministic template ask is spoken instead | `explain.source = "template-fallback"`, `fallback_reason: "grounding gate: ..."`. Fires when the model omits an engine quantity — measured: it dropped coriander once | ✅ verified (battery) |
| 11 | **Injection / "ignore previous instructions"** | refuses; merchant speech is data | `intent: out_of_scope`, `injection_detected: true`, `products: {}` | ✅ verified (battery) |
| 12 | **Cognee cloud unreachable or slow** | *(silent to the merchant)* | recall returns `source: "local-fallback"` + the labelled static graph; dispatch writes local memory regardless | ✅ verified (60 s budget; real recall 12.93 s — the old 10 s budget failed every time) |
| 13 | **Dry demo day (no rain)** | *(no change to the story)* | `WEATHER_MODE=seeded` keeps 78% → coriander 6 → **₹546**. With `WEATHER_MODE=live` the numbers move and the narration must follow the screen | ✅ verified (seeded 78%/₹546; live 94%) |
| 14 | **Broken cached audio** | falls back to the typed transcript | "▶ Cached audio" plays `ui/assets/command_ta.wav` — regenerable with `python make_backup_audio.py`; it is labelled synthetic | ✅ verified (transcribes to `{tomato:20, coriander:10}`) |
| 15 | **Operator needs to re-run the demo** | — | `POST /demo/reset` (button: "↺ Reset demo state") restores seeded stock and clears idempotency. Server start also resets (`DEMO_RESET_ON_START=1`) | ✅ verified (battery) |
| 16 | **Dashboard feels slow** | — | was `localhost` → **~2035 ms/request**; now `127.0.0.1` → **3–33 ms**. Never use `localhost` in the UI, n8n nodes, curl or Postman | ✅ verified (raw-socket timing) |

Swap line (spoken, calm): "Let me switch to our backup audio so you hear it clearly — the flow is
identical either way."
All failure responses must look DESIGNED, not crashed.

## Pre-flight (5 minutes, before every rehearsal and before you go on stage)
1. `curl -s http://127.0.0.1:8000/health` → `status: ok`, `weather_mode: seeded`, `llm_mode: hybrid`
2. `POST /demo/reset` → stock back to tomato 12 / coriander 6
3. `python qa_battery.py` → **83 passed, 0 failed**
4. Click **▶ Cached audio** once and **Reason (Sarvam-105B)** once, so both paths are warm
5. `GET /llm/diag` → `available: true` (and `last_call.finish_reason: "stop"`, not `"length"`)
