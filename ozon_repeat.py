"""Ozon: есть ли среди свежих заказов Top Stay покупатели, которые раньше заказывали и возвращали.
В лог НЕ выводятся персональные данные — только хэш покупателя (8 символов) и номера отправлений."""
import hashlib, json, os, re
from datetime import datetime, timedelta, timezone
import orders_sync as o

o.DAYS = int(os.environ.get("LOOKBACK", "180"))
H = o.ozon_headers()

def fbs_full():
    now = datetime.now(timezone.utc); out, cursor = [], ""
    for _ in range(200):
        body = {"sort_dir": "asc", "cursor": cursor, "limit": 100,
                "filter": {"since": o.iso(now - timedelta(days=o.DAYS)), "to": o.iso(now)},
                "with": {"analytics_data": True}}
        d = o.http("POST", f"{o.OZON_API}/v4/posting/fbs/list", H, body)
        res = d.get("result") if isinstance(d.get("result"), dict) else d
        out += res.get("postings") or []
        if not res.get("has_next"): return out
        cursor = res.get("cursor") or ""
    return out

posts = fbs_full()
print("отправлений FBS:", len(posts))
# какие поля о покупателе вообще приходят
keys = {}
for p in posts:
    for k in ("customer", "addressee", "analytics_data"):
        v = p.get(k)
        if v: keys.setdefault(k, set()).update(x for x, y in v.items() if y) if isinstance(v, dict) else keys.setdefault(k, set()).add(type(v).__name__)
print("поля покупателя:", {k: sorted(v) for k, v in keys.items()})

def ident(p):
    c = p.get("customer") or {}
    a = p.get("addressee") or {}
    parts = [c.get("name"), c.get("phone"), a.get("name"), a.get("phone"),
             ((c.get("address") or {}).get("address_tail"))]
    parts = [re.sub(r"\W", "", str(x).lower()) for x in parts if x]
    if not parts:  # FBS: Ozon не отдаёт данных покупателя — берём номер покупателя (первая часть номера отправления)
        return "покуп." + p["posting_number"].split("-")[0]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]

# возвраты: из МойСклад — отгрузки Ozon с пометкой «возврат» в комментарии
ret = set()
for d in o.http("GET", f"{o.MS_API}/entity/demand?filter=agent={o.MS_API}/entity/counterparty/{o.AGENT_OZON}&limit=1000", o.ms_headers()).get("rows") or []:
    desc = (d.get("description") or "")
    if re.search(r"возвр|вовзр", desc, re.I):
        ret.add(desc.splitlines()[0].strip())
# и из Ozon, если метод отвечает
try:
    lid = 0
    for _ in range(20):
        r = o.http("POST", f"{o.OZON_API}/v1/returns/list", H, {"filter": {}, "limit": 500, "last_id": lid})
        rows = r.get("returns") or []
        for x in rows:
            if x.get("posting_number"): ret.add(x["posting_number"])
        if not r.get("has_next") or not rows: break
        lid = rows[-1].get("id") or 0
except Exception as e:
    print("Ozon returns/list:", str(e)[:150])
print("возвратных отправлений:", len(ret))

ts = {l.split(",")[0] for l in open("ozon_mapping.csv") if re.match(r"S[EQTK]", l)}
by = {}
for p in posts:
    h = ident(p)
    if h: by.setdefault(h, []).append(p)
recent = [p for p in posts if (p.get("in_process_at") or "") >= o.iso(datetime.now(timezone.utc) - timedelta(days=int(os.environ.get("RECENT", "14"))))
          and any(x.get("offer_id") in ts for x in p.get("products") or [])]
print("свежих заказов Top Stay:", len(recent), "| с данными покупателя:", sum(1 for p in recent if ident(p)))
for p in recent:
    h = ident(p)
    prev = [q for q in by.get(h, []) if q["posting_number"] != p["posting_number"]] if h else []
    prev_ret = [q["posting_number"] for q in prev if q["posting_number"] in ret]
    pref = p["posting_number"].split("-")[0]
    prev_ret = sorted(set(prev_ret) | {r for r in ret if r.split("-")[0] == pref and r != p["posting_number"]})
    city = (p.get("analytics_data") or {}).get("city") or ""
    print("TS|" + "|".join([p["posting_number"], (p.get("in_process_at") or "")[:10], p.get("status", ""),
          ",".join(x.get("offer_id", "") for x in p.get("products") or []), h or "нет данных",
          str(len(prev)), ",".join(prev_ret) or "-", city]))
