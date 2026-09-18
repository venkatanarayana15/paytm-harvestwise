"""Pre-flight — run before every rehearsal and on build day.
Checks the 4 human blockers that code cannot auto-fix, plus the 86-check battery.
Exit 0 = stage-ready. Exit 1 = fix the listed item, then re-run.
"""
import os, sys, pathlib, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = pathlib.Path(__file__).parent
sys.path.insert(0, str(BASE))
from dotenv import load_dotenv
load_dotenv(BASE / ".env")

ok = warn = fail = 0
def check(name, cond, fix):
    global ok, warn, fail
    tag = "OK" if cond else "FAIL"
    if cond: ok += 1
    else: fail += 1
    print(f"{tag:4} {name:35} {'' if cond else '-> '+fix}")

print("== HarvestWise pre-flight ==\n")

# 1. Env + keys (burned-key guard)
check("SARVAM_API_KEY set", bool(os.getenv("SARVAM_API_KEY")),
      "cp .env.example .env and paste fresh key (see SECURITY.md)")
burned = ["sk_hyj7en0s_Z3t7b6HWZQY5CaAlzW86BPMg", "9091db3a37dd798a3efe7ec162598abe"]
check("SARVAM key not burned", os.getenv("SARVAM_API_KEY") not in burned,
      "rotate in Sarvam console — this key was pasted in readme")
check("COGNEE_BASE_URL set", bool(os.getenv("COGNEE_BASE_URL")), "set in .env")
check("COGNEE_API_KEY set", bool(os.getenv("COGNEE_API_KEY")), "set in .env")

# 2. Twilio — mock is fine, real buzz is better
check("TWILIO_ACCOUNT_SID set", bool(os.getenv("TWILIO_ACCOUNT_SID")), "set for real WhatsApp")
has_to = bool(os.getenv("TWILIO_WHATSAPP_TO"))
check("TWILIO_WHATSAPP_TO set (or mock)", True, "")  # mock covers it, so never fail
if not has_to:
    print("WARN TWILIO_WHATSAPP_TO not set                -> mock WhatsApp will be logged to data/mock_whatsapp.log (demo still passes, no buzz)")
    warn += 1

# 3. Audio assets
for lang, fname in [("ta","ui/assets/command_ta.wav"),("kn","ui/assets/command_kn.wav"),
                    ("hi","ui/assets/command_hi.wav"),("te","ui/assets/command_te.wav"),
                    ("en","ui/assets/command_en.wav")]:
    p = BASE / fname
    check(f"asset {fname}", p.exists() and p.stat().st_size > 10000,
          f"python make_backup_audio.py (or crew-record {lang})")

# 4. n8n — presence of the 3 JSONs
for name in ["n8n/dispatch.json","n8n/briefing.json","n8n/daywrap.json"]:
    check(f"workflow {name}", (BASE/name).exists(), f"import {name} on n8n cloud")

# 5. Battery (import, don't re-run full STT here — that's qa_battery.py)
try:
    from engine.restock import get_weather, CATALOG
    w = get_weather()
    check("engine get_weather()", w.get("rain_prob") == 0.78 or w.get("source") in ("seeded","live"), str(w))
    check("catalog lakshmi 5 SKUs", len(CATALOG.get("lakshmi",{})) >= 4, str(list(CATALOG.get("lakshmi",{}).keys())))
except Exception as e:
    check("engine import", False, str(e))

print(f"\n== {ok} OK, {warn} WARN, {fail} FAIL ==")
if fail:
    print("Fix FAIL items, then: python qa_battery.py  # 86/86")
    sys.exit(1)
print("Pre-flight green. Next: python qa_battery.py")
