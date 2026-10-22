"""Разово: вернуть ручному заказу правильную привязку (внешний код + комментарий) и убрать чужую этикетку.
ORDER — номер заказа МС, EXT — правильный внешний код, DESC — комментарий, WRONG — номер чужого отправления."""
import os, urllib.parse
from orders_sync import MS_API, http

tok = os.environ["MS_ORDERS_TOKEN"].strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip", "Content-Type": "application/json"}
name, ext, desc, wrong = (os.environ[k] for k in ("ORDER", "EXT", "DESC", "WRONG"))
f = urllib.parse.quote(f"name={name}", safe="")
o = http("GET", f"{MS_API}/entity/customerorder?filter={f}&limit=1", H)["rows"][0]
print("было:", o.get("externalCode"), "|", o.get("description"))
http("PUT", o["meta"]["href"], H, {"externalCode": ext, "description": desc})
for x in http("GET", o["meta"]["href"] + "/files?limit=100", H).get("rows") or []:
    fn = x.get("filename") or x.get("title") or ""
    if wrong in fn:
        http("DELETE", x["meta"]["href"], H)
        print("удалён файл:", fn)
o = http("GET", o["meta"]["href"], H)
print("стало:", o.get("externalCode"), "|", o.get("description"))
