import orders_sync as o
pn = "31594325-0688-1"
for m in o.ms_order_demands(f"ozon-{pn}", pn):
    d = o.http("GET", m["href"], o.ms_headers())
    print("DEMAND", d.get("name"), "returns:", len(d.get("returns") or []))
    for r in d.get("returns") or []:
        x = o.http("GET", r["meta"]["href"], o.ms_headers())
        print("SR", x.get("name"), x.get("created"), x.get("moment"), "провед." if x.get("applicable") else "черн.", "|", (x.get("description") or "").replace("\n", " / "))
