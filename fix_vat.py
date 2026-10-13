"""Разовое исправление: заказы и отгрузки, созданные скриптом (внешний код kaspi-/ozon-/ozonfbo-),
переводятся на НДС 16%, цена включает НДС (суммы не меняются).
DRY_RUN=1 (по умолчанию) — только список, DRY_RUN=0 — запись."""
import urllib.parse
from orders_sync import MS_API, VAT, DRY_RUN, http, ms_headers


def rows(url):
    out, offset = [], 0
    while True:
        d = http("GET", f"{url}&limit=100&offset={offset}", ms_headers())
        r = d.get("rows") or []
        out += r
        if len(r) < 100:
            return out
        offset += 100


def fix_doc(href, kind):
    doc = http("GET", href, ms_headers())
    pos = rows(href + "/positions?")
    bad = [p for p in pos if p.get("vat") != VAT or not p.get("vatEnabled")]
    if doc.get("vatEnabled") and doc.get("vatIncluded") and not bad:
        return None
    line = f"{kind} {doc.get('name')} ({(doc.get('description') or '').splitlines()[0] if doc.get('description') else '—'}), " \
           f"сумма {doc.get('sum', 0) / 100:g}, позиций без НДС: {len(bad)}"
    if not DRY_RUN:
        http("PUT", href, ms_headers(), {"vatEnabled": True, "vatIncluded": True})
        for p in bad:
            http("PUT", p["meta"]["href"], ms_headers(), {"vat": VAT, "vatEnabled": True})
        after = http("GET", href, ms_headers())
        line += f" → исправлено, сумма {after.get('sum', 0) / 100:g}"
    return line


def main():
    print(f"# Исправление НДС ({'ПРОВЕРКА' if DRY_RUN else 'ЗАПИСЬ'})")
    seen, n = set(), 0
    for prefix in ("kaspi-", "ozon"):
        f = urllib.parse.quote(f"externalCode~={prefix}", safe="")
        for o in rows(f"{MS_API}/entity/customerorder?filter={f}"):
            if o["id"] in seen:
                continue
            seen.add(o["id"])
            r = fix_doc(o["meta"]["href"], "Заказ")
            if r:
                n += 1
                print(r)
            for d in o.get("demands") or []:
                r = fix_doc(d["meta"]["href"], "  Отгрузка")
                if r:
                    n += 1
                    print(r)
    print(f"Проверено заказов: {len(seen)}, документов к исправлению: {n}")


if __name__ == "__main__":
    main()
