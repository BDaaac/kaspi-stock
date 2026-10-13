"""Выгрузка остатков «Основного склада» с ценами продажи из карточек МС.
Результат шифруется сертификатом report_cert.pem (расшифровать может только владелец ключа) —
в открытый репозиторий цены в открытом виде не попадают."""
import json, os
from build_feed import fetch_assortment

rows = fetch_assortment(os.environ["MS_TOKEN"].strip())
out = []
for r in rows:
    out.append({
        "code": r.get("code"), "name": r.get("name"), "path": r.get("pathName"),
        "type": (r.get("meta") or {}).get("type"), "archived": r.get("archived"),
        "stock": r.get("stock"), "reserve": r.get("reserve"),
        "prices": {(p.get("priceType") or {}).get("name"): p.get("value") for p in r.get("salePrices") or []},
        "buy": (r.get("buyPrice") or {}).get("value"),
    })
json.dump(out, open("stock_value.json", "w"), ensure_ascii=False)
print(f"позиций: {len(out)}")
