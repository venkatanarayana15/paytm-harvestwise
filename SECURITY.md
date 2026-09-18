# Security — HarvestWise

## Keys exposed 2026-09-18 — ROTATE BEFORE THE FINALE
`finale/.env` once contained real Sarvam + Cognee + Twilio credentials and was pasted into the root
`readme` while the repo was public. Treat every value in that file as **burned**.

**Rotation status: ⬜ OPEN — owner: team (do not mark closed until you have done it)**

| Provider | Where |
|---|---|
| Sarvam | indus.sarvam.ai → API keys → regenerate |
| Cognee | tenant dashboard → rotate |
| Twilio | Console → Auth Token → secondary → promote |

Also rotate `N8N_MCP_TOKEN` and `N8N_MCP_URL` if they ever appeared in a shared log or screenshot.

## .env hygiene
- Never commit `.env` — `.gitignore` blocks `.env`, `.env.*`, `finale/.env`
- Commit only `finale/.env.example` (template; now documents every variable the app reads)
- On build day: `cp finale/.env.example finale/.env`, then paste fresh keys
- Verify before any push: `git check-ignore -v finale/.env` must report the ignore rule
- `api/main.py` now loads `.env` from `BASE_DIR` **and** the cwd, so the app cannot silently start
  with an unloaded key when launched from a different directory

## Local artifact hygiene
`.gitignore` also covers runtime state that should never be reviewed or committed:
`finale/cognee/memory.json`, `finale/data/seed.json`, `finale/data/runtime_state.json`,
`finale/data/dispatched_tokens.json`, `finale/dispatch_record.json`, `finale/tts_*.wav`,
`finale/audio/*.wav`, `.playwright-mcp/`, `qa-runs/n8n-lab/`.
If any of these were committed earlier, purge them from history before publishing the repo.

## What was hardened in the 2026-09-18 pass
- **Removed `verify=False`** from the weather fetch in `engine/restock.py`. It had been disabling TLS
  certificate verification for no reason. Verified absent and TLS is on by default again.
- **No more placeholder sends.** `_fire_twilio` refuses to message the literal placeholder
  `whatsapp:+919999999999`. Previously that produced Twilio error 572002 while the dispatch record
  looked like a successful WhatsApp send — a false capability claim, not just a bug.
- **No secrets in n8n workflow files.** All credentials moved to `$env.*`
  (`COGNEE_BASE_URL`, `COGNEE_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_WHATSAPP_TO`, …). A tenant URL
  had been hardcoded into `n8n/daywrap.json`; it now reads from the environment.
- **LLM output cannot move money or invent quantities.** Every quantity in an outbound payload is
  copied from the deterministic engine; quantities the model emits are discarded before merge
  (`_products_from_llm_names`). Safety refusals (decline / out-of-scope / prompt injection) cannot be
  overturned by the model.
- **Prompt injection is an explicit, tested path.** Merchant speech is treated as data;
  `injection_detected: true` forces `out_of_scope` and orders nothing (asserted by the battery).
- **Money actions require a single-use token**, and idempotency now survives a restart
  (`data/dispatched_tokens.json`) instead of dying with the process.
- **Error surfaces are informative, not leaky.** `/llm/diag` reports model names, latency and
  `finish_reason` — never key material or prompt contents.
