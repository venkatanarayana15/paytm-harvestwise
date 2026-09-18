import json, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console safe

# Single source of truth lives in engine/restock.py CATALOG — this regenerates
# data/seed.json from it so UI copies and docs never drift.
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.restock import CATALOG, WEATHER

data = {"lakshmi": CATALOG["lakshmi"], "weather": WEATHER}

os.makedirs("data", exist_ok=True)
with open("data/seed.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Seed data written to data/seed.json (synced from engine CATALOG)")
print("  weather:", WEATHER["tomorrow"])
for p, d in CATALOG["lakshmi"].items():
    print(f"  {p}: {d['velocity']}/{d['unit']}/day, stock {d['current_stock']}, rain_mod {d['rain_modifier']}, ₹{d['price_per_unit']}/{d['unit']}")