"""Разово: перенести заказы FBO на склад «Ozon FBO» и показать результат."""
import orders_sync as o
for ext in ("ozonfbo-42156903-1075-1", "ozonfbo-42156903-1075-3"):
    try:
        ex = o.ms_existing(ext)
        o.log(f"{ext}: до — склад {ex['store']['meta']['href'].rsplit('/',1)[-1]}")
        r = o.http("PUT", ex["meta"]["href"], o.ms_headers(), {"store": o.ms_meta("store", o.STORE_OZON_FBO)})
        o.log(f"{ext}: после PUT — склад {r['store']['meta']['href'].rsplit('/',1)[-1]}")
    except Exception as e:
        o.log(f"{ext}: ОШИБКА {e}")
open(o.REPORT, "w", encoding="utf-8").write("\n".join(o.lines) + "\n")
