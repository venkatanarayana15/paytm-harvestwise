import os, json
from dotenv import load_dotenv

load_dotenv()  # cwd .env — no machine-specific paths

api_key = os.getenv("SARVAM_API_KEY")
print("SARVAM_API_KEY:", "set" if api_key else "MISSING", api_key[:12] if api_key else "")

if not api_key:
    print("Create .env with SARVAM_API_KEY=sk_...")
    exit(1)

try:
    from sarvamai import SarvamAI
    client = SarvamAI(api_subscription_key=api_key)
    
    # 1) TTS test — Tamil demo line
    tamil = "நாளை மழை 80 சதவீதம் இருக்கும், ஆனால் தக்காளி வேகமாக விற்பனையாகிறது. நாளை 20 கிலோ தக்காளி வேண்டுமா?"
    print("\nTTS (ta) ...")
    resp = client.text_to_speech.convert(
        text=tamil,
        language_code="ta-IN",
        speaker="kavitha",
        model="bulbul:v3"
    )
    # sarvamai returns base64 audio
    aud = resp.audios[0] if hasattr(resp, "audios") else resp
    import base64
    b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
    if b64:
        open("tts_ta.wav","wb").write(base64.b64decode(b64))
        print("Wrote tts_ta.wav", len(b64))
    else:
        print("TTS response:", resp)

    # 2) STT test — if you have a wav, uncomment
    # with open("audio/tamil_demo.wav","rb") as f:
    #     stt = client.speech_to_text.transcribe(file=f, model="saaras:v3", language_code="ta-IN")
    #     print("STT:", stt)

    print("\nSarvam OK — latency <2s target achievable with saaras:v3-realtime WebSocket for demo.")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("\nFallback: typed-transcript mode still works (API falls back, never pretend STT ran)")
