# n8n Cloud + Twilio WhatsApp — Setup Checklist (Build Day)

Total time: ~60 min (Twilio ~20 · n8n ~30 · final test ~10).
Do these in order. Each step has a ✅ verify line — don't skip ahead.
Owner: any one person with the Twilio + n8n logins. A second phone helps for the buzz test.

---

## Part 0 — Gather (5 min)

- [ ] Twilio Console open: https://console.twilio.com (Account SID + Auth Token visible on the dashboard home)
- [ ] Demo phone: WhatsApp installed and able to send/receive
- [ ] n8n Cloud open: https://venkatanarayana15.app.n8n.cloud (owner login)
- [ ] The 3 files from `finale/n8n/` downloaded: `dispatch.json`, `briefing.json`, `daywrap.json`
- [ ] Local API running: `curl -s http://127.0.0.1:8000/health` → `"status":"ok"`

> **No tunnel needed.** The API POSTs *outbound* to n8n Cloud's public webhook URL.
> n8n never calls your laptop — that's why this works from any Wi-Fi, including venue.

---

## Part 1 — Twilio: verified recipient + template (20 min)

### 1.1 Join the sandbox from the demo phone
1. Twilio Console → **Messaging → Try it out → Send a WhatsApp message**.
2. On the demo phone, send the shown join code (e.g. `join orange-lion`) via WhatsApp
   to the sandbox number **+1 415 523 8886**.
3. Wait for Twilio's "connected to the Sandbox" reply.

✅ **Verify:** the phone received "You are connected...".

> In the sandbox, "verified recipient" = **joined participant**. Every number that must
> buzz on stage must send this join message once. Trial/sandbox sessions and
> participants reset periodically — **re-join the morning of the demo** (step 1.4).

### 1.2 Fill `.env` (finale/.env)
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+91XXXXXXXXXX   # the phone that joined, with whatsapp: prefix
```
✅ **Verify:** `TWILIO_WHATSAPP_TO` is NOT the placeholder `+919999999999` (the API refuses to send there — by design).

### 1.3 Content template SID
1. Console → **Messaging → Content Tools → Content Templates** (Content Builder).
2. Sandbox accounts ship with **pre-approved templates** — open one and note its SID
   (starts with `HX...`). If your plan allows submitting a template, create
   "HarvestWise order" with 4 variables: `{{1}}` qty · `{{2}}` product · `{{3}}` supplier · `{{4}}` total.
3. Put its SID in `finale/.env` as `TWILIO_CONTENT_SID` (and `TWILIO_ORDER_CONTENT_SID`).

### 1.4 Morning-of re-join + smoke send
- [ ] Demo phone re-sends the `join ...` code (sandbox expiry is the #1 stage-day gotcha).
- [ ] Send the template once from the console's "Send a WhatsApp message" page with dummy variables.

✅ **Verify:** the phone buzzes. If you see error **63016** here, the ContentSid is not
sandbox-approved — use a pre-approved template's HX sid from step 1.3.
If you see **572002**, the recipient isn't joined — redo 1.4.

---

## Part 2 — n8n Cloud: import, variables, activate (30 min)

### 2.1 Credentials first (before importing)
1. n8n → **Credentials → Add credential → Header Auth**, name it exactly `twilio-basic`.
2. Header name: `Authorization`. Header value: `Basic <base64>` — compute it locally:
   ```bash
   echo -n "ACxxxxxxxx:your_auth_token" | base64
   ```
3. Save.

### 2.2 Define Variables (n8n Cloud's supported way — NOT `$env`)
n8n Cloud may deny `$env` access inside expressions. **Variables** (`$vars.*`) always work.
- [ ] n8n → **Settings → Variables**, create:
  | Name | Value |
  |---|---|
  | `COGNEE_BASE_URL` | your `https://tenant-XXX...cognee.ai` |
  | `COGNEE_API_KEY` | Cognee key |
  | `TWILIO_ACCOUNT_SID` | `AC...` |
  | `TWILIO_WHATSAPP_TO` | `whatsapp:+91XXXXXXXXXX` (joined phone) |
  | `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` |
  | `TWILIO_ORDER_CONTENT_SID` | `HX...` |
  | `TWILIO_BRIEFING_CONTENT_SID` | `HX...` (or reuse ORDER for the test) |

### 2.3 Import the 3 workflows
- [ ] **Workflows → Create Workflow → ⋯ menu → Import from File** → `dispatch.json` → repeat for `briefing.json`, `daywrap.json`.

### 2.4 The `$env` check (do NOT skip)
Open each imported workflow and look at the HTTP-node expressions
(`"Twilio WhatsApp order"`, `"Weather (IMD-shaped)"`, `"Cognee add_text"`, `"Cognee cognify"`):
- If expressions render values → fine.
- If you see **"access to env vars denied"** or an empty value → **Find & replace in the
  workflow**: `$env.` → `$vars.` (Ctrl+H in the expression editor). Every node. Every workflow.

### 2.5 Attach credentials + activate
- [ ] `dispatch.json`: open **"Twilio WhatsApp order"** → Credentials → select `twilio-basic`.
- [ ] Toggle **Active** (top-right) on `dispatch`.
- [ ] Open the **Webhook** node → copy the **Production URL**:
  `https://venkatanarayana15.app.n8n.cloud/webhook/harvestwise-dispatch`
- [ ] Make `finale/.env`'s `N8N_WEBHOOK_URL` exactly that URL.

> ⚠️ **Production URL returns 404 while the workflow is inactive.** The `.env` already
> points at the production path — if dispatches come back `n8n: failed 404`, the toggle is off.

- [ ] Activate `briefing` (cron 6:30 AM) and `daywrap` (webhook `harvestwise-daywrap`) too.

### 2.6 Fire the real test (phone must buzz)
```bash
# with the local API up:
curl -s -X POST http://127.0.0.1:8000/demo/reset
# then in the dashboard: Run typed command → ✅ சரி → Dispatch
```
✅ **Verify (all four):**
1. Dashboard n8n panel shows `"status": "dispatched"` and `n8n: fired`.
2. **n8n → Executions** shows a green run for HarvestWise - Dispatch (open it — this is your judge-facing evidence; do 2-3 runs so history is never empty).
3. `twilio_status` in the record is `200`.
4. **The phone buzzes** with the order.

### 2.7 Test the validation branch (judges love this)
```bash
curl -s -X POST https://venkatanarayana15.app.n8n.cloud/webhook/harvestwise-dispatch \
  -H "Content-Type: application/json" -d '{"product":"tomato"}' -i | head -1
```
✅ **Verify:** HTTP **422** with `"status":"rejected"` — proves n8n independently re-validates before sending.

### 2.8 (Optional) fire briefing + daywrap once
- `briefing`: open workflow → **Test workflow** (runs the 6:30 flow immediately) → phone gets the morning briefing.
- `daywrap`:
  ```bash
  curl -s -X POST https://venkatanarayana15.app.n8n.cloud/webhook/harvestwise-daywrap \
    -H "Content-Type: application/json" \
    -d '{"merchant_id":"lakshmi","products_ordered":{"tomato":20},"total_inr":360,"spoilage_prevented":3}'
  ```
  ✅ `{"status":"learned",...}` and a green Cognee `add_text` node in Executions.

---

## Part 3 — Final pre-stage verification (10 min)

- [ ] `curl -s http://127.0.0.1:8000/health` → ok, `n8n: configured`, `twilio: configured`, `twilio_recipient` shows the real number
- [ ] Full demo flow once: reset → typed command → சரி → dispatch → **buzz received** + ledger `12 → 32`
- [ ] n8n Executions has ≥3 green dispatch runs
- [ ] Demo phone re-joined the sandbox **this morning** (1.4)
- [ ] `POST /demo/reset` → clean state for stage

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `n8n: failed 404` in dispatch record | Workflow not **Active** (production path 404s) | Toggle Active in n8n, retry |
| `"access to env vars denied"` in a node | n8n Cloud restricts `$env` | Replace `$env.` → `$vars.` (Variables from 2.2) |
| Twilio **572002** | Recipient not joined/verified | Re-do sandbox join (1.1/1.4) |
| Twilio **63016** | ContentSid not approved for sandbox | Use a pre-approved template's HX sid (1.3) |
| n8n fired, no buzz | Twilio node errored inside the run | Open the execution → check the Twilio node's output body |
| `twilio_status: "skipped — demo mode"` | `TWILIO_WHATSAPP_TO` missing in **finale/.env** | Set it (1.2) — the API skips rather than fake-sends, by design |
| Buzz works locally, fails at venue | Sandbox participant expiry | Re-join from the venue Wi-Fi in the morning |

*After this checklist: only key rotation (SECURITY.md), crew-recorded Tamil audio, and two full rehearsals remain.*
