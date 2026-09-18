"""Armor-fix verification, phase A (server must be running).
Proves: (1) client total_inr is ignored & corrected, (2) unit-honest quantity fields,
and issues an approval token that phase B will dispatch AFTER a server restart."""
import sys, json, httpx
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = "http://127.0.0.1:8000"
ok = 0
fail = 0
def check(name, cond, detail=""):
    global ok, fail
    print(("  PASS " if cond else "  FAIL ") + name + (("  | " + detail) if detail else ""))
    if cond: ok += 1
    else: fail += 1

print("== armor fix 1: client total_inr is corrected server-side ==")
httpx.post(B + "/demo/reset", timeout=20)
r = httpx.post(B + "/rec/basket", json={"products": {"tomato": 20, "coriander": 10}}, timeout=20).json()
total = {i["product"]: i["total_inr"] for i in r["items"]}
items = [{"product": "tomato", "qty": 20}, {"product": "coriander", "qty": 6}]
a = httpx.post(B + "/voice/approve", json={"transcript": "சரி", "items": items}, timeout=20).json()
tok = {i["product"]: i["approval_token"] for i in a["items"]}

# send a corrupt total for tomato (client claims ₹1 instead of the true ₹360)
d = httpx.post(B + "/dispatch", json={"approval_token": tok["tomato"], "total_inr": 1}, timeout=25).json()
rec = d.get("record", {})
check("dispatch succeeds despite lying client", d.get("status") == "dispatched", d.get("status"))
check("total_inr corrected to 360", rec.get("total_inr") == 360, str(rec.get("total_inr")))
check("correction is labeled", "server-recomputed" in str(rec.get("total_inr_source")), str(rec.get("total_inr_source")))
check("client claim preserved for audit", rec.get("client_total_inr_ignored") == 1, str(rec.get("client_total_inr_ignored")))
check("ledger uses corrected total", json.load(open("../finale/data/runtime_state.json", encoding="utf-8"))["orders"][-1]["total_inr"] == 360)

print("== armor fix 2: unit-honest quantity fields ==")
d2 = httpx.post(B + "/dispatch", json={"approval_token": tok["coriander"], "total_inr": 999}, timeout=25).json()
rec2 = d2.get("record", {})
check("coriander dispatched", d2.get("status") == "dispatched")
check("quantity + unit present", rec2.get("quantity") == 6 and rec2.get("unit") == "bunch",
      f"{rec2.get('quantity')} {rec2.get('unit')}")
check("legacy quantity_kg kept for n8n", rec2.get("quantity_kg") == 6)
check("total corrected here too (999->186)", rec2.get("total_inr") == 186 and rec2.get("client_total_inr_ignored") == 999,
      str(rec2.get("total_inr")))

print("== armor fix 3 (stage): token issued now, dispatched after restart ==")
a3 = httpx.post(B + "/voice/approve", json={"transcript": "சரி", "items": [{"product": "spinach", "qty": 5}]}, timeout=20).json()
check("spinach token issued", a3.get("status") == "approved")
open("pending_token.json", "w").write(json.dumps(a3["items"][0]))
print(f"  staged token for {a3['items'][0]['product']} qty {a3['items'][0]['quantity_kg']}")

print(f"\nPHASE A: {ok} pass, {fail} fail")
sys.exit(1 if fail else 0)
