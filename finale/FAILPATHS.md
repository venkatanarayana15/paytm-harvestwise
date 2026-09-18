# Failure paths — test ALL before recording backup (doctrine 08)
# Demo language: TAMIL primary (crew-fluent), English fallback. All Kannada strings below are placeholders — crew replaces with crew-written Tamil equivalents.

| # | Trigger | System response | UI state |
|---|---|---|---|
| 1 | STT unclear / low confidence | clarification ask: "ನನಗೆ ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ, ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ." | transcript box shows "(unclear)" + mic re-arms |
| 2 | Unknown product | list catalog in her language, ask which | intent JSON shows product:null + clarify flag |
| 3 | Ambiguous quantity ("send more") | ask "ಎಷ್ಟು ಕೆಜಿ?" — NEVER guess | recommendation card shows "quantity needed" |
| 4 | Duplicate approval | idempotency: "ಈ ಆದೇಶ ಈಗಾಗಲೇ ಕಳುಹಿಸಲಾಗಿದೆ." | dispatch record unchanged, no second order |
| 5 | n8n timeout/failure | "ಸಂಪರ್ಕದಲ್ಲಿ ಸಮಸ್ಯೆ — ಒಂದು ನಿಮಿಷದಲ್ಲಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ." retry ×1 → queue to morning briefing | execution panel: amber "queued" |
| 6 | Slow Sarvam (>5s once) | switch to typed-transcript fallback + say the swap line | no visible spinner >3s, ever |
| 7 | Engine-vs-observation anomaly | needs_human_review=true → gentle decline "ನಾಳೆ ಮತ್ತೆ ನೋಡೋಣ" + Cognee logs it | recommendation card: review flag, no dispatch |

Swap line (spoken, calm): "Let me switch to our backup audio so you hear it clearly — the flow is identical either way."
All failure responses must look DESIGNED, not crashed.
