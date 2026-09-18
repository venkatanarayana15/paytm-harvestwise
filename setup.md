# HarvestWise — Full WhatsApp Copilot Setup (Step-by-Step)

> One linear path from zero to a live WhatsApp dispatch bubble. Copy-paste in order. Windows/PowerShell. ~8 min.

## Prereqs

- Docker Desktop running, `D:\Hackathons\paytm` + `D:\Hackathons\WA-AKG` cloned, Python 3.11+
- Allowed phone: `+91 7010919624` (in `COPILOT_ALLOWED_PHONES`). QR scan needs a phone with WhatsApp.

---

## STEP 0 — Confirm Prereqs (30s)

```powershell
docker --version; docker compose version
python --version
```

Expect Docker 29.x, compose v5.x.

---

## STEP 1 — Start WA-AKG Gateway (port 3000)

```powershell
cd D:\Hackathons\WA-AKG
docker compose ps
# If not Up:
docker compose up -d
docker ps  # -> wa-akg-app 0.0.0.0:3000, wa-akg-db 0.0.0.0:3307->3306
```

Wait 15s until `http://localhost:3000` loads.

```powershell
python -c "import httpx; print(httpx.get('http://127.0.0.1:3000/',timeout=5).status_code)"
# -> 200
```

> First ever run: Docker build takes ~5 min (Next.js + MySQL). Subsequent `up -d` is 10s.
> If MySQL 3306 is busy on host, this compose uses `3307->3306` (see `docker-compose.yml`).

---

## STEP 2 — Start HarvestWise API (port 8000)

```powershell
cd D:\Hackathons\paytm\finale
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# Verify .env has 5 copilot vars
Select-String -Path ".env" -Pattern "WA_AKG|COPILOT|TWILIO_CONTENT"

Start-Process -FilePath python -ArgumentList "-m","uvicorn","api.main:app","--host","0.0.0.0","--port","8000" -WindowStyle Hidden
Start-Sleep -Seconds 6
python -c "import httpx,json; print(json.dumps(httpx.get('http://127.0.0.1:8000/health',timeout=10).json()['copilot'],indent=2))"
# -> "wa_akg": true, "twilio_freeform": true, "allowed_phones": ["917010919624"]
```

If `wa_akg: false` add to `finale/.env` and restart:

```
WA_AKG_URL=http://127.0.0.1:3000
WA_AKG_SESSION=f2sxa9
WA_AKG_API_KEY=wag_lJVg8D2OT0Su8lpZhQOaFk83xlpQxu4Y
COPILOT_ALLOWED_PHONES=917010919624
TWILIO_CONTENT_MODE=freeform
TWILIO_TEMPLATE_VARS=6
```

Dashboard: `http://localhost:3000` — Login `admin@harvestwise.in` / `HarvestWise@2026`  
Session: `harvestwise` (`sessionId f2sxa9`) — API `GET /api/sessions/f2sxa9`  
Webhook (Docker → host): `http://host.docker.internal:8000/wa/inbound` events `["message.received"]`

---

## STEP 3 — Verify Brain (no WhatsApp needed) — Must be 103/103

```powershell
cd D:\Hackathons\paytm\finale
python qa_battery.py
# -> === RESULT: 103 passed, 0 failed ===
```

If not 103: `GET http://127.0.0.1:8000/health` → check `copilot`, `llm_last`. See `FAILPATHS.md`.

---

## STEP 4 — Verify Webhook Wiring (proves Docker → host before QR)

```powershell
docker exec wa-akg-app wget -qO- http://host.docker.internal:8000/health | Select-String -Pattern "status"
# -> "status":"ok"

python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/copilot/state',timeout=5).json())"
# -> transports: wa_akg True

# Fake WA-AKG message through /wa/inbound (live path, no QR needed):
python -c "import httpx; r=httpx.post('http://127.0.0.1:8000/wa/inbound',json={'event':'message.received','data':{'key':{'remoteJid':'917010919624@s.whatsapp.net'},'type':'TEXT','content':'நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி'}},timeout=10); print(r.json()['result']['status'], r.json()['result']['basket_total_inr'])"
# -> awaiting_approval 546

python -c "import httpx; r=httpx.post('http://127.0.0.1:8000/wa/inbound',json={'event':'message.received','data':{'key':{'remoteJid':'917010919624@s.whatsapp.net'},'type':'TEXT','content':'சரி'}},timeout=10); print(r.json()['result']['status'])"
# -> dispatched

python -c "import httpx; httpx.post('http://127.0.0.1:8000/demo/reset',timeout=10)"
```

Simulate variant (offline, same brain, never sends real WhatsApp):

```powershell
python -c "import httpx; r=httpx.post('http://127.0.0.1:8000/copilot/simulate',json={'phone':'917010919624','text':'நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி'},timeout=10); print(r.json()['status'], r.json()['basket_total_inr'])"
# -> awaiting_approval 546
```

---

## STEP 5 — Scan QR (only human step) — Makes it Real WhatsApp

```powershell
# 1) Check current status
python -c "import httpx; s=httpx.Client(follow_redirects=True); r=s.get('http://127.0.0.1:3000/api/auth/csrf',timeout=5); csrf=r.json()['csrfToken']; s.post('http://127.0.0.1:3000/api/auth/callback/credentials',data={'csrfToken':csrf,'email':'admin@harvestwise.in','password':'HarvestWise@2026'},timeout=5); print(s.get('http://127.0.0.1:3000/api/sessions/f2sxa9',timeout=5).json()['data']['status'])"
# -> SCAN_QR

# 2) Open QR
start D:\Hackathons\WA-AKG\qr-harvestwise.png
# OR http://localhost:3000 -> Sessions -> harvestwise -> Show QR

# 3) Phone: WhatsApp -> Linked Devices -> Link a Device -> Scan

# 4) Verify CONNECTED
python -c "import httpx; s=httpx.Client(follow_redirects=True); r=s.get('http://127.0.0.1:3000/api/auth/csrf',timeout=5); csrf=r.json()['csrfToken']; s.post('http://127.0.0.1:3000/api/auth/callback/credentials',data={'csrfToken':csrf,'email':'admin@harvestwise.in','password':'HarvestWise@2026'},timeout=5); print(s.get('http://127.0.0.1:3000/api/sessions/f2sxa9',timeout=5).json()['data']['status'])"
# -> CONNECTED
```

> QR rotates ~60s. If it expires: `python -c "import httpx; s=httpx.Client(...); s.post('http://127.0.0.1:3000/api/sessions/f2sxa9/start',...)"` then fetch new `GET /api/sessions/f2sxa9` QR.
> Fix for first-ever `sh: missing ]` admin bug: `docker exec wa-akg-app node scripts/setup-admin.js "admin@harvestwise.in" "HarvestWise@2026"` (already done in current deploy).

---

## STEP 6 — Live Demo (what the judge sees)

From **+91 7010919624** send to the **linked WhatsApp number**:

```
நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி
```

Expect back:

```
... 20 kg தக்காளி -> Rs.360
... 6 bunch கொத்தமல்லி -> Rs.186
Total Rs.546
Stock: tomato 12->32 ... (ledger updated)
Reply சரி to confirm
```

Reply:

```
சரி
```

Expect back (kill-shot bubble):

```
HarvestWise ✅ Order dispatched
• 20 kg தக்காளி -> Rs.360
• 6 bunch கொத்தமல்லி -> Rs.186
Total Rs.546
Stock: tomato 12->32, coriander 5->11 (ledger + memory updated)
```

Voice note: same sentence as audio → identical loop (Sarvam `saaras:v3` OGG native, no ffmpeg).

Reset for next run:

```powershell
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/demo/reset',timeout=10).json()['stock']['lakshmi']['tomato'])"
# -> 12
```

---

## STEP 7 — If Blocked (fallbacks, never quit)

| Blocker | Fix |
|---|---|
| `SCAN_QR` never `CONNECTED` | QR expired → refresh `POST /api/sessions/f2sxa9/start`, fetch new QR |
| `wa_akg: False` | Re-add `WA_AKG_*` to `finale/.env`, restart API `Get-Process python \| Stop-Process` |
| No spare phone / no QR | Demo via API: `POST /copilot/simulate` or `POST /wa/inbound` (STEP 4) — same `546` + `12→32` proof, 103/103 is certificate |
| `wa-akg-app` down | `cd D:\Hackathons\WA-AKG; docker compose restart` |
| Twilio fallback | `TWILIO_CONTENT_MODE=freeform` already set; `POST /twilio/inbound` (sandbox, re-join morning of demo) |

---

## Quick Reference

| URL | Purpose |
|---|---|
| `http://localhost:3000` | WA-AKG dashboard (QR, sessions, webhooks, API key) |
| `http://127.0.0.1:8000/health` | HarvestWise health + `copilot` status |
| `http://127.0.0.1:8000/copilot/state` | Pending orders, allowlist, transports |
| `http://127.0.0.1:8000/docs` | FastAPI Swagger |
| `D:\Hackathons\WA-AKG\qr-harvestwise.png` | Cached QR image (regenerate with `python -c "import qrcode,httpx; ..."` ) |
| `D:\Hackathons\WA-AKG\.env` | WA-AKG secrets (DB, AUTH_SECRET, admin) |
| `D:\Hackathons\paytm\finale\.env` | HarvestWise secrets (Sarvam, Cognee, Twilio, WA_AKG) |

After STEP 6 succeeds once, you are finale-ready — just re-run STEP 3 battery + STEP 5 status before the pitch.
