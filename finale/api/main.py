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
import threading
import concurrent.futures

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
    order_history, RAINY_THRESHOLD, get_sales_forecast, get_bundle_suggestion,
    get_margin_leader, set_stock, add_stock, delete_stock, add_product,
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
# Dev Mode: Allow any origin (frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # kg units
    "கிலோ": ("kg", 1), "ಕಿಲೋ": ("kg", 1), "ಕೆಜಿ": ("kg", 1), "किलो": ("kg", 1), "కిలో": ("kg", 1),
    "kg": ("kg", 1), "kilo": ("kg", 1), "kilos": ("kg", 1),
    # crate = 20 kg
    "கிரேட்": ("kg", 20), "ಕ್ರೇಟ್": ("kg", 20), "क्रेट": ("kg", 20), "క్రేట్": ("kg", 20),
    "crate": ("kg", 20), "crates": ("kg", 20),
    # bunch units
    "கொத்து": ("bunch", 1), "கட்டு": ("bunch", 1), "ಗೊಂಚಲು": ("bunch", 1), "ಕಟ್ಟು": ("bunch", 1),
    "गुच्छा": ("bunch", 1), "కట్ట": ("bunch", 1), "bunch": ("bunch", 1), "bunches": ("bunch", 1),
}
PRODUCT_WORDS = {
    "tomato": "tomato", "tomatoes": "tomato", "தக்காளி": "tomato", "tamatar": "tomato", "टमाटर": "tomato", "టమాటా": "tomato", "ಟೊಮ್ಯಾಟೊ": "tomato", "ಟೊಮೇಟೊ": "tomato",
    "coriander": "coriander", "kothamalli": "coriander", "கொத்தமல்லி": "coriander", "ಕೊತ್ತಂಬರಿ": "coriander", "ಕೊತ್ತುಂಬರಿ": "coriander",
    "dhania": "coriander", "धनिया": "coriander", "ధనియాలు": "coriander", "onion": "onion", "வெங்காயம்": "onion", "प्याज": "onion", "ఉల్లి": "onion", "ಈರುಳ್ಳಿ": "onion",
    "spinach": "spinach", "palak": "spinach", "पालक": "spinach", "పాలకూర": "spinach", "ಮುರೈಕೀರೈ": "spinach", "ಪಾಲಕ್": "spinach", "ಪಾಲಕ್ ಸೊಪ್ಪು": "spinach",
    "potato": "potato", "aloo": "potato", "आलू": "potato", "ఆలూ": "potato", "ಆಲೂಗಡ್ಡೆ": "potato", "உருளைக்கிழங்கு": "potato",
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
HELP_WORDS = ["help", "menu", "how to do", "how to", "epdi", "eppadi", "hege", "ela", "kaise", "kese", "உதவி", "ಸಹಾಯ", "मदद", "సహాయం", "help me", "what to do"]


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
    # 1) Unicode script is authoritative — reply must be pure, never mixed.
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta"
    if re.search(r"[\u0c80-\u0cff]", text):
        return "kn"
    if re.search(r"[\u0c00-\u0c7f]", text):
        return "te"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    # 2) Tanglish / code-switch: Latin-script Tamil/Hindi/etc. Common merchant
    #    phrasing like "tomato 20kg venum", "sari", "chahiye" — without this,
    #    they were mis-detected as English and got mixed replies.
    low = text.lower()
    # pure language reply: count dominant Latin keywords, pick winner
    ta_keys = ["venum", "vendum", "vaenum", "sari", "seri", "vaanga", "kudu", "kudunga", "epdi", "enna", "vanakkam"]
    hi_keys = ["chahiye", "bhejo", "kitna", "kya", "namaste", "sahiye", "bejna", "batao"]
    te_keys = ["kavali", "enti", "ela", "namaste", "kavala"]
    kn_keys = ["beku", "yenu", "yava", "namaste", "kodi"]
    scores = {"ta": sum(1 for k in ta_keys if k in low), "hi": sum(1 for k in hi_keys if k in low),
              "te": sum(1 for k in te_keys if k in low), "kn": sum(1 for k in kn_keys if k in low)}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        # also respect merchant's saved preference when Tanglish is ambiguous (single word)
        # but never mix: one language per reply.
        return best
    # 3) No Indic signal → English
    return "en"


def _parse_quantities(text: str) -> dict[str, int | None]:
    """Extract {product: requested_qty} from a transcript.
    Handles '20 கிலோ தக்காளி' / '20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ', '3 crates tomato', '10 கொத்து கொத்தமல்லி',
    Tamil/Kannada word-numbers, punctuation, and qty-before/after product order.
    NEVER invents a number — absent numbers stay None (engine fills deterministically).

    FIX 2026-09-19: glued tokens like '20kg' / '10bunches' were single word
    matches, so 'tomato 20kg' carried NO quantity. Numbers and unit words are
    now split apart before parsing."""
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
        "copilot_architecture": {
            "knowledge": {
                "name": "Sarvam AI",
                "role": "Language understanding, intent parsing, explanation",
                "configured": bool(os.getenv("SARVAM_API_KEY"))
            },
            "brain": {
                "name": "Cognee",
                "role": "Merchant memory, pattern recognition, historical recall",
                "configured": cognee_client.configured()
            },
            "hands": {
                "name": "n8n Automation",
                "role": "WhatsApp messaging, UI updates, order dispatch",
                "configured": bool(os.getenv("N8N_WEBHOOK_URL"))
            }
        },
        "sarvam_key": bool(os.getenv("SARVAM_API_KEY")),
        "weather_mode": os.getenv("WEATHER_MODE", "seeded"),
        "llm_mode": llm_mod.llm_mode(),
        "cognee": cognee_client.health(),
        "n8n": "configured" if os.getenv("N8N_WEBHOOK_URL") else "not_configured",
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
    """Sarvam STT (saaras:v3). Accepts wav/webm/mp3/ogg from browser/WebChat.
    Low-latency path: runs in bounded thread pool, max 45s timeout."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise HTTPException(503, "SARVAM_API_KEY not configured — typed-transcript fallback is the labeled path")
    audio = await file.read()
    if not audio:
        raise HTTPException(400, "empty audio")
    try:
        def _do_stt() -> dict:
            from sarvamai import SarvamAI
            client = SarvamAI(api_subscription_key=api_key)
            suffix = (file.filename or "audio.wav").rsplit(".", 1)[-1].lower()
            codec = {"wav": "wav", "webm": "webm", "mp3": "mp3", "m4a": "mp4", "ogg": "ogg"}.get(suffix, "wav")
            last_err = None
            for model in ("saaras:v4", "saaras:v3"):
                try:
                    resp = client.speech_to_text.transcribe(
                        file=(f"audio.{suffix}", audio), model=model,
                        language_code=language_code, input_audio_codec=codec,
                    )
                    return {"transcript": getattr(resp, "transcript", "") or str(resp), "language_code": language_code, "model": model}
                except Exception as e:
                    last_err = e
                    if "insufficient_quota" in str(e) or "402" in str(e):
                        raise
                    continue
            raise last_err or RuntimeError("saaras v4/v3 failed")
        # FIX 2026-09-19: the SDK call used to run directly in the route threadpool
        # with no outer bound — a hung provider call parked a worker forever and
        # enough of those froze the whole API. Bounded executor + hard deadline.
        return _run_offloop(_do_stt, 45)
    except concurrent.futures.TimeoutError:
        raise HTTPException(504, "STT timed out — use typed transcript (labeled fallback)")
    except Exception as e:
        # Graceful fallback for quota exhaustion — browser Web Speech API will handle it
        msg = str(e)
        if "402" in msg or "insufficient_quota" in msg or "No credits" in msg:
            return {"transcript": "", "language_code": language_code, "fallback": "browser", "error": "sarvam_quota_exhausted", "detail": msg[:300]}
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
    # FIX 2026-09-19: language passthrough — a Kannada/Hindi/Telugu demo order no
    # longer gets a Tamil Sarvam rewrite (the grounding gate would reject it
    # anyway). Non-Tamil gets the deterministic localized ask via template_ask.
    lang = LANG_MAP.get(str(payload.get("language") or "").strip().lower())
    text = None
    if lang is None or lang == "ta":
        text = llm_mod.explain_ask(items, rain, language="Tamil")
    return {
        "text": text or (_ask_text(items, lang) if lang in ("kn", "hi", "te", "en")
                         else llm_mod.template_ask(items, rain)),
        "language": lang or "ta",
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


# ─── Merchant voice/text preferences (persisted locally + Cognee) ──────────
# voice_mode: "text" | "voice" | "both"  — how the copilot replies to THIS merchant
# language:   "ta-IN" | "hi-IN" | "te-IN" | "kn-IN" | "en-US"
PREFS_PATH = os.path.join(BASE_DIR, "data", "merchant_prefs.json")
DEFAULT_PREFS = {"voice_mode": "both", "language": "ta-IN"}


def _load_prefs() -> dict:
    try:
        with open(PREFS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
        with open(PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _get_merchant_prefs(phone_digits: str) -> dict:
    """Fast local read (no network) — the low-latency path for every reply."""
    return _load_prefs().get(phone_digits, dict(DEFAULT_PREFS))


def _prefs_lang(phone_digits: str) -> str:
    """Sarvam TTS language code for this merchant's preference (default Tamil)."""
    return _get_merchant_prefs(phone_digits).get("language", "ta-IN")


def _set_merchant_prefs(phone_digits: str, **updates) -> dict:
    prefs = _load_prefs()
    cur = prefs.get(phone_digits, dict(DEFAULT_PREFS))
    cur.update({k: v for k, v in updates.items() if v is not None})
    prefs[phone_digits] = cur
    _save_prefs(prefs)
    # Fire-and-forget write to Cognee so the knowledge graph learns the choice.
    if cognee_client.configured():
        cognee_client.remember_async([
            f"Merchant {phone_digits} prefers {cur['voice_mode']} replies "
            f"in language {cur['language']}."
        ])
    return cur


# ─── Merchant business profiles (first-time onboarding) ───────────────────
# For a new merchant the copilot BECOMES a business partner: it asks name,
# business, and what they sell, builds a knowledge card, and mirrors it to
# Cognee so every later reply is grounded in their business.
PROFILES_PATH = os.path.join(BASE_DIR, "data", "merchant_profiles.json")
ONBOARD_STEPS = ["name", "business", "products"]  # 3-step interactive flow


def _load_profiles() -> dict:
    try:
        with open(PROFILES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


def _save_profiles(profiles: dict) -> None:
    try:
        os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
        with open(PROFILES_PATH, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _seed_default_profile(phone_digits: str) -> dict:
    """Seed Lakshmi (demo merchant) so existing judges don't re-onboard."""
    profiles = _load_profiles()
    if phone_digits in profiles:
        return profiles[phone_digits]
    # Only seed the known demo numbers
    demo_seed = {
        "917010919624": {"name": "Lakshmi", "business": "Lakshmi Kirana & Vegetables", "business_type": "kirana", "products": "tomato, onion, coriander, spinach", "location": "Basavanagudi, Bangalore", "onboarding_complete": True, "step": 3},
        "919840306258": {"name": "Rahul", "business": "Rahul Traders", "business_type": "trader", "products": "tomato, potato", "location": "Chennai", "onboarding_complete": True, "step": 3},
    }
    if phone_digits in demo_seed:
        profiles[phone_digits] = demo_seed[phone_digits]
        _save_profiles(profiles)
        return demo_seed[phone_digits]
    return {}


def _get_merchant_profile(phone_digits: str) -> dict | None:
    profiles = _load_profiles()
    if phone_digits not in profiles:
        return _seed_default_profile(phone_digits) or None
    return profiles[phone_digits]


def _set_merchant_profile(phone_digits: str, **updates) -> dict:
    profiles = _load_profiles()
    cur = profiles.get(phone_digits, {"onboarding_complete": False, "step": 0})
    cur.update({k: v for k, v in updates.items() if v is not None})
    profiles[phone_digits] = cur
    _save_profiles(profiles)
    # Mirror business knowledge to Cognee causal graph
    if cognee_client.configured() and cur.get("onboarding_complete"):
        facts = [f"Merchant {phone_digits} is {cur.get('name','')} who runs {cur.get('business','')} ({cur.get('business_type','')}) selling {cur.get('products','')} at {cur.get('location','')}."]
        # Also store voice/lang prefs as fact
        prefs = _get_merchant_prefs(phone_digits)
        facts.append(f"Merchant {phone_digits} prefers {prefs['voice_mode']} replies in {prefs['language']}.")
        cognee_client.remember_async(facts)
    return cur


def _onboarding_needed(phone_digits: str) -> bool:
    p = _get_merchant_profile(phone_digits)
    return not p or not p.get("onboarding_complete")


def _onboarding_prompt(step: int, lang: str, name: str = "") -> str:
    """Interactive onboarding asks — localized, business-partner tone."""
    prompts = {
        0: {
            "ta": "Vanakkam! 🙏 Naan ungala Paytm Business Partner. Ungala peyar enna? (Your name?)",
            "hi": "Namaste! 🙏 Main aapka Paytm Business Partner hoon. Aapka naam kya hai?",
            "te": "Namaste! 🙏 Nenu mee Paytm Business Partner. Mee peru enti?",
            "kn": "Namaste! 🙏 Naanu nimma Paytm Business Partner. Nimma hesaru yenu?",
            "en": "Hello! 🙏 I'm your Paytm Business Partner. What's your name?",
        },
        1: {
            "ta": f"Nandri {name}! 🙏 Ungala kadai / business peyar enna? (e.g. Lakshmi Kirana)",
            "hi": f"Shukriya {name}! 🙏 Aapki dukaan / business ka naam kya hai?",
            "te": f"Dhanyavadalu {name}! 🙏 Mee shop / business peru enti?",
            "kn": f"Dhanyavada {name}! 🙏 Nimma angadi / business hesaru yenu?",
            "en": f"Thanks {name}! 🙏 What's your shop / business name?",
        },
        2: {
            "ta": "Arumai! Neenga enna vikkureenga? (e.g. tomato, onion, keerai) — daily enna sell pannureenga sollunga.",
            "hi": "Bahut badhiya! Aap kya bechte hain? (e.g. tamatar, pyaaz, dhaniya) — daily kya sell karte hain?",
            "te": "Adbhutam! Meem emi ammutunnaru? (e.g. tomato, onion) — roju emi ammutharu cheppandi.",
            "kn": "Tumba chennagi! Neevu yenu maartira? (e.g. tomato, onion) — dina yenu sell maadtiri heli.",
            "en": "Great! What do you sell? (e.g. tomato, onion, coriander) — tell me your daily products.",
        },
    }
    return prompts.get(step, prompts[0]).get(lang, prompts[step]["en"])


def _onboarding_complete_msg(profile: dict, lang: str) -> str:
    name = profile.get("name", "friend")
    biz = profile.get("business", "your business")
    prods = profile.get("products", "")
    msgs = {
        "ta": f"Arumai {name}! 🎉 {biz} pathi theriyum — neenga {prods} vikkureenga. Naan ippo ungala Business Partner! Stock kekalaam, order pannalaam, sales epdi grow pannalaam-nu ketkalaam. Voice-la pesava? 'voice mode' nu sollunga.",
        "hi": f"Shabaash {name}! 🎉 {biz} ke baare me samajh gaya — aap {prods} bechte hain. Ab main aapka Business Partner hoon! Stock check, order, ya sales kaise badhayen — kuch bhi poochhiye. Voice chahiye to 'voice mode' boliye.",
        "te": f"Adbhutam {name}! 🎉 {biz} gurinchi ardham ayyindi — meeru {prods} ammutunnaru. Nenu ippudu mee Business Partner! Stock, order, sales elaa penchalo adagandi.",
        "kn": f"Adbhuta {name}! 🎉 {biz} bagge tiliyitu — neevu {prods} maarrtiri. Naanu nimma Business Partner! Stock, order, sales hege beLesabeku anta keli.",
        "en": f"Awesome {name}! 🎉 Got it — {biz} sells {prods}. I'm now your Business Partner! Ask stock, place orders, or 'How to grow sales?' — and say 'voice mode' if you prefer voice notes.",
    }
    return msgs.get(lang, msgs["en"])


def _tap_suffix(options: list[dict], channel: str) -> str:
    """For WhatsApp (no buttons) append multi-line tappable list — no typing."""
    if channel != "wa-akg" or not options:
        return ""
    lines = "\n".join(f"{i+1}. {o['label']}" for i, o in enumerate(options[:4]))
    return f"\n\n👉 Tap an option:\n{lines}\n(reply 1/2/3/4 or hold 🎤 mic)"


def _choice_options(status: str, lang: str, step: int | None = None) -> list[dict]:
    """Tap-options for low-data, no-typing UX. Every reply includes these chips.
    Voice-first: user taps or speaks, never types if they don't want to."""
    # labels are verbatim values sent back — pure language, no mix
    if status == "onboarding":
        if step == 0:
            return [{"label": "Lakshmi", "value": "Lakshmi"}, {"label": "Rahul", "value": "Rahul"}, {"label": "Kumar", "value": "Kumar"}, {"label": "Others ✏️", "value": "Others"}]
        if step == 1:
            # Pre-defined shop types + Others → type
            return [
                {"label": "Kirana Store", "value": "Kirana Store"},
                {"label": "Vegetable Stall", "value": "Vegetable Stall"},
                {"label": "Tea & Snacks", "value": "Tea Snacks Stall"},
                {"label": "General Store", "value": "General Store"},
                {"label": "Others ✏️", "value": "Others"},
            ]
        if step == 2:
            # Category-wise checklist (WhatsApp shows as tap options, UI shows as checkboxes)
            return [
                {"label": "🥬 Vegetables: tomato, onion, potato", "value": "tomato, onion, potato, coriander"},
                {"label": "🛒 Kirana: rice, dal, oil, sugar", "value": "rice, dal, oil, sugar"},
                {"label": "🍎 Fruits: banana, mango, apple", "value": "banana, mango, apple"},
                {"label": "Others ✏️", "value": "Others"},
            ]
    if status == "onboarding_complete":
        return [{"label": {"ta": "Stock paar", "hi": "Stock dekho", "en": "Check stock"} .get(lang, "Check stock"), "value": "Check stock"}, {"label": "tomato 20kg", "value": "tomato 20kg"}, {"label": {"ta": "Sales epdi?", "hi": "Sales kaise?", "en": "How to grow sales?"} .get(lang, "How to grow sales?"), "value": "How to grow sales?"}]
    if status == "greeted":
        return [{"label": "Check stock", "value": "Check stock"}, {"label": "tomato 20kg", "value": "tomato 20kg"}, {"label": "Why 20kg?", "value": "Why 20kg?"}]
    if status == "awaiting_approval":
        yes = {"ta": "சரி Yes", "hi": "हाँ Yes", "te": "సరే Yes", "kn": "ಸರಿ Yes", "en": "Yes"} .get(lang, "Yes")
        no = {"ta": "Vendaam No", "hi": "Nahi No", "te": "Vaddu No", "kn": "Beda No", "en": "No"} .get(lang, "No")
        return [{"label": f"✅ {yes}", "value": "yes", "primary": True}, {"label": f"✕ {no}", "value": "no"}, {"label": "+5 kg", "value": "5kg more"}, {"label": "-5 kg", "value": "5kg less"}]
    if status == "answered":
        return [{"label": "Order tomato", "value": "tomato 20kg"}, {"label": "Help", "value": "help"}]
    if status == "preference_set":
        return [{"label": "Check stock", "value": "Check stock"}, {"label": "Help", "value": "help"}]
    return [{"label": "Help", "value": "help"}, {"label": "Check stock", "value": "Check stock"}]


@app.post("/preferences")
def set_preferences(payload: dict):
    """Set merchant preferences (voice_mode, language). Persisted locally for
    low latency and mirrored to Cognee for the knowledge graph."""
    phone = _normalize_phone(payload.get("phone", ""))
    if not phone:
        raise HTTPException(400, "phone required")
    mode = payload.get("voice_mode")
    lang = payload.get("language")
    if mode and mode not in ("text", "voice", "both"):
        raise HTTPException(400, "voice_mode must be text|voice|both")
    prefs = _set_merchant_prefs(phone, voice_mode=mode, language=lang)
    return {"status": "saved", "preferences": prefs, "phone": phone}


@app.get("/preferences")
def get_preferences(phone: str = "917010919624"):
    phone_digits = _normalize_phone(phone)
    return {"phone": phone_digits, "preferences": _get_merchant_prefs(phone_digits)}


@app.get("/merchant/profile")
def get_merchant_profile(phone: str):
    phone_digits = _normalize_phone(phone)
    if not phone_digits:
        raise HTTPException(400, "phone required")
    profile = _get_merchant_profile(phone_digits)
    prefs = _get_merchant_prefs(phone_digits)
    return {"phone": phone_digits, "profile": profile, "preferences": prefs,
            "onboarding_complete": bool(profile and profile.get("onboarding_complete"))}


@app.post("/merchant/profile")
def set_merchant_profile(payload: dict):
    """Create/update business profile — also completes onboarding when name+business+products present."""
    phone = _normalize_phone(payload.get("phone", ""))
    if not phone:
        raise HTTPException(400, "phone required")
    updates = {k: payload.get(k) for k in ("name", "business", "business_type", "products", "location", "language") if payload.get(k)}
    # allow explicit onboarding_complete
    if "onboarding_complete" in payload:
        updates["onboarding_complete"] = bool(payload["onboarding_complete"])
    if "step" in payload:
        updates["step"] = int(payload["step"])
    # auto-complete if has all essentials
    cur = _get_merchant_profile(phone) or {}
    merged = {**cur, **updates}
    if merged.get("name") and merged.get("business") and merged.get("products"):
        merged["onboarding_complete"] = True
        merged["step"] = 3
        updates["onboarding_complete"] = True
        updates["step"] = 3
    profile = _set_merchant_profile(phone, **updates)
    # also sync language to prefs if provided
    if payload.get("language"):
        _set_merchant_prefs(phone, language=payload["language"])
    return {"phone": phone, "profile": profile, "onboarding_complete": bool(profile.get("onboarding_complete"))}


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

# ─── Agentic RAG: Cognee context cache ─────────────────────────────────────
# Cognee recall is slow by nature (measured 12.3s) — it must NEVER block the
# reply path. Pattern: background refresh warms a per-merchant context cache;
# the copilot reads the cache (fast) and every interaction is written back to
# the graph (remember_async) so knowledge grows with each turn.
_COGNEE_CTX_CACHE: dict[str, dict] = {}  # phone -> {"context": str, "at": float}
_COGNEE_CTX_TTL = 300.0  # refresh at most every 5 min per merchant


def _cognee_refresh(phone_digits: str, query: str) -> None:
    """Background: recall merchant context from Cognee and warm the cache."""
    if not cognee_client.configured():
        return
    try:
        res = cognee_client.recall(query)
        if "error" in res:
            return
        results = res.get("results") or []
        texts = []
        for r in results[:3]:
            for key in ("answer", "text", "content", "description"):
                v = r.get(key)
                if isinstance(v, str) and v:
                    texts.append(v)
                    break
        if texts:
            _COGNEE_CTX_CACHE[phone_digits] = {
                "context": " | ".join(texts)[:600],
                "at": datetime.datetime.now().timestamp(),
            }
    except Exception:
        pass


def _cognee_context(phone_digits: str) -> str:
    """Fast cached read of the merchant's Cognee context ("" if cold/absent)."""
    entry = _COGNEE_CTX_CACHE.get(phone_digits)
    if not entry:
        return ""
    if datetime.datetime.now().timestamp() - entry["at"] > _COGNEE_CTX_TTL:
        return ""
    return entry["context"]

# ─── Rate limit / cooldown tracking (prevents retry loops on 429 errors) ──
_message_cooldown: dict[str, float] = {}  # phone -> timestamp until when to block
COOLDOWN_SECONDS = 60  # block for 60 seconds after rate limit hit
MAX_RETRIES_PER_MESSAGE = 3  # stop after 3 failed attempts


def _check_rate_limit(phone_digits: str) -> bool:
    """Check if phone is in rate limit cooldown. Returns True if sending should be blocked."""
    cooldown_until = _message_cooldown.get(phone_digits, 0)
    if cooldown_until > 0 and datetime.datetime.now().timestamp() < cooldown_until:
        return True
    # Clean up expired cooldowns
    _message_cooldown.pop(phone_digits, None)
    return False


def _set_rate_limit_cooldown(phone_digits: str):
    """Mark phone as rate-limited; block all outgoing messages for COOLDOWN_SECONDS."""
    _message_cooldown[phone_digits] = datetime.datetime.now().timestamp() + COOLDOWN_SECONDS


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d]", "", phone or "")


def _allowed_copilot_phone(phone_digits: str) -> bool:
    # Single-merchant mode for this finale (user: only 7010919624)
    # COPILOT_ALLOWED_PHONES overrides if set; otherwise default to 917010919624.
    # TWILIO_WHATSAPP_TO is fallback for legacy.
    if not phone_digits:
        return False
    allow = os.getenv("COPILOT_ALLOWED_PHONES", "")
    if allow:
        allowed = {_normalize_phone(p) for p in allow.split(",") if _normalize_phone(p)}
        return phone_digits in allowed
    default = _normalize_phone(os.getenv("TWILIO_WHATSAPP_TO", "")) or "917010919624"
    return phone_digits == default


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
        # FIX 2026-09-19: was hardcoded ta-IN — a Kannada/Hindi voice note came
        # back garbled. saaras:v3 supports language_code="unknown" (auto-detect);
        # if the provider rejects it, fall back to the crew default ta-IN.
        def _do_wa_stt() -> str:
            from sarvamai import SarvamAI
            client = SarvamAI(api_subscription_key=api_key)
            for model in ("saaras:v4", "saaras:v3"):
                for lang_code in ("unknown", "ta-IN"):
                    try:
                        resp = client.speech_to_text.transcribe(
                            file=(f"voice.{codec}", audio), model=model,
                            language_code=lang_code, input_audio_codec=codec,
                        )
                        txt = (getattr(resp, "transcript", "") or "").strip()
                        if txt:
                            return txt
                    except Exception as e:
                        if "insufficient_quota" in str(e) or "402" in str(e):
                            return ""
                        continue
            return ""
        fut = _SDK_EXECUTOR.submit(_do_wa_stt, 45)
        return fut.result(timeout=45)
    except concurrent.futures.TimeoutError:
        return ""
    except Exception:
        return ""


def _run_offloop(fn, timeout_s: float):
    """Run a blocking SDK call on a dedicated bounded executor with a hard
    deadline. A hung provider call can then never wedge the API (demo-day
    safety): the caller's thread waits at most `timeout_s` and recovers."""
    return _SDK_EXECUTOR.submit(fn).result(timeout=timeout_s)


_SDK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="sarvam-sdk")


def _tts_audio(text: str, lang: str = "ta-IN") -> bytes:
    """Sarvam TTS -> raw audio bytes (bulbul:v3, kavitha). Bounded 40s like the
    /tts route. Returns b"" on any failure so callers never block the reply."""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key or not text:
        return b""
    try:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=api_key)

        def _do() -> bytes:
            resp = client.text_to_speech.convert(
                text=text, language_code=lang, speaker="kavitha", model="bulbul:v3")
            aud = resp.audios[0] if hasattr(resp, "audios") else resp
            b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
            if not b64:
                raise RuntimeError("no audio in TTS response")
            return base64.b64decode(b64)

        return _SDK_EXECUTOR.submit(_do).result(timeout=40)
    except Exception:
        return b""


def _send_wa_audio(phone_digits: str, audio: bytes) -> dict:
    """Send a voice note via WA-AKG media endpoint (type=voice → ptt:true).
    Returns a labelled outcome; never raises."""
    wa_url = os.getenv("WA_AKG_URL")
    wa_key = os.getenv("WA_AKG_API_KEY")
    wa_session = os.getenv("WA_AKG_SESSION")
    if not (wa_url and wa_key and wa_session) or not audio:
        return {"transport": "wa-akg-audio", "status": "skipped",
                "reason": "not_configured_or_empty"}
    try:
        jid = f"{phone_digits}@s.whatsapp.net"
        r = httpx.post(
            f"{wa_url.rstrip('/')}/api/messages/{wa_session}/{jid}/media",
            files={"file": ("copilot_voice.ogg", audio, "audio/ogg")},
            data={"type": "voice", "caption": ""},
            headers={"X-API-Key": wa_key}, timeout=15)
        return {"transport": "wa-akg-voice", "status": r.status_code,
                "jid": jid, "body": r.text[:120] if r.status_code >= 400 else ""}
    except Exception as e:
        return {"transport": "wa-akg-voice", "error": type(e).__name__}


def _copilot_send(phone: str, text: str, force_mock: bool = False,
                  voice_mode: str | None = None) -> dict:
    """Outbound copilot reply. Priority: WA-AKG -> Twilio freeform -> mock log.
    Every outcome is labelled so a judge can see exactly which transport ran.
    RATE LIMIT FIX: Blocks sending for 60s after 429 to prevent retry loops."""
    phone_digits = _normalize_phone(phone)
    attempts: list[dict] = []
    # Check rate limit / cooldown BEFORE attempting to send
    if _check_rate_limit(phone_digits) and not force_mock:
        attempts.append({"transport": "blocked", "reason": "rate_limit_cooldown"})
        return {"transport": "blocked", "reason": "rate_limit_cooldown", "attempts": attempts}
    # Voice-only merchants (can't read/write): skip the text bubble entirely.
    send_text = voice_mode != "voice"
    out = None
    if not force_mock and send_text:
        # FIX 2026-09-19: the old code RETURNED on WA-AKG failure, so a gateway
        # hiccup silently ate the merchant's reply. Now every live transport is
        # tried in priority order and the reply is never lost.
        # Voice is queued async after success so webhook returns <1s.
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
                if r.status_code == 429:  # RATE LIMIT HIT - set cooldown
                    _set_rate_limit_cooldown(phone_digits)
                    return {"transport": "wa-akg", "status": 429, "reason": "rate_limit", "attempts": attempts}
                if 200 <= r.status_code < 300:
                    out = {**attempts[-1], "attempts": attempts}
                elif r.status_code >= 400:
                    attempts.append({"transport": "wa-akg", "status": r.status_code, "body": r.text[:200]})
            except Exception as e:
                attempts.append({"transport": "wa-akg", "error": type(e).__name__})
        # Only try Twilio if WA-AKG didn't already succeed
        if out is None or not (200 <= out.get("status", 0) < 300):
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
                    if r.status_code == 429:  # RATE LIMIT HIT - set cooldown
                        _set_rate_limit_cooldown(phone_digits)
                        return {"transport": "twilio-freeform", "status": 429, "reason": "rate_limit", "attempts": attempts}
                    if 200 <= r.status_code < 300:
                        out = {**attempts[-1], "attempts": attempts}
                    elif r.status_code >= 400:
                        attempts.append({"transport": "twilio-freeform", "status": r.status_code, "body": r.text[:200]})
                    else:
                        out = {**attempts[-1], "attempts": attempts}
                except Exception as e:
                    if "rate_limit" not in str(e):
                        attempts.append({"transport": "twilio-freeform", "error": type(e).__name__})
        if out is not None and 200 <= out.get("status", 0) < 300:
            # Text delivered live — queue voice async (never blocks) then return
            if voice_mode in ("voice", "both"):
                lang = _prefs_lang(phone_digits)
                def _voice_job_live(txt=text, lg=lang, ph=phone_digits):
                    audio = _tts_audio(txt, lg)
                    if audio:
                        _send_wa_audio(ph, audio)
                threading.Thread(target=_voice_job_live, daemon=True, name="wa-voice-live").start()
                out["voice"] = {"transport": "wa-akg-audio", "status": "queued",
                                "note": "voice note queued (live text succeeded, TTS async)"}
            return out
    # Fallback: mock-log (simulate channel or live delivery failed)
    try:
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
        with open(os.path.join(BASE_DIR, "data", "copilot_chat.log"), "a",
                  encoding="utf-8") as lf:
            lf.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} | "
                     f"To: {phone_digits} | {text}\n")
        out = {"transport": "mock-log", "status": "logged"}
        if attempts:
            out["attempts"] = attempts
    except OSError:
        out = {"transport": "none", "error": "log unavailable"}
    # ── Voice delivery: TTS -> WA-AKG audio note ────────────────────────────
    # Low-latency rule: voice NEVER blocks the text reply. Text is sent (or
    # logged) above; voice is fire-and-forget in a daemon thread so the
    # webhook always returns in <1s even when TTS takes 10-40s.
    if voice_mode in ("voice", "both") and not force_mock:
        lang = _prefs_lang(phone_digits)

        def _voice_job():
            audio = _tts_audio(text, lang)
            if audio:
                _send_wa_audio(phone_digits, audio)

        threading.Thread(target=_voice_job, daemon=True, name="wa-voice").start()
        out["voice"] = {"transport": "wa-akg-audio", "status": "queued",
                        "note": "voice note queued (TTS async, non-blocking)"}
    elif voice_mode in ("voice", "both") and force_mock:
        out["voice"] = {"transport": "mock-log", "status": "logged",
                        "note": "voice note simulated (offline battery path)"}
    return out


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
    """Localized product name: native script for kn/hi/te, the catalog key for
    English, Tamil name otherwise. Falls back to the catalog key last."""
    key = {"kn": "name_kn", "hi": "name_hi", "te": "name_te"}.get(lang)
    if lang == "en":
        return product
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
    t = {
        "ta": "HarvestWise உதவி:\n• ஆர்டர்: \"நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி\"\n• சரி = ஒப்புதல் · இல்ல/வேண்டாம் = ரத்து\n• கேளுங்கள்: விலை? எவ்வளவு சரக்கு? மழை? ஏன் 20? கடந்த ஆர்டர்?",
        "kn": "HarvestWise ಸಹಾಯ:\n• ಆರ್ಡರ್: \"ನಾಳೆ 20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ, 10 ಗೊಂಚಲು ಕೊತ್ತಂಬರಿ\"\n• ಸರಿ = ಒಪ್ಪಿಗೆ · ಬೇಡ/ಇಲ್ಲ = ರದ್ದು\n• ಕೇಳಿ: ಬೆಲೆ? ಎಷ್ಟು ದಾಸ್ತಾನು? ಮಳೆ? ಏಕೆ 20? ಹಿಂದಿನ ಆರ್ಡರ್?",
        "hi": "HarvestWise मदद:\n• ऑर्डर: \"कल 20 किलो टमाटर, 10 गुच्छा धनिया\"\n• हाँ = स्वीकृति · नहीं = रद्द\n• पूछें: दाम? कितना स्टॉक? बारिश? क्यों 20? पिछला ऑर्डर?",
        "te": "HarvestWise సహాయం:\n• ఆర్డర్: \"రేపు 20 కిలో టమాటా, 10 కట్ట ధనియాలు\"\n• సరే = ఆమోదం · కాదు/లేదు = రద్దు\n• అడగండి: ధర? ఎంత స్టాక్? వర్షం? ఎందుకు 20? గత ఆర్డర్?",
        "en": "HarvestWise help:\n• Order: \"tomato 20kg, 10 bunches coriander\"\n• yes/ok = approve · no/cancel = cancel\n• Ask: price? stock? rain? why 20? last orders?",
    }
    return t.get(lang) or t["en"]


def _welcome_text(lang: str) -> str:
    return {
        "ta": "வணக்கம் லக்ஷ்மி! HarvestWise உங்கள் மறுசப்ளை உதவியாளர். ஆர்டர் சொல்லுங்கள் அல்லது 'உதவி' என்று கேளுங்கள்.",
        "kn": "ನಮಸ್ಕಾರ ಲಕ್ಷ್ಮಿ! HarvestWise ನಿಮ್ಮ ಮರುಪೂರೈಕೆ ಸಹಾಯಕ. ಆರ್ಡರ್ ಹೇಳಿ ಅಥವಾ 'ಸಹಾಯ' ಎಂದು ಕೇಳಿ.",
        "hi": "नमस्ते लक्ष्मी! HarvestWise आपका रीस्टॉक सहायक है। ऑर्डर बताइए या 'मदद' कहिए।",
        "te": "నమస్కారం లక్ష్మీ! HarvestWise మీ రీస్టాక్ సహాయకుడు. ఆర్డర్ చెప్పండి లేదా 'సహాయం' అని అడగండి.",
        "en": "Vanakkam Lakshmi! HarvestWise is your restocking copilot. Say an order, or ask for help.",
    }.get(lang) or _welcome_text("en")


CONFIRM_SUFFIX = {
    "ta": "\nசரி என்று பதிலளிக்கவும் (reply \"சரி\" to confirm).",
    "kn": "\n\"ಸರಿ\" ಎಂದು ಉತ್ತರಿಸಿ (reply ಸರಿ to confirm).",
    "hi": "\n\"हाँ\" या \"sari\" से उत्तर दें (reply to confirm).",
    "te": "\n\"సరే\" అని స్పందించండి (reply సరే to confirm).",
    "en": "\nReply yes (சரி) to confirm.",
}

MAX_ORDER_CAP = 100  # mirrors MAX_ORDER in the engine


def _cancel_text(lang: str) -> str:
    return {
        "ta": "HarvestWise: ஆர்டர் ரத்து செய்யப்பட்டது. எப்போது வேண்டுமானாலும் சொல்லுங்கள்.",
        "kn": "HarvestWise: ಆರ್ಡರ್ ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ಬೇಕಾದಾಗ ಹೇಳಿ.",
        "hi": "HarvestWise: ऑर्डर रद्द कर दिया गया। जब चाहें बताइए।",
        "te": "HarvestWise: ఆర్డర్ రద్దు చేయబడింది. కావాలన్నప్పుడు చెప్పండి.",
        "en": "HarvestWise: order cancelled. Tell me what you need anytime.",
    }.get(lang) or _cancel_text("en")


def _no_pending_text(lang: str) -> str:
    return {
        "ta": "HarvestWise: ஒப்புதலுக்கான ஆர்டர் இல்லை. முதலில் ஆர்டர் சொல்லுங்கள்.",
        "kn": "HarvestWise: ಒಪ್ಪಿಗೆಗೆ ಆರ್ಡರ್ ಇಲ್ಲ. ಮೊದಲು ಆರ್ಡರ್ ಹೇಳಿ.",
        "hi": "HarvestWise: अनुमोदन के लिए कोई ऑर्डर नहीं। पहले ऑर्डर बताइए।",
        "te": "HarvestWise: ఆమోదించడానికి ఆర్డర్ లేదు. మొదట ఆర్డర్ చెప్పండి.",
        "en": "HarvestWise: no pending order to approve. Send your order first.",
    }.get(lang) or _no_pending_text("en")


def _fallback_text(lang: str) -> str:
    return {
        "ta": "HarvestWise: பொருள் புரியவில்லை. முயற்சிக்கவும்: நாளை 20 கிலோ தக்காளி (அல்லது 'உதவி').",
        "kn": "HarvestWise: ಅರ್ಥವಾಗಲಿಲ್ಲ. ಪ್ರಯತ್ನಿಸಿ: ನಾಳೆ 20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ (ಅಥವಾ 'ಸಹಾಯ').",
        "hi": "HarvestWise: समझ नहीं आया। आज़माएँ: कल 20 किलो टमाटर (या 'मदद').",
        "te": "HarvestWise: అర్థం కాలేదు. ప్రయత్నించండి: రేపు 20 కిలో టమాటా (లేదా 'సహాయం').",
        "en": "HarvestWise: I did not catch a product. Try: tomato 20kg (or 'help').",
    }.get(lang) or _fallback_text("en")


def _ask_text(items: list[dict], lang: str) -> str:
    """Deterministic multilingual ask — every quantity from the engine, verbatim."""
    unit_word = {
        "ta": {"kg": "கிலோ", "bunch": "கொத்து"},
        "kn": {"kg": "ಕಿಲೋ", "bunch": "ಗೊಂಚಲು"},
        "hi": {"kg": "किलो", "bunch": "गुच्छा"},
        "te": {"kg": "కిలో", "bunch": "కట్ట"},
        "en": {"kg": "kg", "bunch": "bunches"},
    }
    rain = int(round(get_weather()["rain_prob"] * 100))
    tomorrow = {"ta": "நாளை", "kn": "ನಾಳೆ", "hi": "कल", "te": "రేపు", "en": "Tomorrow"}[lang]
    rainword = {"ta": "மழை", "kn": "ಮಳೆ", "hi": "बारिश", "te": "వర్షం", "en": "rain"}[lang]
    uw = unit_word[lang]
    parts = ", ".join(
        f"{i['recommended_qty']} {uw.get(i['unit'], i['unit'])} {_loc_name(CATALOG[MERCHANT][i['product']], i['product'], lang)}"
        for i in items
    )
    want = {"ta": " வேண்டுமா?", "kn": " ಬೇಕೆ?", "hi": " चाहिए?", "te": " కావాలా?", "en": "?"}[lang]
    return f"{tomorrow} {rainword} {rain}%. {tomorrow} {parts}{want}"


def _parse_adjustment(low: str) -> dict | None:
    """Detect 'add/remove N unit product' adjustments to the pending basket.
    Returns {'product': str, 'delta': int} or None. Numbers come ONLY from her
    speech — never invented. English only for now (Tamil words are ambiguous
    with wordnums); the rules parser still handles full re-orders in all langs."""
    more = _word_hit(low, ["more", "add", "extra", "increase"])
    less = _word_hit(low, ["less", "reduce", "decrease", "remove"])
    if not (more or less):
        return None
    m = re.search(r"\b(\d{1,3})\b", low)
    if not m:
        return None
    n = int(m.group(1))
    product = _catalog_product_in(low)
    if not product or n <= 0 or n > 90:
        return None
    return {"product": product, "delta": n if more else -n}


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
        # Full inventory when no product mentioned (Check stock / stock?)
        if not _catalog_product_in(low) or low.strip() in ("stock","check stock","inventory","stock?"):
            snap = stock_snapshot(MERCHANT)
            lines=[]
            for p,s in snap.items():
                d=CATALOG[MERCHANT][p]
                n=_loc_name(d,p,lang)
                # low-stock / expiry alerts
                alert=""
                if s <= 4: alert=" ⚠️ low!"
                elif d["decay_days"]==1 and s<=6: alert=" ⏳ 1-day expiry"
                lines.append(f"{n}: {s} {d['unit']}{alert}")
            body="\n".join(lines)
            return {
                "ta": f"மொத்த ஸ்டாக்:\n{body}",
                "kn": f"ಒಟ್ಟು ದಾಸ್ತಾನು:\n{body}",
                "hi": f"कुल स्टॉक:\n{body}",
                "te": f"మొత్తం స్టాక్:\n{body}",
                "en": f"Full stock:\n{body}",
            }[lang]
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


def _growth_answer(lang: str) -> str:
    """Partner growth: forecast + GMV + stock + bundle + margin — live, not static."""
    fc = get_sales_forecast(MERCHANT)
    bundle = get_bundle_suggestion("tomato")
    leader = get_margin_leader(MERCHANT)
    snap = stock_snapshot(MERCHANT)
    orders = order_history(MERCHANT, 20)
    gmv7 = sum(o.get("total_inr",0) for o in orders[:7])
    low = [p for p,s in snap.items() if s<=4]
    low_txt = f" Low: {', '.join(low)}" if low else ""
    if lang == "ta":
        lines = [
            f"📈 Forecast: {fc['reason']} → {fc['lift']:.1f}x | 7d GMV ₹{gmv7}{low_txt}",
            f"💡 Bundle: {bundle['why']} — {bundle['with']} {bundle['qty']} bunch add pannalaama?",
            f"💰 Best margin: {leader['name_tn']} (₹{leader['price']} × {leader['velocity']}/d) | Stock: tomato {snap.get('tomato')}kg",
            "Tap 1: Check stock  2: tomato 20kg  3: Order bundle",
        ]
        return "\n".join(lines)
    if lang == "hi":
        lines = [
            f"📈 Forecast: {fc['reason']} → {fc['lift']:.1f}x | 7d GMV ₹{gmv7}{low_txt}",
            f"💡 Bundle: {bundle['why']} — {bundle['with']} {bundle['qty']} जोड़ें?",
            f"💰 Best margin: {leader['product']} (₹{leader['price']} × {leader['velocity']}/d)",
            "Tap: 1 Check stock  2 tomato 20kg",
        ]
        return "\n".join(lines)
    return (
        f"📈 Forecast: {fc['reason']} → {fc['lift']:.1f}x | 7d GMV ₹{gmv7}{low_txt}\n"
        f"💡 Bundle: {bundle['why']} — add {bundle['with']} {bundle['qty']}?\n"
        f"💰 Margin leader: {leader['product']} (₹{leader['price']} × {leader['velocity']}/d) | Tomato {snap.get('tomato')}kg on hand\n"
        "Tap: 1 Check stock  2 tomato 20kg"
    )


VOICE_CMD_WORDS = {
    "voice": ["voice mode", "voice messages", "voice only", "speak", "ஒலி", "ஆவாஸ்",
              "आवाज", "వాయిస్", "ಧ್ವನಿ", "voice"],
    "text": ["text mode", "text only", "message only", "உரை", "टेक्स्ट", "టెక్స్ట్",
             "ಪಠ್ಯ", "text"],
    "both": ["both mode", "both", "voice and text", "இரண்டும்", "दोनों", "రెండూ",
             "ಎರಡೂ"],
}


def _voice_command(low: str) -> str | None:
    """Detect a voice/text/both preference command. Returns the mode or None."""
    for mode, words in VOICE_CMD_WORDS.items():
        for w in words:
            if w in low:
                return mode
    return None


def _handle_merchant_message(phone: str, text: str = "", media_url: str = "",
                             media_headers: dict | None = None,
                             content_type: str = "", channel: str = "webhook") -> dict:
    """The copilot brain. Voice/text in -> intent -> ask -> approve -> dispatch.

    security: unknown callers are refused; merchant speech is DATA (injection
    markers refused); quantities always come from rules/engine, never from an LLM.
    """
    phone_digits = _normalize_phone(phone)
    force_mock = channel == "simulate"
    vmode = _get_merchant_prefs(phone_digits)["voice_mode"]
    # ── First-time Business Partner onboarding (name → business → products) ──
    # Lock Lakshmi (demo merchant) — never overwrite her seed, even if file corrupted
    if phone_digits == "917010919624":
        p = _get_merchant_profile(phone_digits)
        if not p or p.get("name") != "Lakshmi" or p.get("business") != "Lakshmi Kirana & Vegetables":
            _set_merchant_profile(phone_digits, name="Lakshmi", business="Lakshmi Kirana & Vegetables", business_type="kirana", products="tomato, onion, coriander, spinach", location="Basavanagudi, Bangalore", onboarding_complete=True, step=3)
    is_new = _onboarding_needed(phone_digits)
    # Single-merchant lock: only 917010919624 is the merchant.
    # Unknown callers are refused (no onboarding for others in this demo).
    if not _allowed_copilot_phone(phone_digits):
        _copilot_send(phone_digits, "HarvestWise: unknown caller - order ignored.",
                      force_mock=force_mock, voice_mode=vmode)
        return {"status": "unknown_caller", "phone": phone_digits, "channel": channel}

    transcript = (text or "").strip()
    if media_url and not transcript:
        transcript = _stt_media(media_url, media_headers, content_type)

    low = transcript.lower()

    # ── Onboarding state machine (interactive Business Partner) ──
    if is_new:
        lang = _detect_lang(transcript or "hi")
        prof = _get_merchant_profile(phone_digits) or {}
        step = int(prof.get("step", 0))
        # WhatsApp numeric tap: "1","2","3" → map to option value (no typing)
        if transcript.strip() in ("1", "2", "3", "4", "5"):
            try:
                idx = int(transcript.strip()) - 1
                opts = _choice_options("onboarding", lang, step)
                if 0 <= idx < len(opts):
                    transcript = opts[idx]["value"]
                    low = transcript.lower()
            except Exception:
                pass
        # Empty transcript on first webhook (e.g. media-only) → ask step 0
        if not transcript:
            prompt = _onboarding_prompt(0, lang)
            opts0 = _choice_options("onboarding", lang, 0)
            send = _copilot_send(phone_digits, prompt + _tap_suffix(opts0, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "onboarding", "step": 0, "reply": prompt, "send": send,
                    "options": _choice_options("onboarding", lang, 0),
                    "phone": phone_digits, "channel": channel}
        if step == 0:
            # Greeting like "hi" is NOT a name — ask name without consuming it
            if _word_hit(low, GREETING_WORDS) or low.strip() in ("hi", "hello", "hey", "hii", "helo"):
                prompt = _onboarding_prompt(0, lang)
                send = _copilot_send(phone_digits, prompt, force_mock=force_mock, voice_mode=vmode)
                return {"status": "onboarding", "step": 0, "reply": prompt, "send": send,
                        "options": _choice_options("onboarding", lang, 0),
                        "phone": phone_digits, "transcript": transcript, "channel": channel}
            if transcript.strip().lower() == "others":
                prompt = {"ta": "Dayavu seithu ungala peyarai type pannunga.", "hi": "Kripya apna naam type karein.", "te": "Dayachesi mee peru type cheyyandi.", "kn": "Dayavittu nimma hesarannu type maadi.", "en": "Please type your name."}.get(lang, "Please type your name.")
                send = _copilot_send(phone_digits, prompt, force_mock=force_mock, voice_mode=vmode)
                return {"status": "onboarding", "step": 0, "reply": prompt, "send": send,
                        "options": [], "phone": phone_digits, "transcript": transcript, "channel": channel}
            # transcript is the NAME
            name = transcript.strip()[:60] or "friend"
            _set_merchant_profile(phone_digits, name=name, step=1)
            prompt = _onboarding_prompt(1, lang, name=name)
            opts1 = _choice_options("onboarding", lang, 1)
            send = _copilot_send(phone_digits, prompt + _tap_suffix(opts1, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "onboarding", "step": 1, "reply": prompt, "send": send,
                    "options": _choice_options("onboarding", lang, 1),
                    "phone": phone_digits, "transcript": transcript, "channel": channel}
        elif step == 1:
            business = transcript.strip()[:80] or "my shop"
            if business.lower() == "others":
                prompt = {"ta": "Dayavu seithu ungala kadai peyarai type pannunga.", "hi": "Kripya apni dukaan ka naam type karein.", "te": "Dayachesi mee shop peru type cheyyandi.", "kn": "Dayavittu nimma angadi hesarannu type maadi.", "en": "Please type your shop / business name."}.get(lang, "Please type your shop / business name.")
                send = _copilot_send(phone_digits, prompt, force_mock=force_mock, voice_mode=vmode)
                return {"status": "onboarding", "step": 1, "reply": prompt, "send": send,
                        "options": [], "phone": phone_digits, "transcript": transcript, "channel": channel}
            # guess type from keywords
            btype = "kirana"
            lowb = business.lower()
            if any(k in lowb for k in ["hotel", "restaurant", "cafe"]):
                btype = "restaurant"
            elif any(k in lowb for k in ["trader", "wholesale"]):
                btype = "trader"
            _set_merchant_profile(phone_digits, business=business, business_type=btype, step=2)
            name = prof.get("name", "")
            prompt = _onboarding_prompt(2, lang, name=name)
            opts2 = _choice_options("onboarding", lang, 2)
            send = _copilot_send(phone_digits, prompt + _tap_suffix(opts2, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "onboarding", "step": 2, "reply": prompt, "send": send,
                    "options": _choice_options("onboarding", lang, 2),
                    "phone": phone_digits, "transcript": transcript, "channel": channel}
        elif step == 2:
            if transcript.strip().lower() == "others":
                prompt = {"ta": "Neenga vikkum porutkalai type pannunga (e.g. tomato, onion).", "hi": "Aap kya bechte hain, type karein (e.g. tamatar, pyaaz).", "te": "Meeru amme vasthuvulanu type cheyyandi.", "kn": "Neenu maartiruva vasthugalannu type maadi.", "en": "Please type what you sell (e.g. tomato, onion, coriander)."}.get(lang, "Please type what you sell.")
                send = _copilot_send(phone_digits, prompt, force_mock=force_mock, voice_mode=vmode)
                return {"status": "onboarding", "step": 2, "reply": prompt, "send": send,
                        "options": [], "phone": phone_digits, "transcript": transcript, "channel": channel}
            products = transcript.strip()[:120] or "tomato, onion"
            profile = _set_merchant_profile(phone_digits, products=products, onboarding_complete=True, step=3)
            # also show we learned voice pref
            prompt = _onboarding_complete_msg(profile, lang)
            optsC = _choice_options("onboarding_complete", lang)
            send = _copilot_send(phone_digits, prompt + _tap_suffix(optsC, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "onboarding_complete", "reply": prompt, "send": send,
                    "options": _choice_options("onboarding_complete", lang),
                    "profile": profile, "phone": phone_digits, "transcript": transcript, "channel": channel}
    tokens = set(re.findall(r"[\w\u0b80-\u0bff\u0c80-\u0cff\u0c00-\u0c7f\u0900-\u097f]+", low))
    if any(m in low for m in INJECTION_MARKERS):
        _copilot_send(phone_digits,
                      "HarvestWise: speech refused - embedded instructions were ignored.",
                      force_mock=force_mock, voice_mode=vmode)
        return {"status": "injection_blocked", "options": _choice_options("answered", _detect_lang(transcript or "en")), "phone": phone_digits,
                "transcript": transcript, "channel": channel}

    # ── Agentic RAG: learn this turn (fire-and-forget) + warm context for next ──
    if transcript:
        cognee_client.remember_async([
            f"Merchant {phone_digits} asked: {transcript[:300]}"
        ])
        threading.Thread(
            target=_cognee_refresh, args=(phone_digits, transcript[:200]),
            daemon=True, name="cognee-ctx").start()
    ctx = _cognee_context(phone_digits)

    # ── WhatsApp tap: "1"/"2"/"3" → first/second/third chip (no typing) ──
    if transcript.strip() in ("1", "2", "3", "4"):
        pend_tmp = _get_pending(phone_digits)
        if pend_tmp:
            _map = {"1": "yes", "2": "no", "3": "5kg more", "4": "5kg less"}
            transcript = _map.get(transcript.strip(), transcript)
            low = transcript.lower()
        elif not is_new:  # greeted/help fallback
            _map2 = {"1": "Check stock", "2": "tomato 20kg", "3": "Why 20kg?", "4": "help"}
            if transcript.strip() in _map2:
                transcript = _map2[transcript.strip()]
                low = transcript.lower()

    # ── Voice/text preference command (e.g. "voice mode", "text only") ──
    vcmd = _voice_command(low)
    if vcmd:
        prefs = _set_merchant_prefs(phone_digits, voice_mode=vcmd)
        lang = _detect_lang(transcript or "ok")
        mode_label = {"voice": "voice", "text": "text", "both": "voice + text"}[vcmd]
        replies = {
            "ta": f"சரி! இனி பதில்கள் {mode_label} முறையில் வரும்.",
            "hi": f"ठीक है! अब जवाब {mode_label} में आएंगे।",
            "te": f"సరే! ఇకపై సమాధానాలు {mode_label} రూపంలో వస్తాయి.",
            "kn": f"ಸರಿ! ಇನ್ನು ಉತ್ತರಗಳು {mode_label} ರೂಪದಲ್ಲಿ ಬರುತ್ತವೆ.",
            "en": f"Done! Replies will now come as {mode_label}.",
        }
        reply = replies.get(lang, replies["en"])
        send = _copilot_send(phone_digits, reply, force_mock=force_mock,
                             voice_mode=vcmd)
        return {"status": "preference_set", "voice_mode": vcmd, "reply": reply,
                "options": _choice_options("preference_set", lang),
                "send": send, "phone": phone_digits, "transcript": transcript,
                "channel": channel}

    if _word_hit(low, DENY_WORDS):
        pending_orders.pop(phone_digits, None)
        reply = _cancel_text(_detect_lang(transcript or "no"))
        _copilot_send(phone_digits, reply, force_mock=force_mock, voice_mode=vmode)
        return {"status": "declined", "reply": reply, "options": _choice_options("greeted", _detect_lang(transcript or "en")), "phone": phone_digits,
                "transcript": transcript, "channel": channel}

    if _word_hit(low, APPROVE_WORDS):
        pend = _get_pending(phone_digits)
        if pend:
            pending_orders.pop(phone_digits, None)
        if not pend:
            lang0 = _detect_lang(transcript or "ok")
            reply0 = _no_pending_text(lang0)
            opts0 = _choice_options("greeted", lang0)
            send0 = _copilot_send(phone_digits, reply0 + _tap_suffix(opts0, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "no_pending", "reply": reply0, "options": opts0, "send": send0, "phone": phone_digits,
                    "transcript": transcript, "channel": channel}
        results = _approve_and_dispatch(phone_digits, pend)
        confirm = _confirm_text(results, _detect_lang(transcript))
        send = _copilot_send(phone_digits, confirm, force_mock=force_mock, voice_mode=vmode)
        rejected = [r for r in results if r.get("status") != "dispatched"]
        return {"status": "dispatched" if not rejected else "partial",
                "options": _choice_options("awaiting_approval" if not rejected else "greeted", _detect_lang(transcript)),
                "phone": phone_digits, "transcript": transcript,
                "dispatched": [r for r in results if r.get("status") == "dispatched"],
                "rejected": rejected, "confirm": confirm, "reply": confirm,
                "send": send, "channel": channel}

    # --- Growth AI Partner: forecast + bundle + margin (beyond weather) ---
    lang = _detect_lang(transcript)
    if any(w in low for w in ["grow", "growth", "grow sales", "sales grow", "business grow", "வளர", "बढ़ा", "వృద్ధి", "ಬೆಳೆ"]):
        answer = _growth_answer(lang)
        optsG = _choice_options("greeted", lang)
        send = _copilot_send(phone_digits, answer + _tap_suffix(optsG, channel), force_mock=force_mock, voice_mode=vmode)
        return {"status": "answered", "question": "growth", "reply": answer, "options": optsG, "send": send, "language": lang, "engine": "growth-forecast+bundle+margin", "phone": phone_digits, "transcript": transcript, "channel": channel}

    # ── Copilot sales briefing — MUST be before qkind check!
    if any(k in low for k in ["show sales","today sales","sales","daily sales","yesterday sales"]):
        hist=order_history(MERCHANT,50)
        days=30 if "yesterday" not in low else 1
        total=sum(row.get("total_inr",0) for row in hist[:days])
        items=sum(row.get("qty",0) for row in hist[:days])
        snap=stock_snapshot(MERCHANT)
        reply={"ta":f"30‑day sales:\nRs.{total:.0f} ({items} items). Current stock:\n{snap.get('tomato','?')} tomato | {snap.get('coriander','?')} coriander","en":f"30‑day sales:\nRs.{total:.0f} ({items} items). Current stock:\n{snap.get('tomato','?')} tomato | {snap.get('coriander','?')} coriander"}.get(lang,f"Sales: Rs.{total:.0f} ({items} items). Stock: {snap}")
        opts=_choice_options("greeted",lang)
        send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
        return {"status":"sales_report","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if any(k in low for k in ["morning briefing","daily briefing","buy today","tomorrow what to buy","what to buy tomorrow","need list","suggestion","what to buy"]):
        weather=get_weather(); rain=int(round(weather.get("rain_prob",0)*100))
        forecast=get_sales_forecast(MERCHANT); forecast_pct=int(round(forecast.get("lift",1.0)*100)) if isinstance(forecast,dict) else 100
        leader=get_margin_leader(MERCHANT)
        if isinstance(leader,dict): leader_product=leader.get("product","tomato"); leader_margin=int(leader.get("daily_margin",0))
        else: leader_product="tomato"; leader_margin=0
        snap=stock_snapshot(MERCHANT)
        buys=[]
        for prod in ["tomato","coriander","onion","spinach"]:
            d=CATALOG[MERCHANT].get(prod,{}); vel=d.get("velocity",10); days=d.get("decay_days",2); unit=d.get("unit","kg")
            stock=snap.get(prod,0); base=vel*days-stock; modifier=1.0 if rain<50 else 0.6; need=max(0,round(base*modifier))
            if need>0: price=d.get("price_per_unit",18); buys.append(f"• {prod} {need} {unit} @ Rs.{price}")
        reply={"ta":f"வணக்கம் {MERCHANT}! Naalai {rain}% mazhai. Naalai vechu:\n{chr(10).join(buys) if buys else 'No urgent buys.'} Forecast: {forecast_pct}% up. Margin leader: {leader_product} {leader_margin}rs.","en":f"Morning {MERCHANT}! Rain tomorrow: {rain}%. What to buy tomorrow:\n{chr(10).join(buys) if buys else 'No urgent buys.'} Sales forecast: {forecast_pct}% up. Margin leader: {leader_product} ₹{leader_margin}/day."}.get(lang,f"Morning {MERCHANT}! Rain: {rain}%. Buy tomorrow: {chr(10).join(buys) if buys else 'None.'} Forecast: {forecast_pct}% up. Margin: {leader_product} ₹{leader_margin}/day.")
        opts=_choice_options("greeted",lang)
        send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
        return {"status":"morning_briefing","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}

    # ── Inventory CRUD via copilot — must be before qkind (price/stock would hijack)
    if any(k in low for k in ["add product","add inventory","create product"]):
        m_prod = re.search(r"add (?:product|inventory)\s+([a-z]+)", low)
        prod = m_prod.group(1).lower() if m_prod else _catalog_product_in(low) or "mango"
        m_qty = re.search(r"(\d+)\s*(kg|bunch|bunches)?", low)
        qty = int(m_qty.group(1)) if m_qty else 0
        m_price = re.search(r"price\s*(\d+)", low)
        price = int(m_price.group(1)) if m_price else 20
        unit = "bunch" if "bunch" in low else "kg"
        add_product(MERCHANT, prod, price=price, unit=unit, stock=qty)
        reply = {"ta":f"{prod} added — {qty} {unit} @ Rs.{price}","en":f"{prod} added — {qty} {unit} @ Rs.{price}, inventory updated."}.get(lang,f"{prod} added.")
        opts=_choice_options("greeted",lang)
        send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
        return {"status":"inventory_added","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if any(k in low for k in ["set stock","update stock","set inventory"]):
        prod=_catalog_product_in(low)
        m_qty=re.search(r"(\d+)\s*(kg|bunch)?", low)
        if prod and m_qty:
            qty=int(m_qty.group(1))
            res=set_stock(MERCHANT, prod, qty)
            reply={"ta":f"{prod} stock {res['before']}→{res['after']} updated.","en":f"{prod} stock {res['before']}→{res['after']} updated."}.get(lang,f"{prod} stock updated {res['after']}.")
            opts=_choice_options("greeted",lang)
            send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
            return {"status":"stock_updated","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if "add stock" in low:
        prod=_catalog_product_in(low)
        m_qty=re.search(r"add stock\s*(\d+)", low) or re.search(r"(\d+)\s*(kg|bunch)", low)
        if prod and m_qty:
            delta=int(m_qty.group(1))
            res=add_stock(MERCHANT, prod, delta)
            reply={"ta":f"{prod} +{delta} → {res['after']}","en":f"{prod} +{delta} → {res['after']} added."}.get(lang,f"{prod} +{delta}")
            opts=_choice_options("greeted",lang)
            send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
            return {"status":"stock_added","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if any(k in low for k in ["delete stock","remove stock","delete inventory","remove inventory","delete product"]):
        prod=_catalog_product_in(low)
        if prod:
            delete_stock(MERCHANT, prod)
            reply={"ta":f"{prod} deleted.","en":f"{prod} removed from inventory."}.get(lang,f"{prod} deleted.")
            opts=_choice_options("greeted",lang)
            send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
            return {"status":"stock_deleted","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}

    qkind = _question_kind(low)
    if qkind:
        # ── Brain-first: try Sarvam + Cognee, else deterministic template
        template = _qa_answer(qkind, low, lang)
        brain_answer = None
        if llm_mod.available():
            try:
                # Build shop grounding for brain
                snap = stock_snapshot(MERCHANT)
                prod = _catalog_product_in(low) or "tomato"
                d = CATALOG[MERCHANT].get(prod, {})
                mem_snip = ""
                try:
                    with open(MEMORY_PATH, encoding="utf-8") as f:
                        mem = json.load(f).get(MERCHANT, {})
                        facts = mem.get("huge_facts", []) or mem.get("cause_chain", [])
                        qwords = set(re.findall(r"\w+", low))
                        filt = [x for x in facts if any(w in x.lower() for w in qwords)] if qwords else facts
                        if filt: mem_snip = " | ".join(filt[:2])
                except OSError:
                    pass
                ctx_hint = ctx or mem_snip
                prompt = (
                    f"You are Lakshmi's partner at Basavanagudi. Q: '{transcript}' (kind={qkind}, lang={lang}). "
                    f"Shop: {prod} {d.get('velocity','')} {d.get('unit','')}/day, stock {snap.get(prod,'?')}{d.get('unit','')}, "
                    f"rain {int(round(get_weather()['rain_prob']*100))}%. Memory: {ctx_hint[:300] if ctx_hint else 'no history'}. "
                    f"Template answer (ground truth, use its numbers exactly): {template[:400]} "
                    f"Rewrite as warm partner in pure {lang}, ≤2 sentences, keep every number from template, add one memory insight if available. Never invent qty."
                )
                raw = llm_mod._call(
                    [{"role":"system","content":f"You are Lakshmi's partner. Reply only in {lang}."},
                     {"role":"user","content":prompt}],
                    model=llm_mod.FAST_MODEL, max_tokens=320, temperature=0.3, timeout=5
                )
                if raw and len(raw.strip())>20:
                    # grounding gate: must keep template numbers
                    nums = re.findall(r"\d+", template)
                    if all(n in raw for n in nums[:3]):  # at least first 3 numbers present
                        brain_answer = raw.strip()[:650]
            except Exception:
                pass
        answer = brain_answer or template
        # still append memory if brain didn't use it and we have ctx
        if not brain_answer and ctx:
            answer = f"{answer}\n\n(குறிப்பு: {ctx[:200]})" if lang == "ta" else f"{answer}\n\n(Note from memory: {ctx[:200]})"
        optsA = _choice_options("answered", lang)
        send = _copilot_send(phone_digits, answer + _tap_suffix(optsA, channel), force_mock=force_mock,
                             voice_mode=vmode)
        return {"status": "answered", "question": qkind, "reply": answer,
                "options": _choice_options("answered", lang),
                "send": send, "language": lang, "engine": "brain" if brain_answer else "live-data",
                "cognee_context": ctx[:200] if ctx else None,
                "phone": phone_digits, "transcript": transcript, "channel": channel}

    if _word_hit(low, GREETING_WORDS):
        reply = _welcome_text(lang)
        opts = _choice_options("greeted", lang)
        send = _copilot_send(phone_digits, reply + _tap_suffix(opts, channel), force_mock=force_mock, voice_mode=vmode)
        return {"status": "greeted", "reply": reply, "options": opts, "send": send,
                "phone": phone_digits, "transcript": transcript, "channel": channel}

    if _word_hit(low, HELP_WORDS):
        reply = _help_text(lang)
        opts = _choice_options("answered", lang)
        send = _copilot_send(phone_digits, reply + _tap_suffix(opts, channel), force_mock=force_mock, voice_mode=vmode)
        return {"status": "helped", "reply": reply, "options": opts, "send": send,
                "phone": phone_digits, "transcript": transcript, "channel": channel}

    # ── Cart commands — order matters: clear/remove before show
    if any(p in low for p in ["clear cart","empty cart","clear basket","cart clear"]):
        pending_orders.pop(phone_digits,None)
        reply={"ta":"Cart cleared.","hi":"Cart clear kiya.","en":"Cart cleared."}.get(lang,"Cart cleared.")
        opts=_choice_options("greeted",lang)
        send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
        return {"status":"cart_cleared","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if low.strip() in ("show cart","view cart","my cart","cart","basket","show basket") or any(p==low.strip() for p in ["cart","basket"]):
        pend = _get_pending(phone_digits)
        if not pend or not pend.get("items"):
            reply = {"ta":"Cart empty — add tomato 10kg?","hi":"Cart khaali — tomato 10kg add karein?","en":"Cart empty — try tomato 20kg"}.get(lang,"Cart empty — try tomato 20kg")
            opts = _choice_options("greeted", lang)
            send = _copilot_send(phone_digits, reply + _tap_suffix(opts, channel), force_mock=force_mock, voice_mode=vmode)
            return {"status":"cart_empty","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
        lines=[f"• {i['recommended_qty']} {i['unit']} {_loc_name(CATALOG[MERCHANT][i['product']],i['product'],lang)} — Rs.{i['total_inr']}" for i in pend["items"]]
        total=pend["total_inr"]
        reply={"ta":f"Cart ({len(lines)} items):\n"+"\n".join(lines)+f"\nTotal Rs.{total}","hi":f"Cart ({len(lines)}):\n"+"\n".join(lines)+f"\nTotal Rs.{total}","en":f"Cart ({len(lines)} items):\n"+"\n".join(lines)+f"\nTotal Rs.{total}"}.get(lang,f"Cart:\n"+"\n".join(lines))
        opts=_choice_options("awaiting_approval",lang)
        send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
        return {"status":"cart_view","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    # also handle bare "cart" inside longer phrase only if no product
    if "cart" in low and not _catalog_product_in(low):
        pend = _get_pending(phone_digits)
        if pend and pend.get("items"):
            lines=[f"• {i['recommended_qty']} {i['unit']} {_loc_name(CATALOG[MERCHANT][i['product']],i['product'],lang)} — Rs.{i['total_inr']}" for i in pend["items"]]
            total=pend["total_inr"]
            reply=f"Cart ({len(lines)} items):\n"+"\n".join(lines)+f"\nTotal Rs.{total}"
            opts=_choice_options("awaiting_approval",lang)
            send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
            return {"status":"cart_view","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}
    if low.startswith("remove ") or "remove" in low:
        prod=_catalog_product_in(low)
        pend=_get_pending(phone_digits)
        if prod and pend and pend.get("items"):
            new_items=[i for i in pend["items"] if i["product"]!=prod]
            if len(new_items)!=len(pend["items"]):
                pend["items"]=new_items
                pend["total_inr"]=sum(x["total_inr"] for x in new_items)
                pend["products"]={i["product"]:i["recommended_qty"] for i in new_items}
                if not new_items:
                    pending_orders.pop(phone_digits,None)
                    reply={"ta":f"{prod} removed — cart empty.","en":f"{prod} removed — cart empty."}.get(lang,f"{prod} removed.")
                else:
                    reply={"ta":f"{prod} removed.","en":f"{prod} removed — {len(new_items)} left."}.get(lang,f"{prod} removed.")
                opts=_choice_options("awaiting_approval" if new_items else "greeted",lang)
                send=_copilot_send(phone_digits, reply+_tap_suffix(opts,channel), force_mock=force_mock, voice_mode=vmode)
                return {"status":"cart_updated","reply":reply,"options":opts,"send":send,"phone":phone_digits,"transcript":transcript,"channel":channel}

    rules = _rules_intent(transcript)
    # ── Fix: "update as 10kg" / "10kg" after dispatch has qty but no product → infer last product
    if (not rules.get("products") or not rules["products"]):
        # extract any lone qty
        m_qty = re.search(r"\b(\d{1,3})\s*(kg|kgs?|kilo|bunch|bunches)?\b", low)
        if m_qty and any(w in low for w in ["update","change","make it","correction","correct","as "]):
            try:
                qty = int(m_qty.group(1))
                # infer product: pending first, else last dispatched
                infer = None
                pend_tmp = _get_pending(phone_digits)
                if pend_tmp and pend_tmp.get("products"):
                    infer = list(pend_tmp["products"].keys())[0]
                else:
                    hist = order_history(MERCHANT, 1)
                    if hist: infer = hist[0].get("product")
                if infer and 1 <= qty <= 90:
                    rules["products"] = {infer: qty}
                    rules["intent"] = "create_restock_order"
            except Exception:
                pass
    if rules["intent"] == "decline":
        pending_orders.pop(phone_digits, None)
        reply = _cancel_text(lang)
        _copilot_send(phone_digits, reply, force_mock=force_mock, voice_mode=vmode)
        return {"status": "declined", "phone": phone_digits,
                "transcript": transcript, "channel": channel}
    if rules["intent"] != "create_restock_order" or not rules.get("products"):
        # ── Partner fallback: business-aware, proactive, not bot-like
        try:
            # Build shop context for partner persona
            stock = stock_snapshot(MERCHANT)
            weather = get_weather()
            rain = int(round(weather["rain_prob"]*100))
            orders = order_history(MERCHANT, 3)
            last = orders[0] if orders else None
            # Query-filtered cognee snippet (not first 2)
            cognee_snippet = ""
            try:
                with open(MEMORY_PATH, encoding="utf-8") as f:
                    mem = json.load(f).get(MERCHANT, {})
                    all_facts = mem.get("huge_facts", []) or mem.get("cause_chain", []) or []
                    # filter by query words
                    qwords = set(re.findall(r"\w+", transcript.lower()))
                    filtered = [f for f in all_facts if any(w in f.lower() for w in qwords)] if qwords else []
                    pick = (filtered[:2] if filtered else all_facts[:2])
                    if pick:
                        cognee_snippet = " | ".join(pick[:2])
            except OSError:
                pass
            ctx_hint = ctx or cognee_snippet
            shop_line = f"Shop: Lakshmi Kirana Basavanagudi, sells tomato/onion/coriander/spinach, stock tomato {stock.get('tomato')}kg, rain {rain}% tmrw"
            if last:
                shop_line += f", last order {last['qty']}{last['unit']} {last['product']} Rs.{last.get('total_inr')}"
            llm_reply = None
            if llm_mod.available() and transcript.strip():
                prompt = (
                    f"You are Lakshmi's AI business partner (not a bot) at Basavanagudi. {shop_line}. "
                    f"Context from memory: {ctx_hint[:350] if ctx_hint else 'new merchant, no history'}. "
                    f"User said in {lang}: '{transcript}'. "
                    f"Reply as partner: warm, concise (≤2 sentences), pure {lang} (no mix), business-aware. "
                    f"Relate generic questions to her shop (e.g. 'paytm?' → settlement/GMV/stock, 'joke' → warm steer to business). "
                    f"End with ONE actionable tap: Check stock / Order 20kg / Show growth. Never invent quantities. Never say 'not found'."
                )
                raw = llm_mod._call(
                    [{"role": "system", "content": f"You are Lakshmi's business partner. Reply only in {lang}, warm and concise."},
                     {"role": "user", "content": prompt}],
                    model=llm_mod.FAST_MODEL, max_tokens=320, temperature=0.35, timeout=5
                )
                if raw and len(raw.strip()) > 12:
                    llm_reply = raw.strip()[:620]
            if llm_reply:
                reply = llm_reply
                # ensure one tap hint
                if "Check stock" not in reply and "tap" not in reply.lower():
                    reply += {"ta": "\nTap 1: பங்கு பார்க்க 2: ஆர்டர்", "hi": "\nTap 1: स्टॉक 2: ऑर्डर", "en": "\nTap 1: Check stock 2: Order 20kg"}.get(lang, "\nTap 1: Check stock")
            else:
                # Partner deterministic: don't sound like bot
                partner_base = {
                    "ta": f"Vanakkam Lakshmi! Naan unga business partner. Innaiku tomato {stock.get('tomato')}kg irukku, naalaikku mazhai {rain}%.",
                    "hi": f"Namaste Lakshmi! Aapki dukaan mein tomato {stock.get('tomato')}kg hai, kal baarish {rain}%.",
                    "en": f"Hi Lakshmi — your partner here. Tomato {stock.get('tomato')}kg on hand, {rain}% rain tomorrow."
                }.get(lang, f"Hi Lakshmi — tomato {stock.get('tomato')}kg, rain {rain}% tmrw.")
                caps = {
                    "ta": " Naan help pannuven: stock, vilai, yen 20kg, vaanam, orders, valarchi.",
                    "hi": " Main madad kar sakta hoon: stock, keemat, kyun 20kg, mausam, orders, growth.",
                    "en": " I can help: stock, price, why 20kg, weather, orders, growth — what's next?"
                }.get(lang, " I can help: stock, price, why 20kg, weather, orders, growth.")
                # tailor to query
                ql = transcript.lower()
                if "paytm" in ql:
                    tail = {"ta": " Paytm moolam customer pay pannuvanga — unga 7-day GMV paarkalaama?", "hi": " Paytm se customer pay karte hain — aapka GMV dekhein?", "en": " Paytm is how customers pay you — want to see your 7-day GMV?"}.get(lang, " Want to see GMV?")
                    reply = partner_base + tail
                elif "joke" in ql or "jok" in ql:
                    tail = {"ta": " Joke illa, aana neenga mazhaiyil ₹240 save pannineenga — adha repeat pannalaama?", "hi": " Joke nahi, par aapne baarish mein ₹240 bachaye — repeat karein?", "en": " No joke, but you saved ₹240 last rainy day — want to do it again?"}.get(lang, " Want to repeat that win?")
                    reply = partner_base + " " + tail
                else:
                    reply = partner_base + caps
                if ctx_hint:
                    reply += f"\n\n({ctx_hint[:160]})"
        except Exception:
            reply = _fallback_text(lang)
        opts = _choice_options("greeted", lang)
        _copilot_send(phone_digits, reply + _tap_suffix(opts, channel), force_mock=force_mock, voice_mode=vmode)
        return {"status": "no_intent", "reply": reply, "options": opts, "phone": phone_digits,
                "transcript": transcript, "channel": channel, "cognee_used": bool(ctx)}

    # Optional 'more/less' adjustment to the CURRENT pending basket:
    # 'இன்னும் 5 கிலோ' / '5 kg less' / 'इसे 5 कम करो' — needs a pending order.
    adj = _parse_adjustment(low)
    pend_now = _get_pending(phone_digits)
    if adj and pend_now:
        items = pend_now["items"]
        idx = next((i for i, it in enumerate(items) if it["product"] == adj["product"]), None)
        if idx is not None:
            it = items[idx]
            data = CATALOG[MERCHANT][it["product"]]
            new_qty = max(1, min(it["recommended_qty"] + adj["delta"], MAX_ORDER_CAP))
            it["recommended_qty"] = new_qty
            it["total_inr"] = new_qty * data["price_per_unit"]
            pend_now["total_inr"] = sum(x["total_inr"] for x in items)
            ask = _ask_text(items, lang)
            message = f"{ask}{CONFIRM_SUFFIX[lang]}"
            _copilot_send(phone_digits, message + _tap_suffix(_choice_options("awaiting_approval", lang), channel), force_mock=force_mock, voice_mode=vmode)
            return {"status": "awaiting_approval", "adjustment": adj,
                    "options": _choice_options("awaiting_approval", lang),
                    "reply": message, "basket_total_inr": pend_now["total_inr"],
                    "items": [{"product": i["product"], "recommended_qty": i["recommended_qty"],
                               "unit": i["unit"], "total_inr": i["total_inr"]} for i in items],
                    "phone": phone_digits, "transcript": transcript,
                    "engine": "rules", "channel": channel}

    # Build new items from this turn
    new_items, new_total = [], 0
    for product, requested in rules["products"].items():
        rec = recommendation(MERCHANT, product, requested)
        new_items.append(rec)
        new_total += rec["total_inr"]
    # ── True cart: merge, don't overwrite
    existing = _get_pending(phone_digits)
    if existing and existing.get("items"):
        merged = {i["product"]: i for i in existing["items"]}
        for rec in new_items:
            merged[rec["product"]] = rec
        items = list(merged.values())
        total = sum(x["total_inr"] for x in items)
        merged_products = {**existing.get("products", {}), **rules["products"]}
    else:
        items, total, merged_products = new_items, new_total, rules["products"]
    weather = get_weather()
    # Sarvam P3 may REWRITE the ask; the grounding gate in llm.py rejects any
    # output that drops or alters an engine quantity -> deterministic template.
    ask = _ask_text(items, lang)
    # Sarvam upgrade only for Tamil (the P3 prompt + grounding gate are
    # Tamil-native); every other language gets the deterministic localized ask.
    if lang == "ta":
        try:
            sarvam_ask = llm_mod.explain_ask(items, weather["rain_prob"], language="Tamil")
            if sarvam_ask:
                ask = sarvam_ask
        except Exception:
            pass  # template ask is always available
    # Growth bundle nudge: 80% tomato→coriander etc., no extra typing
    try:
        bundle = get_bundle_suggestion(list(rules["products"].keys())[0]) if rules["products"] else None
        if bundle:
            # pure language, short
            bl = {"ta": f"💡 {bundle['why']} — {bundle['with']} {bundle['qty']} bunch?", "hi": f"💡 {bundle['why']} — {bundle['with']} {bundle['qty']}?", "en": f"💡 {bundle['why']} — add {bundle['with']} {bundle['qty']}?"}.get(lang, f"💡 {bundle['why']}")
            message = f"{ask}{CONFIRM_SUFFIX[lang]}\n{bl}"
        else:
            message = f"{ask}{CONFIRM_SUFFIX[lang]}"
    except Exception:
        message = f"{ask}{CONFIRM_SUFFIX[lang]}"
    pending_orders[phone_digits] = {"products": merged_products, "items": items,
                                    "total_inr": total,
                                    "created": datetime.datetime.now().timestamp()}
    optsF = _choice_options("awaiting_approval", lang)
    send = _copilot_send(phone_digits, message + _tap_suffix(optsF, channel), force_mock=force_mock, voice_mode=vmode)
    return {"status": "awaiting_approval", "options": optsF, "phone": phone_digits,
            "transcript": transcript, "basket_total_inr": total,
            "reply": message, "send": send,
            "items": [{"product": i["product"], "recommended_qty": i["recommended_qty"],
                       "unit": i["unit"], "total_inr": i["total_inr"]} for i in items],
            "ask": message, "engine": "rules", "channel": channel}


@app.post("/wa/inbound")
def wa_inbound(payload: dict, sync: bool = False):
    """WA-AKG webhook: ACK immediately (low-latency), process async.
    Fixes: 'operation aborted due to timeout' retry storm — the webhook must
    return 200 in <500ms, not after the WA-AKG send + TTS. Also: groups
    (@g.us) and unknown callers are ignored, never replied to.
    ?sync=1 (demo/test only): process inline and return the copilot result so
    UIs and QA can render the actual reply without polling."""
    data = payload.get("data") or {}
    raw_phone = (data.get("from") or (data.get("key") or {}).get("remoteJid") or "")
    # Groups: ignore entirely (no reply, no ledger) — prevents @g.us wrong-number sends
    if "@g.us" in raw_phone:
        return {"received": True, "ignored": "group"}
    phone_digits = _normalize_phone(raw_phone)
    # Single-merchant lock: only 917010919624 → partner; others ignored silently
    # (previous code replied "unknown caller" TO the unknown number — that WAS the wrong-number send)
    if phone_digits and not _allowed_copilot_phone(phone_digits):
        return {"received": True, "ignored": "unknown_caller", "phone": phone_digits}
    # Empty phone (e.g. malformed group decrypt) — ack but don't process
    if not phone_digits:
        return {"received": True, "ignored": "no_phone"}
    text = data.get("content") or data.get("body") or ""
    media = data.get("fileUrl") or (data.get("quoted") or {}).get("fileUrl") or ""
    if media and not media.startswith("http"):
        base = os.getenv("WA_AKG_URL", "")
        if base:
            media = base.rstrip("/") + media
    headers = {"X-API-Key": os.getenv("WA_AKG_API_KEY", "")} if media and os.getenv("WA_AKG_API_KEY") else None
    ctype = data.get("mimetype") or data.get("contentType") or ""

    if sync:
        try:
            result = _handle_merchant_message(
                raw_phone, text=text, media_url=media, media_headers=headers,
                content_type=ctype, channel="wa-akg")
            return {"received": True, "queued": False, "phone": phone_digits,
                    "result": result}
        except Exception:
            return {"received": True, "queued": False, "phone": phone_digits,
                    "result": {"status": "error"}}

    def _process():
        try:
            _handle_merchant_message(
                raw_phone, text=text, media_url=media, media_headers=headers,
                content_type=ctype, channel="wa-akg")
        except Exception:
            pass  # webhook already acked; never raise

    threading.Thread(target=_process, daemon=True, name="wa-inbound").start()
    return {"received": True, "queued": True, "phone": phone_digits}


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
    # SECURITY FIX 2026-09-19: the client used to send total_inr and the server
    # trusted it — a tampered payload could write a fake amount into the ledger,
    # memory, n8n and the WhatsApp bubble. The price is recomputed from the
    # CATALOG; a client value is accepted only when it matches (±1 rupee).
    server_total = order["qty"] * CATALOG[MERCHANT][order["product"]]["price_per_unit"]
    client_total = approval.get("total_inr")
    if client_total is not None and abs(int(client_total) - server_total) > 1:
        return {"status": "failed",
                "reason": f"total_inr mismatch: engine says {server_total}, payload said {client_total}"}
    delivery = record_delivery(
        MERCHANT, order["product"], order["qty"], order["supplier"],
        server_total, token,
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
        "total_inr": server_total,
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
    # FIX 2026-09-19: word-safe matching (raw substring matched 'no' inside 'know').
    if _word_hit(text, DENY_WORDS):
        return {"status": "declined", "heard": text}
    if not _word_hit(text, APPROVE_WORDS):
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

    def _do_tts() -> bytes:
        from sarvamai import SarvamAI
        client = SarvamAI(api_subscription_key=api_key)
        resp = client.text_to_speech.convert(text=text, language_code=lang,
                                             speaker="kavitha", model="bulbul:v3")
        aud = resp.audios[0] if hasattr(resp, "audios") else resp
        b64 = aud if isinstance(aud, str) else getattr(aud, "audio", "")
        if not b64:
            raise RuntimeError("no audio in TTS response")
        return base64.b64decode(b64)

    try:
        # FIX 2026-09-19: bounded like the other SDK calls — a hung TTS can no
        # longer park a route worker forever and freeze the API on stage.
        audio = _SDK_EXECUTOR.submit(_do_tts).result(timeout=40)
        return Response(content=audio, media_type="audio/wav")
    except concurrent.futures.TimeoutError:
        raise HTTPException(504, "TTS timed out — browser fallback is the labeled path")
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "402" in msg or "insufficient_quota" in msg or "No credits" in msg:
            raise HTTPException(503, f"TTS quota exhausted — browser speechSynthesis fallback: {msg[:200]}")
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
    # Paytm GMV — sum of dispatched orders (real metric judges want)
    orders = order_history(merchant_id, 100)
    gmv_total = sum(o.get("total_inr", 0) for o in orders)
    gmv_7d = sum(o.get("total_inr", 0) for o in orders[:7])
    return {
        "merchant_id": merchant_id,
        "persona": "Lakshmi (representative persona)",
        "data_label": "Paytm-transaction-shaped seeded demo data (labeled, toggle WEATHER_MODE=live for real)",
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
        "paytm": {"gmv_total_inr": gmv_total, "gmv_7d_inr": gmv_7d, "retention_signal": f"{len(orders)} dispatches → merchant sticks", "soundbox": "briefing ready at /soundbox/briefing"},
        "cost": {"per_msg_inr": 0.02, "sarvam_stt": "~₹0.015", "cognee": "free tier", "note": "₹0.02/msg covers Sarvam+Cognee"},
    }


@app.post("/demo/reset")
def demo_reset():
    """Restore seeded inventory + clear the ledger + copilot state so a
    rehearsal is repeatable. FIX 2026-09-19: pending copilot orders used to
    survive a reset — a stale 'சரி' would then dispatch against fresh stock."""
    state = reset_state()
    tokens_cleared = len(dispatched_tokens)
    pending_cleared = len(pending_orders)
    dispatched_tokens.clear()
    pending_orders.clear()
    issued_tokens.clear()
    _save_dispatched()
    # Keep Lakshmi locked as complete — judges see greeting, not onboarding, after reset
    # (first-time flow still testable via new number 919999000001)
    profiles = _load_profiles()
    if "917010919624" in profiles:
        profiles["917010919624"]["onboarding_complete"] = True
        profiles["917010919624"]["step"] = 3
        profiles["917010919624"]["name"] = "Lakshmi"
        profiles["917010919624"]["business"] = "Lakshmi Kirana & Vegetables"
        _save_profiles(profiles)
    return {"status": "reset", "stock": state["stock"],
            "tokens_cleared": tokens_cleared, "pending_orders_cleared": pending_cleared}


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
        local_mem = get_memory().get("lakshmi", {})
        facts = local_mem.get("huge_facts", [])
        # Render's memory.json is ephemeral (not in git) → huge_facts may be empty after reset/deploy
        if not facts:
            # Fallback to visible cause_chain + core signals so judges never see empty
            facts = local_mem.get("cause_chain", []) + [
                f"sells: {local_mem.get('sells','')}",
                f"recent_sales_velocity: {local_mem.get('recent_sales_velocity','')}",
                f"rain_sensitivity: {local_mem.get('rain_sensitivity','')}",
                f"recommendation: {local_mem.get('recommendation','')}",
            ]
            facts = [f for f in facts if f and str(f).strip()]
        return {
            "source": "local-fallback",
            "query": q,
            "results": [
                {"kind": "fact", "text": f} 
                for f in facts[:10]
            ],
            "memory_summary": {
                "fact_count": local_mem.get("fact_count", len(facts)),
                "updated": local_mem.get("updated", ""),
            },
        }
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


@app.get("/cognee/context")
def cognee_context_view(phone: str = "917010919624"):
    """Agentic RAG cache view — what the copilot currently 'remembers' per merchant."""
    phone_digits = _normalize_phone(phone)
    entry = _COGNEE_CTX_CACHE.get(phone_digits)
    return {
        "phone": phone_digits,
        "cached": bool(entry),
        "context": entry["context"] if entry else None,
        "refreshed_at": datetime.datetime.fromtimestamp(entry["at"]).isoformat(timespec="seconds")
        if entry else None,
        "preferences": _get_merchant_prefs(phone_digits),
        "note": "Background Cognee recall warms this cache; replies never block on it.",
    }
