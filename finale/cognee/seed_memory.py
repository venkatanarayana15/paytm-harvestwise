"""Local causal-memory seed (labeled fallback for Cognee cloud).

Cognee cloud is the primary store (engine/cognee_client.py: add_text -> cognify
-> recall). This file is the offline fallback the API serves if the cloud is
unreachable, and the human-readable view the dashboard renders.
"""
import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 console safe
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.restock import BASE_DIR, CATALOG  # noqa: E402

MEM_PATH = os.path.join(BASE_DIR, "cognee", "memory.json")


def seed(rain_pct: int = 78):
    tomato = CATALOG["lakshmi"]["tomato"]
    coriander = CATALOG["lakshmi"]["coriander"]
    memory = {
        "lakshmi": {
            "sells": "tomato, coriander, onion, spinach",
            "recent_sales_velocity": f"+18% vs last week (tomato {tomato['velocity']}kg/day avg)",
            "current_stock": "12 kg tomato, 6 bunches coriander, 15 kg onion, 4 bunches spinach on hand",
            "expected_rain": f"{rain_pct}% tomorrow (seeded demo constant; WEATHER_MODE=live fetches IMD/Open-Meteo)",
            "shelf_life": "tomato 2 days, coriander 1 day, onion 5 days, spinach 1 day at 85% humidity",
            "rain_sensitivity": "coriander -40% / spinach -50% / onion -9% rainy-day sales (90d history); tomato holds",
            "recommendation": "20 kg tomato + 6 bunches coriander (10 asked, rain-adjusted) — basket ₹546",
            "cause_chain": [
                "Lakshmi -> sells -> Tomato, Coriander, Onion, Spinach",
                "Tomato -> velocity -> +18% (14kg/day)",
                "Coriander -> rainy-day sales -> -40%",
                "Stock -> 12kg tomato, 6 bunches coriander, 15kg onion",
                f"Tomorrow -> rain -> {rain_pct}%",
                "Engine -> tomato 20kg x1.0, coriander 10x0.6=6 bunches",
                "Basket -> 360 + 186 = Rs.546 -> approved & dispatched",
            ],
            "order_history": [],
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "rahul": {
            "sells": "tomato, potato",
            "recent_sales_velocity": "tomato 12kg/day, potato 15kg/day avg",
            "current_stock": "10 kg tomato, 20 kg potato on hand",
            "expected_rain": f"{rain_pct}% tomorrow (seeded demo constant)",
            "shelf_life": "tomato 2 days, potato 10 days",
            "rain_sensitivity": "potato -5% rainy-day sales (history)",
            "recommendation": "fresh merchant — cold-start via federated patterns",
            "cause_chain": [
                "Rahul -> sells -> Tomato, Potato",
                "KR Market -> festival week -> demand up",
                "Engine -> cold-start federated pattern from similar stalls",
            ],
            "order_history": [],
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        },
    }
    os.makedirs(os.path.dirname(MEM_PATH), exist_ok=True)
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
