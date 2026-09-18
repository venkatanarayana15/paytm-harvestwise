import json, os, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console safe

# Lightweight Cognee mock — stores causal memory as JSON (real Cognee cloud is
# wired via /cognee/recall in api/main.py; this is the labeled local fallback).
MEM_PATH = "cognee/memory.json"

def seed():
    memory = {
        "lakshmi": {
            "sells": "tomato, coriander",
            "recent_sales_velocity": "+18% vs last week (tomato 14kg/day avg)",
            "current_stock": "12 kg tomato, 6 bunches coriander on hand",
            "expected_rain": "78% tomorrow (IMD, Basavanagudi)",
            "shelf_life": "tomato 2 days, coriander 1 day at 85% humidity",
            "rain_sensitivity": "coriander rainy-day sales -40% (90d history); tomato holds",
            "recommendation": "20 kg tomato (requested 3 crates) + 6 bunches coriander (10 asked, rain-adjusted) — basket ₹546",
            "cause_chain": [
                "Lakshmi -> sells -> Tomato, Coriander",
                "Tomato -> velocity -> +18% (14kg/day)",
                "Coriander -> rainy-day sales -> -40%",
                "Stock -> 12kg tomato, 6 bunches coriander",
                "Tomorrow -> rain -> 78%",
                "Engine -> tomato 20kg x1.0, coriander 10x0.6=6 bunches",
                "Basket -> 360 + 186 = Rs.546 -> approved & dispatched"
            ],
            "updated": datetime.datetime.now().isoformat()
        }
    }
    os.makedirs("cognee", exist_ok=True)
    with open(MEM_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)
    print(f"Seeded {MEM_PATH}")
    for line in memory["lakshmi"]["cause_chain"]:
        print("  ", line)
    return memory

def search(query: str):
    if not os.path.exists(MEM_PATH):
        return {"error": "no memory, run seed() first"}
    with open(MEM_PATH, encoding="utf-8") as f:
        mem = json.load(f)
    hits = []
    for k, v in mem["lakshmi"].items():
        if query.lower() in str(v).lower() or query.lower() in k:
            hits.append({k: v})
    return hits if hits else mem["lakshmi"]

if __name__ == "__main__":
    seed()
    print("\nQuery 'why 546':", search("546"))
