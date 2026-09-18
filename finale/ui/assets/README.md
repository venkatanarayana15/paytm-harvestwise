# Demo Audio Assets

## What is in here
| File | Content | Status |
|---|---|---|
| `command_ta.wav` | the Tamil **order command** — `நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி` | ⚠️ **synthetic (Sarvam bulbul:v3), labelled backup** |
| `command_en.wav` | `Tomorrow twenty kilos of tomatoes, and ten bunches of coriander` | ⚠️ same, English fallback |

Both are distinct files with distinct md5s (214 KB / 270 KB).

> **History — read this before you trust an audio file.** An earlier version of this folder had
> `command_ta.wav`, `command_en.wav`, `audio/tamil_demo.wav` and `tts_ta.wav` all **byte-identical**
> — they were copies of a TTS *question* ("…நாளை இருபது கிலோ தக்காளி வேண்டுமா?"), not the order.
> Clicking "▶ Cached audio" therefore played an utterance with **no coriander**, silently turning the
> ₹546 backup path into a tomato-only order. Do not reintroduce copied placeholder audio.

## What the crew records for stage
The cached files are synthetic and exist only so the demo never dies. **The on-stage live command
should be a human recording** — crew-native Tamil, 16 kHz mono WAV, saved here as
`command_ta_human.wav` (keep the synthetic file as the labeled fallback).

**Line to record (canonical — do not change the numbers):**
> `நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி`

**Translation:** "Tomorrow, 20 kilos of tomatoes and 10 bunches of coriander."

**Why this exact line:** it is the phrase the parser, the engine calibration and the deck are all
verified against → tomato 20 kg (₹360) + coriander 10 → 6 bunches (₹186) = **₹546**.
Do **not** record "3 crates" (parses to 60 kg and breaks the ₹546 story), and do not say
"இருபது சதவீதம்" (20% rain) — the demo constant is **78%**.

**Requirements:** 16 kHz mono WAV · place in `ui/assets/` · then point the dashboard's cached-audio
button at it. Fallback: the typed transcript always works and is the labelled backup path.

## Regenerating the synthetic backups
```
python make_backup_audio.py
```
It prints the byte size and the exact line for each file.

## Verifying an audio file is the right one
```
python -c "import httpx;print(httpx.post('http://127.0.0.1:8000/stt',files={'file':open('ui/assets/command_ta.wav','rb')},timeout=60).json()['transcript'])"
```
Expected: `நாளை 20 கிலோ தக்காளி 10 கொத்து கொத்தமல்லி வேண்டும்.`
Then `POST /intent` on that transcript must return `{"tomato": 20, "coriander": 10}` — the battery
asserts exactly this.
