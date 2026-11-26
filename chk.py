import urllib.parse
import orders_sync as o
H = o.ms_headers()
print("== Ozon: возвраты, полученные с 25.11")
rows = [x for x in o.ozon_returns_all() if ((x.get("visual") or {}).get("status") or {}).get("sys_name") == "ReceivedBySeller"
        and ((x.get("visual") or {}).get("change_moment") or "") >= "2026-11-25"]
hist = o._hist_ozon(); ret = o._returned_numbers()
seen = set()
for x in sorted(rows, key=lambda r: r.get("posting_number")):
    pn = x.get("posting_number"); pr = x.get("product") or {}
    b = pn.split("-")[0]; prev = hist.get(b, set()) - {pn}
    print("R|", pn, "|", pr.get("offer_id"), "×", pr.get("quantity"), "|", (x.get("visual") or {}).get("change_moment", "")[:16],
          "|", x.get("return_reason_name"), "| у покупателя ещё заказов:", len(prev), "возвратов:", len(prev & ret), sorted(prev & ret))
    if pn in seen: continue
    seen.add(pn)
    for m in o.ms_order_demands(f"ozon-{pn}", pn):
        d = o.http("GET", m["href"], H)
        for r in d.get("returns") or []:
            s = o.http("GET", r["meta"]["href"], H)
            print("   МС: отгрузка", d.get("name"), "→ возврат", s.get("name"), s.get("created", "")[:16], "провед." if s.get("applicable") else "черн.",
                  "| ИИ" if "ИИ" in (s.get("description") or "") else "| вручную")
        if not d.get("returns"):
            print("   МС: отгрузка", d.get("name"), "→ возврата НЕТ")
