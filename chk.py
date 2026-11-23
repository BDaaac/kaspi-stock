import orders_sync as o
for m in o.ms_order_demands("kaspi-1143386126", "1143386126"):
    d = o.http("GET", m["href"], o.ms_headers())
    for r in d.get("returns") or []:
        x = o.http("GET", r["meta"]["href"], o.ms_headers())
        print("SR", x.get("name"), x.get("created"), x.get("sum", 0) / 100, "провед." if x.get("applicable") else "черн.", "|", (x.get("description") or "").replace("\n", " / "))
co = o.http("GET", o.ms_existing("kaspi-1143386126")["meta"]["href"], o.ms_headers())
print("ORDER оплачено", co.get("payedSum", 0) / 100)
