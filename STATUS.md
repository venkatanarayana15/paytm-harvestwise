# STATUS — Team Sairam · HarvestWise · Paytm Build for India AI Hackathon
Living mission log. Mentor reads this FIRST every session; update on every decision/blocker/phase change.
Last updated: 2026-09-19 09:58 — Narrated copilot fail-safe video built (`copilot_narrated.mp4`, 32 s). 126/126 battery + 38-check UI smoke ALL GREEN; Q&A copilot live in 5 languages.

## Phase
Round 1: SHORTLISTED ✅ — HarvestWise PDF selected for the next round (portal + team confirmed 2026-09-15).
Finale: in-person build day — **FULL COPILOT WHATSAPP LIVE — CONNECTED ✅** WA-AKG `f2sxa9` CONNECTED (was SCAN_QR), webhook `host.docker.internal:8000/wa/inbound`, HarvestWise `wa_akg:true`, battery **103/103**, `/wa/inbound` live `awaiting_approval 546 → dispatched` proven. Send a real WhatsApp now.

## Blockers (owner + status)
1. Round-1 PDF upload confirmation — owner: team — CLOSED ✅ 2026-09-13
2. **`TWILIO_WHATSAPP_TO` not set** — owner: team — **CLOSED ✅ 2026-09-18**
   Verified end-to-end: dispatch → Twilio 201 → **`delivered`** on the demo phone, twice.
   `/whatsapp/status` now exposes recipient + live delivery state for the dashboard card.
3. **Crew-recorded Tamil command** — owner: Venkata / Malaravan — OPEN
   `ui/assets/command_ta.wav` currently holds a **labelled synthetic TTS** backup. Generator:
   `python make_backup_audio.py`. Stage audio should still be a human take.
4. **Rotate burned keys** — owner: team — OPEN (see SECURITY.md)
   Sarvam + Cognee + Twilio credentials were pasted into the root readme during build. Treat as burned.
5. **Import + activate the 3 n8n JSONs on n8n cloud** — owner: team — OPEN
6. **WA-AKG live transport** — owner: team — **CONNECTED ✅ 2026-09-18 23:35**
   `wa-akg-app` (wa-akg-app:latest) + `wa-akg-db` (mysql:8.0) both Up (ports 3000 / 3307->3306).
   Dashboard: http://localhost:3000  Admin: admin@harvestwise.in / HarvestWise@2026
   Session: `harvestwise` (sessionId `f2sxa9`, id `cmu744ruq...`) status `SCAN_QR` — QR at `D:\Hackathons\WA-AKG\qr-harvestwise.png` + `finale/qr-harvestwise.png` (also at `GET /api/sessions/f2sxa9`).
   API key: `wag_lJVg8D2O...` stored in `finale/.env` (WA_AKG_URL/SESSION/API_KEY).
   Webhook: `harvestwise-copilot` → `http://host.docker.internal:8000/wa/inbound` events `["message.received"]` (verified: Docker → host `GET /health` 200). HarvestWise `/health` reports `copilot.wa_akg: true`.
   **Action needed: scan the QR with WhatsApp Linked Devices NOW** — after that, merchant `917010919624` can use full loop (text/voice → ask → `சரி` → dispatch confirm 12→32). Until scanned, `/copilot/simulate` + `/wa/inbound` API (103/103) carry the demo.

## Locked decisions (do not relitigate without new evidence)
- Track 1 Merchant Growth AI; HarvestWise perishable-restocking wedge; Lakshmi = labeled representative persona
- Demo language TAMIL primary + English fallback (crew-fluent: Tamil/Telugu/English)
- Numbers: ledger 09 is law; billing = proposed + simulated; data = seeded + labeled
- **Demo determinism is a product decision**: `WEATHER_MODE=seeded` (default) so ₹546 holds any day;
  `DEMO_RESET_ON_START=1` so rehearsals repeat. Live weather and the deep reasoning model are
  deliberate *opt-ins*, never the default path.
- **The live loop never uses the reasoning model.** Measured: `sarvam-105b` takes 32–61 s and returns
  empty content when its token budget is consumed by reasoning. Fast loop = `sarvam-105b-conversations`
  (~0.3–2 s); deep reasoning is a separate, labelled, on-demand call.

## Next single action
**WA-AKG is LIVE — scan the QR NOW:** Open `http://localhost:3000` (or the PNG at `finale/qr-harvestwise.png`), WhatsApp → Linked Devices → Link a Device → scan. After `status: CONNECTED`, send a test: `நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி` → expect vernacular ask (546), then `சரி` → `HarvestWise ✅ Order dispatched · Total Rs.546 · Stock tomato 12→32`. If no spare phone, the API path is already 103/103 proven: `POST /wa/inbound` (WA-AKG payload) works. Then do blocker 5 (import 3 n8n JSONs) → blocker 4 (rotate keys).

## Eval log
- **2026-09-19 (morning, copilot intelligence pass): 126/126 battery + 38-check UI smoke ALL GREEN.**
  Judge-verified: the copilot is now a real Q&A product, not an order taker. Every answer is composed
  LIVE from the engine/ledger/catalog/weather — zero scripted numbers.
  - 🔴 **Word-boundary matching fixed**: `"ha" in text` fired the approval gate on "w*ha*t";
    `"no" in text` CANCELLED orders containing "now". `_word_hit()` does ASCII token-boundary
    matching (Indic stays substring). Regression-tested: "what is your policy?", "what time is it now?".
  - 🔴 **Every question was answered "I did not catch a product"** — the copilot could not answer
    anything. New Q&A intents (price/stock/why/weather/orders/sales/greeting/help) all composed from
    live data: "why 20 kg tomato?" returns the engine line with the CURRENT stock; stock answers are
    asserted in tests to match `/state` exactly.
  - 🔴 **EN "tomato 20kg" carried NO quantity** (glued token) — masked because the engine coincidentally
    also produced 20. Numbers glued to units are now split before parsing.
  - 🔴 **Telugu was never detected** (`\u0c00` range missing) and ALL copilot replies were Tamil-only.
    The full reply surface (ask, confirm, cancel, no-pending, help, welcome, Q&A) is now ta/kn/hi/te/en.
  - 🔴 **/dispatch trusted client total_inr** — a tampered payload could write a fake amount into the
    ledger, memory, n8n and WhatsApp. Server recomputes from CATALOG; mismatch is REFUSED; battery
    asserts 9999 is rejected and the ledger shows the engine price.
  - 🟠 WA-AKG send failure **silently ate the merchant's reply** — now cascades WA-AKG → Twilio → mock,
    every attempt labelled. WhatsApp voice notes STT with auto-language (`unknown`) instead of hardcoded ta-IN.
  - 🟠 `/demo/reset` did not clear `pending_orders` — a stale "சரி" after reset dispatched against fresh
    stock. Also clears issued tokens; pending baskets expire after 30 min (TTL).
  - 🟠 P1 prompt emits singular `product` while code read `products` — the LLM product-name assist was
    dead code. Now merged (quantity still discarded — doctrine holds).
  - 🟠 Copilot chat bubbles never showed awaiting/dispatched highlights (meta.status on a string).
  - 🟠 Sarvam ask was Tamil even for EN/KN/HI/TE orders; `/explain` and the P3 path are now
    language-aware; EN "why" answers use "tomato" not "தக்காளி".
  - ➕ Basket adjustment flow: "5 kg tomato less" → 20→15, "3 kg tomato more" → 15→18 (numbers only from
    her speech, engine re-priced). Merchant phone editable in the UI chip.
  - Every copilot response now carries a `reply` field (the exact WhatsApp bubble text) — the UI chat
    renders the same content WhatsApp sends.
  - Battery grew 103 → **126** checks (sections 14-15: Q&A grounded-data, word-boundary regressions,
    multilingual orders/adjustments, money-tamper security, reset semantics). UI smoke grew 29 → 38
    (copilot chat loop driven in-browser: Q price → Q stock → order → awaiting → approve → dispatched
    ₹546 → ledger 12→32 → stock card mirrors).
- **2026-09-18 (21:00, WA-AKG LIVE): 103/103 battery green, Docker transports proven.**- **2026-09-18 (21:00, WA-AKG LIVE): 103/103 battery green, Docker transports proven.**
  - WA-AKG stack up after fixing Dockerfile `if [ -n "$ADMIN_EMAIL"]` missing-space bug (was `sh: missing ]`, admin never created) → `docker exec setup-admin` → login 200 → session `f2sxa9` `SCAN_QR` → API key `wag_lJVg...` → webhook `harvestwise-copilot` → `host.docker.internal:8000/wa/inbound` (`message.received`) → Docker→host `GET /health` 200 → HarvestWise `/health` now `copilot.wa_akg: true, twilio_freeform: true` → battery still 103/103 → live `POST /wa/inbound` payload proves `awaiting_approval 546` → `dispatched 2 · 546 · 12→32` before any phone is linked. QR saved (`WA-AKG/qr-harvestwise.png` + `finale/qr-harvestwise.png`, also `GET /api/sessions/f2sxa9`). MySQL remapped 3307->3306 (host conflict), DB healthy. Full loop is now: WhatsApp text/voice → Sarvam saaras:v3 OGG-native → `_handle_merchant_message` (allowlist + injection guard) → deterministic `recommendation()` → `template_ask` → `pending_orders[phone]` → `சரி` → per-item token+dispatch → stock ledger 12→32 + mock/copilot logs.
- **2026-09-18 (late night, copilot brain): 103/103 battery green — commit `a495fce` pushed.**
  - Full WhatsApp copilot built & verified end-to-end via `/copilot/simulate` (force_mock — no real sends):
    1. Merchant order (Tamil text): `நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி` → parsed, basket
       **₹546** (tomato 20kg + coriander 6 bunches @78% rain), vernacular ask with `சரி` confirm suffix.
    2. `சரி` → per-item token → idempotent dispatch → confirmation bubble proving the loop:
       `20 kg தக்காளி -> Rs.360 · 6 bunch கொத்தமல்லி -> Rs.186 · Total Rs.546 ·
       Stock: tomato 12->32, coriander 5->11 (ledger + memory updated)`.
    3. Security verified: unknown caller refused, injection (`ignore previous instructions`) blocked,
       repeat approval → `no_pending`, deny cancels + clears basket, reset restores for rehearsal.
  - New endpoints: `POST /wa/inbound` (WA-AKG JSON webhook) · `POST /twilio/inbound` (form-encoded
    webhook, voice notes → Sarvam saaras:v3 OGG-native STT) · `POST /copilot/simulate` (offline path) ·
    `GET /copilot/state` (pending orders + allowlist + transports). `/health` reports copilot status.
  - Outbound transport-agnostic `_copilot_send`: **WA-AKG > Twilio freeform > mock log**, labelled.
  - `TWILIO_CONTENT_MODE=freeform` added — kills the "Appt" template blocker in sandbox (plain Body).
  - Phone allowlist via `COPILOT_ALLOWED_PHONES`; default = `TWILIO_WHATSAPP_TO`. `.env.example` updated.
  - Battery grew 86 → **103** checks (section 13, 17 new).
- **2026-09-19 (morning, stage fail-safe #2): copilot Q&A demo RECORDED + NARRATED** —
  `finale/backup_demo/copilot_narrated.mp4` (H.264 + AAC, 1360×850, 32 s, **PRIMARY** fail-safe):
  real headed-Chromium run of the copilot chat — Q&A from live data (price ₹18, stock 12),
  Tamil order ₹546, "5 kg less" adjust 20→15 re-priced ₹456, "சரி" → dispatched, stock 12→27,
  ledger row — narrated by the same Sarvam `bulbul:v3`/`kavitha` voice as the product.
  Master `copilot.webm`, timestamped `copilot_transcript.txt`, proof stills
  `copilot_stage_ask/dispatched.png`. Regen: `node qa-runs/pw/record_copilot.js` then
  `python make_copilot_narrated.py` (rename Playwright's `page@*.webm` → `copilot.webm`).
  Same ⚠ as below: drives a real dispatch — `POST /demo/reset` after re-recording.
- **2026-09-19 (reliability hardening): API-wedge root cause FIXED.** After heavy bursts the
  API stopped accepting (health timeouts). Root cause: Sarvam SDK calls (`/stt`, `/wa/inbound`
  STT, `/tts`) ran directly in the route threadpool with **no outer timeout** — a hung provider
  call parked a worker forever; enough of them froze the server. All three now run on a dedicated
  bounded executor with hard deadlines (45/45/40 s) that return **labeled fallbacks** (typed
  transcript / "" / cached-audio hint) instead of hanging. Restart procedure fixed too: kill by
  port (`netstat`/`taskkill`), not by a pid file that was recording the bash subshell.
- **2026-09-18 (night, stage fail-safe): backup demo RECORDED + NARRATED** — `finale/backup_demo/`:
  real Full Auto run captured in headed Chromium → `demo_backup_narrated.mp4` (H.264 + AAC,
  1360×850, 34 s) with a Sarvam `bulbul:v3` narration track timed to the pipeline beats, plus a
  silent 23 s cut, 3 proof stills and the transcript. Playlist rules in `backup_demo/README.md`
  (honest labeling, fullscreen, never talk over the dispatch beat). ⚠ Recording drives a real
  dispatch (WhatsApp + ledger mutate) — always `POST /demo/reset` after re-recording.
- **2026-09-18 (evening, UI + WhatsApp pass): 86/86 battery green · 29/29 UI smoke green.**
  - ✅ **WhatsApp verified END-TO-END for the first time**: approve → dispatch → n8n 200 →
    Twilio **201** → Twilio API shows **`delivered`** (tomato + coriander, both). Re-join the
    sandbox **the morning of the demo** — trial/sandbox participants reset (N8N_TWILIO_SETUP.md §1.4).
  - New: `GET /whatsapp/status` (recipient + live Twilio delivery state), dispatch record now
    keeps `twilio_sid`; dashboard gained a WhatsApp delivery card + numbered pipeline stepper.
  - Dashboard rebuilt (`ui/index.html`): stepper (HEAR→DECIDE→APPROVE→DISPATCH→REMEMBER),
    dynamic stock cards with `↑ delivered` markers, dead code removed, broken CSS vars fixed,
    **STT language selector now actually wired** (was ignored — /stt always got ta-IN).
  - ⚠ Sarvam key in `.env` is still the burned one (preflight flags it) — rotation is a human task.
- **2026-09-18 (hardening pass): 86/86 battery green**, stable across 4 consecutive runs (0 failures,
  0 warnings). Reproduced by running the code, not reading it.
  Six defects were demo-breaking or doctrine-breaking. Full details + evidence: `finale/IMPROVEMENTS.md`.
  - 🔴 "Live weather" had **never worked**: a pre-encoded timezone (`Asia%2FCalcutta`) was double-encoded
    by httpx → HTTP 400 on every call, hidden by `except: pass`. Also fetched *today* while narrating
    "tomorrow".
  - 🔴 ₹546 was weather-dependent with no lock (dry day → coriander 10 → ₹670, failing two checks).
  - 🔴 All four WAV assets were byte-identical; `command_ta.wav` was the TTS *question*, not the order,
    so the cached-audio backup silently dropped coriander.
  - 🔴 WhatsApp never sent: no `TWILIO_WHATSAPP_TO` → posted to the placeholder number → Twilio 572002.
  - 🟠 Acceptance criterion #5 was unimplemented: memory.json unchanged and stock still 12 after a 20 kg
    order. Now a real ledger (`stock_before → stock_after`), an `order_history` audit trail and `/state`.
  - 🟠 Cognee was half-wired: recall timed out (10 s client budget vs 12.3 s real latency) and there was
    **no write path at all**. Now `add_text → cognify → recall` verified live against the tenant.
  - 🟠 Sarvam's LLM was never called despite P1–P4 existing. Now wired with the fast/reasoning model
    split, quantities structurally discarded, a grounding gate, and hard timeouts.
  - 🟠 `recommendation()` never returned `name_tn` → every Tamil product name rendered blank.
  - 🟡 `localhost` cost **~2035 ms per request** vs **3–33 ms** for `127.0.0.1` (IPv6 fallback).
    The dashboard was on `localhost`, so every click felt broken.
  - 🟡 n8n used nonexistent credentials (`$credentials.sid`, `cognee_url`, `api_url`); briefing sent a
    bogus `OPENWEATHER_KEY` to open-meteo; daywrap/briefing had no respond node.
  - 🟡 Docs contradicted each other (22 vs 28 vs the real 31 checks; a 20%-rain script vs the 78% story;
    Kannada-first DEMOSCRIPT vs Tamil-first build).
  - 🟡 **Provider flakiness found and absorbed:** Sarvam intermittently returns an Azure Application
    Gateway error page (`text/html`, 183 bytes) instead of JSON. Falls back correctly, but it made the
    suite non-deterministic. Added a single retry inside `_call` (verified: 4 consecutive clean runs)
    and a one-line `_clean_error` so `/llm/diag` shows something readable instead of an HTTP header dump.
  - Verified in the same pass: injection refusal, idempotency surviving restart, backup audio
    transcribing to `{tomato:20, coriander:10}`, seeded 78%/₹546, live path 94%, dashboard DOM render.
  - The suite now separates hard invariants (quantities, safety refusals, labelled fallbacks) from
    provider-dependent capability probes, which WARN instead of failing — degradation to rules is
    designed behavior, not a defect.
- 2026-09-18 (earlier): 31/31 checks — intent battery, engine invariants (20kg/6 bunches/₹546/rain 78%),
  approve→dispatch security (replay + bogus refused, deny gate held), graceful 400s, real STT round-trip.
- 2026-09-13: mentor red-team battery 9.5/10 across 10 adversarial tests; no further prompt defects found.
