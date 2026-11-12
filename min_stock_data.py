"""Данные для неснижаемого остатка: сроки поставки (заказ поставщику -> приёмка) и продажи по товарам за N дней."""
import datetime as dt, os, urllib.parse
from collections import defaultdict
from orders_sync import MS_API, http
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
DAYS = int(os.environ.get("DAYS") or 365)
since = (dt.datetime.utcnow() - dt.timedelta(days=DAYS)).strftime("%Y-%m-%d 00:00:00")

def allrows(path, flt=None, expand=None, limit=100):
    out, off = [], 0
    while True:
        q = f"{MS_API}/{path}?limit={limit}&offset={off}"
        if flt: q += "&filter=" + urllib.parse.quote(flt, safe="")
        if expand: q += "&expand=" + expand
        r = http("GET", q, H).get("rows") or []
        out += r
        if len(r) < limit: return out
        off += limit

def d(s): return dt.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")

# 1) сроки поставки
print("== LEAD")
for po in allrows("entity/purchaseorder", expand="agent,supplies", limit=100):
    sup = [s for s in (po.get("supplies") or []) if s.get("moment")]
    first = min((d(s["moment"]) for s in sup), default=None)
    print("LEAD|" + "|".join([po.get("name", ""), po["moment"][:10], (po.get("agent") or {}).get("name", ""),
                              first.strftime("%Y-%m-%d") if first else "", str((first - d(po["moment"])).days) if first else "",
                              str(len(sup))]))
# приёмки без заказа — для истории прихода
for s in allrows("entity/supply", expand="agent", limit=100):
    print("SUPPLY|" + "|".join([s.get("name", ""), s["moment"][:10], (s.get("agent") or {}).get("name", ""),
                                "PO" if s.get("purchaseOrder") else ""]))

# 2) продажи по товарам
sold = defaultdict(float); first_sale = {}
for kind, sign in (("demand", 1), ("salesreturn", -1)):
    for doc in allrows(f"entity/{kind}", flt=f"moment>={since};applicable=true", limit=100):
        pos = allrows(doc["meta"]["href"].split("/api/remap/1.2/")[1] + "/positions", limit=1000)
        for p in pos:
            pid = p["assortment"]["meta"]["href"].rsplit("/", 1)[1]
            sold[pid] += sign * p.get("quantity", 0)
            if sign > 0:
                m = doc["moment"][:10]
                first_sale[pid] = min(first_sale.get(pid, m), m)

# 3) товары + остатки
stock = defaultdict(float)
for r in allrows("report/stock/bystore/current", limit=1000) if False else []:
    pass
st = http("GET", f"{MS_API}/report/stock/all/current?stockType=stock", H)
for r in (st if isinstance(st, list) else st.get("rows", [])):
    stock[r["assortmentId"]] = r.get("stock", 0)
print("== PROD")
for p in allrows("entity/product", flt="archived=false", limit=1000):
    ms = p.get("minimumStock") or {}
    print("PROD|" + "|".join([p["id"], p.get("code") or "", (p.get("name") or "").replace("|", "/"), p.get("pathName") or "",
                              f"{sold.get(p['id'], 0):g}", first_sale.get(p["id"], ""), f"{stock.get(p['id'], 0):g}",
                              str(ms.get("type", "")), f"{ms.get('quantity', p.get('minimumBalance', 0)) or 0:g}",
                              p.get("created", "")[:10]]))
