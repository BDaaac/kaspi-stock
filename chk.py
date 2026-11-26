import urllib.parse
import orders_sync as o
H = o.ms_headers()
for kind, name in (("demand", "00793"), ("salesreturn", "00076")):
    r = (o.http("GET", f"{o.MS_API}/entity/{kind}?filter=name={name}&expand=positions.assortment", H).get("rows") or [])[0]
    pos = o.http("GET", r["positions"]["meta"]["href"] + "?expand=assortment", H).get("rows") or []
    print(kind, name, r.get("moment", "")[:10], "|", "; ".join(f"{p['assortment'].get('code')}×{p['quantity']:g}" for p in pos), "| сумма", r.get("sum", 0) / 100)
