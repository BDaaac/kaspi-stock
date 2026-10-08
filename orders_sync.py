"""Заказы Kaspi и Ozon -> «Заказы покупателя» в МойСклад.

DRY_RUN=1 (по умолчанию): ничего не пишет, только собирает отчёт orders_report.md
(без данных покупателей: номер, дата, статус, товары, количество, цена).
"""
import base64
import csv
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from build_feed import API as MS_API, STORE_ID

DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
RESERVE = os.environ.get("RESERVE", "1") == "1"
INCLUDE_FBO = os.environ.get("INCLUDE_FBO", "0") == "1"
DAYS = int(os.environ.get("ORDERS_DAYS", "7"))
AUTO_ASSEMBLE = os.environ.get("AUTO_ASSEMBLE", "0") == "1"   # «Я упаковал, сформировать накладные»
AUTO_ACCEPT = os.environ.get("AUTO_ACCEPT", "0") == "1"       # принять новый заказ Kaspi, если товар есть

ORG_ID = "c9415ec7-badf-11ee-0a80-07d10000acd5"            # ENIMAX
AGENT_KASPI = "2363a7c4-5d82-11f1-0a80-16ae0029fb07"       # Каспи магазин (ЧЛ)
AGENT_OZON = "d1af9410-6dd4-11f1-0a80-0e6e0024cf6c"        # Ozon (ЧЛ)
STORE_OZON_FBO = "2ccb6a0a-b68b-11f1-0a80-13b3001a4364"    # Ozon FBO

KASPI_API = "https://kaspi.kz/shop/api/v2"
# Ozon: заказ с резервом создаётся, пока отправление не передано в доставку
OZON_OPEN = {"awaiting_registration", "acceptance_in_progress", "awaiting_approve",
             "awaiting_packaging", "awaiting_deliver"}
OZON_API = "https://api-seller.ozon.ru"
REPORT = "orders_report.md"
lines = []


def log(s=""):
    print(s)
    lines.append(s)


class HttpError(Exception):
    pass


def http(method, url, headers=None, body=None, raw=False):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                import gzip
                content = gzip.decompress(content)
            ctype = r.headers.get("Content-Type", "")
            if raw:
                return content, ctype
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        raise HttpError(f"{method} {url.split('?')[0]} -> HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")


# ---------------- Kaspi ----------------
def kaspi_headers():
    return {"X-Auth-Token": os.environ["KASPI_TOKEN"].strip(),
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
            "User-Agent": "enimax-sync/1.0"}


def kaspi_orders():
    now = datetime.now(timezone.utc)
    since = int((now - timedelta(days=DAYS)).timestamp() * 1000)
    until = int(now.timestamp() * 1000)
    out = []
    for state in ["NEW", "SIGN_REQUIRED", "PICKUP", "DELIVERY", "KASPI_DELIVERY", "ARCHIVE"]:
        page = 0
        while True:
            q = urllib.parse.urlencode({
                "page[number]": page, "page[size]": 100,
                "filter[orders][state]": state,
                "filter[orders][creationDate][$ge]": since,
                "filter[orders][creationDate][$le]": until,
            })
            d = http("GET", f"{KASPI_API}/orders?{q}", kaspi_headers())
            rows = d.get("data") or []
            for o in rows:
                o["_state"] = state
            out.extend(rows)
            if len(rows) < 100:
                break
            page += 1
    return out


def kaspi_entries(order):
    d = http("GET", f"{KASPI_API}/orders/{order['id']}/entries", kaspi_headers())
    items = []
    for e in d.get("data") or []:
        a = e.get("attributes") or {}
        offer = a.get("offer") or {}
        sku = offer.get("code") or a.get("merchantProduct", {}).get("code")
        if not sku:  # запасной путь: карточка товара продавца
            try:
                mp = http("GET", f"{KASPI_API}/orderentries/{e['id']}/product/merchantProduct", kaspi_headers())
                sku = ((mp.get("data") or {}).get("attributes") or {}).get("code")
            except HttpError:
                sku = None
        items.append({"sku": sku, "qty": a.get("quantity"), "price": a.get("basePrice"),
                      "name": offer.get("name")})
    return items


# ---------------- Ozon ----------------
def ozon_headers():
    return {"Client-Id": os.environ["OZON_CLIENT_ID"].strip(),
            "Api-Key": os.environ["OZON_API_KEY"].strip(),
            "Content-Type": "application/json"}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def ozon_fbs():
    now = datetime.now(timezone.utc)
    out, offset = [], 0
    while True:
        body = {"dir": "ASC", "limit": 100, "offset": offset,
                "filter": {"since": iso(now - timedelta(days=DAYS)), "to": iso(now)}, "with": {}}
        d = http("POST", f"{OZON_API}/v3/posting/fbs/list", ozon_headers(), body)
        res = d.get("result") or {}
        out.extend(res.get("postings") or [])
        if not res.get("has_next"):
            return out
        offset += 100


def ozon_fbo():
    now = datetime.now(timezone.utc)
    out, offset = [], 0
    while True:
        body = {"dir": "ASC", "limit": 100, "offset": offset,
                "filter": {"since": iso(now - timedelta(days=DAYS)), "to": iso(now)}}
        d = http("POST", f"{OZON_API}/v2/posting/fbo/list", ozon_headers(), body)
        rows = d.get("result") or []
        out.extend(rows)
        if len(rows) < 100:
            return out
        offset += 100


# ---------------- Этикетки ----------------
def ozon_label(posting_number):
    content, ctype = http("POST", f"{OZON_API}/v2/posting/fbs/package-label", ozon_headers(),
                          {"posting_number": [posting_number]}, raw=True)
    if "json" in ctype:  # некоторые версии отдают PDF внутри JSON
        d = json.loads(content)
        b64 = d.get("file_content") or (d.get("result") or {}).get("file_content")
        if not b64:
            raise HttpError(f"Ozon этикетка {posting_number}: в ответе нет файла: {str(d)[:200]}")
        return base64.b64decode(b64)
    return content


def kaspi_accept(order_id, code):
    body = {"data": {"type": "orders", "id": order_id,
                     "attributes": {"code": code, "status": "ACCEPTED_BY_MERCHANT"}}}
    http("POST", f"{KASPI_API}/orders", kaspi_headers(), body)


def ms_available():
    """код -> остаток минус резерв на «Основном складе» (тот же расчёт, что для площадок)."""
    from build_feed import fetch_assortment, available_by_code
    av = available_by_code(fetch_assortment(os.environ["MS_TOKEN"].strip()))
    return {c: v[0] for c, v in av.items() if len(v) == 1}


def need_pieces(items, mapping):
    need = {}
    for it in items:
        m = mapping.get(it["sku"] or "")
        if not m:
            return None
        need[m[0]] = need.get(m[0], 0) + int(it["qty"] or 0) * m[1]
    return need


def kaspi_assemble(order_id, places=1):
    """Kaspi Доставка: статус ASSEMBLE (как кнопка «Я упаковал, сформировать накладные»)."""
    body = {"data": {"type": "orders", "id": order_id,
                     "attributes": {"status": "ASSEMBLE", "numberOfSpace": str(places)}}}
    http("POST", f"{KASPI_API}/orders", kaspi_headers(), body)
    for _ in range(6):  # накладная формируется не мгновенно
        time.sleep(5)
        d = http("GET", f"{KASPI_API}/orders/{order_id}", kaspi_headers())
        url = (((d.get("data") or {}).get("attributes") or {}).get("kaspiDelivery") or {}).get("waybill")
        if url:
            return url
    return None


def kaspi_label(url):
    h = kaspi_headers()
    h["Accept"] = "application/pdf, */*"
    content, ctype = http("GET", url, h, raw=True)
    if not content.startswith(b"%PDF"):
        raise HttpError(f"Kaspi накладная: пришёл не PDF ({ctype}, {len(content)} байт)")
    return content


def ms_attach_label(order_href, filename, get_pdf):
    """Прикрепить PDF к заказу, если такого файла ещё нет. Возвращает текст для отчёта."""
    files = http("GET", order_href + "/files?limit=100", ms_headers())
    if any(f.get("filename") == filename for f in files.get("rows") or []):
        return "этикетка уже прикреплена"
    if DRY_RUN:
        return "этикетка: прикрепил бы"
    pdf = get_pdf()
    http("POST", order_href + "/files", ms_headers(),
         [{"filename": filename, "content": base64.b64encode(pdf).decode()}])
    return f"этикетка прикреплена ({len(pdf) // 1024} КБ)"


# ---------------- МойСклад ----------------
def ms_headers():
    return {"Authorization": f"Bearer {os.environ['MS_ORDERS_TOKEN'].strip()}",
            "Accept-Encoding": "gzip", "Content-Type": "application/json"}


def ms_meta(kind, id_):
    return {"meta": {"href": f"{MS_API}/entity/{kind}/{id_}", "type": kind, "mediaType": "application/json"}}


def ms_products():
    """код -> meta товара (через тот же токен заказов)."""
    out, offset = {}, 0
    while True:
        d = http("GET", f"{MS_API}/entity/assortment?limit=1000&offset={offset}", ms_headers())
        rows = d.get("rows") or []
        for r in rows:
            code = (r.get("code") or "").strip()
            if code:
                out.setdefault(code, []).append(r["meta"])
        if len(rows) < 1000:
            return out
        offset += 1000


def ms_existing(external_code):
    f = urllib.parse.quote(f"externalCode={external_code}", safe="")
    d = http("GET", f"{MS_API}/entity/customerorder?filter={f}&limit=1", ms_headers())
    rows = d.get("rows") or []
    return rows[0] if rows else None


def load_map(path, key):
    with open(path, encoding="utf-8", newline="") as f:
        return {r[key]: (r["ms_code"].strip(), int(r["units_per_offer"])) for r in csv.DictReader(f)}


def build_positions(items, mapping, products, reserve):
    pos, problems = [], []
    for it in items:
        m = mapping.get(it["sku"] or "")
        if not m:
            problems.append(f"артикул {it['sku']} не найден в таблице соответствия")
            continue
        code, units = m
        metas = products.get(code)
        if not metas or len(metas) != 1:
            problems.append(f"код {code} {'не найден' if not metas else 'не уникален'} в МойСклад")
            continue
        qty = int(it["qty"] or 0) * units
        price_per_piece = round(float(it["price"] or 0) / units * 100)  # в тиынах
        p = {"quantity": qty, "price": price_per_piece, "assortment": {"meta": metas[0]}}
        if reserve:
            p["reserve"] = qty
        pos.append(p)
    return pos, problems


def main():
    log(f"# Заказы → МойСклад ({'ПРОВЕРКА, без записи' if DRY_RUN else 'ЗАПИСЬ'})")
    log(f"Период: {DAYS} дн., резерв: {'да' if RESERVE else 'нет'}, FBO: {'да' if INCLUDE_FBO else 'нет'}, "
        f"запуск {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    kmap, omap = load_map("mapping.csv", "kaspi_sku"), load_map("ozon_mapping.csv", "offer_id")
    kmap.update(load_map("kaspi_orders_extra.csv", "kaspi_sku"))  # товары Kaspi, снятые с продажи
    try:
        products = ms_products()
        log(f"МойСклад (токен заказов): прочитано {sum(len(v) for v in products.values())} карточек — OK")
    except Exception as e:
        log(f"МойСклад: ОШИБКА {e}")
        products = {}

    plans = []  # (external_code, agent, store, description, items, mapping, status_text, active)

    log("\n## Kaspi")
    for url in ("https://kaspi.kz/", "https://kaspi.kz/shop/api/v2/orders"):
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "enimax-sync/1.0"}), timeout=20)
            log(f"доступ {url}: OK")
        except urllib.error.HTTPError as e:
            log(f"доступ {url}: сайт отвечает (HTTP {e.code})")
        except Exception as e:
            log(f"доступ {url}: НЕТ СВЯЗИ ({e})")
    try:
        orders = kaspi_orders()
        seen = {}
        for o in orders:  # один заказ может прийти в нескольких состояниях
            seen[(o.get("attributes") or {}).get("code")] = o
        log(f"заказов за период: {len(seen)}")
        avail = ms_available() if AUTO_ACCEPT else {}
        for code, o in seen.items():
            a = o.get("attributes") or {}
            created = datetime.fromtimestamp((a.get("creationDate") or 0) / 1000, timezone(timedelta(hours=5)))
            status = a.get("status")
            kd = a.get("kaspiDelivery") or {}
            handed = kd.get("courierTransmissionDate")
            items = kaspi_entries(o)
            waybill = bool(kd.get("waybill"))
            if AUTO_ACCEPT and status == "APPROVED_BY_BANK" and o["_state"] == "NEW":
                need = need_pieces(items, kmap)
                mine = ms_existing(f"kaspi-{code}")
                short = []
                if need is None:
                    short.append("товар не найден в таблице соответствия")
                else:
                    for c, q in need.items():
                        have = avail.get(c, 0) + (q if mine else 0)  # свой резерв по этому заказу не считаем
                        if have < q:
                            short.append(f"{c}: нужно {q}, доступно {int(have)}")
                if short:
                    log(f"ОШИБКА: Kaspi заказ №{code} НЕ принят автоматически — " + "; ".join(short)
                        + ". Примите или отмените вручную.")
                elif DRY_RUN:
                    log(f"Kaspi заказ №{code}: принял бы автоматически (товар есть)")
                else:
                    kaspi_accept(o["id"], code)
                    status = "ACCEPTED_BY_MERCHANT"
                    for c, q in need.items():
                        if not mine:
                            avail[c] = avail.get(c, 0) - q
                    log(f"Kaspi заказ №{code}: принят автоматически")
            active = (status in ("APPROVED_BY_BANK", "ACCEPTED_BY_MERCHANT")
                      and o["_state"] in ("NEW", "SIGN_REQUIRED", "PICKUP", "DELIVERY", "KASPI_DELIVERY")
                      and not handed)
            label = None
            if waybill:
                label = (f"kaspi-{code}.pdf", lambda u=kd.get("waybill"): kaspi_label(u))
            elif (AUTO_ASSEMBLE and active and o["_state"] == "KASPI_DELIVERY"
                  and status == "ACCEPTED_BY_MERCHANT"):
                def _assemble_and_get(oid=o["id"], c=code):
                    url = kaspi_assemble(oid)
                    if not url:
                        raise HttpError(f"Kaspi {c}: ASSEMBLE отправлен, но накладная пока не появилась — заберу в следующем цикле")
                    return kaspi_label(url)
                label = (f"kaspi-{code}.pdf", _assemble_and_get)
            plans.append((f"kaspi-{code}", AGENT_KASPI, STORE_ID, f"Заказ №{code}", items, kmap,
                          f"{o['_state']}/{status}, передан курьеру: {'да' if handed else 'нет'}, "
                          f"накладная: {'есть' if waybill else 'нет'}", active, created, label))
    except Exception as e:
        log(f"Kaspi: ОШИБКА {e}")

    log("\n## Ozon FBS")
    try:
        posts = ozon_fbs()
        log(f"отправлений за период: {len(posts)}")
        for p in posts:
            items = [{"sku": x.get("offer_id"), "qty": x.get("quantity"), "price": x.get("price")}
                     for x in p.get("products") or []]
            created = p.get("in_process_at") or p.get("created_at")
            active = p.get("status") in OZON_OPEN
            label = None
            if p.get("status") == "awaiting_deliver":  # этикетка доступна после сборки
                label = (f"ozon-{p['posting_number']}.pdf", lambda n=p["posting_number"]: ozon_label(n))
            plans.append((f"ozon-{p['posting_number']}", AGENT_OZON, STORE_ID, p["posting_number"], items, omap,
                          p.get("status"), active, created, label))
    except Exception as e:
        log(f"Ozon FBS: ОШИБКА {e}")

    log("\n## Ozon FBO")
    try:
        fbo = ozon_fbo()
        log(f"отправлений за период: {len(fbo)}" + ("" if INCLUDE_FBO else " (в заказы не берутся, только проверка доступа)"))
        if INCLUDE_FBO:
            for p in fbo:
                items = [{"sku": x.get("offer_id"), "qty": x.get("quantity"), "price": x.get("price")}
                         for x in p.get("products") or []]
                plans.append((f"ozonfbo-{p['posting_number']}", AGENT_OZON, STORE_OZON_FBO,
                              f"{p['posting_number']}\n\nFBO", items, omap, p.get("status"),
                              p.get("status") in OZON_OPEN, p.get("in_process_at") or p.get("created_at"), None))
    except Exception as e:
        log(f"Ozon FBO: ОШИБКА {e}")

    log("\n## Что было бы создано / изменено")
    log("| Площадка | Номер | Дата | Статус | Товары (артикул → код МС × шт) | Уже есть в МС | Действие |")
    log("|---|---|---|---|---|---|---|")
    created_n = errors_n = 0
    for ext, agent, store, desc, items, mapping, status, active, created, label in plans:
        pos, problems = build_positions(items, mapping, products, RESERVE and active)
        goods = "; ".join(f"{it['sku']}{(' (' + it['name'] + ')') if it.get('name') and it['sku'] not in mapping else ''}×{it['qty']} @ {it['price']}" +
                          (f" → {mapping[it['sku']][0]}×{int(it['qty'] or 0) * mapping[it['sku']][1]}" if it['sku'] in mapping else "")
                          for it in items)
        try:
            existing = ms_existing(ext) if products else None
        except Exception as e:
            existing, problems = None, problems + [str(e)]
        if problems:
            action = "ПРОПУСК: " + "; ".join(problems)
            errors_n += 1
        elif existing:
            action = "уже есть" if active else "снять резерв (отгружен или отменён)"
        else:
            action = "создать с резервом" if active else "не создавать (уже отгружен или отменён)"
        log(f"| {ext.split('-')[0]} | {desc.splitlines()[0]} | {created} | {status} | {goods} | "
            f"{'да' if existing else 'нет'} | {action} |")

        order_href = existing["meta"]["href"] if existing else None
        if DRY_RUN or problems:
            if label and existing:
                try:
                    log(f"| | {desc.splitlines()[0]} | | | | | {ms_attach_label(order_href, label[0], label[1])} |")
                except Exception as e:
                    log(f"ОШИБКА этикетки {ext}: {e}")
            continue
        try:
            if not existing and active:
                body = {"organization": ms_meta("organization", ORG_ID), "agent": ms_meta("counterparty", agent),
                        "store": ms_meta("store", store), "description": desc, "externalCode": ext,
                        "positions": pos}
                r = http("POST", f"{MS_API}/entity/customerorder", ms_headers(), body)
                got = ((r.get("store") or {}).get("meta") or {}).get("href", "").rsplit("/", 1)[-1]
                if got and got != store:  # МойСклад однажды поставил склад по умолчанию — поправляем
                    http("PUT", r["meta"]["href"], ms_headers(), {"store": ms_meta("store", store)})
                    log(f"{ext}: склад исправлен с {got} на {store}")
                created_n += 1
                order_href = r["meta"]["href"]
            elif existing and not active:
                d = http("GET", existing["meta"]["href"] + "/positions?limit=1000", ms_headers())
                for r in d.get("rows") or []:
                    if r.get("reserve"):
                        http("PUT", r["meta"]["href"], ms_headers(), {"reserve": 0})
                if status == "cancelled" and "Отменён на площадке" not in (existing.get("description") or ""):
                    http("PUT", existing["meta"]["href"], ms_headers(),
                         {"description": (existing.get("description") or "") + "\nОтменён на площадке"})
        except Exception as e:
            errors_n += 1
            log(f"ОШИБКА записи {ext}: {e}")
            continue
        if label and order_href:
            try:
                log(f"| | {desc.splitlines()[0]} | | | | | {ms_attach_label(order_href, label[0], label[1])} |")
            except Exception as e:
                errors_n += 1
                log(f"ОШИБКА этикетки {ext}: {e}")

    log(f"\nИтого: строк {len(plans)}, создано {created_n}, с ошибками/пропусками {errors_n}")
    return errors_n


if __name__ == "__main__":
    bad = 1
    try:
        bad = main()
    except Exception:
        log("ОШИБКА:\n```\n" + traceback.format_exc() + "\n```")
    finally:
        open(REPORT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    # ошибки площадок/МС тоже видны: в логе ищите «ОШИБКА» и «ПРОПУСК»
    any_err = bad or any("ОШИБКА" in l for l in lines)
    sys.exit(1 if any_err else 0)
