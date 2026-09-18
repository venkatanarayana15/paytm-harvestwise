"""Generate the CACHED backup command audio for the demo.

Why this exists (found 2026-09-18): ui/assets/command_ta.wav, command_en.wav,
audio/tamil_demo.wav and tts_ta.wav were all byte-identical copies of a TTS
*question* ("...நாளை இருபது கிலோ தக்காளி வேண்டுமா?"). The dashboard's
"▶ Cached audio" button therefore played the wrong utterance — it contained no
coriander, so the ₹546 backup path silently became tomato-only.

This script writes the correct ORDER command so the backup path actually
reproduces 20 kg tomato + 10 bunches coriander -> ₹546.

LABELING RULE (doctrine 08): this is SYNTHETIC audio. The on-stage live command
must still be crew-recorded human speech. Play this file only as the labeled
backup, and say so: "this is our cached backup audio — the flow is identical."

Run:  python make_backup_audio.py
"""
import base64
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402

from engine.restock import BASE_DIR  # noqa: E402

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv()

OUT_DIR = os.path.join(BASE_DIR, "ui", "assets")

LINES = [
    ("command_ta.wav", "ta-IN",
     "நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி வேண்டும்"),
    ("command_en.wav", "en-IN",
     "Tomorrow twenty kilos of tomatoes, and ten bunches of coriander"),
]


def main() -> int:
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        print("SARVAM_API_KEY not set — create finale/.env first.")
        return 1

    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=api_key)
    os.makedirs(OUT_DIR, exist_ok=True)

    for filename, lang, text in LINES:
        path = os.path.join(OUT_DIR, filename)
        try:
            resp = client.text_to_speech.convert(
                text=text, language_code=lang, speaker="kavitha", model="bulbul:v3",
            )
            aud = resp.audios[0] if hasattr(resp, "audios") else resp
            b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
            if not b64:
                print(f"  {filename}: no audio in response")
                continue
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
            print(f"  {filename} [{lang}] {os.path.getsize(path)} bytes  <- {text}")
        except Exception as e:
            print(f"  {filename}: FAILED {type(e).__name__}: {e}")

    print("\nLabeled as synthetic. Crew still records the human take for stage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
