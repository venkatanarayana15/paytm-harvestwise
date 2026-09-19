"""HarvestWise API — orchestration only.

Contract (doctrine 08):
  - This layer NEVER invents a quantity. It calls the deterministic engine.
  - The LLM classifies intent and writes sentences; quantities are discarded.
  - Every money-moving action requires a merchant-approved, single-use token.
  - n8n re-validates before execution.

Fixed 2026-09-18:
  - Paths are absolute (BASE_DIR) -> the app no longer depends on the cwd, so
    `uvicorn api.main:app` works from the repo root as well as from finale/.
  - Dispatch now performs acceptance criterion #5: a VISIBLE inventory update
    and an auditable memory write, plus a real Cognee add_text -> cognify.
  - Idempotency survives a server restart (dispatched tokens are persisted).
"""
import json
import os
import re
import base64
import uuid
import datetime

from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

from engine.restock import (  # noqa: E402
    BASE_DIR, CATALOG, WEATHER, calculate_quantity, recommendation, validate_order,
    get_weather, reset_state, record_delivery, get_stock, stock_snapshot,
    order_history, RAINY_THRESHOLD,
)
from engine import cognee_client, llm as llm_mod

# .env is looked up next to this file first, then the cwd — was cwd-only.
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv()

MERCHANT = "lakshmi"
MEMORY_PATH = os.path.join(BASE_DIR, "cognee", "memory.json")
DISPATCH_RECORD_PATH = os.path.join(BASE_DIR, "dispatch_record.json")
TOKENS_PATH = os.path.join(BASE_DIR, "data", "dispatched_tokens.json")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Deterministic demo start: seeded inventory + warm the Cognee recall path.
    Set DEMO_RESET_ON_START=0 to keep inventory across restarts during a rehearsal."""
    if os.getenv("DEMO_RESET_ON_START", "1") != "0":
        reset_state()
    if cognee_client.configured():
        cognee_client.warm()
    yield


app = FastAPI(title="HarvestWise", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Approval token store: issued tokens are single-use (idempotent dispatch) ──
issued_tokens: dict[str, dict] = {}
dispatched_tokens: set[str] = set()


def _load_dispatched():
    try:
        with open(TOKENS_PATH, encoding="utf-8") as f:
            dispatched_tokens.update(json.load(f))
    except Exception:
        pass


def _save_dispatched():
    try:
        os.makedirs(os.path.dirname(TOKENS_PATH), exist_ok=True)
        with open(TOKENS_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(dispatched_tokens), f, indent=2)
    except OSError:
        pass


_load_dispatched()


# ─── Multilingual lexicons ────────────────────────────────────────────────
TAMIL_WORDNUM = {"ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5,
                 "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10,
                 "இருபது": 20, "முப்பது": 30}
KANNADA_WORDNUM = {"ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
                   "ಆರು": 6, "ಏಳು": 7, "ಎಂಟು": 8, "ಒಂಬತ್ತು": 9, "ಹತ್ತು": 10,
                   "ಇಪ್ಪತ್ತು": 20, "ಮೂವತ್ತು": 30}
HINDI_WORDNUM = {"एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "बीस": 20, "तीस": 30}
TELUGU_WORDNUM = {"ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "ఆరు": 6, "ఏడు": 7, "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10, "ఇరవై": 20, "ముప్పై": 30}
WORDNUM = {**TAMIL_WORDNUM, **KANNADA_WORDNUM, **HINDI_WORDNUM, **TELUGU_WORDNUM}
# unit word -> (canonical unit, multiplier into that unit)
UNIT_WORDS = {
    "கிலோ": ("kg", 1), "ಕಿಲೋ": ("kg", 1), "ಕೆಜಿ": ("kg", 1), "????": ("kg", 1), "????": ("kg", 1), "किलो": ("kg", 1), "కిలో": ("kg", 1), "kg": ("kg", 1), "kilo": ("kg", 1), "kilos": ("kg", 1),
    "கிரேட்": ("kg", 20), "ಕ್ರೇಟ್": ("kg", 20), "?????": ("kg", 20), "??????": ("kg", 20), "क्रेट": ("kg", 20), "క్రేట్": ("kg", 20), "crate": ("kg", 20), "crates": ("kg", 20),
    "கொத்து": ("bunch", 1), "கட்டு": ("bunch", 1), "ಗೊಂಚಲು": ("bunch", 1), "ಕಟ್ಟು": ("bunch", 1), "??????": ("bunch", 1), "????": ("bunch", 1), "गुच्छा": ("bunch", 1), "కట్ట": ("bunch", 1), "bunch": ("bunch", 1), "bunches": ("bunch", 1),
}
PRODUCT_WORDS = {
    "tomato": "tomato", "tomatoes": "tomato", "தக்காளி": "tomato", "tamatar": "tomato", "टमाटर": "tomato", "టమాటా": "tomato", "ಟೊಮ್ಯಾಟೊ": "tomato", "ಟೊಮೇಟೊ": "tomato",
    "coriander": "coriander", "kothamalli": "coriander", "கொத்தமல்லி": "coriander", "ಕೊತ್ತಂಬರಿ": "coriander", "ಕೊತ್ತುಂಬರಿ": "coriander",
    "dhania": "coriander", "धनिया": "coriander", "ధనియాలు": "coriander", "?????": "coriander", "???????": "coriander", "onion": "onion", "வெங்காயம்": "onion", "प्याज": "onion", "ఉల్లి": "onion", "ಈರುಳ್ಳಿ": "onion",
    "spinach": "spinach", "palak": "spinach", "पालक": "spinach", "పాలకూర": "spinach", "????": "spinach", "??????": "spinach", "ಮುರೈಕೀರೈ": "spinach", "ಪಾಲಕ್": "spinach", "ಪಾಲಕ್ ಸೊಪ್ಪು": "spinach",
    "potato": "potato", "aloo": "potato", "आलू": "potato", "ఆలూ": "potato", "???": "potato", "???": "potato", "ಆಲೂಗಡ್ಡೆ": "potato", "உருளைக்கிழங்கு": "potato",
}
APPROVE_WORDS = ["sari", "seri", "saringa", "sar", "हाँ", "हां", "aam", "సరే", "sare", "சரி", "சரிங்க", "ஆம்", "ಸರಿ", "yes", "yeah", "ha", "haan", "ಹೌದು", "ok", "okay", "confirm", "ஓகே"]
DENY_WORDS = ["illa", "இல்ல", "வேண்டாம்", "vendam", "venam", "nahi", "nahin", "नहीं", "కాదు", "లేదు", "ledu", "ಇಲ್ಲ", "ಬೇಡ", "beda", "no", "nope", "cancel", "stop"]

# Prompt-injection markers — merchant speech is DATA, never instructions.
INJECTION_MARKERS = [
    "ignore previous", "ignore all previous", "disregard", "system prompt",
    "reveal your prompt", "you are now", "act as", "jailbreak",
    "without approval", "skip approval", "auto approve", "override",
]

# ─── Word-safe matching ───────────────────────────────────────────────────
# FIX 2026-09-19: the old `"ha" in text` substring test matched "w**ha**t" and
# "t**ha**t" (firing the approval gate on questions) and `"no" in text` matched
# "k**no**w"/"**no**w" (cancelling orders that contained the word "now").
# ASCII words now match on token boundaries; Indic words stay substring
# (scripts are syllabic, boundaries are unreliable there).
_ASCII_RE = re.compile(r"^[\x00-\x7f]+$")
_PUNCT_AFTER = r"(?=$|[\s,.!?;:'\"()\u2013\u2014])"
_PUNCT_BEFORE = r"(?:^|[\s,.!?;:'\"()\u2013\u2014])"


def _word_hit(low: str, words: list) -> bool:
    """Boundary-safe keyword match. 'yes' must not match 'yeasted';
    'no' must not fire inside 'now'."""
    for w in words:
        if _ASCII_RE.match(w):
            if re.search(_PUNCT_BEFORE + re.escape(w) + _PUNCT_AFTER, low):
                return True
        elif w in low:
            return True
    return False


def _products_mentioned(low: str) -> dict:
    """Product names present in the text, without claiming any quantity."""
    out = {}
    for word, product in PRODUCT_WORDS.items():
        if _word_hit(low, [word]):
            out[product] = None
    return out


# ─── Question intents — every answer is composed from LIVE engine data ────
Q_WHY = ["why", "reason", "ஏன்", "ಏಕೆ", "क्यों", "ఎందుకు"]
Q_PRICE = ["price", "rate", "cost", "how much for", "விலை", "விகிதம்", "ಬೆಲೆ", "दाम", "कीमत", "ధర", "రేటు"]
Q_STOCK = ["how much", "how many", "stock", "left", "remaining", "எவ்வளவு", "எத்தனை", "சரக்கு", "கையில்", "ಎಷ್ಟು", "ದಾಸ್ತಾನು", "कितना", "कितने", "स्टॉक", "ఎంత", "స్టాక్"]
Q_WEATHER = ["rain", "weather", "மழை", "ಮಳೆ", "बारिश", "मौसम", "వర్ష", "వాతావరణం"]
Q_ORDERS = ["last order", "my orders", "order history", "orders", "bill", "கடந்த ஆர்டர்", "ஆர்டர் வரலாறு", "பில்", "ಹಿಂದಿನ ಆರ್ಡರ್", "ಬಿಲ್", "पिछला आर्डर", "बिल", "గత ఆర్డర్", "బిల్లు"]
Q_SALES = ["sold", "sales", "velocity", "விற்பனை", "ಮಾರಾಟ", "बिक्री", "అమ్మకం"]
GREETING_WORDS = ["hi", "hello", "hey", "vanakkam", "வணக்கம்", "ನಮಸ್ಕಾರ", "namaste", "नमस्ते", "నమస్కారం", "ನಮಸ್ತೆ"]
HELP_WORDS = ["help", "menu", "உதவி", "ಸಹಾಯ", "मदद", "సహాయం"]


def _question_kind(low: str) -> str | None:
    if _word_hit(low, Q_WHY):
        return "why"
    if _word_hit(low, Q_PRICE):
        return "price"
    if _word_hit(low, Q_STOCK):
        return "stock"
    if _word_hit(low, Q_WEATHER):
        return "weather"
    if _word_hit(low, Q_ORDERS):
        return "orders"
    if _word_hit(low, Q_SALES):
        return "sales"
    return None


LANG_MAP = {
    "ta": "ta", "tamil": "ta", "ta-in": "ta",
    "kn": "kn", "kannada": "kn", "kn-in": "kn",
    "hi": "hi", "hindi": "hi", "hi-in": "hi",
    "en": "en", "english": "en", "en-in": "en",
    "te": "te", "telugu": "te",
}


def _detect_lang(text: str) -> str:
    # Telugu FIX 2026-09-19: \u0c00-\u0c7f was missing, so Telugu transcripts
    # were treated as English and got Tamil asks.
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta"
    if re.search(r"[\u0c80-\u0cff]", text):
        return "kn"
    if re.search(r"[\u0c00-\u0c7f]", text):
        return "te"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    return "en"


def _parse_quantities(text: str) -> dict[str, int | None]:
    """Extract {product: requested_qty} from a transcript.
    Handles '20 கிலோ தக்காளி' / '20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ', '3 crates tomato', '10 கொத்து கொத்தமல்லி',
    Tamil/Kannada word-numbers, punctuation, and qty-before/after product order.
    NEVER invents a number — absent numbers stay None (engine fills deterministically).

    FIX 2026-09-19: glued tokens like '20kg' / '10bunches' were single \w+ matches,
    so 'tomato 20kg' carried NO quantity. Numbers and unit words are now split
    apart before parsing."""
    # Split digits glued to unit words: '20kg' -> '20 kg', '10bunches' -> '10 bunches'
    text = re.sub(r"(\d)(kgs?|kilos?|crates?|bunches?|bunch)\b", r"\1 \2", text, flags=re.IGNORECASE)
    # Also split a Devanagari/Indic unit glued after digits: '20किलो' -> '20 किलो'
    text = re.sub(r"(\d)([\u0b80-\u0bff\u0c80-\u0cff\u0c00-\u0c7f\u0900-\u097f]+)", r"\1 \2", text)
    tokens = re.findall(r"[\w\u0b80-\u0bff\u0c80-\u0cff\u0c00-\u0c7f\u0900-\u097f]+", text.lower())
    found: dict[str, int | None] = {}
    i = 0
    while i < len(tokens):
        t = tokens[i]
        v = WORDNUM.get(t, int(t) if t.isdigit() else None)
        if v is not None:
            mult, j = 1, i + 1
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


def _rules_intent(text: str) -> dict:
    """Deterministic rule-based intent parse. Authoritative for all quantities."""
    low = text.lower()
    tokens = set(re.findall(r"[\w\u0b80-\u0bff\u0c80-\u0cff\u0c00-\u0c7f\u0900-\u097f]+", low))
    if not text.strip():
        return {"intent": "silence", "products": {}, "clarification_needed": True}
    if any(w in tokens for w in DENY_WORDS):
        return {"intent": "decline", "products": {}, "clarification_needed": False}
    has_product = any(word in low for word in PRODUCT_WORDS)
    has_approve = any(w in tokens for w in APPROVE_WORDS)
    if not has_product and not has_approve:
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
            "clarification_needed": ambiguous, "language": _detect_lang(text)}


def _products_from_llm_names(names: dict | None) -> dict[str, int | None]:
    """Map LLM-reported product names to catalog keys, DISCARDING every number.

    This is the doctrinal firewall: the model may tell us WHICH product, never
    HOW MUCH. A quantity the model emits becomes None (engine derives it)."""
    out: dict[str, int | None] = {}
    if not isinstance(names, dict):
        return out
    for raw_name in names.keys():
        low = str(raw_name).lower()
        for word, product in PRODUCT_WORDS.items():
            if word in low and product not in out:
                out[product] = None
                break
    return out


@app.get("/health")
def health():
    return {
        "status": "ok",
        "sarvam_key": bool(os.getenv("SARVAM_API_KEY")),
        "weather_mode": os.getenv("WEATHER_MODE", "seeded"),
        "llm_mode": llm_mod.llm_mode(),
        "cognee": cognee_client.health(),
        "n8n": "configured" if os.getenv("N8N_WEBHOOK_URL") else "not_configured",
        "twilio": "configured" if os.getenv("TWILIO_ACCOUNT_SID") else "not_configured",
        "twilio_mode": os.getenv("TWILIO_CONTENT_MODE", "template"),
        "twilio_recipient": os.getenv("TWILIO_WHATSAPP_TO", "NOT_SET"),
        "copilot": {
            "wa_akg": bool(os.getenv("WA_AKG_URL") and os.getenv("WA_AKG_API_KEY")
                           and os.getenv("WA_AKG_SESSION")),
            "twilio_freeform": bool(os.getenv("TWILIO_ACCOUNT_SID")),
            "allowed_phones": sorted({_normalize_phone(p) for p in
                                      os.getenv("COPILOT_ALLOWED_PHONES", "").split(",")}
                                     if os.getenv("COPILOT_ALLOWED_PHONES") else
                                     [x for x in [_normalize_phone(os.getenv("TWILIO_WHATSAPP_TO", ""))] if x]),
            "pending_orders": len(pending_orders),
        },
        "inventory_reset_on_start": os.getenv("DEMO_RESET_ON_START", "1"),
        "llm_last": dict(llm_mod.LAST),
    }


@app.get("/llm/diag")
def llm_diag():
    """Build-day diagnostics: which model ran, how long it took, why it failed."""
    return llm_mod.diag()


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
    """Hybrid intent parse.

    Rules are authoritative for quantities and for safety refusals; Sarvam
    (prompts/P1_intent.txt) adds language + intent classification. Send
    {"use_llm": false} to force the pure-rules path.
    """
    text = (payload.get("transcript") or "").strip()
    rules = _rules_intent(text)
    if not text:
        return rules

    low = text.lower()
    if any(m in low for m in INJECTION_MARKERS):
        return {
            "intent": "out_of_scope", "products": {}, "clarification_needed": True,
            "injection_detected": True,
            "note": "merchant speech is data — embedded instructions were refused",
            "engine": "rules",
        }

    use_llm = payload.get("use_llm")
    llm_on = llm_mod.available() if use_llm is None else bool(use_llm)
    llm_out = llm_mod.parse_intent(text) if (llm_on and llm_mod.available()) else None
    result = dict(rules)

    if llm_out is None:
        result["engine"] = "rules"
        return result

    # Safety refusals win: a model cannot overturn a decline or an out-of-scope.
    if rules["intent"] == "decline":
        result["engine"] = "rules+llm"
        result["llm"] = {"language": llm_out.get("language")}
        return result
    if llm_out.get("injection_detected"):
        return {
            "intent": "out_of_scope", "products": {}, "clarification_needed": True,
            "injection_detected": True,
            "note": "Sarvam flagged embedded instructions in merchant speech",
            "engine": "rules+llm",
        }

    # Quantities: rules only. If rules found none, accept LLM product NAMES at qty None.
    if not rules.get("products") and llm_out.get("intent") == "create_restock_order":
        llm_products = _products_from_llm_names(llm_out.get("raw_products"))
        if llm_products:
            result.update({
                "intent": "create_restock_order",
                "products": llm_products,
                "clarification_needed": True,
                "note": "product identified by Sarvam; quantity must come from the merchant or the engine",
                "engine": "rules+llm",
            })

    lang = LANG_MAP.get(str(llm_out.get("language") or "").strip().lower())
    if lang and result.get("intent") == "create_restock_order":
        result["language"] = lang
    result["engine"] = "rules+llm"
    result["llm"] = {
        "intent": llm_out.get("intent"),
        "language": llm_out.get("language"),
        "confidence": llm_out.get("confidence"),
        "quantities_ignored": llm_out.get("raw_products") if any(
            isinstance(v, (int, float)) for v in (llm_out.get("raw_products") or {}).values()
        ) else None,
    }
    return result


@app.post("/rec")
def get_recommendation(payload: dict):
    """Deterministic recommendation, single product."""
    product = payload.get("product", "tomato")
    requested = payload.get("requested_qty")
    merchant_id = payload.get("merchant_id", MERCHANT)
    try:
        return recommendation(merchant_id, product, requested)
    except KeyError:
        raise HTTPException(400, f"Unknown product — catalog: {', '.join(CATALOG.get(merchant_id, []))}")


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
    weather = get_weather()
    return {
        "items": items,
        "basket_total_inr": total,
        "weather": weather,
        "ask": llm_mod.template_ask(items, weather["rain_prob"]),
        "ask_source": "template",
        "engine": "deterministic",
    }


@app.post("/explain")
def explain(payload: dict):
    """P3 — vernacular explanation by Sarvam. Falls back to the template."""
    products = payload.get("products")
    merchant_id = payload.get("merchant_id", MERCHANT)
    if products:
        items = []
        for product, requested in products.items():
            try:
                items.append(recommendation(merchant_id, product, requested))
            except KeyError:
                raise HTTPException(400, f"Unknown product: {product}")
    else:
        items = payload.get("items") or []
    if not items:
        raise HTTPException(400, "no items to explain")
    rain = get_weather()["rain_prob"]
    text = llm_mod.explain_ask(items, rain)
    return {
        "text": text or llm_mod.template_ask(items, rain),
        "source": "sarvam-llm" if text else "template-fallback",
        "fallback_reason": None if text else (llm_mod.LAST.get("error") or
                          "grounding gate: explanation omitted an engine quantity"),
        "model": llm_mod.FAST_MODEL if text else None,
        "quantities_from": "deterministic engine",
        "items_injected": [i["recommended_qty"] for i in items],
    }


@app.post("/reason")
def reason(payload: dict):
    """P2 — grounded reasoning over REAL observations fetched here (not invented).

    Returns the observation trace alongside the model's reasoning so a judge can
    see that every number came from the engine, not from the language model.
    Uses the deep reasoning model deliberately — this is the on-demand path.
    """
    product = payload.get("product", "tomato")
    requested = payload.get("requested_qty")
    merchant_id = payload.get("merchant_id", MERCHANT)
    try:
        rec = recommendation(merchant_id, product, requested)
    except KeyError:
        raise HTTPException(400, f"Unknown product: {product}")

    weather = get_weather()
    data = CATALOG[merchant_id][product]
    observations = [
        {"tool": "get_stock", "args": product, "result": f"{rec['stock_on_hand']} {rec['unit']}"},
        {"tool": "get_sales_velocity", "args": product, "result": f"{data['velocity']} {rec['unit']}/day avg"},
        {"tool": "get_weather", "args": "tomorrow",
         "result": f"{int(weather['rain_prob']*100)}% rain ({weather.get('source')})"},
        {"tool": "get_decay", "args": product, "result": f"{data['decay_days']} days shelf life"},
        {"tool": "get_recommendation", "args": product,
         "result": f"{rec['recommended_qty']} {rec['unit']} = Rs.{rec['total_inr']} (DETERMINISTIC ENGINE)"},
    ]
    # Default = fast model (~1s, stage-safe). Pass {"deep": true} for the
    # reasoning model (~32s, for a seated judge walkthrough — never mid-pitch).
    profile = "deep" if payload.get("deep") else "fast"
    out = llm_mod.reason(rec, observations, profile=profile)
    deterministic = (
        f"Engine: stock {rec['stock_on_hand']} {rec['unit']}, velocity {data['velocity']}/day, "
        f"shelf life {data['decay_days']}d, rain {int(weather['rain_prob']*100)}% -> "
        f"{rec['recommended_qty']} {rec['unit']} (Rs.{rec['total_inr']})."
    )
    return {
        "product": product,
        "recommended_qty": rec["recommended_qty"],
        "total_inr": rec["total_inr"],
        "observations": observations,
        "reasoning": (out or {}).get("reasoning") or deterministic,
        "memory_note": (out or {}).get("memory_note") or f"{product}: ordered {rec['recommended_qty']} {rec['unit']}",
        "needs_human_review": bool((out or {}).get("needs_human_review")),
        "source": f"sarvam-llm({profile})" if out else "deterministic-trace",
        "model": (llm_mod.DEEP_MODEL if profile == "deep" else llm_mod.FAST_MODEL) if out else None,
        "profile": profile,
        "elapsed_s": llm_mod.LAST.get("elapsed_s"),
        "finish_reason": llm_mod.LAST.get("finish_reason"),
        "fallback_reason": None if out else (
            llm_mod.LAST.get("error") or
            ("model returned no content (finish_reason=" + str(llm_mod.LAST.get('finish_reason')) +
             ") — raise LLM_DEEP_MAX_TOKENS for the deep profile")
        ),
        "quantities_from": "deterministic engine",
    }


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


def _append_memory_audit(entry: dict, memory_note: str = "") -> dict:
    """Append the dispatched order to the visible memory so judges SEE learning."""
    try:
        with open(MEMORY_PATH, encoding="utf-8") as f:
            memory = json.load(f)
    except OSError:
        memory = {}
    merchant = memory.setdefault(entry["merchant_id"], {})
    history = merchant.setdefault("order_history", [])
    history.append({**entry, "memory_note": memory_note})
    merchant["last_order"] = (
        f"{entry['qty']} {entry['unit']} {entry.get('name_tn') or ''} "
        f"({entry['product']}) -> {entry['supplier']} (Rs.{entry['total_inr']})"
    )
    merchant["stock_on_hand"] = entry["stock_after"]
    merchant["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except OSError as e:
        entry["memory_write_error"] = str(e)
    return memory


def _fire_n8n(record: dict) -> None:
    n8n_url = os.getenv("N8N_WEBHOOK_URL")
    if not n8n_url:
        record["n8n"] = "not_configured"
        return
    try:
        r = httpx.post(n8n_url, json=record, timeout=8)
        record["n8n"] = "fired"
        record["n8n_status"] = r.status_code
        if r.status_code >= 400:
            record["n8n_body"] = r.text[:200]
    except Exception as e:
        record["n8n"] = "failed"
        record["n8n_error"] = str(e)


def _twilio_content_vars(record: dict, order: dict, n_vars: int) -> dict:
    """ContentVariables sized to the registered Twilio template.

    2 = qty + product (legacy/Appt template)
    4 = + supplier + total (n8n dispatch.json default)
    6 = + stock_before + stock_after — the copilot proof: the WhatsApp
        bubble itself shows the ledger move ("Stock 12 → 32").
    """
    content_vars = {"1": str(order["qty"]), "2": order["product"]}
    if n_vars >= 4:
        content_vars.update({"3": order["supplier"], "4": str(record.get("total_inr") or "")})
    if n_vars >= 6:
        content_vars.update({"5": str(record.get("stock_before") or ""),
                             "6": str(record.get("stock_after") or "")})
    return content_vars


def _fire_twilio(record: dict, order: dict, approval: dict) -> None:
    """Send the order over WhatsApp via Twilio.

    Never fakes success: every outcome is labelled on the record —
    `sent` (201), a real error code, or `skipped` with a plain-language note.
    The message SID is kept on the record so delivery can be verified later.
    """
    twilio_sid, twilio_token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    if not twilio_sid or not twilio_token:
        return
    recipient = approval.get("merchant_phone") or os.getenv("TWILIO_WHATSAPP_TO")
    if not recipient:
        # Never post to the placeholder number — that produced error 572002 while
        # looking like a real send. Mock it so the UI still shows a bubble.
        record["twilio_status"] = "skipped — demo mode"
        record["twilio_note"] = (
            "TWILIO_WHATSAPP_TO not set — mock WhatsApp logged (no placeholder send). "
            "Set it + verify in Twilio console for a real buzz on stage."
        )
        mock_msg = (f"HarvestWise order: {order['qty']} {order['product']} "
                    f"({record['total_inr']} INR) -> {order['supplier']} "
                    f"| stock {record.get('stock_before')}->{record.get('stock_after')} (ledger updated)")
        try:
            os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
            with open(os.path.join(BASE_DIR, "data", "mock_whatsapp.log"), "a", encoding="utf-8") as lf:
                lf.write(f"{record['at']} | To: mock | {mock_msg}\n")
            record["mock_whatsapp"] = mock_msg
        except Exception:
            pass
        return
    try:
        n_vars = max(int(os.getenv("TWILIO_TEMPLATE_VARS", "2") or 2), 2)
        record["twilio_vars"] = n_vars
        auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
        # TWILIO_CONTENT_MODE=freeform sends a plain Body (sandbox/dev — no
        # template approval needed, kills the "Appt" bug). template (default)
        # uses a registered ContentSid + ContentVariables (production).
        content_mode = os.getenv("TWILIO_CONTENT_MODE", "template")
        if content_mode == "freeform":
            body = (f"HarvestWise order: {order['qty']} {order['product']} "
                    f"({record['total_inr']} INR) -> {order['supplier']} "
                    f"| stock {record.get('stock_before')}->{record.get('stock_after')} (ledger updated)")
            data = {
                "To": recipient,
                "From": os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
                "Body": body,
            }
            record["twilio_mode"] = "freeform"
            record["twilio_vars"] = 0
        else:
            data = {
                "To": recipient,
                "From": os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
                "ContentSid": os.getenv("TWILIO_CONTENT_SID", ""),
                "ContentVariables": json.dumps(_twilio_content_vars(record, order, n_vars)),
            }
            record["twilio_mode"] = "template"
        r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                       data=data, headers={"Authorization": f"Basic {auth}"}, timeout=10)
        record["twilio_status"] = r.status_code
        if r.status_code < 300:
            body = r.json() if "application/json" in r.headers.get("content-type", "") else {}
            record["twilio_sid"] = (body.get("sid") or "")[:34]
            record["twilio_to"] = recipient
        elif r.status_code >= 400:
            record["twilio_body"] = r.text[:300]
            record["twilio_note"] = "template send rejected — see Twilio console (dispatch still recorded)"
    except Exception as e:
        record["twilio_error"] = str(e)


# ─── WhatsApp COPILOT (full Observe -> Ask -> Approve -> Act -> Learn loop) ──
# Transport-agnostic: WA-AKG (live demo) > Twilio freeform (fallback) > mock log.
# The webhook endpoints enforce an allowlist; /copilot/simulate is the offline
# battery path and NEVER sends to a real user (force_mock=True).
pending_orders: dict[str, dict] = {}


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d]", "", phone or "")


def _allowed_copilot_phone(phone_digits: str) -> bool:
    if not phone_digits:
        return False
    allow = os.getenv("COPILOT_ALLOWED_PHONES", "")
    if allow:
        allowed = {_normalize_phone(p) for p in allow.split(",") if _normalize_phone(p)}
        return phone_digits in allowed
    default = _normalize_phone(os.getenv("TWILIO_WHATSAPP_TO", ""))
    return bool(default) and phone_digits == default


def _stt_media(url: str, headers: dict | None = None, content_type: str = "") -> str:
    """Download a WhatsApp voice note and transcribe it with Sarvam saaras:v3.
    Saaras accepts OGG/OPUS natively — no ffmpeg conversion needed."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        return ""
    try:
        r = httpx.get(url, headers=headers or {}, timeout=20)
        r.raise_for_status()
        audio = r.content
        if not audio:
            return ""
        if "ogg" in content_type or "opus" in content_type:
            codec = "ogg"
        elif "mp4" in content_type or "m4a" in content_type:
            codec = "mp4"
        elif "webm" in content_type:
            codec = "webm"
        elif "mp3" in content_type:
            codec = "mp3"
        else:
            codec = "wav"
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=api_key)
        # FIX 2026-09-19: was hardcoded ta-IN — a Kannada/Hindi voice note came
        # back garbled. saaras:v3 supports language_code="unknown" (auto-detect);
        # if the provider rejects it, fall back to the crew default ta-IN.
        for lang_code in ("unknown", "ta-IN"):
            try:
                resp = client.speech_to_text.transcribe(
                    file=(f"voice.{codec}", audio), model="saaras:v3",
                    language_code=lang_code, input_audio_codec=codec,
                )
                return (getattr(resp, "transcript", "") or "").strip()
            except Exception:
                continue
        return ""
    except Exception:
        return ""


def _copilot_send(phone: str, text: str, force_mock: bool = False) -> dict:
    """Outbound copilot reply. Priority: WA-AKG -> Twilio freeform -> mock log.
    Every outcome is labelled so a judge can see exactly which transport ran."""
    phone_digits = _normalize_phone(phone)
    attempts: list[dict] = []
    if not force_mock:
        # FIX 2026-09-19: the old code RETURNED on WA-AKG failure, so a gateway
        # hiccup silently ate the merchant's reply. Now every live transport is
        # tried in priority order and the reply is never lost.
        wa_url = os.getenv("WA_AKG_URL")
        wa_key = os.getenv("WA_AKG_API_KEY")
        wa_session = os.getenv("WA_AKG_SESSION")
        if wa_url and wa_key and wa_session:
            try:
                jid = f"{phone_digits}@s.whatsapp.net"
                r = httpx.post(
                    f"{wa_url.rstrip('/')}/api/messages/{wa_session}/{jid}/send",
                    json={"message": {"text": text}},
                    headers={"X-API-Key": wa_key}, timeout=10)
                attempts.append({"transport": "wa-akg", "status": r.status_code, "jid": jid})
                if 200 <= r.status_code < 300:
                    return {**attempts[-1], "attempts": attempts}
            except Exception as e:
                attempts.append({"transport": "wa-akg", "error": type(e).__name__})
        tw_sid, tw_tok = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
        if tw_sid and tw_tok:
            try:
                auth = base64.b64encode(f"{tw_sid}:{tw_tok}".encode()).decode()
                r = httpx.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{tw_sid}/Messages.json",
                    data={"To": f"whatsapp:+{phone_digits}",
                          "From": os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
                          "Body": text},
                    headers={"Authorization": f"Basic {auth}"}, timeout=10)
                attempts.append({"transport": "twilio-freeform", "status": r.status_code})
                if 200 <= r.status_code < 300:
                    return {**attempts[-1], "attempts": attempts}
            except Exception as e:
                attempts.append({"transport": "twilio-freeform", "error": type(e).__name__})
    try:
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
        with open(os.path.join(BASE_DIR, "data", "copilot_chat.log"), "a",
                  encoding="utf-8") as lf:
            lf.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} | "
                     f"To: {phone_digits} | {text}\n")
        return {"transport": "mock-log", "status": "logged"}
    except OSError:
        return {"transport": "none", "error": "log unavailable"}


def _approve_and_dispatch(phone_digits: str, pend: dict) -> list[dict]:
    """Issue one single-use token per item and execute each (idempotent).
    Mirrors /voice/approve + /dispatch exactly — no new money-moving code."""
    results = []
    for item in pend.get("items", []):
        product = item.get("product")
        qty = item.get("recommended_qty")
        data = CATALOG.get(MERCHANT, {}).get(product)
        if not data:
            results.append({"product": product, "status": "rejected", "reason": "unknown_product"})
            continue
        valid, reason = validate_order(MERCHANT, product, qty, data["supplier"])
        if not valid:
            results.append({"product": product, "status": "rejected", "reason": reason})
            continue
        token = str(uuid.uuid4())
        issued_tokens[token] = {"product": product, "qty": qty, "supplier": data["supplier"]}
        out = dispatch_order({"token": token, "total_inr": item.get("total_inr"),
                              "merchant_phone": f"whatsapp:+{phone_digits}"})
        results.append(out)
    return results


def _confirm_text(results: list[dict], lang: str = "ta") -> str:
    """The kill-shot bubble: order + total + stock movement, all from the ledger,
    in the merchant's language (numbers and '12->32' stay machine-readable)."""
    heads = {
        "ta": "HarvestWise ✅ ஆர்டர் அனுப்பப்பட்டது",
        "kn": "HarvestWise ✅ ಆರ್ಡರ್ ಕಳುಹಿಸಲಾಗಿದೆ",
        "hi": "HarvestWise ✅ ऑर्डर भेज दिया गया",
        "te": "HarvestWise ✅ ఆర్డర్ పంపబడింది",
        "en": "HarvestWise ✅ Order dispatched",
    }
    nones = {
        "ta": "HarvestWise: ஒப்புதல் பதிவானது, ஆனால் எதுவும் அனுப்பப்படவில்லை.",
        "kn": "HarvestWise: ಒಪ್ಪಿಗೆ ದಾಖಲಾಗಿದೆ, ಆದರೆ ಏನೂ ಕಳುಹಿಸಲಾಗಲಿಲ್ಲ.",
        "hi": "HarvestWise: अनुमोदन दर्ज हुआ, पर कुछ भेजा नहीं गया।",
        "te": "HarvestWise: ఆమోదం నమోదైంది, కానీ ఏమీ పంపబడలేదు.",
        "en": "HarvestWise: approval recorded but nothing dispatched (see engine response).",
    }
    totals = {"ta": "மொத்தம் ரூ.", "kn": "ಒಟ್ಟು ರೂ.", "hi": "कुल रु.", "te": "మొత్తం రూ.", "en": "Total Rs."}
    stocks = {"ta": "சரக்கு: ", "kn": "ದಾಸ್ತಾನು: ", "hi": "स्टॉक: ", "te": "స్టాక్: ", "en": "Stock: "}
    updated = {"ta": " (லெட்ஜர் + மெமரி புதுப்பிக்கப்பட்டது)", "kn": " (ಲೆಡ್ಜರ್ + ಮೆಮೊರಿ ಅಪ್ಡೇಟ್)",
               "hi": " (लेजर + मेमोरी अपडेटेड)", "te": " (లెడ్జర్ + మెమరీ అప్‌డేట్)", "en": " (ledger + memory updated)"}
    dispatched = [r for r in results if r.get("status") == "dispatched"]
    if not dispatched:
        return nones.get(lang, nones["en"])
    lines, moves, total = [heads.get(lang, heads["en"])], [], 0
    for r in dispatched:
        rec = r.get("record", {})
        data = CATALOG.get(MERCHANT, {}).get(rec.get("product") or "", {})
        name = _loc_name(data, rec.get("product") or "", lang)
        lines.append(f"• {rec.get('quantity_kg')} {rec.get('unit')} {name} -> Rs.{rec.get('total_inr')}")
        moves.append(f"{rec.get('product')} {rec.get('stock_before')}->{rec.get('stock_after')}")
        total += rec.get("total_inr") or 0
    lines.append(totals.get(lang, totals["en"]) + str(total))
    lines.append(stocks.get(lang, stocks["en"]) + ", ".join(moves) + updated.get(lang, updated["en"]))
    return "\n".join(lines)


LANG_NAMES = {"ta": "Tamil", "kn": "Kannada", "hi": "Hindi", "te": "Telugu", "en": "English"}
PENDING_TTL_S = 30 * 60  # an unconfirmed basket dies after 30 min — stale approvals never dispatch


def _catalog_product_in(low: str) -> str | None:
    """First catalog product named in the text (word-safe)."""
    for word, product in PRODUCT_WORDS.items():
        if _word_hit(low, [word]):
            return product
    return None


def _loc_name(data: dict, product: str, lang: str) -> str:
    """Localized product name; falls back to Tamil then the catalog key."""
    key = {"kn": "name_kn", "hi": "name_hi", "te": "name_te"}.get(lang)
    return (data.get(key) if key else None) or data.get("name_tn") or product


def _get_pending(phone_digits: str) -> dict | None:
    """Pending basket with a TTL — expired ones are dropped silently."""
    pend = pending_orders.get(phone_digits)
    if not pend:
        return None
    if datetime.datetime.now().timestamp() - pend.get("created", 0) > PENDING_TTL_S:
        pending_orders.pop(phone_digits, None)
        return None
    return pend


def _help_text(lang: str) -> str:
    return {
        "ta": "HarvestWise உதவி:\n• ஆர்டர்: \"நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி\"\n• சரி = ஒப்புதல் · இல்ல/வேண்டாம் = ரத்து\n• கேளுங்கள்: விலை? எவ்வளவு சரக்கு? மழை? ஏன் 20? கடந்த ஆர்டர்?",
        "kn": "HarvestWise ಸಹಾಯ:\n• ಆರ್ಡರ್: \"ನಾಳೆ 20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ, 10 ಗೊಂಚಲು ಕೊತ್ತಂಬರಿ\"\n• ಸರಿ = ಒಪ್ಪಿಗೆ · ಬೇಡ/ಇಲ್ಲ = ರದ್ದು\n• ಕೇಳಿ: ಬೆಲೆ? ಎಷ್ಟು ದಾಸ್ತಾನು? ಮಳೆ? ಏಕೆ 20? ಹಿಂದಿನ ಆರ್ಡರ್?",
        "hi": "HarvestWise मदद:\n• ऑर्डर: \"कल 20 किलो टमाटर, 10 गुच्छा धनिया\"\n• हाँ = स्वीकृति · नहीं = रद्द\n• पूछें: दाम? कितना स्टॉक? बारिश? क्यों 20? पिछला ऑर्डर?",
        "te": "HarvestWise సహాయం:\n• ఆర్డర్: \"రేపు 20 కిలో టమాటా, 10 కట్ట ధనియాలు\"\n• సరే = ఆమోదం · కాదు/లేదు = రద్దు\n• అడగండి: ధర? ఎంత స్టాక్? వర్షం? ఎందుకు 20? గత ఆర్డర్?",
        "en": "HarvestWise help:\n• Order: \"tomato 20kg, 10 bunches coriander\"\n• yes/ok = approve · no/cancel = cancel\n• Ask: price? stock? rain? why 20? last orders?",
    }.get(lang) or _help_text("en") if False else {
        "ta": "HarvestWise உதவி:\n• ஆர்டர்: \"நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி\"\n• சரி = ஒப்புதல் · இல்ல/வேண்டாம் = ரத்து\n• கேளுங்கள்: விலை? எவ்வளவு சரக்கு? மழை? ஏன் 20? கடந்த ஆர்டர்?",
        "kn": "HarvestWise ಸಹಾಯ:\n• ಆರ್ಡರ್: \"ನಾಳೆ 20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ, 10 ಗೊಂಚಲು ಕೊತ್ತಂಬರಿ\"\n• ಸರಿ = ಒಪ್ಪಿಗೆ · ಬೇಡ/ಇಲ್ಲ = ರದ್ದು\n• ಕೇಳಿ: ಬೆಲೆ? ಎಷ್ಟು ದಾಸ್ತಾನು? ಮಳೆ? ಏಕೆ 20? ಹಿಂದಿನ ಆರ್ಡರ್?",
        "hi": "HarvestWise मदद:\n• ऑर्डर: \"कल 20 किलो टमाटर, 10 गुच्छा धनिया\"\n• हाँ = स्वीकृति · नहीं = रद्द\n• पूछें: दाम? कितना स्टॉक? बारिश? क्यों 20? पिछला ऑर्डर?",
        "te": "HarvestWise సహాయం:\n• ఆర్డర్: \"రేపు 20 కిలో టమాటా, 10 కట్ట ధనియాలు\"\n• సరే = ఆమోదం · కాదు/లేదు = రద్దు\n• అడగండి: ధర? ఎంత స్టాక్? వర్షం? ఎందుకు 20? గత ఆర్డర్?",
        "en": "HarvestWise help:\n• Order: \"tomato 20kg, 10 bunches coriander\"\n• yes/ok = approve · no/cancel = cancel\n• Ask: price? stock? rain? why 20? last orders?",
    }[lang]


def _welcome_text(lang: str) -> str:
    return {
        "ta": "வணக்கம் லக்ஷ்மி! HarvestWise உங்கள் மறுசப்ளை உதவியாளர். ஆர்டர் சொல்லுங்கள் அல்லது 'உதவி' என்று கேளுங்கள்.",
        "kn": "ನಮಸ್ಕಾರ ಲಕ್ಷ್ಮಿ! HarvestWise ನಿಮ್ಮ ಮರುಪೂರೈಕೆ ಸಹಾಯಕ. ಆರ್ಡರ್ ಹೇಳಿ ಅಥವಾ 'ಸಹಾಯ' ಎಂದು ಕೇಳಿ.",
        "hi": "नमस्ते लक्ष्मी! HarvestWise आपका रीस्टॉक सहायक है। ऑर्डर बताइए या 'मदद' कहिए।",
        "te": "నమస్కారం లక్ష్మీ! HarvestWise మీ రీస్టాక్ సహాయకుడు. ఆర్డర్ చెప్పండి లేదా 'సహాయం' అని అడగండి.",
        "en": "Vanakkam Lakshmi! HarvestWise is your restocking copilot. Say an order, or ask for help.",
    }[lang]


def _qa_answer(kind: str, low: str, lang: str) -> str:
    """Q&A composed LIVE from engine/catalog/ledger/weather — never scripted numbers."""
    product = _catalog_product_in(low)
    weather = get_weather()
    rain = int(round(weather["rain_prob"] * 100))
    if kind == "weather":
        return {
            "ta": f"நாளை மழை {rain} சதவீதம் (ஆதாரம்: {weather.get('source')}).",
            "kn": f"ನಾಳೆ ಮಳೆ {rain} ಪ್ರತಿಶತ (ಮೂಲ: {weather.get('source')}).",
            "hi": f"कल बारिश {rain} प्रतिशत (स्रोत: {weather.get('source')}).",
            "te": f"రేపు వర్షం {rain} శాతం (మూలం: {weather.get('source')}).",
            "en": f"Rain tomorrow: {rain}% (source: {weather.get('source')}).",
        }[lang]
    product = product or "tomato"
    data = CATALOG[MERCHANT][product]
    name = _loc_name(data, product, lang)
    unit = data["unit"]
    if kind == "price":
        return {
            "ta": f"{name} விலை ரூ.{data['price_per_unit']}/{unit} (மண்டி விலை, விதைக்கப்பட்ட டெமோ தரவு).",
            "kn": f"{name} ಬೆಲೆ ರೂ.{data['price_per_unit']}/{unit} (ಮಾರುಕಟ್ಟೆ ದರ, ಬಿತ್ತಿದ ಡೆಮೊ ದತ್ತಾಂಶ).",
            "hi": f"{name} कीमत रु.{data['price_per_unit']}/{unit} (मंडी भाव, सीडेड डेमो डेटा).",
            "te": f"{name} ధర రూ.{data['price_per_unit']}/{unit} (మండీ ధర, సీడెడ్ డెమో డేటా).",
            "en": f"{name}: Rs.{data['price_per_unit']}/{unit} (mandi rate, seeded demo data).",
        }[lang]
    if kind == "stock":
        stock = get_stock(MERCHANT, product)
        return {
            "ta": f"{name}: இப்போது {stock} {unit} கையில் உள்ளது.",
            "kn": f"{name}: ಈಗ {stock} {unit} ದಾಸ್ತಾನು ಇದೆ.",
            "hi": f"{name}: अभी {stock} {unit} स्टॉक है।",
            "te": f"{name}: ఇప్పుడు {stock} {unit} స్టాక్ ఉంది.",
            "en": f"{name}: {stock} {unit} on hand right now.",
        }[lang]
    if kind == "sales":
        return {
            "ta": f"{name}: சராசரியாக நாளுக்கு {data['velocity']} {unit} விற்பனை (90 நாள்).",
            "kn": f"{name}: ಸರಾಸರಿ ದಿನಕ್ಕೆ {data['velocity']} {unit} ಮಾರಾಟ (90 ದಿನ).",
            "hi": f"{name}: औसतन {data['velocity']} {unit} प्रति दिन बिक्री (90 दिन)।",
            "te": f"{name}: సగటున రోజుకు {data['velocity']} {unit} అమ్మకం (90 రోజులు).",
            "en": f"{name}: {data['velocity']} {unit}/day average (90d).",
        }[lang]
    if kind == "orders":
        hist = order_history(MERCHANT, 3)
        if not hist:
            return {
                "ta": "இதுவரை ஆர்டர் இல்லை. ஆர்டர் சொல்லுங்கள்!",
                "kn": "ಇನ್ನೂ ಆರ್ಡರ್ ಇಲ್ಲ. ಆರ್ಡರ್ ಹೇಳಿ!",
                "hi": "अभी तक कोई ऑर्डर नहीं। ऑर्डर बताइए!",
                "te": "ఇంకా ఆర్డర్ లేదు. ఆర్డర్ చెప్పండి!",
                "en": "No orders yet. Say an order!",
            }[lang]
        head = {"ta": "கடந்த ஆர்டர்கள்:", "kn": "ಹಿಂದಿನ ಆರ್ಡರ್‌ಗಳು:", "hi": "पिछले ऑर्डर:",
                "te": "గత ఆర్డర్‌లు:", "en": "Recent orders:"}[lang]
        lines = [f"• {o['at'][:10]} {o['qty']} {o['unit']} {o.get('name_tn') or o['product']} Rs.{o.get('total_inr')}"
                 for o in hist]
        return head + "\n" + "\n".join(lines)
    if kind == "why":
        rec = recommendation(MERCHANT, product, None)
        stock = rec["stock_on_hand"]
        return {
            "ta": (f"எஞ்சின் பரிந்துரை: {name} வேகமாக விற்கிறது (நாளுக்கு {data['velocity']} {unit}), "
                   f"கையில் {stock} {unit} மட்டுமே, நாளை மழை {rain}% — அதனால் {rec['recommended_qty']} {unit} "
                   f"(ரூ.{rec['total_inr']}). எண் எப்போதும் எஞ்சினிலிருந்தே."),
            "kn": (f"ಎಂಜಿನ್ ಶಿಫಾರಸು: {name} ವೇಗವಾಗಿ ಮಾರಾಟವಾಗುತ್ತದೆ (ದಿನಕ್ಕೆ {data['velocity']} {unit}), "
                   f"ದಾಸ್ತಾನು {stock} {unit} ಮಾತ್ರ, ನಾಳೆ ಮಳೆ {rain}% — ಆದ್ದರಿಂದ {rec['recommended_qty']} {unit} "
                   f"(ರೂ.{rec['total_inr']}). ಸಂಖ್ಯೆ ಯಾವಾಗಲೂ ಎಂಜಿನ್‌ನಿಂದ."),
            "hi": (f"इंजन की सिफारिश: {name} तेज़ बिकता है ({data['velocity']} {unit}/दिन), "
                   f"स्टॉक सिर्फ {stock} {unit}, कल बारिश {rain}% — इसलिए {rec['recommended_qty']} {unit} "
                   f"(रु.{rec['total_inr']}). संख्या हमेशा इंजन से।"),
            "te": (f"ఇంజన్ సిఫార్సు: {name} వేగంగా అమ్ముడవుతుంది (రోజుకు {data['velocity']} {unit}), "
                   f"స్టాక్ {stock} {unit} మాత్రమే, రేపు వర్షం {rain}% — అందుకే {rec['recommended_qty']} {unit} "
                   f"(రూ.{rec['total_inr']}). సంఖ్య ఎప్పుడూ ఇంజన్ నుంచి."),
            "en": (f"Engine: {name} sells {data['velocity']} {unit}/day, only {stock} {unit} on hand, "
                   f"{rain}% rain tomorrow -> {rec['recommended_qty']} {unit} (Rs.{rec['total_inr']}). "
                   f"Numbers always come from the engine."),
        }[lang]
    return _help_text(lang)


def _handle_merchant_message(phone: str, text: str = "", media_url: str = "",
                             media_headers: dict | None = None,
                             content_type: str = "", channel: str = "webhook") -> dict:
    """The copilot brain. Voice/text in -> intent -> ask -> approve -> dispatch.

    security: unknown callers are refused; merchant speech is DATA (injection
    markers refused); quantities always come from rules/engine, never from an LLM.
    """
    phone_digits = _normalize_phone(phone)
    force_mock = channel == "simulate"
    if not _allowed_copilot_phone(phone_digits):
        _copilot_send(phone_digits, "HarvestWise: unknown caller - order ignored.",
                      force_mock=force_mock)
        return {"status": "unknown_caller", "phone": phone_digits, "channel": channel}

    transcript = (text or "").strip()
    if media_url and not transcript:
        transcript = _stt_media(media_url, media_headers, content_type)

    low = transcript.lower()
    tokens = set(re.findall(r"[\w\u0b80-\u0bff\u0c80-\u0cff\u0c00-\u0c7f\u0900-\u097f]+", low))
    if any(m in low for m in INJECTION_MARKERS):
        _copilot_send(phone_digits,
                      "HarvestWise: speech refused - embedded instructions were ignored.",
                      force_mock=force_mock)
        return {"status": "injection_blocked", "phone": phone_digits,
                "transcript": transcript, "channel": channel}

    if _word_hit(low, DENY_WORDS):
        pending_orders.pop(phone_digits, None)
        _copilot_send(phone_digits,
                      _cancel_text(_detect_lang(transcript or "no")), force_mock=force_mock)
        return {"status": "declined", "phone": phone_digits,
                "transcript": transcript, "channel": channel}

    if _word_hit(low, APPROVE_WORDS):
        pend = pending_orders.pop(phone_digits, None)
        if not pend:
            _copilot_send(phone_digits,
                          "HarvestWise: no pending order to approve. Send your order first.",
                          force_mock=force_mock)
            return {"status": "no_pending", "phone": phone_digits,
                    "transcript": transcript, "channel": channel}
        results = _approve_and_dispatch(phone_digits, pend)
        confirm = _confirm_text(results)
        _copilot_send(phone_digits, confirm, force_mock=force_mock)
        rejected = [r for r in results if r.get("status") != "dispatched"]
        return {"status": "dispatched" if not rejected else "partial",
                "phone": phone_digits, "transcript": transcript,
                "dispatched": [r for r in results if r.get("status") == "dispatched"],
                "rejected": rejected, "confirm": confirm, "channel": channel}

    # --- Best-response: Why / Stock / Memory (grounded, Sarvam + Cognee, never hardcoded) ---
    low_why = low
    if any(m in low_why for m in ["why", "etharku", "ethukku", "karanam", "kaaranam", "reason", "explain", "stock", "inventory", "memory", "recall", "enna", "edhukku", "vilakam"]):
        # Try to answer about current recommendation or stock, grounded on engine + Cognee
        prod_in_why = None
        for w, p in PRODUCT_WORDS.items():
            if w in low_why:
                prod_in_why = p
                break
        if prod_in_why or any(w in low_why for w in ["stock", "inventory"]):
            # Stock snapshot without product → return all stocks (deterministic, not hardcoded)
            if any(w in low_why for w in ["stock", "inventory"]) and not prod_in_why:
                snap = stock_snapshot(MERCHANT)
                lines = [f"{p}: {qty} {CATALOG[MERCHANT][p]['unit']}" for p, qty in snap.items()]
                answer = "Stock now — " + " · ".join(lines) + "."
                _copilot_send(phone_digits, answer, force_mock=force_mock)
                return {"status": "answered", "phone": phone_digits, "transcript": transcript, "answer": answer, "channel": channel, "engine": "stock_snapshot"}
            try:
                target = prod_in_why or "tomato"
                rec = recommendation(MERCHANT, target, None)
                weather = get_weather()
                observations = [
                    {"tool": "get_stock", "args": target, "result": f"{rec['stock_on_hand']} {rec['unit']}"},
                    {"tool": "get_sales_velocity", "args": target, "result": f"{CATALOG[MERCHANT][target]['velocity']} {rec['unit']}/day"},
                    {"tool": "get_weather", "args": "tomorrow", "result": f"{int(weather['rain_prob']*100)}% rain ({weather.get('source')})"},
                    {"tool": "get_recommendation", "args": target, "result": f"{rec['recommended_qty']} {rec['unit']} = Rs.{rec['total_inr']}"},
                ]
                reason_out = llm_mod.reason(rec, observations, language="Tamil", profile="fast")
                cog = cognee_client.recall(f"Why did HarvestWise recommend {rec['recommended_qty']} {rec['unit']} {target} for Lakshmi?", dataset="harvestwise") if cognee_client.configured() else {"error": "cognee not configured"}
                reasoning = (reason_out or {}).get("reasoning") if reason_out else None
                if not reasoning:
                    reasoning = f"Engine: stock {rec['stock_on_hand']} {rec['unit']}, velocity {CATALOG[MERCHANT][target]['velocity']}/day, rain {int(weather['rain_prob']*100)}% -> {rec['recommended_qty']} {rec['unit']} (Rs.{rec['total_inr']})."
                cog_text = ""
                if cog.get("results"):
                    cog_text = " · ".join([str(x.get("text") or x.get("content") or "")[:120] for x in cog["results"][:1] if x.get("text") or x.get("content")])
                answer = reasoning
                if cog_text:
                    answer += f"\n\nMemory: {cog_text[:180]}"
                answer += f"\n\nStock now: {rec['stock_on_hand']} {rec['unit']} on hand."
                _copilot_send(phone_digits, answer, force_mock=force_mock)
                return {"status": "answered", "phone": phone_digits, "transcript": transcript, "product": target, "answer": answer, "channel": channel, "engine": "reason+cognee"}
            except Exception:
                pass

    rules = _rules_intent(transcript)
    if rules["intent"] != "create_restock_order" or not rules.get("products"):
        _copilot_send(phone_digits,
                      "HarvestWise: I did not catch a product. Try: நாளை 20 கிலோ தக்காளி.",
                      force_mock=force_mock)
        return {"status": "no_intent", "phone": phone_digits,
                "transcript": transcript, "channel": channel}

    items, total = [], 0
    for product, requested in rules["products"].items():
        rec = recommendation(MERCHANT, product, requested)
        items.append(rec)
        total += rec["total_inr"]
    weather = get_weather()
    # Best response: Sarvam P3 explain with grounding gate, fallback to deterministic template (never hardcoded numbers)
    ask = llm_mod.template_ask(items, weather["rain_prob"])
    try:
        sarvam_ask = llm_mod.explain_ask(items, weather["rain_prob"], language="Tamil")
        if sarvam_ask:
            ask = sarvam_ask
    except Exception:
        pass
    suffix = ("\nசரி என்று பதில் சொல்லுங்கள் (reply சரி to confirm)."
              if _detect_lang(transcript) == "ta" else
              "\nReply சரி to confirm.")
    message = f"{ask}{suffix}"
    pending_orders[phone_digits] = {"products": rules["products"], "items": items,
                                    "total_inr": total}
    _copilot_send(phone_digits, message, force_mock=force_mock)
    return {"status": "awaiting_approval", "phone": phone_digits,
            "transcript": transcript, "basket_total_inr": total,
            "items": [{"product": i["product"], "recommended_qty": i["recommended_qty"],
                       "unit": i["unit"], "total_inr": i["total_inr"]} for i in items],
            "ask": message, "engine": "rules", "channel": channel}


@app.post("/wa/inbound")
def wa_inbound(payload: dict):
    """WA-AKG webhook: JSON {"event":"message.received","data":{...,"type":
    "TEXT|AUDIO","content":"...","key":{"remoteJid":"91...@s.whatsapp.net"},
    "fileUrl":"/media/..."}}."""
    data = payload.get("data") or {}
    phone = (data.get("from") or (data.get("key") or {}).get("remoteJid") or "")
    text = data.get("content") or data.get("body") or ""
    media = data.get("fileUrl") or (data.get("quoted") or {}).get("fileUrl") or ""
    if media and not media.startswith("http"):
        base = os.getenv("WA_AKG_URL", "")
        if base:
            media = base.rstrip("/") + media
    headers = {"X-API-Key": os.getenv("WA_AKG_API_KEY", "")} if media and os.getenv("WA_AKG_API_KEY") else None
    result = _handle_merchant_message(
        phone, text=text, media_url=media, media_headers=headers,
        content_type=data.get("mimetype") or data.get("contentType") or "",
        channel="wa-akg")
    return {"received": True, "result": result}


@app.post("/twilio/inbound")
async def twilio_inbound(request: Request):
    """Twilio sandbox webhook (form-encoded): From, Body, NumMedia, MediaUrl0,
    MediaContentType0. Voice notes arrive as audio/ogg -> Sarvam STT (native)."""
    form = await request.form()
    try:
        form = dict(form)
    except Exception:
        form = {}
    phone = form.get("From", "")
    text = form.get("Body", "") or ""
    media_url = form.get("MediaUrl0", "") or ""
    content_type = form.get("MediaContentType0", "") or ""
    headers = None
    sid, tok = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    if media_url and sid and tok:
        headers = {"Authorization":
                   f"Basic {base64.b64encode(f'{sid}:{tok}'.encode()).decode()}"}
    result = _handle_merchant_message(
        phone, text=text, media_url=media_url, media_headers=headers,
        content_type=content_type, channel="twilio")
    return {"received": True, "result": result}


@app.post("/copilot/simulate")
def copilot_simulate(payload: dict):
    """Offline end-to-end test of the copilot brain — battery + offline demo path.
    Never sends to a real user: replies are returned in the body and logged to
    data/copilot_chat.log (force_mock=True). No external services required."""
    return _handle_merchant_message(
        payload.get("phone", "917010919624"),
        text=payload.get("text", ""),
        media_url=payload.get("media_url", ""),
        content_type=payload.get("media_type", ""),
        channel="simulate")


@app.get("/copilot/state")
def copilot_state():
    allow = os.getenv("COPILOT_ALLOWED_PHONES", "")
    allowed = sorted({_normalize_phone(p) for p in allow.split(",")} if allow
                     else [x for x in [_normalize_phone(os.getenv("TWILIO_WHATSAPP_TO", ""))] if x])
    return {
        "allowed_phones": allowed,
        "pending_orders": {
            phone: {"products": p["products"], "basket_total_inr": p["total_inr"]}
            for phone, p in pending_orders.items()
        },
        "transports": {
            "wa_akg": bool(os.getenv("WA_AKG_URL") and os.getenv("WA_AKG_API_KEY")
                           and os.getenv("WA_AKG_SESSION")),
            "twilio_freeform": bool(os.getenv("TWILIO_ACCOUNT_SID")),
            "mock_log": True,
        },
        "note": "WA-AKG webhook -> /wa/inbound | Twilio sandbox webhook -> /twilio/inbound"
                " | offline test -> /copilot/simulate",
    }


@app.get("/whatsapp/status")
def whatsapp_status():
    """One-glance WhatsApp health for the dashboard + judges.

    Reports config (is a verified recipient set?), the recipient number, and the
    delivery state of the most recent outbound message straight from Twilio's
    API (accepted/queued/sent/delivered/read or failed + error code). Falls back
    to the local dispatch record when Twilio is unreachable — never blocks.
    """
    sid, tok = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    recipient = os.getenv("TWILIO_WHATSAPP_TO")
    out = {
        "account_configured": bool(sid and tok),
        "recipient_set": bool(recipient),
        "recipient": recipient or None,
        "mode": "live" if (sid and tok and recipient) else "mock",
    }
    # Most recent local record, for context even when Twilio is unreachable.
    try:
        with open(DISPATCH_RECORD_PATH, encoding="utf-8") as f:
            rec = json.load(f)
        out["last_dispatch"] = {
            "product": rec.get("product"), "qty": rec.get("quantity_kg"),
            "unit": rec.get("unit"), "total_inr": rec.get("total_inr"),
            "twilio_status": rec.get("twilio_status"), "at": rec.get("at"),
            "message_sid": rec.get("twilio_sid"),
        }
        sid_local = rec.get("twilio_sid")
    except Exception:
        sid_local = None
    if not (sid and tok):
        out["last_message"] = {"status": "no_account"}
        return out
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        if sid_local:
            url += f"/{sid_local}"
        else:
            url += "?PageSize=1"
        r = httpx.get(url, headers={"Authorization": f"Basic {auth}"}, timeout=6)
        if r.status_code == 200:
            m = r.json()
            msg = m if "sid" in m else (m.get("messages") or [{}])[0]
            out["last_message"] = {
                "status": msg.get("status"), "error_code": msg.get("error_code"),
                "to": msg.get("to"), "date": str(msg.get("date_created") or ""),
                "source": "twilio-api",
            }
        else:
            out["last_message"] = {"status": f"probe-http-{r.status_code}", "source": "twilio-api"}
    except Exception as e:
        out["last_message"] = {"status": "probe-failed", "error": type(e).__name__, "source": "twilio-api"}
    return out


@app.post("/dispatch")
def dispatch_order(approval: dict):
    """Execute an approved order: ledger + memory + n8n + WhatsApp (idempotent)."""
    token = approval.get("token") or approval.get("approval_token")
    if not token:
        return {"status": "failed", "reason": "missing token"}
    if token in dispatched_tokens:
        return {"status": "duplicate_ignored", "reason": "idempotency: this order was already dispatched"}
    order = issued_tokens.pop(token, None)
    if order is None:
        return {"status": "failed", "reason": "unknown or already-used approval token"}

    # ── Acceptance criterion #5: visible inventory update + auditable memory ──
    delivery = record_delivery(
        MERCHANT, order["product"], order["qty"], order["supplier"],
        approval.get("total_inr"), token,
    )
    entry = delivery["entry"]

    record = {
        "token": token, "status": "dispatched",
        "merchant_id": MERCHANT,
        "product": order["product"],
        "name_tn": entry.get("name_tn", ""),
        "quantity_kg": order["qty"],
        "unit": entry.get("unit", ""),
        "supplier": order["supplier"],
        "total_inr": approval.get("total_inr"),
        "stock_before": entry["stock_before"],
        "stock_after": entry["stock_after"],
        "at": entry["at"],
    }

    with open(DISPATCH_RECORD_PATH, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    dispatched_tokens.add(token)
    _save_dispatched()

    memory_note = approval.get("memory_note") or ""
    _append_memory_audit(entry, memory_note)
    record["memory_updated"] = True

    # Real Cognee write: add_text -> cognify, in the background (never blocks).
    if cognee_client.configured():
        lines = [
            f"On {entry['at']} merchant {MERCHANT} approved a restocking order for "
            f"{order['qty']} {entry.get('unit', '')} {order['product']} from {order['supplier']} "
            f"for Rs.{record['total_inr']}. Stock on hand moved {entry['stock_before']} -> "
            f"{entry['stock_after']}. Reason: {memory_note or 'deterministic engine recommendation'}."
        ]
        cognee_client.remember_async(lines)
        record["cognee"] = "add_text+cognify queued"

    _fire_n8n(record)
    _fire_twilio(record, order, approval)

    return {"status": "dispatched", "record": record,
            "inventory": {"stock_on_hand": delivery["stock_on_hand"]},
            "memory": {"path": "cognee/memory.json", "updated": True}}


@app.post("/voice/approve")
def voice_approve(payload: dict):
    """Voice approval gate: {transcript, items: [{product, qty}], or legacy product/qty}."""
    text = (payload.get("transcript") or "").lower()
    if any(w in text for w in DENY_WORDS):
        return {"status": "declined", "heard": text}
    if not any(w in text for w in APPROVE_WORDS):
        return {"status": "needs_confirmation", "heard": text}

    merchant_id = payload.get("merchant_id", MERCHANT)
    items = payload.get("items")
    if not items:
        product = payload.get("product", "tomato")
        qty = payload.get("qty") or calculate_quantity(merchant_id, product)
        items = [{"product": product, "qty": qty}]

    approved = []
    for item in items:
        product = item.get("product", "tomato")
        qty = item.get("qty") or calculate_quantity(merchant_id, product)
        data = CATALOG.get(merchant_id, {}).get(product)
        if not data:
            return {"status": "rejected", "reason": f"unknown_product: {product}"}
        supplier = data["supplier"]
        valid, reason = validate_order(merchant_id, product, qty, supplier)
        if not valid:
            return {"status": "rejected", "reason": f"{product}: {reason}"}
        token = str(uuid.uuid4())
        issued_tokens[token] = {"product": product, "qty": qty, "supplier": supplier}
        approved.append({"approval_token": token, "product": product,
                         "name_tn": data.get("name_tn", ""),
                         "quantity_kg": qty, "unit": data.get("unit", ""),
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
        with open(MEMORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {"lakshmi": {"note": "run python cognee/seed_memory.py first"}}


@app.get("/state")
def get_state(merchant_id: str = MERCHANT):
    """Everything the dashboard needs: stock, weather, orders, memory summary."""
    weather = get_weather()
    memory = {}
    try:
        with open(MEMORY_PATH, encoding="utf-8") as f:
            memory = json.load(f).get(merchant_id, {})
    except OSError:
        pass
    return {
        "merchant_id": merchant_id,
        "persona": "Lakshmi (representative persona)",
        "data_label": "Paytm-transaction-shaped seeded demo data",
        "stock_on_hand": stock_snapshot(merchant_id),
        "products": {
            p: {"name_tn": d.get("name_tn"), "name_kn": d.get("name_kn"),
                "unit": d["unit"], "price_per_unit": d["price_per_unit"],
                "velocity": d["velocity"], "decay_days": d["decay_days"],
                "rain_modifier": d["rain_modifier"]}
            for p, d in CATALOG.get(merchant_id, {}).items()
        },
        "weather": weather,
        "orders": order_history(merchant_id, 10),
        "memory": {"recommendation": memory.get("recommendation"),
                   "last_order": memory.get("last_order"),
                   "stock_on_hand": memory.get("stock_on_hand"),
                   "order_count": len(memory.get("order_history", []))},
    }


@app.post("/demo/reset")
def demo_reset():
    """Restore seeded inventory + clear the ledger so a rehearsal is repeatable."""
    state = reset_state()
    tokens_cleared = len(dispatched_tokens)
    dispatched_tokens.clear()
    _save_dispatched()
    return {"status": "reset", "stock": state["stock"], "tokens_cleared": tokens_cleared}


@app.get("/soundbox/briefing")
def soundbox_briefing(merchant_id: str = MERCHANT):
    """Morning briefing audio payload — Soundbox plays the same voice briefing (simulated)."""
    w = get_weather()
    rain = int(w["rain_prob"] * 100)
    stock = stock_snapshot(merchant_id)
    tomato = CATALOG[merchant_id]["tomato"]
    coriander = CATALOG[merchant_id]["coriander"]
    text = (
        f"Vanakkam Lakshmi! Naalai {rain} sathaveetham mazhai. "
        f"Thakkali {stock.get('tomato')} kilo ullathu, kothamalli {stock.get('coriander')} kothu. "
        f"Mandi vilai kilo {tomato['price_per_unit']} rubai, kothamalli {coriander['price_per_unit']} rubai."
    )
    return {
        "text": text,
        "rain_prob": w["rain_prob"],
        "weather_source": w.get("source"),
        "source": "HarvestWise Soundbox briefing (simulated — plays on Paytm Soundbox rail)",
        "plays_on": "Paytm Soundbox",
    }


@app.post("/cognee/recall")
async def cognee_recall(payload: dict):
    """Graph-grounded recall from Cognee cloud (falls back to labeled local memory)."""
    import asyncio
    q = payload.get("query", "Why 20 kg tomato?")
    result = await asyncio.to_thread(cognee_client.recall, q)
    if "error" in result:
        return {**result, "memory": get_memory(), "source": "local-fallback"}
    return result


@app.post("/cognee/remember")
async def cognee_remember(payload: dict):
    """Explicitly persist a fact/lesson into the causal graph (add_text -> cognify)."""
    import asyncio
    texts = payload.get("texts") or []
    if not texts and payload.get("text"):
        texts = [payload["text"]]
    if not texts:
        raise HTTPException(400, "no texts to remember")
    added = await asyncio.to_thread(cognee_client.add_text, texts)
    cognified = await asyncio.to_thread(cognee_client.cognify) if added.get("ok") else {"error": "add_text failed"}
    return {"added": added, "cognify": cognified}
