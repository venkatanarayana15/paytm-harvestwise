# STATUS — Team Sairam · HarvestWise · Paytm Build for India AI Hackathon
Living mission log. Mentor reads this FIRST every session; update on every decision/blocker/phase change.
Last updated: 2026-09-18 (UI rebuild + WhatsApp verified end-to-end)

## Phase
Round 1: SHORTLISTED ✅ — HarvestWise PDF selected for the next round (portal + team confirmed 2026-09-15).
Finale: in-person build day — **vertical slice is BUILT AND VERIFIED** (see Eval log).

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
   Set `$env` vars on the n8n side: `COGNEE_BASE_URL`, `COGNEE_API_KEY`, `TWILIO_ACCOUNT_SID`,
   `TWILIO_WHATSAPP_TO`, `TWILIO_WHATSAPP_FROM`, `TWILIO_ORDER_CONTENT_SID`,
   `TWILIO_BRIEFING_CONTENT_SID`, plus the `twilio-basic` httpHeaderAuth credential.

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
Build day is INTEGRATE, not build. Run `python qa_battery.py` first (expect **86/86**); if anything
fails, `GET /llm/diag` shows the last model call's latency and `finish_reason` — that is the fastest
diagnosis path for a silent LLM. Then do blockers 5 → 2 → 3 above.

## Eval log
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
