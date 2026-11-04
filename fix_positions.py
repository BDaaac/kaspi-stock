"""Разово: пересобрать позиции заказа МС (без отгрузки) по таблице соответствия Ozon, с комплектующими.
EXT — внешний код заказа; ITEMS — offer_id:кол-во:цена;... (цена площадки за 1 шт оффера)."""
import os
import orders_sync as s

ext = os.environ["EXT"]
items = [dict(zip(("sku", "qty", "price"), x.split(":"))) for x in os.environ["ITEMS"].split(";") if x]
o = s.ms_existing(ext)
full = s.http("GET", o["meta"]["href"], s.ms_headers())
if full.get("demands"):
    raise SystemExit(f"{ext}: по заказу уже есть отгрузка — позиции не трогаю")
products = s.ms_products()
pos, problems = s.build_positions(items, s.load_map("ozon_mapping.csv", "offer_id"), products, True)
if problems:
    raise SystemExit("; ".join(problems))
old = s.http("GET", o["meta"]["href"] + "/positions?limit=1000", s.ms_headers()).get("rows") or []
for r in old:
    s.http("DELETE", r["meta"]["href"], s.ms_headers())
s.http("POST", o["meta"]["href"] + "/positions", s.ms_headers(), pos)
print(ext, "позиции:", [(p["assortment"]["meta"]["href"].rsplit("/", 1)[-1], p["quantity"], p["price"]) for p in pos])
