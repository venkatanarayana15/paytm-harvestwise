"""Generate the narrated backup demo video — stage fail-safe with voiceover.

Pipeline:
  1. Pad the base video with a freeze-frame tail (tpad) so the closing
     reasoning panel stays readable while the narrator wraps up.
  2. Sarvam TTS (bulbul:v3, speaker 'kavitha') renders each narration line.
  3. ffmpeg assembles the lines at fixed offsets over a silent bed.
  4. ffmpeg muxes narration onto the padded video (video re-encoded once, audio AAC).

Timing is aligned to demo_transcript.txt of the recorded run:
  ~0s boot · ~4s basket · ~6s approve · ~11s dispatch · ~16s reasoning.
Each line must FIT its slot — the script measures durations and fails loudly
on overlap instead of producing a garbled track.

Re-record the base video first (qa-runs/pw/record_backup.js) if the timeline
changed, then re-run this script. Requires SARVAM_API_KEY in finale/.env.

Run:  python make_narrated_video.py          (from finale/)
"""
import base64
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402
from engine.restock import BASE_DIR  # noqa: E402

load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv()

DEMO_DIR = os.path.join(BASE_DIR, "backup_demo")
BASE_VIDEO = os.path.join(DEMO_DIR, "demo_backup.mp4")
VIDEO_PADDED = os.path.join(DEMO_DIR, "video_padded_noaudio.mp4")
NARRATION_WAV = os.path.join(DEMO_DIR, "narration.wav")
OUT_MP4 = os.path.join(DEMO_DIR, "demo_backup_narrated.mp4")
TMP_DIR = os.path.join(DEMO_DIR, "_tts_tmp")

BASE_DUR = 22.64          # recorded run (auto-detected below, this is the fallback)
PAD_TO = 34.0             # total narrated video length in seconds


def ffmpeg() -> str:
    """Prefer a full ffmpeg build (needs libx264/AAC); Playwright's bundled one lacks them."""
    exe = os.getenv("FFMPEG_PATH")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"  # hope a full build is on PATH


def probe_duration(ff: str, path: str) -> float:
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def tts_line(text: str, lang: str, out_path: str) -> None:
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        print("SARVAM_API_KEY not set — cannot generate narration.")
        sys.exit(1)
    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=api_key)
    resp = client.text_to_speech.convert(text=text, language_code=lang,
                                         speaker="kavitha", model="bulbul:v3")
    aud = resp.audios[0] if hasattr(resp, "audios") else resp
    b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
    if not b64:
        raise RuntimeError(f"no audio returned for: {text[:40]}…")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))


# (start_s, latest_safe_end_s, language, narration)
# English so judges follow. bulbul:v3 paces at ~0.64 s/word — mid-video slots
# fit ~8 words; the freeze-frame tail carries the closing line.
SCRIPT = [
    (0.6, 6.6, "en-IN",
     "HarvestWise: a voice note becomes an executed order."),
    (7.0, 11.6, "en-IN",
     "She says yes. Nothing moves without approval."),
    (12.0, 17.6, "en-IN",
     "Dispatched. WhatsApp sent, stock and memory updated."),
    (18.0, 23.4, "en-IN",
     "Every number traces to a real observation."),
    (24.2, 33.2, "en-IN",
     "The model explains, the engine decides — HarvestWise closes the loop."),
]


def main() -> int:
    if not os.path.exists(BASE_VIDEO):
        print(f"missing {BASE_VIDEO} — run qa-runs/pw/record_backup.js first")
        return 1
    ff = ffmpeg()
    os.makedirs(TMP_DIR, exist_ok=True)

    # ── 1. pad the base video with a frozen last frame ──
    base_dur = probe_duration(ff, BASE_VIDEO) or BASE_DUR
    pad = max(0.0, PAD_TO - base_dur)
    print(f"== 1. pad video {base_dur:.2f}s -> {PAD_TO:.2f}s (freeze tail {pad:.2f}s) ==")
    if not os.path.exists(VIDEO_PADDED) or abs(probe_duration(ff, VIDEO_PADDED) - PAD_TO) > 0.5:
        r = subprocess.run(
            [ff, "-y", "-i", BASE_VIDEO,
             "-vf", f"tpad=stop_mode=clone:stop_duration={pad:.2f}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-an",
             VIDEO_PADDED],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-600:]); return 1
    print(f"  {os.path.basename(VIDEO_PADDED)}: {probe_duration(ff, VIDEO_PADDED):.2f}s")

    # ── 2. TTS each line and verify it fits its slot ──
    print("== 2. TTS lines (Sarvam bulbul:v3, speaker kavitha) ==")
    rows = []
    prev_end = 0.0
    for i, (start, latest, lang, text) in enumerate(SCRIPT):
        wav = os.path.join(TMP_DIR, f"line_{i}.wav")
        tts_line(text, lang, wav)
        dur = probe_duration(ff, wav)
        end = start + dur
        flag = "ok" if end <= latest and start >= prev_end - 0.05 else "OVERLAP"
        print(f"  line {i}: {start:>5.1f}s -> {end:>5.1f}s (dur {dur:4.1f}s, slot ends {latest}s)  {flag}")
        if flag != "ok":
            print(f"\nLine {i} does not fit — shorten the narration text and re-run.")
            return 1
        prev_end = end
        rows.append((start, wav))

    # ── 3. assemble the narration track at the timed offsets ──
    # Inputs 0..n-1 are the line WAVs; the silent bed is created INSIDE the
    # filtergraph (a second lavfi -i input would shift indices and one line
    # would silently receive the bed instead of its WAV — measured bug).
    print("== 3. assemble narration track ==")
    inputs = []
    for _, wav in rows:
        inputs += ["-i", wav]
    n = len(rows)
    parts = [f"[{i}:a]adelay={int(rows[i][0] * 1000)}:all=1[d{i}]" for i in range(n)]
    filter_complex = (
        f"anullsrc=r=16000:cl=mono:d={PAD_TO:.3f}[bed];"
        + ";".join(parts) + ";"
        + "[bed]" + "".join(f"[d{i}]" for i in range(n))
        + f"amix=inputs={n + 1}:normalize=0[aout]"
    )
    cmd = [ff, "-y", *inputs,
           "-filter_complex", filter_complex,
           "-map", "[aout]", "-t", f"{PAD_TO:.3f}",
           "-ar", "16000", "-ac", "1", NARRATION_WAV]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-600:]); return 1
    print(f"  narration.wav: {probe_duration(ff, NARRATION_WAV):.2f}s")

    # ── 4. mux: padded video + narration (AAC) ──
    print("== 4. mux narrated video ==")
    cmd = [ff, "-y", "-i", VIDEO_PADDED, "-i", NARRATION_WAV,
           "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
           "-shortest", OUT_MP4]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-600:]); return 1
    print(f"  {OUT_MP4} ({os.path.getsize(OUT_MP4)} B, {probe_duration(ff, OUT_MP4):.2f}s)")
    print("\nStage rule: announce 'this is our recorded run with narration — the live flow is identical.'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
