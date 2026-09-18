"""Armor-fix verification, phase B (run AFTER restarting the server).
Dispatches the token staged by phase A — if it works, approval tokens survive
a server restart (armor fix 3)."""
import sys, json, httpx
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = "http://127.0.0.1:8000"
ok = fail = 0
def check(name, cond, detail=""):
    global ok, fail
    print(("  PASS " if cond else "  FAIL ") + name + (("  | " + detail) if detail else ""))
    if not cond: fail += 1

staged = json.load(open("pending_token.json"))
token = staged["approval_token"]

print("== armor fix 3: approval token survives server restart ==")
d = httpx.post(B + "/dispatch", json={"approval_token": token, "total_inr": 90}, timeout=25).json()
rec = d.get("record", {})
check("staged token accepted after restart", d.get("status") == "dispatched", d.get("status"))
check("correct product (spinach)", rec.get("product") == "spinach", str(rec.get("product")))
check("total server-recomputed (5x18=90)", rec.get("total_inr") == 90, str(rec.get("total_inr")))
replay = httpx.post(B + "/dispatch", json={"approval_token": token}, timeout=20).json()
check("replay still refused", replay.get("status") == "duplicate_ignored", replay.get("status"))

print("== armor fix 4: reset trims memory audit trail ==")
mem = httpx.get(B + "/memory", timeout=10).json()["lakshmi"]
check("history accumulated from phase A", len(mem.get("order_history", [])) >= 2, str(len(mem.get("order_history", []))))
rz = httpx.post(B + "/demo/reset", timeout=20).json()
check("reset reports trimmed count", rz.get("memory_orders_trimmed", 0) >= 2, str(rz.get("memory_orders_trimmed")))
mem2 = httpx.get(B + "/memory", timeout=10).json()["lakshmi"]
check("order_history empty after reset", mem2.get("order_history") == [], str(mem2.get("order_history")))
check("last_order cleared", not mem2.get("last_order"), str(mem2.get("last_order")))
check("inventory still reset", httpx.get(B + "/state", timeout=10).json()["stock_on_hand"]["tomato"] == 12)

print(f"\nPHASE B: {ok} pass, {fail} fail")
sys.exit(1 if fail else 0)
