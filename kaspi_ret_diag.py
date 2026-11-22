import urllib.parse
import orders_sync as o
H = o.ms_headers()
code = "1143386126"
for m in o.ms_order_demands(f"kaspi-{code}", code):
    d = o.http("GET", m["href"], H)
    print("DEMAND|", d.get("name"), d.get("moment", "")[:10], "сумма", d.get("sum", 0) / 100, "оплачено", d.get("payedSum", 0) / 100,
          "проведена", d.get("applicable"), "| заказ:", bool(d.get("customerOrder")))
co = o.ms_existing(f"kaspi-{code}")
if co:
    print("ORDER|", co.get("name"), "сумма", co.get("sum", 0) / 100, "оплачено", co.get("payedSum", 0) / 100)
f = urllib.parse.quote(f"agent={o.MS_API}/entity/counterparty/{o.AGENT_KASPI}", safe="")
for kind in ("paymentin", "cashin"):
    rows = o.http("GET", f"{o.MS_API}/entity/{kind}?filter={f}&limit=15&order=moment,desc", H).get("rows") or []
    print(kind, "строк:", len(rows))
    for r in rows:
        ops = r.get("operations") or []
        print(f" {kind}|", r.get("name"), r.get("moment", "")[:10], r.get("sum", 0) / 100, "| связей:", len(ops),
              "|", ",".join(x["meta"]["type"] for x in ops)[:60], "|", (r.get("description") or "").replace("\n", " / ")[:90],
              "| статья:", bool(r.get("expenseItem")), "| проведён:", r.get("applicable"))
rows = o.http("GET", f"{o.MS_API}/entity/paymentout?filter={f}&limit=5&order=moment,desc", H).get("rows") or []
print("paymentout строк:", len(rows))
for r in rows:
    print(" out|", r.get("name"), r.get("moment", "")[:10], r.get("sum", 0) / 100, "|", (r.get("description") or "")[:80], "| связей:", len(r.get("operations") or []))
# возвраты Kaspi: как Настя оформляет деньги по ним
f2 = urllib.parse.quote(f"agent={o.MS_API}/entity/counterparty/{o.AGENT_KASPI}", safe="")
for r in o.http("GET", f"{o.MS_API}/entity/salesreturn?filter={f2}&limit=5&order=moment,desc", H).get("rows") or []:
    print(" SR|", r.get("name"), r.get("sum", 0) / 100, "выплачено", r.get("payedSum", 0) / 100, "| payments:", len(r.get("payments") or []))
