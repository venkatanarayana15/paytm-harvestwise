import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console safe
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Single source of truth lives in engine/restock.py CATALOG — this regenerates
# data/seed.json from it so UI copies and docs never drift.
from engine.restock import BASE_DIR, CATALOG, WEATHER  # noqa: E402

data = {"lakshmi": CATALOG["lakshmi"], "rahul": CATALOG["rahul"], "weather": WEATHER}

out_dir = os.path.join(BASE_DIR, "data")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "seed.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Seed data written to {out_path} (synced from engine CATALOG)")
print("  weather:", WEATHER["tomorrow"])
for merchant, products in CATALOG.items():
    for p, d in products.items():
        print(f"  {merchant}/{p}: {d['velocity']}/{d['unit']}/day, stock {d['current_stock']}, "
              f"rain_mod {d['rain_modifier']}, ₹{d['price_per_unit']}/{d['unit']}")
