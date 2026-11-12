"""Записать неснижаемый остаток в карточки МС по min_stock_plan.json ([{id, code, q}])."""
import json, os, time
from orders_sync import MS_API, http
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip", "Content-Type": "application/json"}
plan = json.load(open("min_stock_plan.json"))
if os.environ.get("VERIFY"):
    bad = 0
    for x in plan:
        v = http("GET", f"{MS_API}/entity/product/{x['id']}", H).get("minimumBalance") or 0
        if abs(v - x["q"]) > 0.001:
            bad += 1; print("НЕ СОВПАДАЕТ", x["code"], "план", x["q"], "в МС", v)
    print(f"проверено {len(plan)}, расхождений {bad}")
    raise SystemExit
def meta(pid): return {"href": f"{MS_API}/entity/product/{pid}", "type": "product", "mediaType": "application/json"}
# проба на первой позиции: какое поле принимает аккаунт
p0 = plan[0]
try:
    http("PUT", f"{MS_API}/entity/product/{p0['id']}", H, {"minimumStock": {"type": "ALL_STORES_SAME", "quantity": p0["q"]}})
    field = "minimumStock"
except Exception as e:
    print("minimumStock не принят:", str(e)[:200])
    http("PUT", f"{MS_API}/entity/product/{p0['id']}", H, {"minimumBalance": p0["q"]})
    field = "minimumBalance"
print("поле:", field)
def body(x):
    return {"meta": meta(x["id"]), **({"minimumStock": {"type": "ALL_STORES_SAME", "quantity": x["q"]}} if field == "minimumStock" else {"minimumBalance": x["q"]})}
ok = 1
for i in range(1, len(plan), 100):
    chunk = plan[i:i + 100]
    for a in range(4):
        try:
            http("POST", f"{MS_API}/entity/product", H, [body(x) for x in chunk]); ok += len(chunk); break
        except Exception as e:
            if a == 3: print("ОШИБКА пачки", i, str(e)[:300])
            time.sleep(10)
print(f"записано {ok} из {len(plan)}")
chk = http("GET", f"{MS_API}/entity/product/{plan[-1]['id']}", H)
print("проверка", plan[-1]["code"], "план", plan[-1]["q"], "в МС", chk.get("minimumStock"), chk.get("minimumBalance"))
