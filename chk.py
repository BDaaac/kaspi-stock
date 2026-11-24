import json, urllib.parse
import orders_sync as o
code = "1161977923"
q = urllib.parse.urlencode({"filter[orders][code]": code})
for x in o.http("GET", f"{o.KASPI_API}/orders?{q}", o.kaspi_headers()).get("data") or []:
    a = x.get("attributes") or {}
    kd = a.get("kaspiDelivery") or {}
    print("KASPI", a.get("state"), a.get("status"), a.get("cancellationReason"), "| курьеру:", bool(kd.get("courierTransmissionDate")), "| returnedToWarehouse:", kd.get("returnedToWarehouse"), "| сумма", a.get("totalPrice"))
co = o.ms_existing(f"kaspi-{code}")
if co:
    co = o.http("GET", co["meta"]["href"], o.ms_headers())
    st = o.http("GET", co["state"]["meta"]["href"], o.ms_headers()).get("name") if co.get("state") else None
    print("MS ORDER", co.get("name"), "статус:", st, "проведён:", co.get("applicable"), "резерв:", any(p.get("reserve") for p in (o.http("GET", co["positions"]["meta"]["href"], o.ms_headers()).get("rows") or [])),
          "отгрузок:", len(co.get("demands") or []), "оплачено:", co.get("payedSum", 0) / 100)
    for d in co.get("demands") or []:
        dd = o.http("GET", d["meta"]["href"], o.ms_headers())
        print("DEMAND", dd.get("name"), "возвратов:", len(dd.get("returns") or []))
else:
    print("MS ORDER нет")
