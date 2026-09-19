# Start Dev Environment

## Step 1: Start API Backend
```powershell
cd D:\Hackathons\paytm\finale
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Step 2: Open UI
Open `ui/index.html` in your browser (drag into Chrome/Firefox)

## Step 3: Test
Type in the chat box: "How can I increase sales?"

## Expected Result
- Chat shows your message
- Activity Log shows: api → sarvam → cognee → n8n
- Copilot responds with business insights
