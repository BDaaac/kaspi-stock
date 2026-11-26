import collections, urllib.parse
import orders_sync as o
H = o.ms_headers()
meta = o.http("GET", f"{o.MS_API}/entity/customerorder/metadata", H)
names = {s["meta"]["href"]: s["name"] for s in meta.get("states") or []}
print("СТАТУСЫ:", list(names.values()))
for ag, nm in ((o.AGENT_OZON, "Ozon"), (o.AGENT_KASPI, "Kaspi")):
    f = urllib.parse.quote(f"agent={o.MS_API}/entity/counterparty/{ag}", safe="")
    rows = o.http("GET", f"{o.MS_API}/entity/customerorder?filter={f}&limit=200&order=moment,desc", H).get("rows") or []
    c = collections.Counter(); ret = collections.Counter()
    for r in rows:
        st = names.get((r.get("state") or {}).get("meta", {}).get("href"), "—")
        c[st] += 1
        if r.get("demands"):
            for d in r["demands"]:
                if o.http("GET", d["meta"]["href"], H).get("returns"):
                    ret[st] += 1; break
    print(nm, "все:", dict(c)); print(nm, "с возвратом:", dict(ret))
