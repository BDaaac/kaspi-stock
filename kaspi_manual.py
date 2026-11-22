"""Ручные действия по заказу Kaspi: оплата (как приходит от Kaspi) и возврат покупателя.
ACTION=pay — входящий платёж на сумму заказа, привязан к заказу, датой выполнения заказа в Kaspi.
ACTION=return — возврат покупателя (проведённый) на основании отгрузки."""
import os, urllib.parse
from datetime import datetime, timezone, timedelta
import orders_sync as o

code, action = os.environ["CODE"].strip(), os.environ["ACTION"].strip()
H = o.ms_headers()
order = o.ms_existing(f"kaspi-{code}")
if not order:
    raise SystemExit(f"заказ kaspi-{code} в МойСклад не найден")
order = o.http("GET", order["meta"]["href"], H)
if action == "pay":
    if order.get("payedSum"):
        raise SystemExit(f"по заказу {order.get('name')} уже есть оплата {order['payedSum'] / 100:g} — ничего не делаю")
    q = urllib.parse.urlencode({"filter[orders][code]": code})
    a = ((o.http("GET", f"{o.KASPI_API}/orders?{q}", o.kaspi_headers()).get("data") or [{}])[0].get("attributes") or {})
    ts = a.get("completionDate") or a.get("creationDate")
    moment = datetime.fromtimestamp(ts / 1000, timezone(timedelta(hours=5))).strftime("%Y-%m-%d %H:%M:%S")
    body = {"organization": order["organization"], "agent": order["agent"], "sum": order["sum"], "moment": moment,
            "operations": [{"meta": order["meta"]}], "applicable": True,
            "description": f"Оплата Kaspi по заказу №{code}\n{o.AI_MARK}"}
    if order.get("organizationAccount"):
        body["organizationAccount"] = order["organizationAccount"]
    r = o.http("POST", f"{o.MS_API}/entity/paymentin", H, body)
    print(f"входящий платёж №{r.get('name')} от {moment[:10]} на {r.get('sum', 0) / 100:g} тг создан, привязан к заказу {order.get('name')}")
elif action == "return":
    dms = o.ms_order_demands(f"kaspi-{code}", code)
    if not dms:
        raise SystemExit("отгрузки нет")
    if any(o.ms_has_return(d) for d in dms):
        raise SystemExit("возврат уже оформлен — ничего не делаю")
    name = o.ms_make_return(dms[0], None, {}, f"Возврат Kaspi {code}: возврат после доставки")
    print(f"возврат покупателя №{name} создан (проведён)")
