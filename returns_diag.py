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
hk = o._hist_kaspi()
for b, v in hk.items():
    if len(v) > 1:
        r = v & ret
        print("KB|", len(v), "заказов, возвратов", len(r))
