import json, urllib.parse
import orders_sync as o
code = "1143386126"
q = urllib.parse.urlencode({"filter[orders][code]": code})
d = o.http("GET", f"{o.KASPI_API}/orders?{q}", o.kaspi_headers())
for x in d.get("data") or []:
    a = x.get("attributes") or {}
    safe = {k: v for k, v in a.items() if k not in ("customer", "deliveryAddress", "originAddress", "recipient")}
    print("K|", json.dumps(safe, ensure_ascii=False, default=str)[:1500])
    dms = o.ms_order_demands(f"kaspi-{code}", code)
    print("МС: заказ", bool(o.ms_existing(f"kaspi-{code}")), "отгрузок", len(dms), "возврат", any(o.ms_has_return(m) for m in dms))
if not d.get("data"):
    print("не найден по code:", json.dumps(d, ensure_ascii=False)[:500])
