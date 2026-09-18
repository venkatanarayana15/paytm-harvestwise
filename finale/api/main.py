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

from fastapi import FastAPI, UploadFile, File, HTTPException
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
WORDNUM = {**TAMIL_WORDNUM, **KANNADA_WORDNUM}
# unit word -> (canonical unit, multiplier into that unit)
UNIT_WORDS = {
    "கிலோ": ("kg", 1), "ಕಿಲೋ": ("kg", 1), "ಕೆಜಿ": ("kg", 1), "????": ("kg", 1), "????": ("kg", 1), "kg": ("kg", 1), "kilo": ("kg", 1), "kilos": ("kg", 1),
    "கிரேட்": ("kg", 20), "ಕ್ರೇಟ್": ("kg", 20), "?????": ("kg", 20), "??????": ("kg", 20), "crate": ("kg", 20), "crates": ("kg", 20),
    "கொத்து": ("bunch", 1), "கட்டு": ("bunch", 1), "ಗೊಂಚಲು": ("bunch", 1), "ಕಟ್ಟು": ("bunch", 1), "??????": ("bunch", 1), "????": ("bunch", 1), "bunch": ("bunch", 1), "bunches": ("bunch", 1),
}
PRODUCT_WORDS = {
    "tomato": "tomato", "tomatoes": "tomato", "தக்காளி": "tomato", "tamatar": "tomato", "ಟೊಮ್ಯಾಟೊ": "tomato", "ಟೊಮೇಟೊ": "tomato",
    "coriander": "coriander", "kothamalli": "coriander", "கொத்தமல்லி": "coriander", "ಕೊತ್ತಂಬರಿ": "coriander", "ಕೊತ್ತುಂಬರಿ": "coriander",
    "dhania": "coriander", "?????": "coriander", "???????": "coriander", "onion": "onion", "வெங்காயம்": "onion", "ಈರುಳ್ಳಿ": "onion",
    "spinach": "spinach", "palak": "spinach", "????": "spinach", "??????": "spinach", "ಮುರೈಕೀರೈ": "spinach", "ಪಾಲಕ್": "spinach", "ಪಾಲಕ್ ಸೊಪ್ಪು": "spinach",
    "potato": "potato", "aloo": "potato", "???": "potato", "???": "potato", "ಆಲೂಗಡ್ಡೆ": "potato", "உருளைக்கிழங்கு": "potato",
}
APPROVE_WORDS = ["sari", "சரி", "ಸರಿ", "yes", "ha", "haan", "ಹೌದು", "ஆம்", "ok", "confirm"]
DENY_WORDS = ["illa", "இல்ல", "ಇಲ್ಲ", "no", "venam", "வேண்டாம்", "ಬೇಡ", "nahi", "cancel", "stop"]

# Prompt-injection markers — merchant speech is DATA, never instructions.
INJECTION_MARKERS = [
    "ignore previous", "ignore all previous", "disregard", "system prompt",
    "reveal your prompt", "you are now", "act as", "jailbreak",
    "without approval", "skip approval", "auto approve", "override",
]

LANG_MAP = {
    "ta": "ta", "tamil": "ta", "ta-in": "ta",
    "kn": "kn", "kannada": "kn", "kn-in": "kn",
    "hi": "hi", "hindi": "hi", "hi-in": "hi",
    "en": "en", "english": "en", "en-in": "en",
    "te": "te", "telugu": "te",
}


def _parse_quantities(text: str) -> dict[str, int | None]:
    """Extract {product: requested_qty} from a transcript.
    Handles '20 கிலோ தக்காளி' / '20 ಕಿಲೋ ಟೊಮ್ಯಾಟೊ', '3 crates tomato', '10 கொத்து கொத்தமல்லி',
    Tamil/Kannada word-numbers, punctuation, and qty-before/after product order.
    NEVER invents a number — absent numbers stay None (engine fills deterministically)."""
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


def _detect_lang(text: str) -> str:
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta"
    if re.search(r"[\u0c80-\u0cff]", text):
        return "kn"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    return "en"


def _rules_intent(text: str) -> dict:
    """Deterministic rule-based intent parse. Authoritative for all quantities."""
    low = text.lower()
    if not text.strip():
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
        "twilio_recipient": os.getenv("TWILIO_WHATSAPP_TO", "NOT_SET"),
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


def _fire_twilio(record: dict, order: dict, approval: dict) -> None:
    twilio_sid, twilio_token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
    if not twilio_sid or not twilio_token:
        return
    recipient = approval.get("merchant_phone") or os.getenv("TWILIO_WHATSAPP_TO")
    if not recipient:
        # Never post to the placeholder number — that produced error 572002 while
        # looking like a real send. Refuse loudly instead, and stay labeled.
        record["twilio_status"] = "skipped"
        record["twilio_note"] = (
            "TWILIO_WHATSAPP_TO not set — refusing to send to a placeholder number. "
            "Set it in .env (verified recipient in the Twilio console)."
        )
        return
    try:
        auth = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode()).decode()
        data = {
            "To": recipient,
            "From": os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"),
            "ContentSid": os.getenv("TWILIO_CONTENT_SID", ""),
            "ContentVariables": json.dumps({
                "1": str(order["qty"]), "2": order["product"],
                **({"3": order["supplier"], "4": str(record["total_inr"] or "")}
                  if os.getenv("TWILIO_TEMPLATE_VARS") == "4" else {}),
            }),
        }
        r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                       data=data, headers={"Authorization": f"Basic {auth}"}, timeout=10)
        record["twilio_status"] = r.status_code
        if r.status_code >= 400:
            record["twilio_body"] = r.text[:300]
            record["twilio_note"] = "template send rejected — see Twilio console (dispatch still recorded)"
    except Exception as e:
        record["twilio_error"] = str(e)


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
