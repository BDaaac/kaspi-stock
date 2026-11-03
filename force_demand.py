"""Разово: создать отгрузки из заказов МС по внешним кодам (EXTS через запятую), черновиком."""
import os
import orders_sync as s

for ext in [x.strip() for x in os.environ["EXTS"].split(",") if x.strip()]:
    o = s.ms_existing(ext)
    print(ext, "->", s.ms_demand_from_order(o, posted=False) if o else "заказ не найден")
