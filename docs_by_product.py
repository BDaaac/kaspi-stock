"""Документы МС, где встречается товар (по id): приёмки, оприходования, отгрузки, перемещения, списания, инвентаризации, заказы."""
import os, urllib.parse
from orders_sync import MS_API, http
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
for pid in os.environ["IDS"].split(","):
    pid = pid.strip()
    p = http("GET", f"{MS_API}/entity/product/{pid}", H)
    print(f"== {p.get('code')} | {p.get('pathName')} | архив: {p.get('archived')}")
    href = f"{MS_API}/entity/product/{pid}"
    for kind in ("supply", "enter", "demand", "move", "loss", "inventory", "customerorder", "salesreturn", "purchasereturn"):
        f = urllib.parse.quote(f"assortment={href}", safe="")
        try:
            rows = http("GET", f"{MS_API}/entity/{kind}?filter={f}&limit=100", H).get("rows") or []
        except Exception as e:
            print(f"   {kind}: ошибка {str(e)[:100]}"); continue
        for d in rows:
            pos = http("GET", d["meta"]["href"] + "/positions?limit=1000", H).get("rows") or []
            q = sum(x.get("quantity", 0) for x in pos if x["assortment"]["meta"]["href"].endswith(pid))
            print(f"   {kind} {d.get('name')} от {d.get('moment','')[:10]} проведён={d.get('applicable')} кол-во={q}")
