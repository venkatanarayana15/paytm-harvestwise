# n8n Workflows — HarvestWise Paytm Copilot

> All workflows are transport-agnostic: trigger via `POST /wa/inbound` (WA-AKG), `POST /twilio/inbound`, `POST /copilot/simulate` (offline), or dashboard `POST /dispatch`. Credentials via env: `N8N_WEBHOOK_URL`, `WA_AKG_*`, `TWILIO_*`. Search nodes with `usage=agentTool` when wiring as Agent tools.

## 1) Voice Order → Approve → Dispatch
```
Merchant voice note (WhatsApp) ─┐
                               ├─ /wa/inbound (AUDIO) → Sarvam STT (saaras:v3) → transcript
Dashboard mic ─────────────────┘
         │
         ▼
   _handle_merchant_message (rules intent + Sarvam P1) → engine.recommendation() → pending_orders[phone]
         │  ask_text + CONFIRM_SUFFIX (Tamil-grounded P3, gate: every qty present)
         ▼
   _copilot_send(text, voice_mode) → WA-AKG /api/messages/{session}/{jid}/send (text)
                                  → if voice_mode in (voice,both): Sarvam TTS bulbul:v3 → WA-AKG /api/messages/{session}/{jid}/media type=audio
         │
Merchant: "சரி" / "yes" (APPROVE_WORDS, word-safe)
         ▼
   _approve_and_dispatch → validate_order → single-use token → dispatch_order → record_delivery (stock_before→after)
         ├─ _append_memory_audit → data/cognee/memory.json
         ├─ cognee.remember_async(add_text→cognify) [fire-and-forget, never blocks]
         ├─ _fire_n8n(record) → POST N8N_WEBHOOK_URL {record, stock movement, total_inr}
         └─ _fire_twilio / WA-AKG confirm (voice if preferred)
```

## 2) Credit-Recovery Nudge (future, wired via Cognee recall)
```
Cron (n8n) daily 10am → GET /memory + GET /cognee/context → debtors with overdue → POST /wa/inbound synthetic → copilot sends nudge (text+voice) via WA-AKG
```

## 3) Growth Partner Daily Brief
```
n8n Cron 8am → GET /soundbox/briefing → TTS → WA-AKG media (voice) + dashboard card. Also on-demand via "How to grow sales?" → _qa_answer(why) with engine factors.
```

## 4) Inventory Guard
```
Every dispatch → stock_snapshot → if stock < threshold → n8n alert → supplier lead (Paytm revenue stream)
```

## Low-latency guarantees
- Cognee recall is NEVER on hot path: background Thread + 5-min cache (`_COGNEE_CTX_CACHE`). Dashboard reads cache via `GET /cognee/context`.
- Sarvam calls bounded via `_SDK_EXECUTOR` + hard timeouts: STT 45s, TTS 40s, intent 8s.
- Health cache (30s) so first paint never blocks.

## Wiring checklist
- [ ] `N8N_WEBHOOK_URL` set → _fire_n8n fires
- [ ] WA-AKG session `un1b1` healthy → WA-AKG text+audio
- [ ] `SARVAM_API_KEY` set → STT/TTS live, else browser speechSynthesis fallback (labeled)
- [ ] `COGNEE_BASE_URL` + `COGNEE_API_KEY` set → graph grows
