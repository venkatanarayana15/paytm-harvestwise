# STATUS — Team Sairam · HarvestWise · Paytm Build for India AI Hackathon
Living mission log. Mentor reads this FIRST every session; update on every decision/blocker/phase change.
Last updated: 2026-09-13

## Phase
Round 1: SHORTLISTED ✅ — HarvestWise PDF selected for next round (portal confirmed + team confirmed shortlist 2026-09-15).
Finale: in-person build day — ACTIVE PREP.


## Countdown — VERIFY WITH TEAM FIRST
Round 1 deadline was "tomorrow" as of session start 2026-09-11/12. Today is 2026-09-13. If not uploaded, this is now <24h or OVERDUE — upload verification outranks everything.

## Blockers (owner + status)
1. Round-1 PDF upload confirmation — owner: team — CLOSED ✅ 2026-09-13
2. SARVAM_API_KEY (indus.sarvam.ai free credits) — owner: team — OPEN
3. Tamil command drafted + recorded WAV (crew-native; semantic: 3 crates tomatoes + 10 bunches coriander, tomorrow morning) — owner: Venkata / Malaravan — OPEN
4. Dual-SKU demo sign-off (recommended: yes; fallback tomato-only) — owner: crew — OPEN

## Locked decisions (do not relitigate without new evidence)
- Track 1 Merchant Growth AI; HarvestWise perishable-restocking wedge; Lakshmi = labeled representative persona
- Demo language TAMIL primary + English fallback (supersedes Kannada plan; crew-fluent: Tamil/Telugu/English)
- Numbers: ledger 09 is law; billing = proposed + simulated; data = seeded + labeled
- Mentor agent live (mode: all; restart opencode to activate /mentor)

## Next single action
Finale build is REAL and verified (22/22 API battery 2026-09-18): STT loop live (Sarvam saaras:v3, Tamil round-trip proven), deterministic engine calibrated (tomato 20kg / coriander 10→6 / ₹546 = deck), basket approve→dispatch with idempotency, UI has mic capture. Remaining: (1) record Tamil command WAV → `finale/ui/assets/command_ta.wav` — use "நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி" (NOT "3 crates" — that parses to 60kg and breaks the ₹546 story), (2) Twilio console: add merchant number as verified recipient (err 572002), (3) import-test the 3 repaired n8n JSONs on n8n cloud + activate, (4) rotate the Sarvam + n8n keys that were pasted into the root readme (now redacted; treat as burned).

## Eval log
- 2026-09-18: build verified — 22/22 checks: intent battery (Tamil numeric/word-num/decline/ambiguous), engine invariants (20kg/6bunches/₹546/rain 78%), approve→dispatch security (replay+bogus refused, deny gate held), graceful 400s, real STT round-trip → intent tomato=20. Secrets redacted from readme, .gitignore added. n8n JSONs rewritten to modern schemas (v2 IF + false branch, body extraction, Twilio HTTP node) after static audit found: body-wrapper bug (would hang webhook), wrong WhatsApp provider node, missing connections in briefing, no daywrap respond node. Cognee cloud probe: UP.
- 2026-09-13: mentor red-team battery 5/5 — numbers-trap refusal (G1) ✓ · scope-creep kill with hidden costs (G3) ✓ · hostile-paste Adopt/Fix/Reject (G6+G1) ✓ · trivial lookup direct answer, no trace ✓ (but over-read 14 files → added Pass-2 retrieval-economy rule) · judge-Q&A one-breath trust answer ✓. Default-to-frozen-scope on the open dual-SKU call = correct G3 behavior.
- 2026-09-13: battery #2 4/4 — deadline triage under 3h pressure (cut both options, stabilize+record plan with owner) ✓ · G5 escalation on data-sharing consent (refuse + options + human sign-off gate) ✓ · G2 multi-question (answered track call, queued latency/LinkedIn with reasons) ✓ · unknown-fact refusal on Soundbox pricing (offered web-check path, compliant swap) ✓. Re-test: retrieval-economy fix works (2 files vs 14). FINAL: 9.5/10 across 10 adversarial tests; no further prompt defects found.
