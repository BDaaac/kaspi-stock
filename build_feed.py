"""Собирает прайс-лист Kaspi (docs/kaspi.xml) с остатками из МойСклад.

Остаток Kaspi = (остаток - резерв на складе) // units_per_offer.
Цены, названия и склад берутся из kaspi_base.xml и не меняются.
"""
import csv
import gzip
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

API = "https://api.moysklad.ru/api/remap/1.2"
STORE_ID = "c9435ee5-badf-11ee-0a80-07d10000acd8"  # «Основной склад»
NS = "kaspiShopping"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
BASE, MAPPING, OUT = "kaspi_base.xml", "mapping.csv", "docs/kaspi.xml"


def fetch_assortment(token):
    """Вся номенклатура с остатком и резервом на складе STORE_ID."""
    flt = urllib.parse.quote(f"stockStore={API}/entity/store/{STORE_ID}", safe="")
    rows, offset = [], 0
    while True:
        url = f"{API}/entity/assortment?limit=1000&offset={offset}&filter={flt}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        page = json.loads(raw)["rows"]
        rows.extend(page)
        if len(page) < 1000:
            return rows
        offset += 1000


def available_by_code(rows):
    """код МС -> список (остаток - резерв) по всем карточкам с этим кодом."""
    out = {}
    for r in rows:
        code = (r.get("code") or "").strip()
        if code:
            out.setdefault(code, []).append((r.get("stock") or 0) - (r.get("reserve") or 0))
    return out


def load_mapping():
    with open(MAPPING, encoding="utf-8", newline="") as f:
        return {r["kaspi_sku"]: (r["ms_code"].strip(), int(r["units_per_offer"]))
                for r in csv.DictReader(f)}


def build(rows):
    mapping = load_mapping()
    avail = available_by_code(rows)
    ET.register_namespace("", NS)
    ET.register_namespace("xsi", XSI)
    root = ET.parse(BASE).getroot()
    offers = root.findall(f".//{{{NS}}}offer")
    errors = []
    seen = set()
    for offer in offers:
        sku = offer.get("sku")
        seen.add(sku)
        if sku not in mapping:
            errors.append(f"нет в mapping.csv: {sku}")
            continue
        code, units = mapping[sku]
        found = avail.get(code)
        if not found:
            errors.append(f"код не найден в МойСклад: {code} (Kaspi {sku})")
            continue
        if len(found) > 1:
            errors.append(f"в МойСклад несколько карточек с кодом {code} (Kaspi {sku})")
            continue
        if units < 1:
            errors.append(f"units_per_offer < 1: {sku}")
            continue
        count = max(0, int(found[0] // units))
        for av in offer.findall(f".//{{{NS}}}availability"):
            av.set("stockCount", str(count))
            av.set("available", "yes" if count > 0 else "no")
    for sku in mapping:
        if sku not in seen:
            errors.append(f"есть в mapping.csv, но нет в kaspi_base.xml: {sku}")
    if errors:
        sys.exit("Файл НЕ обновлён:\n  " + "\n  ".join(errors))
    return root


def same_content(a, b):
    def norm(el):
        el = ET.fromstring(ET.tostring(el))
        el.set("date", "")
        return ET.tostring(el)
    return norm(a) == norm(b)


def main():
    token = os.environ.get("MS_TOKEN", "").strip()
    if not token:
        sys.exit("Нет секрета MS_TOKEN")
    root = build(fetch_assortment(token))
    if os.path.exists(OUT) and same_content(ET.parse(OUT).getroot(), root):
        print("Остатки не изменились")
        return
    root.set("date", datetime.now(ZoneInfo("Asia/Almaty")).strftime("%Y-%m-%d %H:%M"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ET.ElementTree(root).write(OUT, encoding="UTF-8", xml_declaration=True)
    print("Обновлён", OUT)


if __name__ == "__main__":
    main()
