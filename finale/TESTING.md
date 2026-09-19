# Test Plan: Paytm Copilot Voice-First

## End-to-End Test Cases

### 1. Voice Input Test
```powershell
# Step 1: Start API
cd D:\Hackathons\paytm\finale
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Step 2: Test STT
Invoke-WebRequest -Uri "http://localhost:8000/stt" -Method POST

# Step 3: Test TTS
Invoke-RestMethod -Uri "http://localhost:8000/tts" -Method POST -Body '{"text":"hello"}'

# Step 4: Test Preferences
Invoke-RestMethod -Uri "http://localhost:8000/preferences" -Method POST -Body '{"voice_mode":"voice"}'
```

### 2. Copilot Interaction Test
```powershell
# Test Growth Suggestion
$body = '{"phone":"917010919624","text":"How to grow sales","channel":"simulate"}'
$r = Invoke-RestMethod -Uri "http://localhost:8000/copilot/simulate" -Method POST -Body $body
$r.reply

# Test Voice Mode
$body = '{"phone":"917010919624","text":"Check stock","channel":"simulate"}'
$r = Invoke-RestMethod -Uri "http://localhost:8000/copilot/simulate" -Method POST -Body $body
$r.reply
```

### 3. n8n Integration Test
```powershell
# Simulate n8n webhook
$body = '{"order":"tomato","qty":20,"total":400}'
Invoke-RestMethod -Uri "https://your-n8n-webhook.com" -Method POST -Body $body
```

### 4. Cognee Memory Test
```powershell
# Add memory entry
Invoke-RestMethod -Uri "http://localhost:8000/cognee/add" -Method POST -Body '{"text":"customer prefers voice"}'

# Retrieve memory
Invoke-RestMethod -Uri "http://localhost:8000/cognee/recall" -Method POST -Body '{"query":"voice"}'
```

### 5. Latency Test
```powershell
$times = @()
for($i=0; $i<10; $i++) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5 | Out-Null
    $times += $sw.ElapsedMilliseconds
}
"Average: $(($times | Measure-Object -Average).Average)ms"
```

## Expected Results

| Test | Expected | Pass Criteria |
|------|----------|---------------|
| STT | transcript | "tomato" recognized |
| TTS | audio_url | Valid URL or mock |
| Preferences | saved | Mode updated |
| Copilot | reply | "Suggest" in response |
| n8n | status | 200 OK |
| Cognee | retrieved | Memory returned |
| Latency | <2000ms | Fast response |

## Demo Script

1. Open `ui/index.html` in browser
2. Click microphone, say "Check stock"
3. See response in chat with voice playback
4. Check Activity Log for full flow
5. Change preferences to "Voice Only"
6. Repeat with different questions
