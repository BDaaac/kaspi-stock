"""Отправляет остатки из МойСклад в Ozon (склад FBS) через Seller API.

Остаток Ozon = (остаток - резерв на «Основном складе») // units_per_offer.
Цены не трогает. Отчёт о последней отправке — docs/ozon.csv.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request

from build_feed import available_by_code, fetch_assortment

OZON = "https://api-seller.ozon.ru"
MAPPING, REPORT = "ozon_mapping.csv", "docs/ozon.csv"


def ozon(path, body, client_id, api_key):
    req = urllib.request.Request(OZON + path, data=json.dumps(body).encode(), headers={
        "Client-Id": client_id, "Api-Key": api_key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Ozon {path}: HTTP {e.code} {e.read().decode(errors='replace')[:500]}")


def warehouse_id(client_id, api_key):
    forced = os.environ.get("OZON_WAREHOUSE_ID", "").strip()
    if forced:
        return int(forced)
    data = ozon("/v1/warehouse/list", {}, client_id, api_key)
    items = data.get("result") or data.get("warehouses") or []
    if len(items) != 1:
        names = ", ".join(f"{w.get('name')}={w.get('warehouse_id')}" for w in items)
        sys.exit(f"Складов Ozon не один ({names or 'нет'}): задайте OZON_WAREHOUSE_ID")
    return int(items[0]["warehouse_id"])


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
    status = push(items, warehouse_id(client_id, api_key), client_id, api_key)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["offer_id", "ms_code", "units_per_offer", "stock", "status"])
        for o, c, u, s in items:
            w.writerow([o, c, u, s, status[o]])
    bad = [(o, st) for o, st in status.items() if st != "ok"]
    print(f"Отправлено: {len(items)}, с ошибкой: {len(bad)}")
    if bad:
        sys.exit("Ozon не принял:\n  " + "\n  ".join(f"{o}: {st}" for o, st in bad))


if __name__ == "__main__":
    main()
