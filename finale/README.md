# HarvestWise — Finale Build (vertical slice)

Goal: on build day this repo means **INTEGRATE + REHEARSE**, not architect.
Scope = frozen vertical slice (knowledge/08): tomato + coriander restocking, one Tamil voice command,
deterministic recommendation, voice approval, n8n dispatch, memory + inventory update.

Verified 2026-09-18: **83/83 QA battery green** (`python qa_battery.py`) and the dashboard renders
end-to-end in a real browser (headless Chrome DOM dump).

## Structure (as built)
```
finale/
  api/main.py              FastAPI orchestration — /health /stt /intent /rec /rec/basket
                           /explain /reason /approve /voice/approve /dispatch /tts
                           /memory /state /demo/reset /llm/diag /soundbox/briefing
                           /cognee/recall /cognee/remember
                           single-use approval tokens, persisted idempotency
  engine/restock.py        DETERMINISTIC engine: stock-adjusted demand × rain modifier.
                           Also owns the WEATHER modes and the live inventory ledger.
                           The LLM never sets a quantity.
  engine/llm.py            Sarvam LLM layer (P1 intent, P2 grounded reasoning, P3 explain)
                           with hard wall-clock budgets + a grounding gate.
  engine/cognee_client.py  Cognee causal memory: add_text -> cognify -> recall.
  data/seed_gen.py         regenerates data/seed.json FROM the engine CATALOG (no drift)
  data/runtime_state.json  live inventory + order ledger (written by dispatch)
  prompts/P1..P4           Sarvam prompts (intent, ReAct, explain, dispatch)
  n8n/*.json               importable workflows: briefing / dispatch / daywrap
  cognee/seed_memory.py    local memory seed (labeled offline fallback)
  cognee/graph_fallback.svg static graph, shown if the cloud is unreachable
  ui/index.html            single-file dashboard (real mic capture, typed fallback,
                           live stock/ledger panel, LLM reasoning + Cognee recall)
  ui/assets/command_ta.wav CACHED BACKUP command audio (TTS — see labeling note)
  qa_battery.py            83 regression checks — run with the API up
  make_backup_audio.py     regenerates the cached backup audio
  FAILPATHS.md             the failure states + expected behavior
```

## Run
```
pip install -r requirements.txt
cp .env.example .env                 # add SARVAM_API_KEY (STT/TTS/LLM)
python data/seed_gen.py              # writes data/seed.json (synced from engine)
python cognee/seed_memory.py         # writes cognee/memory.json
python -m uvicorn api.main:app --port 8000
start ui/index.html                  # dashboard at file://
```
Open the API at **http://127.0.0.1:8000**, never `http://localhost:8000`.

> Why: on this machine `localhost` costs **~2 s per request** (IPv6 `::1` is tried first, then
> falls back), while `127.0.0.1` answers in 3–35 ms. The dashboard already uses the IPv4 literal.
> Use it in the n8n nodes and any curl/Postman calls too.

Demo command (deck-consistent): **"நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி"**
→ basket: tomato 20 kg × ₹18 = ₹360 · coriander 10→6 bunches (rain −40%) × ₹31 = ₹186 · **₹546**.

The parser also accepts "3 crates tomato" (60 kg) — for the ₹546 story use the 20 கிலோ phrasing.

## Demo-safety switches (all optional, sensible defaults)
| Var | Default | Effect |
|---|---|---|
| `WEATHER_MODE` | `seeded` | `seeded` = the 78% constant, so **₹546 holds on any day at any venue**. `live` = real Open-Meteo for Basavanagudi. |
| `DEMO_RESET_ON_START` | `1` | Inventory resets to the seeded baseline on every server start, so runs repeat. |
| `LLM_MODE` | `hybrid` | `hybrid` = Sarvam assists but rules stay authoritative; `off` = pure deterministic. |
| `LLM_TIMEOUT` | `8` | Hard budget for the fast model. On timeout the rules path answers — the demo never hangs. |

`POST /demo/reset` restores the seeded inventory mid-session (or click **↺ Reset demo state**).

## The two-model rule (measured, not guessed)
| Path | Model | Measured | Used for |
|---|---|---|---|
| live loop | `sarvam-105b-conversations` | **~0.3–2 s** | P1 intent classification, P3 spoken ask |
| on demand | `sarvam-105b` (reasoning) | **~55–61 s** | the "Reason (Sarvam-105B)" button, `{"deep": true}` |

Pointing the live loop at the reasoning model is the trap: it emits `reasoning_content` first and
burned 10,263 chars / 32.5 s with the doctrine P1 prompt, returning `content=null` at 1200 tokens
(the budget was consumed by reasoning). `GET /llm/diag` shows the last call's model, latency and
`finish_reason` — check it first if the LLM ever seems silent.

**Grounding gate:** a generated Tamil ask is rejected unless it names *every* engine quantity.
Measured failure it prevents: the model said "நாளை 20 கிலோ தக்காளி வேண்டுமா?" and silently dropped the
coriander, which would have let the merchant approve an item she never heard.

## Build-day protocol (Luma agenda: build 10:00–17:00, demos 18:00–20:00)
- **Hour 0–2:** clone · run seed · `python qa_battery.py` (expect 83/83) · dashboard shows state
- **Hour 2–5:** import the 3 n8n JSONs, point webhooks at your tunnel · pre-run one dispatch so
  execution history has real records · hit `/reason` once to pre-warm
- **Hour 5–7:** noise stress-test the command · RECORD BACKUP DEMO (OBS + phone) · rehearse 3:00
- Checkpoints only at T+2h / T+4h / T+6h

## Non-negotiables on build day (knowledge/08 + 09)
- Data on screen = "Paytm-transaction-shaped seeded demo data" — never imply live Paytm access
- LLM explains; engine decides; n8n re-validates — Sarvam must never set a quantity
- Billing = simulated ₹149 concept; never "Paytm handles it"
- No new stats, no new billing mechanics — ledger is law

## WhatsApp (Twilio trial) — one-time crew step
`TWILIO_WHATSAPP_TO` must be set to a **verified recipient** (Twilio Console → Messaging → WhatsApp
sandbox settings). Without it the API now **skips the send and says so** — it no longer posts to the
placeholder `+919999999999`, which returned error 572002 while looking like a successful dispatch.
The demo still completes: the dispatch record and inventory/memory update are real either way.

## Audio labeling
`ui/assets/command_ta.wav` / `command_en.wav` are **synthetic (bulbul:v3)** and exist only as the
cached backup. The on-stage live command should still be crew-recorded human speech. Say so when you
use the backup: *"this is our cached backup audio — the flow is identical."* Regenerate with
`python make_backup_audio.py`.
