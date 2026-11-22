"""Проверка (без записи): какие возвраты создались бы и как работает история покупателей."""
import os
os.environ["DRY_RUN"] = "1"
import orders_sync as o
o.RETURNS_FROM = os.environ.get("FROM", "2026-10-01T00:00:00Z")
products = o.ms_products()
omap, kmap = o.load_map("ozon_mapping.csv", "offer_id"), o.load_map("mapping.csv", "kaspi_sku")
o.returns_to_ms(products, omap, kmap)
hk = o._hist_kaspi(); ho = o._hist_ozon(); ret = o._returned_numbers()
print("Kaspi покупателей:", len(hk), "с >1 заказом:", sum(1 for v in hk.values() if len(v) > 1),
      "из них с возвратом:", sum(1 for v in hk.values() if len(v) > 1 and v & ret))
print("Ozon покупателей:", len(ho), "с >1 заказом:", sum(1 for v in ho.values() if len(v) > 1),
      "из них с возвратом:", sum(1 for v in ho.values() if len(v) > 1 and v & ret))
print("номеров с возвратом:", len(ret))
for pn in ("0192839574-0040-1", "31594325-0698-1", "26509942-0390-1"):
    print("пример", pn, "->", o.buyer_note("ozon", pn) or "без пометки")
import collections
vals = collections.defaultdict(set)
for z in o.kaspi_window(["ARCHIVE"], 28):
    for k, v in ((z.get("attributes") or {}).get("customer") or {}).items():
        vals[k].add(str(v))
print("Kaspi customer: разных значений по полям:", {k: len(v) for k, v in vals.items()})
print("Kaspi user id разных:", len({str(((z.get("relationships") or {}).get("user") or {}).get("data")) for z in o.kaspi_window(["ARCHIVE"], 28)}))
print("Kaspi relationships:", sorted((z.get("relationships") or {}).keys()))
