"""Отправляет остатки из МойСклад в Ozon (склад FBS) через Seller API.

Остаток Ozon = (остаток - резерв на «Основном складе») // units_per_offer.
Цены не трогает. Итог отправки пишется в лог запуска.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request

from build_feed import available_by_code, fetch_assortment

OZON = "https://api-seller.ozon.ru"
MAPPING = "ozon_mapping.csv"
WAREHOUSE_FILE, WAREHOUSE_NAME = "ozon_warehouse_id.txt", "enimax"


class OzonError(Exception):
    pass


def ozon(path, body, client_id, api_key):
    req = urllib.request.Request(OZON + path, data=json.dumps(body).encode(), headers={
        "Client-Id": client_id, "Api-Key": api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise OzonError(f"Ozon {path}: HTTP {e.code} {e.read().decode(errors='replace')[:500]}")


def warehouse_id(client_id, api_key):
    """Номер склада FBS: из ozon_warehouse_id.txt, иначе из списка складов Ozon."""
    if os.path.exists(WAREHOUSE_FILE):
        forced = open(WAREHOUSE_FILE, encoding="utf-8").read().strip()
        if forced:
            return int(forced)
    data = ozon("/v2/warehouse/list", {"limit": 200}, client_id, api_key)
    items = data.get("warehouses") or data.get("result") or []
    if isinstance(items, dict):
        items = items.get("warehouses") or []
    named = [w for w in items if str(w.get("name", "")).strip().lower() == WAREHOUSE_NAME]
    pick = named if len(named) == 1 else items
    listing = ", ".join(f"{w.get('name')}={w.get('warehouse_id')}" for w in items) or "нет"
    print("Склады Ozon:", listing)
    if len(pick) != 1:
        raise OzonError(f"Не удалось выбрать склад ({listing}): впишите номер в {WAREHOUSE_FILE}")
    return int(pick[0]["warehouse_id"])


def compute(rows):
    """[(offer_id, ms_code, units, stock)] либо выход с ошибкой, ничего не отправляя."""
    avail = available_by_code(rows)
    out, errors = [], []
    with open(MAPPING, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            offer, code, units = r["offer_id"], r["ms_code"].strip(), int(r["units_per_offer"])
            found = avail.get(code)
            if not found:
                errors.append(f"код не найден в МойСклад: {code} (Ozon {offer})")
            elif len(found) > 1:
                errors.append(f"в МойСклад несколько карточек с кодом {code} (Ozon {offer})")
            elif units < 1:
                errors.append(f"units_per_offer < 1: {offer}")
            else:
                out.append((offer, code, units, max(0, int(found[0] // units))))
    if errors:
        sys.exit("В Ozon НИЧЕГО не отправлено:\n  " + "\n  ".join(errors))
    return out


def push(items, wh, client_id, api_key):
    """offer_id -> 'ok' или текст ошибки."""
    status = {}
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        body = {"stocks": [{"offer_id": o, "stock": s, "warehouse_id": wh} for o, _, _, s in chunk]}
        res = ozon("/v2/products/stocks", body, client_id, api_key).get("result", [])
        for r in res:
            errs = "; ".join(e.get("code", "") or e.get("message", "") for e in r.get("errors") or [])
            status[r.get("offer_id")] = "ok" if r.get("updated") and not errs else (errs or "not updated")
        for o, _, _, _ in chunk:
            status.setdefault(o, "нет ответа")
    return status


def main():
    token = os.environ.get("MS_TOKEN", "").strip()
    client_id = os.environ.get("OZON_CLIENT_ID", "").strip()
    api_key = os.environ.get("OZON_API_KEY", "").strip()
    if not (token and client_id and api_key):
        sys.exit("Нужны секреты MS_TOKEN, OZON_CLIENT_ID, OZON_API_KEY")
    items = compute(fetch_assortment(token))
    try:
        status = push(items, warehouse_id(client_id, api_key), client_id, api_key)
    except OzonError as e:
        sys.exit(str(e))
    bad = [(o, st) for o, st in status.items() if st != "ok"]
    print(f"Отправлено: {len(items)}, с ошибкой: {len(bad)}")
    if bad:
        sys.exit("Ozon не принял:\n  " + "\n  ".join(f"{o}: {st}" for o, st in bad))


if __name__ == "__main__":
    main()
