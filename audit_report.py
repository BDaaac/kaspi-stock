"""Журнал аудита МС за период (что и кем менялось) — результат шифруется, как stock_value."""
import json, os, urllib.parse
from orders_sync import MS_API, http

FROM = os.environ.get("AUDIT_FROM", "2026-10-09 12:00:00")
TO = os.environ.get("AUDIT_TO", "2026-10-09 18:00:00")
EXTRA = os.environ.get("AUDIT_FILTER", "").strip()  # напр. entityType=demand;source=remap-1.2
out = {"from": FROM, "to": TO, "contexts": []}
for env in ("MS_ORDERS_TOKEN", "MS_TOKEN"):
    tok = os.environ.get(env, "").strip()
    if not tok:
        continue
    h = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
    try:
        f = urllib.parse.quote(f"moment>={FROM};moment<={TO}" + (";" + EXTRA if EXTRA else ""), safe="")
        offset = 0
        while True:
            d = http("GET", f"{MS_API}/audit?filter={f}&limit=100&offset={offset}", h)
            rows = d.get("rows") or []
            for ctx in rows:
                ev = http("GET", f"{MS_API}/audit/{ctx['id']}/events?limit=100", h)
                out["contexts"].append({"ctx": {k: ctx.get(k) for k in ("moment", "uid", "source", "info", "entityType", "eventType", "objectCount")},
                                        "events": [{k: e.get(k) for k in ("moment", "uid", "source", "eventType", "entityType", "objectType", "name", "diff", "additionalInfo")}
                                                   for e in ev.get("rows") or []]})
            if len(rows) < 100:
                break
            offset += 100
        out["token"] = env
        break
    except Exception as e:
        out.setdefault("errors", []).append(f"{env}: {e}")
json.dump(out, open("audit.json", "w"), ensure_ascii=False)
print("contexts:", len(out["contexts"]), "errors:", out.get("errors"))
