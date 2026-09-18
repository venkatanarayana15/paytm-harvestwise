import math

# ─── Catalog: seeded demo data (labeled as such on every screen) ───────────
# price_per_unit: tomato ₹18/kg · coriander ₹31/bunch (mandi price, seeded —
# 6×31=₹186 + 20×18=₹360 = ₹546 basket, matches deck slide 5)
CATALOG = {
    "lakshmi": {
        "tomato": {
            "name_tn": "தக்காளி",
            "unit": "kg",
            "velocity": 14,
            "decay_days": 2,
            "current_stock": 12,
            "rain_modifier": 1.0,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 18,
        },
        "coriander": {
            "name_tn": "கொத்தமல்லி",
            "unit": "bunch",
            "velocity": 8,
            "decay_days": 1,
            "current_stock": 6,
            "rain_modifier": 0.6,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 31,
        },
        "onion": {
            "name_tn": "வெங்காயம்",
            "unit": "kg",
            "velocity": 10,
            "decay_days": 5,
            "current_stock": 15,
            "rain_modifier": 0.9,
            "supplier": "Basavanagudi Mandi",
            "price_per_unit": 22,
        },
        "spinach": {
            "name_tn": "முரைக்கீரை",
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
            "name_tn": "तामाटर",
            "unit": "kg",
            "velocity": 12,
            "decay_days": 2,
            "current_stock": 10,
            "rain_modifier": 1.0,
            "supplier": "KR Market",
            "price_per_unit": 20,
        },
        "potato": {
            "name_tn": "आलू",
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

# Seeded weather (IMD-shaped, demo-reproducible)
WEATHER = {"tomorrow": {"rain_prob": 0.78, "humidity": 85}}


def get_weather(city: str = "basavanagudi") -> dict:
    """Fetch live weather (Open-Meteo) — falls back to seeded if unavailable."""
    try:
        import httpx
        # Bangalore coords; change to city-specific if needed
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": 12.9716, "longitude": 77.5946, "daily": "precipitation_probability_max", "timezone": "Asia%2FCalcutta", "forecast_days": 1},
            timeout=5, verify=False
        )
        if r.status_code == 200:
            data = r.json()
            return {"rain_prob": data["daily"]["precipitation_probability_max"][0] / 100, "humidity": 85}
    except Exception as e:
        pass
    return WEATHER["tomorrow"]
RAINY_THRESHOLD = 0.5
SAFETY_MARGIN = 1.25   # restock buffer: cover demand shortfall with headroom

MAX_ORDER = {"tomato": 100, "coriander": 100, "onion": 100, "spinach": 100, "potato": 100}


def calculate_quantity(merchant_id: str, product: str, requested_qty: int | None = None) -> int:
    """Deterministic restocking engine — LLM never decides quantity.

    Formula (every constant documented):
      base      = requested_qty if stated by merchant,
                  else ceil((velocity × decay_days − current_stock) × SAFETY_MARGIN)
      rainy     = rain_prob ≥ RAINY_THRESHOLD
      quantity  = ceil(base × rain_modifier)   [rain_modifier per product]
    Calibrated outputs for the demo command (tomato 20kg, coriander 10→6):
      tomato    base=20 (requested 3 crates ≈ 20 kg) ×1.0 → 20 kg
      coriander base=10 (requested) ×0.6 (−40% rain history) → 6 bunches
    """
    data = CATALOG.get(merchant_id, {}).get(product)
    if not data:
        raise KeyError(f"Unknown product: {product}")

    if requested_qty and requested_qty > 0:
        base = requested_qty
    else:
        shortfall = data["velocity"] * data["decay_days"] - data["current_stock"]
        base = max(1, math.ceil(shortfall * SAFETY_MARGIN))

    weather = get_weather()
    rain = weather["rain_prob"]
    modifier = data["rain_modifier"] if rain >= RAINY_THRESHOLD else 1.0
    qty = max(1, math.ceil(base * modifier))
    return min(qty, MAX_ORDER.get(product, 50))


def recommendation(merchant_id: str, product: str, requested_qty: int | None = None) -> dict:
    """Full recommendation payload: quantity + the traceable factor list."""
    data = CATALOG.get(merchant_id, {}).get(product)
    if not data:
        raise KeyError(f"Unknown product: {product}")
    weather = get_weather()
    rain = weather["rain_prob"]
    base = requested_qty if requested_qty else None
    qty = calculate_quantity(merchant_id, product, requested_qty)

    factors = [
        {"source": "velocity", "fact": f"{data['velocity']} {data['unit']}/day avg (90d)"},
        {"source": "weather", "fact": f"{int(rain*100)}% rain expected"},
        {"source": "stock", "fact": f"{data['current_stock']} {data['unit']} on hand"},
        {"source": "decay", "fact": f"{data['decay_days']}-day shelf life"},
    ]
    if data["rain_modifier"] < 1.0 and rain >= RAINY_THRESHOLD:
        factors.append({"source": "rain_sensitivity",
                        "fact": f"rainy-day sales −{int((1-data['rain_modifier'])*100)}% (history)"})
    if base:
        factors.append({"source": "merchant_request", "fact": f"she asked for {base} {data['unit']}"})

    return {
        "product": product,
        "requested": requested_qty,
        "recommended_qty": qty,
        "unit": data["unit"],
        "factors": factors,
        "supplier": data["supplier"],
        "price_per_unit": data["price_per_unit"],
        "total_inr": qty * data["price_per_unit"],
    }


def validate_order(merchant_id: str, product: str, qty: int, supplier: str) -> tuple[bool, str]:
    """Hard validation rules — applied again by n8n before execution."""
    if product not in CATALOG.get(merchant_id, {}):
        return False, "unknown_product"
    if not isinstance(qty, int) or qty < 1:
        return False, "invalid_quantity"
    if qty > MAX_ORDER.get(product, 50):
        return False, "exceeds_max"
    if supplier != CATALOG[merchant_id][product]["supplier"]:
        return False, "unknown_supplier"
    return True, "approved"
