# Security — HarvestWise

## Keys burned 2026-09-18
`finale/.env` once contained real Sarvam + Cognee + Twilio tokens and was pasted into `readme` during build (now redacted). Treat those values as **burned**.

**Action:** rotate in consoles before finale:
- Sarvam: indus.sarvam.ai → API keys → regenerate
- Cognee: tenant dashboard → rotate
- Twilio: console → Auth Token → secondary → promote

## .env hygiene
- Never commit `.env` — `.gitignore` blocks `finale/.env` and root `.env`
- Commit only `finale/.env.example` (template)
- On build day: `cp finale/.env.example finale/.env` then paste fresh keys
- `git check-ignore -v finale/.env` must say `.env` before push
