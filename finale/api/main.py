import json, os, re, base64, uuid, io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()  # .env next to cwd; D:/ path import removed — was machine-specific
from engine.restock import CATALOG, WEATHER, calculate_quantity, recommendation, validate_order

app = FastAPI(title="HarvestWise")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MERCHANT = "lakshmi"

# ─── Approval token store: issued tokens are single-use (idempotent dispatch) ──
issued_tokens: dict[str, dict] = {}      # token -> {product, qty, supplier}
dispatched_tokens: set[str] = set()

TAMIL_WORDNUM = {"ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5,
                 "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
                 "இருபது": 20, "முப்பது": 30}
# unit word -> (canonical unit, multiplier into that unit)
UNIT_WORDS = {
    "கிலோ": ("kg", 1), "kg": ("kg", 1), "kilo": ("kg", 1), "kilos": ("kg", 1),
    "கிரேட்": ("kg", 20), "crate": ("kg", 20), "crates": ("kg", 20),
    "கொத்து": ("bunch", 1), "கட்டு": ("bunch", 1), "bunch": ("bunch", 1), "bunches": ("bunch", 1),
}
PRODUCT_WORDS = {
    "tomato": "tomato", "tomatoes": "tomato", "தக்காளி": "tomato", "tamatar": "tomato",
    "coriander": "coriander", "kothamalli": "coriander", "கொத்தமல்லி": "coriander",
    "dhania": "coriander", "onion": "onion", "வெங்காயம்": "onion",
}
APPROVE_WORDS = ["sari", "சரி", "yes", "ha", "haan", "ஆம்", "ok", "confirm"]
DENY_WORDS = ["illa", "இல்ல", "no", "venam", "வேண்டாம்", "nahi", "cancel", "stop"]


def _parse_quantities(text: str) -> dict[str, int | None]:
    """Extract {product: requested_qty} from a transcript.
    Handles '20 கிலோ தக்காளி', '3 crates tomato', '10 கொத்து கொத்தமல்லி',
    Tamil word-numbers, punctuation, and qty-before/after product order.
    NEVER invents a number — absent numbers stay None (engine fills deterministically)."""
    tokens = re.findall(r"[\w\u0b80-\u0bff]+", text.lower())
    found: dict[str, int | None] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        v = TAMIL_WORDNUM.get(t, int(t) if t.isdigit() else None)
        if v is not None:
            mult, j = 1, i + 1
            unit = None
            if j < len(tokens) and tokens[j] in UNIT_WORDS:
                unit, mult = UNIT_WORDS[tokens[j]]
                j += 1
            # product after the number/unit (natural Tamil order: qty unit product)
            k = j
            while k < len(tokens) and tokens[k] not in PRODUCT_WORDS:
                k += 1
            if k < len(tokens):
                found[PRODUCT_WORDS[tokens[k]]] = v * mult
            else:
                # product before the number ("தக்காளி 20 கிலோ")
                b = i - 1
                while b >= 0 and tokens[b] not in PRODUCT_WORDS:
                    b -= 1
                if b >= 0:
                    found[PRODUCT_WORDS[tokens[b]]] = v * mult
            i = j if j > i else i + 1
            continue
        i += 1
    return found


@app.get("/health")
def health():
    checks = {"status": "ok", "sarvam_key": bool(os.getenv("SARVAM_API_KEY"))}
    # dependency probes — never crash health, just report
    try:
        base, key = os.getenv("COGNEE_BASE_URL"), os.getenv("COGNEE_API_KEY")
        if base and key:
            r = httpx.get(f"{base}/api/v1/datasets/status", headers={"X-Api-Key": key}, timeout=3)
            checks["cognee"] = "up" if r.status_code < 500 else f"down:{r.status_code}"
        else:
            checks["cognee"] = "not_configured"
    except Exception as e:
        checks["cognee"] = f"down:{str(e)[:80]}"
    checks["n8n"] = "configured" if os.getenv("N8N_WEBHOOK_URL") else "not_configured"
    checks["twilio"] = "configured" if os.getenv("TWILIO_ACCOUNT_SID") else "not_configured"
    return checks


@app.post("/stt")
async def speech_to_text(file: UploadFile = File(...), language_code: str = "ta-IN"):
    """Sarvam STT (saaras:v3). Accepts wav/webm/mp3 from browser MediaRecorder."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise HTTPException(503, "SARVAM_API_KEY not configured — typed-transcript fallback is the labeled path")
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "empty audio")
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=api_key)
        suffix = (file.filename or "audio.wav").rsplit(".", 1)[-1].lower()
        codec = {"wav": "wav", "webm": "webm", "mp3": "mp3", "m4a": "mp4", "ogg": "ogg"}.get(suffix, "wav")
        resp = client.speech_to_text.transcribe(
            file=(f"audio.{suffix}", audio), model="saaras:v3",
            language_code=language_code, input_audio_codec=codec,
        )
        return {"transcript": getattr(resp, "transcript", "") or str(resp), "language_code": language_code}
    except Exception as e:
        raise HTTPException(502, f"STT failed: {e}")


@app.post("/intent")
def extract_intent(payload: dict):
    """Rule-based intent parse of a transcript (real parser; Sarvam-105B P1 is the
    upgrade path on build day). NEVER invents a quantity — echoes merchant words."""
    text = (payload.get("transcript") or "").strip()
    low = text.lower()
    if not text:
        return {"intent": "silence", "products": {}, "clarification_needed": True}
    if any(w in low for w in DENY_WORDS):
        return {"intent": "decline", "products": {}, "clarification_needed": False}
    if not any(w in low for w in APPROVE_WORDS + list(PRODUCT_WORDS)):
        return {"intent": "out_of_scope", "products": {}, "clarification_needed": True,
                "note": "no catalog product detected"}

    products = _parse_quantities(text)
    # products mentioned without any number still count (qty None → engine derives)
    for word, product in PRODUCT_WORDS.items():
        if word in low and product not in products:
            products[product] = None

    if not products:
        return {"intent": "out_of_scope", "products": {}, "clarification_needed": True}
    ambiguous = any(q is None for q in products.values())
    return {"intent": "create_restock_order", "products": products,
            "clarification_needed": ambiguous,
            "language": "ta" if re.search(r"[\u0b80-\u0bff]", text) else "en"}


@app.post("/rec")
def get_recommendation(payload: dict):
    """Deterministic recommendation, single product or basket."""
    product = payload.get("product", "tomato")
    requested = payload.get("requested_qty")
    merchant_id = payload.get("merchant_id", MERCHANT)
    try:
        rec = recommendation(merchant_id, product, requested)
    except KeyError as e:
        raise HTTPException(400, f"Unknown product — catalog: {', '.join(CATALOG.get(merchant_id, []))}")
    rain = WEATHER["tomorrow"]["rain_prob"]
    rec["rain_prob"] = rain
    return rec


@app.post("/rec/basket")
def get_basket(payload: dict):
    """Basket rec from intent products: {'products': {'tomato': 20, 'coriander': None}}"""
    products: dict = payload.get("products") or {"tomato": None}
    merchant_id = payload.get("merchant_id", MERCHANT)
    items, total = [], 0
    for product, requested in products.items():
        try:
            rec = recommendation(merchant_id, product, requested)
        except KeyError:
            raise HTTPException(400, f"Unknown product: {product}")
        items.append(rec)
        total += rec["total_inr"]
    return {"items": items, "basket_total_inr": total,
            "weather": WEATHER["tomorrow"]}


class Order(BaseModel):
    product: str
    qty: int
    supplier: str


@app.post("/approve")
def approve_order(order: Order):
    valid, status = validate_order(MERCHANT, order.product, order.qty, order.supplier)
    if not valid:
        return {"status": "rejected", "reason": status}
    token = str(uuid.uuid4())
    issued_tokens[token] = {"product": order.product, "qty": order.qty, "supplier": order.supplier}
    return {"status": "approved", "approval_token": token}


@app.post("/dispatch")
def dispatch_order(approval: dict):
    token = approval.get("token") or approval.get("approval_token")
    if not token:
        return {"status": "failed", "reason": "missing token"}
    if token in dispatched_tokens:
        return {"status": "duplicate_ignored", "reason": "idempotency: this order was already dispatched"}
    order = issued_tokens.pop(token, None)
    if order is None:
        return {"status": "failed", "reason": "unknown or already-used approval token"}

    record = {
        "token": token, "status": "dispatched",
        "product": order["product"], "quantity_kg": order["qty"],
        "supplier": order["supplier"],
        "total_inr": approval.get("total_inr"),
    }
    with open("dispatch_record.json", "w") as f:
        json.dump(record, f, indent=2)
    dispatched_tokens.add(token)

    n8n_url = os.getenv("N8N_WEBHOOK_URL")
    if n8n_url:
        try:
            httpx.post(n8n_url, json=record, timeout=5)
            record["n8n"] = "fired"
        except Exception as e:
            record["n8n_error"] = str(e)

    twilio_sid, twilio_token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    if twilio_sid and twilio_token:
        try:
            auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
            data = {
                "To": approval.get("merchant_phone", os.getenv("TWILIO_WHATSAPP_TO", "whatsapp:+919999999999")),
                "From": os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
                "ContentSid": os.getenv("TWILIO_CONTENT_SID", ""),
                # Default 2 vars match the currently-registered content template.
                # When the dedicated order template (qty/product/supplier/total) is
                # approved in the Twilio console, set TWILIO_TEMPLATE_VARS=4.
                "ContentVariables": json.dumps({
                    "1": str(order["qty"]), "2": order["product"],
                    **({"3": order["supplier"], "4": str(record["total_inr"] or "")}
                       if os.getenv("TWILIO_TEMPLATE_VARS") == "4" else {}),
                }),
            }
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                           data=data, headers={"Authorization": f"Basic {auth}"}, timeout=8)
            record["twilio_status"] = r.status_code
            if r.status_code >= 400:
                record["twilio_body"] = r.text[:300]
                record["twilio_note"] = "template send rejected — see Twilio console (dispatch still recorded)"
        except Exception as e:
            record["twilio_error"] = str(e)
    return {"status": "dispatched", "record": record}


@app.post("/voice/approve")
def voice_approve(payload: dict):
    """Voice approval gate: {transcript, items: [{product, qty}], or legacy product/qty}."""
    text = (payload.get("transcript") or "").lower()
    if any(w in text for w in DENY_WORDS):
        return {"status": "declined", "heard": text}
    if not any(w in text for w in APPROVE_WORDS):
        return {"status": "needs_confirmation", "heard": text}

    items = payload.get("items")
    if not items:
        product = payload.get("product", "tomato")
        qty = payload.get("qty") or calculate_quantity(MERCHANT, product)
        items = [{"product": product, "qty": qty}]

    approved = []
    for item in items:
        product = item.get("product", "tomato")
        qty = item.get("qty") or calculate_quantity(MERCHANT, product)
        supplier = CATALOG[MERCHANT][product]["supplier"]
        valid, reason = validate_order(MERCHANT, product, qty, supplier)
        if not valid:
            return {"status": "rejected", "reason": f"{product}: {reason}"}
        token = str(uuid.uuid4())
        issued_tokens[token] = {"product": product, "qty": qty, "supplier": supplier}
        approved.append({"approval_token": token, "product": product, "quantity_kg": qty,
                         "supplier": supplier})
    return {"status": "approved", "items": approved,
            "basket_total_inr": payload.get("basket_total_inr")}


@app.post("/tts")
def tts(payload: dict):
    text = payload.get("text", "")
    lang = payload.get("lang", "ta-IN")
    if not text:
        raise HTTPException(400, "no text")
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise HTTPException(503, "SARVAM_API_KEY not configured")
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=api_key)
        resp = client.text_to_speech.convert(text=text, language_code=lang,
                                             speaker="kavitha", model="bulbul:v3")
        aud = resp.audios[0] if hasattr(resp, "audios") else resp
        b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
        if not b64:
            raise HTTPException(502, "no audio in TTS response")
        return Response(content=base64.b64decode(b64), media_type="audio/wav")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"TTS failed: {e}")


@app.get("/memory")
def get_memory():
    try:
        with open("cognee/memory.json", encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"lakshmi": {"note": "run python cognee/seed_memory.py first"}}


@app.post("/cognee/recall")
def cognee_recall(payload: dict):
    q = payload.get("query", "Why 20 kg tomato?")
    datasets = payload.get("datasets", ["harvestwise"])
    base, key = os.getenv("COGNEE_BASE_URL"), os.getenv("COGNEE_API_KEY")
    if not base or not key:
        return {"error": "cognee not configured — local memory fallback", "memory": get_memory()}
    try:
        r = httpx.post(f"{base}/api/v1/recall", headers={"X-Api-Key": key},
                       json={"query": q, "datasets": datasets}, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e), "memory": get_memory()}
