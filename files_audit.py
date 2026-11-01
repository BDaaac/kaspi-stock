"""Какие файлы висят в карточках товаров МС и когда загружены (только чтение)."""
import os
from orders_sync import MS_API, http

tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
rows, offset = [], 0
while True:
    d = http("GET", f"{MS_API}/entity/product?filter=archived=false&limit=1000&offset={offset}", H)
    rows += d.get("rows") or []
    if len(d.get("rows") or []) < 1000:
        break
    offset += 1000
out = ["код\tгруппа\tфайл\tзагружен"]
for p in rows:
    for x in http("GET", p["meta"]["href"] + "/files?limit=100", H).get("rows") or []:
        out.append(f"{p.get('code')}\t{p.get('pathName')}\t{x.get('filename') or x.get('title')}\t{x.get('created')}")
open("product_files_report.md", "w").write("\n".join(out))
print(len(rows), "товаров,", len(out) - 1, "файлов")
