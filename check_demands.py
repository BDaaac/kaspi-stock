"""Контроль отгрузок: если с ТСД/мобильного приложения МС из отгрузки удалили позицию (или уменьшили
количество), а в заказе покупателя эта позиция есть — отгрузке ставится статус «позиция удалена»,
в комментарий пишется что удалено, и ставятся задачи в МС ответственным.

Источник — журнал аудита МС (изменения через JSON API 1.2, кроме этого скрипта).
DRY_RUN=1 — только показать, ничего не менять. AUDIT_HOURS — за сколько часов смотреть журнал (по умолчанию 3).
"""
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

from orders_sync import MS_API, http, ms_headers, ms_meta

DRY = os.environ.get("DRY_RUN", "0") != "0"
HOURS = float(os.environ.get("AUDIT_HOURS", "3"))
MSK = timezone(timedelta(hours=3))   # время журнала аудита МС
ALMATY = timezone(timedelta(hours=5))
ASSIGNEES = {  # кому ставить задачу
    "Кудабаев Е.": "c9305c69-badf-11ee-0a80-07d10000ac82",
    "Хакимов А.": "2fbb5de8-1444-11ef-0a80-04cb0010e86b",
    "Дидиченко А.": "d532e20f-744e-11f1-0a80-04ad0005306c",
    "Сарыбаев А.": "f95bdda0-661d-11f0-0a80-10d8002ef4b6",
}
MARK = "⚠ Удалено с ТСД"


def is_app(ctx):
    info = ((ctx.get("info") or {}).get("additionalInfo") or "")
    return ctx.get("source") == "remap-1.2" and "Python-urllib" not in info


def pos_id(p):
    return ((p.get("assortment") or {}).get("meta") or {}).get("href", "").rsplit("/", 1)[-1]


def removed_positions(diff):
    """[(assortment_id, name, сколько убрали)] — удалённые позиции и уменьшенные количества."""
    out = []
    for p in (diff or {}).get("positions") or []:
        old, new = p.get("oldValue"), p.get("newValue")
        if not old:
            continue
        oq = float(old.get("quantity") or 0)
        nq = float((new or {}).get("quantity") or 0) if new else 0.0
        if new and pos_id(new) != pos_id(old):
            nq = 0.0
        if nq < oq:
            out.append((pos_id(old), (old.get("assortment") or {}).get("name") or "?", oq - nq))
    return out


def state_meta():
    md = http("GET", f"{MS_API}/entity/demand/metadata", ms_headers())
    for s in md.get("states") or []:
        if "удален" in (s.get("name") or "").lower():
            return {"meta": s["meta"]}, s["name"]
    return None, None


def main():
    since = (datetime.now(MSK) - timedelta(hours=HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    f = urllib.parse.quote(f"moment>={since};entityType=demand", safe="")
    contexts, offset = [], 0
    while True:
        d = http("GET", f"{MS_API}/audit?filter={f}&limit=100&offset={offset}", ms_headers())
        rows = d.get("rows") or []
        contexts += rows
        if len(rows) < 100:
            break
        offset += 100
    print(f"# Контроль отгрузок ({'ПРОВЕРКА' if DRY else 'ЗАПИСЬ'}): журнал с {since} МСК, записей: {len(contexts)}")
    state, state_name = state_meta()
    if not state:
        print("ОШИБКА: в МС нет статуса отгрузки со словом «удален» — статус не поставлю")
    problems = 0
    for ctx in contexts:
        if not is_app(ctx):
            continue
        ev = http("GET", f"{MS_API}/audit/{ctx['id']}/events?limit=100", ms_headers())
        for e in ev.get("rows") or []:
            rem = removed_positions(e.get("diff"))
            href = ((e.get("entity") or {}).get("meta") or {}).get("href")
            if not rem or not href:
                continue
            dem = http("GET", href, ms_headers())
            when = datetime.strptime(e["moment"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MSK).astimezone(ALMATY)
            tag = f"{MARK} {when:%d.%m.%Y %H:%M}"
            if tag in (dem.get("description") or ""):
                continue  # уже отмечено
            order = dem.get("customerOrder")
            if not order:
                continue
            opos = http("GET", order["meta"]["href"] + "/positions?limit=1000", ms_headers()).get("rows") or []
            in_order = {pos_id(p) for p in opos}
            dpos = http("GET", href + "/positions?limit=1000", ms_headers()).get("rows") or []
            now_q = {}
            for p in dpos:
                now_q[pos_id(p)] = now_q.get(pos_id(p), 0) + float(p.get("quantity") or 0)
            # позиция есть в заказе и в отгрузке её до сих пор не вернули
            ordered = {}
            for p in opos:
                ordered[pos_id(p)] = ordered.get(pos_id(p), 0) + float(p.get("quantity") or 0)
            bad = [(n, q) for i, n, q in rem if i in in_order and now_q.get(i, 0) < ordered[i]]
            if not bad:
                continue
            problems += 1
            user = (ctx.get("uid") or "").split("@")[0]
            what = "; ".join(f"{n} — {q:g} шт" for n, q in bad)
            line = f"{tag} ({user}): {what}. Позиция есть в заказе {(http('GET', order['meta']['href'], ms_headers()).get('name'))}."
            print(f"- Отгрузка {dem.get('name')}: {what}")
            if DRY:
                continue
            body = {"description": ((dem.get("description") or "") + "\n" + line).strip()}
            if state:
                body["state"] = state
            http("PUT", href, ms_headers(), body)
            due = datetime.now(ALMATY).replace(hour=20, minute=0, second=0, microsecond=0)
            if due <= datetime.now(ALMATY):
                due += timedelta(days=1)
            for fio, emp in ASSIGNEES.items():
                http("POST", f"{MS_API}/entity/task", ms_headers(), {
                    "description": f"Проверить отгрузку {dem.get('name')}: с ТСД удалено — {what}. "
                                   f"В заказе позиция есть. Если товар отгружен — вернуть позицию в отгрузку.",
                    "assignee": ms_meta("employee", emp),
                    "operation": {"meta": dem["meta"]},
                    "dueToDate": due.astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S"),
                })
            print(f"  статус «{state_name}», комментарий, задачи: {', '.join(ASSIGNEES)}")
    print(f"Найдено отгрузок с удалёнными позициями: {problems}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ОШИБКА контроля отгрузок: {e}")
        sys.exit(1)
