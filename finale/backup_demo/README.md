# Backup Demo Recording — Stage Fail-Safe

If the live demo fails on stage (mic, STT, network, provider outage), play this
pre-recorded screen capture of a **real** Full Auto run instead. Nothing in it
is mocked — it is the actual dashboard driving the actual API, recorded
2026-09-18 (see `demo_transcript.txt` for the timestamped step log).

## Contents

| File | What it is |
|---|---|
| `demo_backup_narrated.mp4` | **Play this one.** H.264 MP4, 1360×850, 34 s, with a Sarvam-voice narration track (same `bulbul:v3` / `kavitha` voice as the product's spoken ask). Ends on a freeze-frame of the reasoning panel while the narrator closes. |
| `demo_backup.mp4` | Silent 23 s cut of the same run — use if you narrate live yourself. |
| `video.webm` | Original Chromium capture (higher fidelity master; keep for re-encoding). |
| `narration.wav` | The narration track alone (regenerable; timings in `make_narrated_video.py`). |
| `stage_1_boot.png` | Dashboard booted: API ok, weather seeded, llm hybrid, stock 12/6. |
| `stage_2_dispatched.png` | After dispatch: basket ₹546, ledger `6 → 12`, stepper all green, WhatsApp card live. |
| `stage_3_reason.png` | Grounded reasoning panel: observations + Sarvam trace, engine-locked quantity. |
| `demo_transcript.txt` | Timestamped log of every step the recorder executed. |
| `proof_panel.txt` | The ledger + WhatsApp panel text at the end of the run. |

## What the video shows (34 seconds, narrated)

| Time | Screen | Narration |
|---|---|---|
| 0–5 s | Dashboard boots, API green, seeded state | "HarvestWise: a voice note becomes an executed order." |
| 5–11 s | Basket ₹546 → approval gate | "She says yes. Nothing moves without approval." |
| 12–17 s | Dispatch, n8n, WhatsApp, ledger `6 → 12` | "Dispatched. WhatsApp sent, stock and memory updated." |
| 18–23 s | Grounded reasoning panel | "Every number traces to a real observation." |
| 24–34 s | Freeze-frame of the reasoning panel | "The model explains, the engine decides — HarvestWise closes the loop." |

## Stage rules for the backup

- Announce it honestly (same rule as the cached audio):
  *“This is a pre-recorded run of the exact flow you would have seen live — same dashboard, same engine.”*
- Open the video FULLSCREEN (F in VLC / PowerPoint kiosk) — it is exactly 1360×850, so it letterboxes cleanly.
- Do not talk over step 4 (dispatch + WhatsApp) — pause two seconds and let the ledger be read.
- The live phone should still buzz if only the *dashboard/mic* failed — say so; it proves the backend is still real.

## Regenerating the recording (rehearsals change state — re-record after changes)

```bash
# API must be up on 127.0.0.1:8000
cd qa-runs/pw && node record_backup.js
# convert to MP4 (any full ffmpeg with libx264):
ffmpeg -y -i finale/backup_demo/video.webm -c:v libx264 -pix_fmt yuv420p \
  -crf 23 -movflags +faststart finale/backup_demo/demo_backup.mp4
# then add the narrated version (Sarvam TTS + timed mux, ~1 min):
cd finale && python make_narrated_video.py
```

Note: Playwright's bundled ffmpeg lacks the MP4 muxer; use a full ffmpeg build
(system ffmpeg, or `pip install imageio-ffmpeg` and use its binary).

Recording drives a REAL dispatch: it sends WhatsApp messages and mutates the
ledger. Always `POST /demo/reset` before a live demo after recording.
