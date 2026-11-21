"""Ozon: возвраты в пути — есть ли среди них покупатели, которые заказывали раньше.
Без персональных данных: только номера отправлений и префикс покупателя."""
import os, re
from datetime import datetime, timedelta, timezone
import orders_sync as o

H = o.ozon_headers()
rets, src = [], None
tries = [
    ("/v1/returns/list", lambda lid: {"filter": {}, "limit": 500, "last_id": lid}),
    ("/v3/returns/company/fbs", lambda lid: {"filter": {}, "limit": 1000, "last_id": lid}),
    ("/v2/returns/company/fbs", lambda lid: {"filter": {}, "limit": 1000, "offset": 0}),
]
for path, body in tries:
    try:
        lid = 0; got = []
        for _ in range(30):
            r = o.http("POST", f"{o.OZON_API}{path}", H, body(lid))
            rows = r.get("returns") or (r.get("result") or {}).get("returns") or []
            got += rows
            if not rows or not (r.get("has_next") or (r.get("result") or {}).get("has_next")) or "offset" in body(0): break
            lid = rows[-1].get("id") or 0
        print("метод", path, "OK, строк:", len(got)); rets, src = got, path; break
    except Exception as e:
        print("метод", path, "ошибка:", str(e)[:160])
if not src:
    raise SystemExit("ни один метод возвратов не доступен")

if rets: print("поля:", sorted(rets[0].keys()))
def st(x):
    v = x.get("visual") or {}
    s = (v.get("status") or {})
    return " / ".join(str(i) for i in [s.get("sys_name") or x.get("status"), s.get("display_name") or x.get("status_name")] if i)

o.DAYS = 365
import ozon_repeat_lib as L
posts = L.fbs_full(o, H, 365)
byb = {}
for p in posts: byb.setdefault(p["posting_number"].split("-")[0], []).append(p)
allret = {x.get("posting_number") for x in rets if x.get("posting_number")}
for x in rets:
    s = st(x)
    pn = x.get("posting_number") or ""
    prod = x.get("product") or {}
    offer = prod.get("offer_id") or x.get("offer_id") or ""
    qty = prod.get("quantity") or x.get("quantity") or ""
    b = pn.split("-")[0]
    others = [q for q in byb.get(b, []) if q["posting_number"] != pn]
    oret = sorted({r for r in allret if r and r.split("-")[0] == b and r != pn})
    print("R|" + "|".join(map(str, [pn, s, f"{offer}×{qty}", (x.get("logistic") or {}).get("return_date") or x.get("returned_to_seller_date_time") or x.get("return_date") or "",
          len(others), ",".join(q["posting_number"] + ":" + q.get("status", "") for q in others) or "-", ",".join(oret) or "-",
          x.get("return_reason_name") or x.get("return_reason") or ""])))
