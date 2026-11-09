"""Какие наименования товаров МС менялись за последние N дней (аудит по каждому изменённому товару)."""
import datetime, os, urllib.parse
from orders_sync import MS_API, http

DAYS = int(os.environ.get("DAYS") or 21)
since = (datetime.datetime.utcnow() + datetime.timedelta(hours=3) - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%d %H:%M:%S")
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
prods, off = [], 0
while True:
    f = urllib.parse.quote(f"updated>={since}", safe="")
    rows = http("GET", f"{MS_API}/entity/product?filter={f}&limit=1000&offset={off}", H).get("rows") or []
    prods += rows
    if len(rows) < 1000:
        break
    off += 1000
print(f"с {since} (МСК): изменённых товаров {len(prods)}", flush=True)
found = []
for p in prods:
    eo = 0
    while True:
        ev = http("GET", f"{p['meta']['href']}/audit?limit=100&offset={eo}", H).get("rows") or []
        for e in ev:
            if (e.get("moment") or "") < since:
                continue
            nd = (e.get("diff") or {}).get("name")
            if nd:
                found.append((e["moment"][:16], (e.get("uid") or "").split("@")[0], p.get("code"),
                              nd.get("oldValue"), nd.get("newValue")))
        if len(ev) < 100 or (ev and (ev[-1].get("moment") or "") < since):
            break
        eo += 100
print(f"смен наименования: {len(found)}")
for r in sorted(found):
    print("NAME|" + "|".join(str(x) for x in r))
