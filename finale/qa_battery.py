"""HarvestWise regression battery — run with the API up: python qa_battery.py
Requires: uvicorn api.main:app on :8000. Exits 1 on any failure."""
import sys, json, httpx
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = "http://localhost:8000"
ok = fail = 0

def check(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  PASS {name} {detail}")
    else: fail += 1; print(f"  FAIL {name} {detail}")

print("== 1. health ==")
h = httpx.get(f"{B}/health", timeout=10).json()
check("health", h.get("status") == "ok", str(h))

print("== 2. intent battery ==")
cases = [
    ("Tamil numeric", "நாளை 20 கிலோ தக்காளி, 10 கொத்து கொத்தமல்லி", {"tomato": 20, "coriander": 10}),
    ("English crates", "send 3 crates tomato and 10 bunches coriander", {"tomato": 60, "coriander": 10}),
    ("decline", "இல்ல வேண்டாம்", None),
    ("ambiguous", "தக்காளி அனுப்பு", {"tomato": None}),
]
for name, t, expect in cases:
    r = httpx.post(f"{B}/intent", json={"transcript": t}, timeout=10).json()
    if expect is None:
        check(name, r["intent"] in ("decline", "out_of_scope"), r["intent"])
    else:
        check(name, r.get("products") == expect and r["intent"] == "create_restock_order", str(r.get("products")))

print("== 3. engine invariants ==")
r = httpx.post(f"{B}/rec/basket", json={"products": {"tomato": 20, "coriander": 10}}, timeout=10).json()
it = {i["product"]: i for i in r["items"]}
check("tomato 20", it["tomato"]["recommended_qty"] == 20)
check("coriander 6", it["coriander"]["recommended_qty"] == 6)
check("basket 546", r["basket_total_inr"] == 546, f"got {r['basket_total_inr']}")
check("rain factor 78%", any("78" in f["fact"] for f in it["tomato"]["factors"]))
r2 = httpx.post(f"{B}/rec", json={"product": "tomato", "requested_qty": None}, timeout=10).json()
check("formula fallback 20", r2["recommended_qty"] == 20, f"got {r2['recommended_qty']} ((14*2-12)*1.25)")
check("no demo_map in engine", "demo_map" not in open("engine/restock.py", encoding="utf-8").read())

print("== 4. approve/dispatch security ==")
items = [{"product": "tomato", "qty": 20}, {"product": "coriander", "qty": 6}]
a = httpx.post(f"{B}/voice/approve", json={"transcript": "சரி", "items": items}, timeout=10).json()
tok = {i["product"]: i["approval_token"] for i in a["items"]}
check("approve", a["status"] == "approved")
d = httpx.post(f"{B}/dispatch", json={"approval_token": tok["tomato"], "total_inr": 360}, timeout=15).json()
check("dispatch", d.get("status") == "dispatched", "| n8n:" + str(d.get("record", {}).get("n8n")))
check("replay refused", httpx.post(f"{B}/dispatch", json={"approval_token": tok["tomato"]}, timeout=10).json().get("status") == "duplicate_ignored")
check("bogus refused", httpx.post(f"{B}/dispatch", json={"approval_token": "bogus"}, timeout=10).json().get("status") == "failed")
check("deny gate", httpx.post(f"{B}/voice/approve", json={"transcript": "இல்ல", "items": items}, timeout=10).json().get("status") == "declined")

print("== 5. graceful errors ==")
check("400 unknown product", httpx.post(f"{B}/rec", json={"product": "mango"}, timeout=10).status_code == 400)
check("STT no-file 422", httpx.post(f"{B}/stt", timeout=10).status_code == 422)

print("== 6. multi-merchant support ==")
try:
    r = httpx.post(f"{B}/rec", json={"product": "onion", "requested_qty": 10}, timeout=10).json()
    check("onion in lakshmi catalog", r.get("product") == "onion" and r.get("recommended_qty") <= 10, str(r))
    r = httpx.post(f"{B}/rec", json={"product": "potato", "requested_qty": 10, "merchant_id": "rahul"}, timeout=10).json()
    check("potato in rahul catalog", r.get("product") == "potato" and r.get("recommended_qty") <= 10, str(r))
except Exception as e:
    check("multi-merchant catalog", False, str(e))

print("== 7. STT round-trip ==")
try:
    wav = open("tts_ta.wav", "rb").read()
    s = httpx.post(f"{B}/stt", files={"file": ("t.wav", wav, "audio/wav")}, timeout=40)
    check("STT 200", s.status_code == 200)
    tr = s.json().get("transcript", "")
    check("STT transcript Tamil", "தக்காளி" in tr, tr[:50])
    pi = httpx.post(f"{B}/intent", json={"transcript": tr}, timeout=10).json()
    check("STT->intent tomato=20", pi.get("products", {}).get("tomato") == 20, str(pi.get("products")))
except FileNotFoundError:
    check("STT fixture (tts_ta.wav)", False, "run test_voice.py first to generate the fixture")

print("== 8. cross-file consistency ==")
check("rain 0.78 in engine", "0.78" in open("engine/restock.py", encoding="utf-8").read())
check("multi-merchant catalog", "rahul" in open("engine/restock.py", encoding="utf-8").read())
check("multi-product catalog", "onion" in open("engine/restock.py", encoding="utf-8").read())
mem = json.load(open("cognee/memory.json", encoding="utf-8"))["lakshmi"]
check("memory 78%+546", "78%" in mem["expected_rain"] and "546" in mem["recommendation"])
check("health stable x3", all(httpx.get(f"{B}/health", timeout=10).json().get("status") == "ok" for _ in range(3)))

print(f"\n=== RESULT: {ok} passed, {fail} failed ===")
sys.exit(1 if fail else 0)
