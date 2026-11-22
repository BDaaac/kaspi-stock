"""Диагностика полей возвратов (без персональных данных)."""
import collections, hashlib, json, urllib.parse
from datetime import datetime, timedelta, timezone
import orders_sync as o
H = o.ozon_headers()
r = o.http("POST", f"{o.OZON_API}/v1/returns/list", H, {"filter": {}, "limit": 500, "last_id": 0})
rows = r.get("returns") or []
print("has_next", r.get("has_next"), "rows", len(rows), "ids уникальных", len({x.get("id") for x in rows}))
x = rows[-1]
print("visual:", json.dumps(x.get("visual"), ensure_ascii=False))
print("logistic:", json.dumps(x.get("logistic"), ensure_ascii=False))
print("product:", json.dumps(x.get("product"), ensure_ascii=False)[:400])
print("exemplars:", json.dumps(x.get("exemplars"), ensure_ascii=False)[:300])
c = collections.Counter(x.get("posting_number") for x in rows)
for pn, n in c.most_common(4):
    ids = [y.get("id") for y in rows if y.get("posting_number") == pn]
    print("P|", pn, n, "ids:", len(set(ids)), [ (y.get("product") or {}).get("quantity") for y in rows if y.get("posting_number") == pn])
# Kaspi: отменённые/возвращённые за 56 дней
now = datetime.now(timezone.utc); end = now
ids = collections.Counter()
for _ in range(4):
    beg = end - timedelta(days=14)
    q = urllib.parse.urlencode({"page[number]": 0, "page[size]": 100, "filter[orders][state]": "ARCHIVE",
        "filter[orders][creationDate][$ge]": int(beg.timestamp()*1000), "filter[orders][creationDate][$le]": int(end.timestamp()*1000)})
    for z in o.http("GET", f"{o.KASPI_API}/orders?{q}", o.kaspi_headers()).get("data") or []:
        a = z.get("attributes") or {}
        cu = a.get("customer") or {}
        ids[hashlib.sha256(str(cu.get("id")).encode()).hexdigest()[:6]] += 1
        if a.get("status") in ("CANCELLED", "RETURNED"):
            kd = a.get("kaspiDelivery") or {}
            print("K|", a.get("code"), a.get("status"), "| kd:", {k: (v if not isinstance(v, str) or len(v) < 30 else "…") for k, v in kd.items() if k not in ("waybill",)},
                  "| keys:", sorted(k for k in a if k not in ("customer", "deliveryAddress", "kaspiDelivery")))
            ext = f"kaspi-{a.get('code')}"
            mo = o.ms_existing(ext)
            print("   МС заказ:", bool(mo), "отгрузок:", len((o.http('GET', mo['meta']['href'], o.ms_headers()).get('demands') or [])) if mo else 0)
    end = beg
print("Kaspi покупателей (по customer.id):", len(ids), "макс заказов у одного:", max(ids.values()) if ids else 0)
