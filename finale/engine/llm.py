"""Sarvam LLM layer — understanding + explanation only.

Doctrine 08 boundary, enforced in code:
  - The LLM may classify intent and WRITE sentences.
  - The LLM may NEVER originate a number. Every quantity in an outbound
    payload is copied from the deterministic engine's output, and any
    quantity the model emits is DISCARDED before merge.

Model selection — measured on the live API 2026-09-18 (all timings real):
  - 'sarvam-105b-conversations' is the FAST chat model: 0.3-1.0s, clean JSON.
  - 'sarvam-105b' is a REASONING model: it emits `reasoning_content` first.
    With the doctrine P1 prompt it burned 10,263 chars of reasoning and took
    32.5s (and returned content=None at max_tokens=1200 because the budget was
    consumed by reasoning). At max_tokens=3000 it finally returned JSON in
    32.5s — far too slow for a live voice loop.

So: the live loop uses the fast model with a tight budget, and the deep
reasoning model is used only for the on-demand "Reason" button where a
20-40s wait is expected and narrated.

Every call runs under a hard wall-clock budget via a worker thread, so a slow
or dead API can never stall the demo — callers fall back to deterministic code.
"""
import concurrent.futures
import json
import os
import re
import time

from engine.restock import BASE_DIR

PROMPT_DIR = os.path.join(BASE_DIR, "prompts")

CATALOG_PRODUCTS = ["tomato", "coriander", "onion", "spinach", "potato"]

VALID_INTENTS = {
    "create_restock_order", "adjust_order", "ask_sales", "ask_stock",
    "ask_advice", "ask_bill", "smalltalk", "out_of_scope",
}

FAST_MODEL = os.getenv("SARVAM_LLM_MODEL", "sarvam-105b-conversations")
DEEP_MODEL = os.getenv("SARVAM_LLM_DEEP_MODEL", "sarvam-105b")

# The reasoning model spends most of its budget on `reasoning_content` before it
# emits any `content`, so a small max_tokens returns finish_reason='length' with
# content=None. Tune without touching code: LLM_DEEP_MAX_TOKENS.
def _deep_max_tokens() -> int:
    try:
        return int(os.getenv("LLM_DEEP_MAX_TOKENS", "8000"))
    except ValueError:
        return 8000

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="sarvam-llm")

# Diagnostics for the build-day team (surfaced by /llm/diag and /health).
LAST = {"model": None, "elapsed_s": None, "finish_reason": None,
        "reasoning_chars": None, "error": None, "ok": None, "at": None}


def llm_mode() -> str:
    """off | hybrid (default). 'off' keeps the demo fully deterministic."""
    return (os.getenv("LLM_MODE") or "hybrid").strip().lower()


def fast_timeout() -> float:
    try:
        return float(os.getenv("LLM_TIMEOUT", "8"))
    except ValueError:
        return 8.0


def deep_timeout() -> float:
    try:
        return float(os.getenv("LLM_DEEP_TIMEOUT", "75"))
    except ValueError:
        return 75.0


def available() -> bool:
    return bool(os.getenv("SARVAM_API_KEY")) and llm_mode() != "off"


def _load_prompt(name: str, fallback: str = "") -> str:
    try:
        with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return fallback


def _client():
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))


def _call(messages: list[dict], model: str, max_tokens: int,
          temperature: float = 0.1, timeout: float | None = None) -> str | None:
    """Blocking chat call with a hard wall-clock budget. Returns content or None."""
    if not available():
        LAST.update({"error": "llm unavailable", "ok": False})
        return None
    budget = timeout if timeout is not None else fast_timeout()
    started = time.time()

    def _attempt():
        kwargs = dict(model=model, messages=messages,
                      temperature=temperature, max_tokens=max_tokens)
        if model == DEEP_MODEL:
            kwargs["reasoning_effort"] = "low"   # reasoning models need this
        resp = _client().chat.completions(**kwargs)
        choices = getattr(resp, "choices", None) or []
        if not choices:
            return None, None, None
        msg = choices[0].message
        return (getattr(msg, "content", None),
                choices[0].finish_reason,
                len(getattr(msg, "reasoning_content", None) or ""))

    def _work():
        # The provider intermittently returns an Azure Application Gateway error
        # page (text/html, content-length 183) instead of JSON. Verified live
        # 2026-09-18. A single retry turns most of those into a normal answer
        # instead of a degraded one, at the cost of ~0.5s.
        try:
            return _attempt()
        except Exception:
            time.sleep(0.5)
            return _attempt()

    try:
        future = _EXECUTOR.submit(_work)
        content, finish, rchars = future.result(timeout=budget)
        LAST.update({"model": model, "elapsed_s": round(time.time() - started, 2),
                     "finish_reason": finish, "reasoning_chars": rchars,
                     "error": None, "ok": bool(content),
                     "at": time.strftime("%H:%M:%S")})
        return content
    except concurrent.futures.TimeoutError:
        LAST.update({"model": model, "elapsed_s": round(time.time() - started, 2),
                     "finish_reason": "client-timeout", "error": f"exceeded {budget}s budget",
                     "ok": False, "at": time.strftime("%H:%M:%S")})
        return None
    except Exception as e:
        LAST.update({"model": model, "elapsed_s": round(time.time() - started, 2),
                     "finish_reason": "exception", "error": _clean_error(e),
                     "ok": False, "at": time.strftime("%H:%M:%S")})
        return None


def _clean_error(e: Exception) -> str:
    """One readable line. The raw provider error was a multi-line HTTP header
    dump (Azure gateway HTML page) — unreadable on stage and in /llm/diag."""
    text = " ".join(str(e).split())
    hint = ""
    if "503" in text or "502" in text or "text/html" in text:
        hint = " (upstream gateway error — transient, retried once)"
    elif "429" in text:
        hint = " (rate limited)"
    elif "401" in text or "403" in text:
        hint = " (check SARVAM_API_KEY)"
    return f"{type(e).__name__}: {text[:150]}{hint}"


def diag() -> dict:
    return {"mode": llm_mode(), "fast_model": FAST_MODEL, "deep_model": DEEP_MODEL,
            "fast_timeout_s": fast_timeout(), "deep_timeout_s": deep_timeout(),
            "deep_max_tokens": _deep_max_tokens(),
            "available": available(), "last_call": dict(LAST)}


def _extract_json(text: str | None) -> dict | None:
    """Tolerant JSON extraction — models sometimes wrap JSON in prose/fences."""
    if not text:
        return None
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


# ── P1: intent understanding (FAST model) ─────────────────────────────────
def parse_intent(transcript: str) -> dict | None:
    """Classify intent/language via Sarvam using prompts/P1_intent.txt.

    QUANTITIES ARE NOT TRUSTED: the caller keeps the regex parser's numbers.
    """
    system = _load_prompt("P1_intent.txt", "Return only JSON.")
    user = (
        f"Catalog products: {', '.join(CATALOG_PRODUCTS)}\n"
        f"Transcript: {transcript}\n"
        "Return ONLY the JSON object specified in your instructions."
    )
    raw = _call(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=FAST_MODEL, max_tokens=900, temperature=0.1,
    )
    parsed = _extract_json(raw)
    if not parsed:
        return None
    intent = str(parsed.get("intent") or "").strip()
    return {
        "intent": intent if intent in VALID_INTENTS else "out_of_scope",
        "language": str(parsed.get("language") or "").strip() or None,
        "injection_detected": bool(parsed.get("injection_detected")),
        "clarification_needed": bool(parsed.get("clarification_needed")),
        "confidence": parsed.get("confidence"),
        "raw_products": parsed.get("products") if isinstance(parsed.get("products"), dict) else None,
    }


# ── P2: grounded reasoning over observations fetched by the API (DEEP model) ─
def reason(rec: dict, observations: list[dict], language: str = "Tamil",
           profile: str = "fast") -> dict | None:
    """Reason over REAL observations (never invented ones).

    profile='fast' (default): the chat model answers in ~1s — usable on stage.
    profile='deep': the reasoning model. Measured 32.5s and 10k reasoning chars,
    so it is opt-in only: a 30s silky pause is dead air in a live demo. Use it
    for a seated judge walkthrough, never inside the timed pitch.
    """
    deep = profile == "deep"
    system = _load_prompt("P2_react.txt", "Reason over the observations. Never invent numbers.")
    obs_text = "\n".join(f"- {o['tool']}({o.get('args','')}) -> {o['result']}" for o in observations)
    engine_line = (
        f"ENGINE OUTPUT (the ONLY source of truth for quantity): "
        f"{rec['recommended_qty']} {rec['unit']} {rec['product']}, total ₹{rec['total_inr']}"
    )
    user = (
        f"{engine_line}\n\nOBSERVATIONS (already fetched by the API — do not invent others):\n{obs_text}\n\n"
        f"Reply in {language}. Return ONLY JSON with keys: "
        '{"reasoning":"<=2 sentences citing only the observations above",'
        '"memory_note":"one line to store about this merchant",'
        '"needs_human_review":true|false}'
    )
    raw = _call(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=DEEP_MODEL if deep else FAST_MODEL,
        max_tokens=_deep_max_tokens() if deep else 900,
        temperature=0.1,
        timeout=deep_timeout() if deep else fast_timeout() + 4,
    )
    parsed = _extract_json(raw)
    if not parsed:
        return None
    return {
        "reasoning": str(parsed.get("reasoning") or "").strip(),
        "memory_note": str(parsed.get("memory_note") or "").strip(),
        "needs_human_review": bool(parsed.get("needs_human_review")),
    }


# ── P3: vernacular explanation (FAST model + grounding gate) ──────────────
def _grounded(text: str, items: list[dict]) -> bool:
    """A spoken ask is only trustworthy if it names EVERY engine quantity.

    Measured failure mode: on the real prompt the model said
    'நாளை 20 கிலோ தக்காளி வேண்டுமா?' — correct for tomato but it silently
    dropped the 6 bunches of coriander. An ask that omits an item would let the
    merchant approve an order she never heard. So: all quantities present, or
    we speak the deterministic template instead.
    """
    if not text:
        return False
    for item in items:
        if str(item["recommended_qty"]) not in text:
            return False
        name = item.get("name_tn") or item["product"]
        if name not in text and item["product"] not in text.lower():
            return False
    return True


def explain_ask(items: list[dict], rain_prob: float, language: str = "Tamil") -> str | None:
    """Warm <=3 sentence Tamil ask ending in the exact approval question.
    Quantities are INJECTED from the engine, never generated — and the output is
    rejected unless every injected quantity actually appears in it."""
    system = _load_prompt("P3_explain.txt", "Speak warmly in Tamil, <=3 short sentences.")
    injected = ", ".join(
        f"{i['recommended_qty']} {i['unit']} {i.get('name_tn') or i['product']}" for i in items
    )
    user = (
        f"Rain tomorrow: {int(rain_prob * 100)}%.\n"
        f"Engine-approved quantities (use these EXACTLY, do not change, do not omit any): {injected}.\n"
        f"Top factors: {'; '.join(f['fact'] for i in items for f in i.get('factors', [])[:3])}\n"
        "Speak in Tamil. Mention EVERY item above with its exact number. "
        "End by asking her to say 'சரி' to confirm. "
        "Do not mention any number that is not in the injected quantities."
    )
    raw = _call(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=FAST_MODEL, max_tokens=700, temperature=0.3, timeout=fast_timeout() + 4,
    )
    if not raw:
        return None
    text = raw.strip().strip('"')
    return text if _grounded(text, items) else None


def template_ask(items: list[dict], rain_prob: float) -> str:
    """Deterministic Tamil fallback — always available, always complete."""
    rain = int(round(rain_prob * 100))
    parts = ", ".join(
        f"{i['recommended_qty']} {('கிலோ' if i['unit'] == 'kg' else 'கொத்து')} {i.get('name_tn') or i['product']}"
        for i in items
    )
    return (
        f"நாளை மழை {rain} சதவீதம் இருக்கும். "
        f"நாளை {parts} வேண்டுமா? "
        "வேண்டும் என்றால் \"சரி\" என்று சொல்லுங்கள்."
    )
