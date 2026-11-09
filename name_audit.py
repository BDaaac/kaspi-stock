"""Какие наименования товаров МС менялись за последние N дней (журнал аудита, поле name)."""
import datetime, json, os, urllib.parse
from orders_sync import MS_API, http

DAYS = int(os.environ.get("DAYS") or 21)
since = (datetime.datetime.utcnow() + datetime.timedelta(hours=5) - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%d %H:%M:%S")
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
flt = urllib.parse.quote(f"moment>={since};entityType=product;eventType=update", safe="")
found, off, ctxs = [], 0, 0
while True:
    d = http("GET", f"{MS_API}/audit?filter={flt}&limit=100&offset={off}", H)
    rows = d.get("rows") or []
    for c in rows:
        ctxs += 1
        eo = 0
        while True:
            ev = http("GET", f"{MS_API}/audit/{c['id']}/events?limit=100&offset={eo}", H).get("rows") or []
            for e in ev:
                diff = e.get("diff") or {}
                if "name" in diff:
                    nd = diff["name"]
                    found.append((e.get("moment", "")[:16], (e.get("uid") or "").split("@")[0],
                                  nd.get("oldValue"), nd.get("newValue")))
            if len(ev) < 100:
                break
            eo += 100
    if len(rows) < 100:
        break
    off += 100
print(f"с {since}: контекстов изменений товаров {ctxs}, смен наименования {len(found)}")
for m, u, o, n in sorted(found):
    print(f"NAME|{m}|{u}|{o}|{n}")
