# Failure paths — test ALL before recording backup (doctrine 08)
# Demo language: TAMIL primary (crew-fluent), English fallback.

| # | Trigger | System response (Tamil) | UI state |
|---|---|---|---|
| 1 | STT unclear / low confidence | "சரியாகக் கேட்கவில்லை, தயவுசெய்து மீண்டும் சொல்லுங்கள்." | transcript box shows "(unclear)" + mic re-arms |
| 2 | Unknown product | list catalog in her language, ask which: "தக்காளி, கொத்தமல்லி, வெங்காயம் — எது?" | intent JSON shows product:null + clarify flag |
| 3 | Ambiguous quantity ("send more") | ask "எத்தனை கிலோ?" — NEVER guess | recommendation card shows "quantity needed" |
| 4 | Duplicate approval | idempotency: "இந்த ஆர்டர் ஏற்கனவே அனுப்பப்பட்டது." | dispatch record unchanged, no second order |
| 5 | n8n timeout/failure | "இணைப்பில் பிரச்சினை — ஒரு நிமிடத்தில் மீண்டும் முயற்சிக்கவும்." retry ×1 → queue to morning briefing | execution panel: amber "queued" |
| 6 | Slow Sarvam (>5s once) | switch to typed-transcript fallback + say the swap line | no visible spinner >3s, ever |
| 7 | Engine-vs-observation anomaly | needs_human_review=true → gentle decline "நாளை மீண்டும் பார்ப்போம்" + Cognee logs it | recommendation card: review flag, no dispatch |

Swap line (spoken, calm): "Let me switch to our backup audio so you hear it clearly — the flow is identical either way."
All failure responses must look DESIGNED, not crashed.
