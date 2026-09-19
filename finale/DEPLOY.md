# Deploy HarvestWise — Backend + Frontend (2 mins)

## 1) Backend (Render, free)
1. Push `finale/` to GitHub (keep `.env` out, use `.env.example`).
2. https://dashboard.render.com → New → Blueprint → connect repo → picks `render.yaml` **or** Manual:
   - Runtime: `Python 3.11`, Root: `finale`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - Health: `/health`
3. Add env vars (Dashboard → Environment):
   ```
   SARVAM_API_KEY
   COGNEE_BASE_URL
   COGNEE_API_KEY
   N8N_WEBHOOK_URL=https://venkatanarayana15.app.n8n.cloud/webhook/harvestwise-dispatch
   WA_AKG_URL=https://your-wa-akg.public.com  # if local, use ngrok http 3000
   WA_AKG_SESSION=un1b1
   WA_AKG_API_KEY=wag_...
   COPILOT_ALLOWED_PHONES=917010919624
   WEATHER_MODE=seeded
   LLM_MODE=hybrid
   ```
4. Deploy → `https://harvestwise-api.onrender.com` → `GET /health` → `ok`

> WA-AKG must be public. If running locally: `ngrok http 3000` → put `https://xxxx.ngrok-free.app` in `WA_AKG_URL` and update webhook in WA-AKG dashboard to `https://harvestwise-api.onrender.com/wa/inbound`.

## 2) Frontend (Vercel, 10s)
1. https://vercel.com → Add New → Project → import same repo → Root: `finale/ui` → Deploy (static, no build).
   - Or drag `ui/` folder to https://vercel.com/new
2. Open `https://harvestwise-ui.vercel.app/?api=https://harvestwise-api.onrender.com`
   - The `?api=` is saved to `localStorage.api_base` — share that link with judges.
3. Alternative: `npx serve ui -p 8080` or GitHub Pages (`ui/` as `gh-pages`).

## 3) Smoke test (prod)
```bash
curl https://harvestwise-api.onrender.com/health
curl -X POST https://harvestwise-api.onrender.com/copilot/simulate -H "Content-Type: application/json" -d '{"phone":"917010919624","text":"hi","channel":"simulate"}'
# WhatsApp: message "hi" to 7010919624 → reply + voice note (check data/copilot_chat.log)
```

## Local still works
```bash
cd finale && python -m uvicorn api.main:app --port 8000  # API
python -m http.server 8080 --directory ui               # UI → http://localhost:8080/?api=http://localhost:8000
```
