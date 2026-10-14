"""Выгрузка остатков «Основного склада» с ценами продажи из карточек МС.
Результат шифруется сертификатом report_cert.pem (расшифровать может только владелец ключа) —
в открытый репозиторий цены в открытом виде не попадают."""
import gzip, json, os, urllib.parse, urllib.request
from build_feed import API, STORE_ID

MOMENT = os.environ.get("MOMENT", "").strip()  # «YYYY-MM-DD HH:MM:SS» — остаток на дату; пусто — сейчас


def fetch(token, archived):
    flt = f"stockStore={API}/entity/store/{STORE_ID};archived={'true' if archived else 'false'}"
    if MOMENT:
        flt += f";stockMoment={MOMENT}"
    rows, offset = [], 0
    while True:
        url = f"{API}/entity/assortment?limit=1000&offset={offset}&filter={urllib.parse.quote(flt, safe='')}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        page = json.loads(raw)["rows"]
        rows += page
        if len(page) < 1000:
            return rows
        offset += 1000


token = os.environ["MS_TOKEN"].strip()
rows = fetch(token, False) + fetch(token, True)
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
