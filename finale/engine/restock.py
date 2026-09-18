"""HarvestWise deterministic restocking engine.

Responsibility boundary (doctrine 08 — non-negotiable):
  - THIS MODULE decides quantities. Pure, auditable, ordinary code.
  - The LLM may understand and explain, but must NEVER set a quantity.
  - n8n re-validates every field before execution.

Determinism policy (demo safety):
  - WEATHER_MODE=seeded (default)  -> ₹546 story is guaranteed on any demo day.
  - WEATHER_MODE=live              -> fetch real Open-Meteo rain; numbers move,
                                      narration must follow the screen.
"""
import json
import math
import os
import datetime

# ─── Paths (absolute, so the API works from any cwd — was a real fragility) ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # …/finale
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_PATH = os.path.join(DATA_DIR, "runtime_state.json")

# ─── Catalog: seeded demo data (labeled as such on every screen) ───────────
# price_per_unit: tomato ₹18/kg · coriander ₹31/bunch (mandi price, seeded —
# 6×31=₹186 + 20×18=₹360 = ₹546 basket, matches deck slide 5)
CATALOG = {
    "lakshmi": {
        "tomato": {
            "name_tn": "தக்காளி", "name_kn": "ಟೊಮ್ಯಾಟೊ", "name_hi": "टमाटर", "name_te": "టమాటా",
            "unit": "kg",
            "velocity": 14,
            "decay_days": 2,
            "current_stock": 12,
            "rain_modifier": 1.0,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 18,
        },
        "coriander": {
            "name_tn": "கொத்தமல்லி", "name_kn": "ಕೊತ್ತಂಬರಿ", "name_hi": "धनिया", "name_te": "ధనియాలు",
            "unit": "bunch",
            "velocity": 8,
            "decay_days": 1,
            "current_stock": 6,
            "rain_modifier": 0.6,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 31,
        },
        "onion": {
            "name_tn": "வெங்காயம்", "name_kn": "ಈರುಳ್ಳಿ", "name_hi": "प्याज़", "name_te": "ఉల్లి",
            "unit": "kg",
            "velocity": 10,
            "decay_days": 5,
            "current_stock": 15,
            "rain_modifier": 0.9,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 22,
        },
        "spinach": {
            "name_tn": "முரைக்கீரை", "name_kn": "ಪಾಲಕ್ ಸೊಪ್ಪು", "name_hi": "पालक", "name_te": "పాలకూర",
            "unit": "bunch",
            "velocity": 6,
            "decay_days": 1,
            "current_stock": 4,
            "rain_modifier": 0.5,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 18,
        },
    },
    "rahul": {
        "tomato": {
            "name_tn": "தக்காளி", "name_kn": "ಟೊಮ್ಯಾಟೊ", "name_hi": "टमाटर", "name_te": "టమాటా",
            "unit": "kg",
            "velocity": 12,
            "decay_days": 2,
            "current_stock": 10,
            "rain_modifier": 1.0,
            "supplier": "KR Market",
            "price_per_unit": 20,
        },
        "potato": {
            "name_tn": "உருளைக்கிழங்கு", "name_kn": "ಆಲೂಗಡ್ಡೆ", "name_hi": "आलू", "name_te": "ఆలూ",
            "unit": "kg",
            "velocity": 15,
            "decay_days": 10,
            "current_stock": 20,
            "rain_modifier": 0.95,
            "supplier": "KR Market",
            "price_per_unit": 15,
        },
    },
}

# Seeded weather (IMD-shaped, demo-reproducible). Ledger 09 + deck slide 5: 78%.
WEATHER = {"tomorrow": {"rain_prob": 0.78, "humidity": 85}}

RAINY_THRESHOLD = 0.5
SAFETY_MARGIN = 1.25   # restock buffer: cover demand shortfall with headroom

MAX_ORDER = {"tomato": 100, "coriander": 100, "onion": 100, "spinach": 100, "potato": 100}

BENGALURU_LAT, BENGALURU_LON = 12.9716, 77.5946


# ══════════════════════════════════════════════════════════════════════════
# Weather — deterministic by default, real by opt-in
# ══════════════════════════════════════════════════════════════════════════
_weather_cache: dict = {}
_weather_cache_at: float = 0.0
WEATHER_TTL = 600  # 10 min


def weather_mode() -> str:
    """'seeded' (default, demo-safe) or 'live' (real Open-Meteo fetch)."""
    return (os.getenv("WEATHER_MODE") or "seeded").strip().lower()


def _seeded_weather(reason: str = "seeded") -> dict:
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    return {
        "rain_prob": WEATHER["tomorrow"]["rain_prob"],
        "humidity": WEATHER["tomorrow"]["humidity"],
        "source": "seeded",
        "reason": reason,
        "date": tomorrow,
        "city": "Basavanagudi, Bengaluru",
    }


def get_weather(city: str = "basavanagudi", force_live: bool = False) -> dict:
    """Tomorrow's rain probability.

    Default path returns the SEEDED 78% value so the ₹546 demo story holds on
    any day at any venue. With WEATHER_MODE=live (or force_live=True) the real
    Open-Meteo forecast is fetched, cached 10 min, and falls back to seeded on
    any failure — the demo must never block on a network call.

    Bug fixed 2026-09-18: the timezone value was pre-encoded ('Asia%2FCalcutta')
    and then URL-encoded again by httpx -> 'Asia%252FCalcutta' -> HTTP 400 on
    every single call, so 'live weather' never actually worked. Also
    forecast_days=1 returned TODAY's value while narrating it as tomorrow.
    """
    global _weather_cache, _weather_cache_at
    import time

    live = force_live or weather_mode() == "live"
    if not live:
        return _seeded_weather()

    now = time.time()
    if _weather_cache and now - _weather_cache_at < WEATHER_TTL:
        return _weather_cache

    # Open-Meteo needs no API key. verify defaults to True (TLS verification ON);
    # the previous verify=False disabled certificate checks for no reason.
    try:
        import httpx
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": BENGALURU_LAT,
                "longitude": BENGALURU_LON,
                "daily": "precipitation_probability_max",
                "timezone": "Asia/Kolkata",   # raw value — httpx encodes it once
                "forecast_days": 2,           # [0]=today, [1]=tomorrow
            },
            timeout=4,
        )
        if r.status_code == 200:
            daily = r.json()["daily"]
            probs = daily.get("precipitation_probability_max") or []
            dates = daily.get("time") or []
            if len(probs) >= 2 and probs[1] is not None:
                idx = 1
            elif probs and probs[0] is not None:
                idx = 0
            else:
                return _seeded_weather("live-empty")
            _weather_cache = {
                "rain_prob": probs[idx] / 100,
                "humidity": 85,
                "source": "live",
                "reason": "open-meteo",
                "date": dates[idx] if len(dates) > idx else None,
                "city": "Basavanagudi, Bengaluru",
            }
            _weather_cache_at = now
            return _weather_cache
        return _seeded_weather(f"live-http-{r.status_code}")
    except Exception as e:
        # Never crash the demo on the network — label the fallback honestly.
        return _seeded_weather(f"live-error:{type(e).__name__}")


# ══════════════════════════════════════════════════════════════════════════
# Live inventory ledger — makes acceptance criterion #5 visible
# (doctrine 08: "A visible memory/inventory update")
# ══════════════════════════════════════════════════════════════════════════
_STATE: dict | None = None


def _blank_state() -> dict:
    return {
        "stock": {
            m: {p: d["current_stock"] for p, d in prods.items()}
            for m, prods in CATALOG.items()
        },
        "orders": [],
        "delivered": 0,
    }


def _load_state() -> dict:
    global _STATE
    if _STATE is not None:
        return _STATE
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            base = _blank_state()
            base.update({k: v for k, v in loaded.items() if k in base})
            _STATE = base
            return _STATE
        except Exception:
            pass
    _STATE = _blank_state()
    return _STATE


def _save_state() -> None:
    state = _load_state()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def reset_state() -> dict:
    """Restore the seeded starting inventory. Demo runs are repeatable."""
    global _STATE
    _STATE = _blank_state()
    _save_state()
    return _STATE


def get_stock(merchant_id: str, product: str) -> int:
    """Stock on hand right now (seeded baseline, decremented/increased by orders)."""
    state = _load_state()
    return state["stock"].get(merchant_id, {}).get(product, 0)


def stock_snapshot(merchant_id: str) -> dict:
    state = _load_state()
    return state["stock"].get(merchant_id, {})


def record_delivery(merchant_id: str, product: str, qty: int, supplier: str,
                    total_inr: int | None, token: str) -> dict:
    """A dispatched order arrives from the mandi -> inventory rises, ledger
    appends an auditable row. Returns the updated stock + the ledger entry."""
    state = _load_state()
    before = state["stock"].setdefault(merchant_id, {}).get(product, 0)
    after = before + qty
    state["stock"][merchant_id][product] = after
    entry = {
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "merchant_id": merchant_id,
        "product": product,
        "name_tn": CATALOG.get(merchant_id, {}).get(product, {}).get("name_tn", ""),
        "qty": qty,
        "unit": CATALOG.get(merchant_id, {}).get(product, {}).get("unit", ""),
        "supplier": supplier,
        "total_inr": total_inr,
        "token": token,
        "stock_before": before,
        "stock_after": after,
        "source": "approved voice order -> n8n dispatch",
    }
    state["orders"].append(entry)
    state["delivered"] = state.get("delivered", 0) + 1
    _save_state()
    return {"entry": entry, "stock_on_hand": after}


def order_history(merchant_id: str | None = None, limit: int = 20) -> list:
    orders = _load_state()["orders"]
    if merchant_id:
        orders = [o for o in orders if o.get("merchant_id") == merchant_id]
    return orders[-limit:][::-1]


def _product(merchant_id: str, product: str) -> dict:
    data = CATALOG.get(merchant_id, {}).get(product)
    if not data:
        raise KeyError(f"Unknown product: {product}")
    return data


def _localized(data: dict) -> dict:
    return {k: data[k] for k in ("name_tn", "name_kn", "name_hi") if k in data}


# ══════════════════════════════════════════════════════════════════════════
# The deterministic decision
# ══════════════════════════════════════════════════════════════════════════
def calculate_quantity(merchant_id: str, product: str, requested_qty: int | None = None) -> int:
    """Deterministic restocking engine — the LLM never decides quantity.

    Formula (every constant documented):
      base      = requested_qty if stated by the merchant,
                  else ceil((velocity × decay_days − stock_on_hand) × SAFETY_MARGIN)
      rainy     = rain_prob ≥ RAINY_THRESHOLD
      quantity  = ceil(base × rain_modifier)   [rain_modifier per product]
    Calibrated outputs for the demo command (tomato 20kg, coriander 10→6):
      tomato    base=20 (requested) ×1.0  → 20 kg
      coriander base=10 (requested) ×0.6 (−40% rain history) → 6 bunches
    """
    data = _product(merchant_id, product)
    stock = get_stock(merchant_id, product)

    if requested_qty and requested_qty > 0:
        base = requested_qty
    else:
        shortfall = data["velocity"] * data["decay_days"] - stock
        base = max(1, math.ceil(shortfall * SAFETY_MARGIN))

    rain = get_weather()["rain_prob"]
    modifier = data["rain_modifier"] if rain >= RAINY_THRESHOLD else 1.0
    qty = max(1, math.ceil(base * modifier))
    return min(qty, MAX_ORDER.get(product, 50))


def recommendation(merchant_id: str, product: str, requested_qty: int | None = None) -> dict:
    """Full recommendation payload: quantity + the traceable factor list."""
    data = _product(merchant_id, product)
    weather = get_weather()
    rain = weather["rain_prob"]
    stock = get_stock(merchant_id, product)
    qty = calculate_quantity(merchant_id, product, requested_qty)

    factors = [
        {"source": "velocity", "fact": f"{data['velocity']} {data['unit']}/day avg (90d)"},
        {"source": "weather", "fact": f"{int(rain*100)}% rain expected"},
        {"source": "stock", "fact": f"{stock} {data['unit']} on hand"},
        {"source": "decay", "fact": f"{data['decay_days']}-day shelf life"},
    ]
    if data["rain_modifier"] < 1.0 and rain >= RAINY_THRESHOLD:
        factors.append({"source": "rain_sensitivity",
                        "fact": f"rainy-day sales −{int((1-data['rain_modifier'])*100)}% (history)"})
    if requested_qty:
        factors.append({"source": "merchant_request", "fact": f"she asked for {requested_qty} {data['unit']}"})

    return {
        "product": product,
        **_localized(data),
        "requested": requested_qty,
        "recommended_qty": qty,
        "unit": data["unit"],
        "factors": factors,
        "supplier": data["supplier"],
        "price_per_unit": data["price_per_unit"],
        "total_inr": qty * data["price_per_unit"],
        "stock_on_hand": stock,
        "rain_prob": rain,
        "unit_price_inr": data["price_per_unit"],
        "weather_source": weather.get("source"),
        "engine": "deterministic",
    }


def validate_order(merchant_id: str, product: str, qty: int, supplier: str) -> tuple[bool, str]:
    """Hard validation rules — applied again by n8n before execution."""
    if product not in CATALOG.get(merchant_id, {}):
        return False, "unknown_product"
    if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
        return False, "invalid_quantity"
    if qty > MAX_ORDER.get(product, 50):
        return False, "exceeds_max"
    if supplier != CATALOG[merchant_id][product]["supplier"]:
        return False, "unknown_supplier"
    return True, "approved"
