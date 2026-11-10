"""Товары МС (не в архиве) без фото."""
import os
from orders_sync import MS_API, http
tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
rows, off = [], 0
while True:
    d = http("GET", f"{MS_API}/entity/product?filter=archived=false&limit=1000&offset={off}", H).get("rows") or []
    rows += d
    if len(d) < 1000:
        break
    off += 1000
no = [p for p in rows if not ((p.get("images") or {}).get("meta") or {}).get("size")]
print(f"товаров: {len(rows)}, без фото: {len(no)}")
for p in sorted(no, key=lambda p: (p.get("pathName") or "", p.get("name") or "")):
    print("NOPHOTO|" + "|".join([p.get("pathName") or "", p.get("article") or "", p.get("code") or "", p.get("name") or ""]))
