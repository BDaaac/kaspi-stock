"""Диагностика перед автоматическими возвратами (без персональных данных в логе)."""
import collections, hashlib, urllib.parse
from datetime import datetime, timedelta, timezone
import orders_sync as o

H = o.ms_headers()
# 1. Как сейчас оформляются возвраты в МС
for name, ag in (("Ozon", o.AGENT_OZON), ("Kaspi", o.AGENT_KASPI)):
    f = urllib.parse.quote(f"agent={o.MS_API}/entity/counterparty/{ag}", safe="")
    rows = o.http("GET", f"{o.MS_API}/entity/salesreturn?filter={f}&limit=100&order=moment,desc", H).get("rows") or []
    print(f"МС возвраты покупателя {name}: {len(rows)}")
    for r in rows[:15]:
        print("  SR|", r.get("name"), r.get("moment", "")[:10], "провед." if r.get("applicable") else "черн.",
              "демand" if r.get("demand") else "без отгрузки", "|", (r.get("description") or "").replace("\n", " / ")[:80])
# 2. Kaspi: работает ли период больше 14 дней и какие статусы в архиве
now = datetime.now(timezone.utc)
def kq(state, d1, d2, page=0):
    q = urllib.parse.urlencode({"page[number]": page, "page[size]": 100, "filter[orders][state]": state,
        "filter[orders][creationDate][$ge]": int(d1.timestamp()*1000), "filter[orders][creationDate][$le]": int(d2.timestamp()*1000)})
    return o.http("GET", f"{o.KASPI_API}/orders?{q}", o.kaspi_headers())
for days in (14, 30, 90):
    try:
        d = kq("ARCHIVE", now - timedelta(days=days), now)
        print(f"Kaspi ARCHIVE {days} дн: OK, строк {len(d.get('data') or [])}, meta {d.get('meta')}")
    except Exception as e:
        print(f"Kaspi ARCHIVE {days} дн: ошибка {str(e)[:200]}")
st = collections.Counter(); keys = set(); cust = collections.Counter(); ret = []
end = now
for _ in range(13):  # ~180 дней окнами по 14
    beg = end - timedelta(days=14)
    for state in ("ARCHIVE", "KASPI_DELIVERY", "DELIVERY", "PICKUP"):
        page = 0
        while True:
            try: d = kq(state, beg, end, page)
            except Exception as e: print("ошибка", state, str(e)[:120]); break
            rows = d.get("data") or []
            for x in rows:
                a = x.get("attributes") or {}
                st[(state, a.get("status"))] += 1
                c = a.get("customer") or {}
                keys |= set(k for k, v in c.items() if v)
                cid = hashlib.sha256(str(c.get("id") or c.get("cellPhone")).encode()).hexdigest()[:8]
                cust[cid] += 1
                if "RETURN" in str(a.get("status")):
                    ret.append((a.get("code"), a.get("status"), datetime.fromtimestamp((a.get("creationDate") or 0)/1000).date(), cid,
                                (a.get("kaspiDelivery") or {}).get("returnedToWarehouse") , sorted(k for k in a if "eturn" in k)))
            if len(rows) < 100: break
            page += 1
    end = beg
print("Kaspi статусы за ~180 дн:", dict(st))
print("поля customer:", sorted(keys))
print("покупателей:", len(cust), "повторных:", sum(1 for v in cust.values() if v > 1))
for r in ret: print("KR|", *r)
