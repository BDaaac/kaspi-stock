import orders_sync as o
pn = "0153864531-0060-1"
d = o.http("POST", f"{o.OZON_API}/v3/posting/fbs/get", o.ozon_headers(), {"posting_number": pn})
r = d.get("result") or {}
print("OZ| создан", r.get("in_process_at"), "| отгружен", r.get("shipment_date"), "| доставка", r.get("delivering_date"), "| статус", r.get("status"))
co = o.ms_existing(f"ozon-{pn}")
if co: print("MS| заказ", co.get("name"), co.get("moment"))
for m in o.ms_order_demands(f"ozon-{pn}", pn):
    x = o.http("GET", m["href"], o.ms_headers()); print("MS| отгрузка", x.get("name"), x.get("moment"))
