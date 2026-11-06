"""Диагностика этикетки Ozon: по одному запросу на метод с паузой, вывод в формате для поддержки Ozon."""
import datetime, json, os, time, urllib.request, urllib.error
from orders_sync import OZON_API, ozon_headers
pn = os.environ["PN"]
h = ozon_headers()
print("Client-Id:", h["Client-Id"], "| первые 3 символа Api-Key:", h["Api-Key"][:3])
for path in ["/v2/posting/fbs/package-label", "/v2/posting/fbs/package-label/create", "/v1/posting/fbs/package-label/create"]:
    time.sleep(20)
    body = {"posting_number": [pn]}
    t = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
    req = urllib.request.Request(OZON_API + path, data=json.dumps(body).encode(), headers=h, method="POST")
    print("=" * 60)
    print("Время запроса (Алматы, UTC+5):", t.strftime("%d.%m.%Y %H:%M:%S"))
    print("Метод: POST", OZON_API + path)
    print("Тело запроса:", json.dumps(body, ensure_ascii=False))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print("Ответ:", r.status, "| x-o3-trace-id:", r.headers.get("x-o3-trace-id"), "| тип:", r.headers.get("Content-Type"))
            b = r.read()
            print("Тело ответа:", b[:300].decode("utf-8", "replace") if b"%PDF" not in b[:10] else f"PDF {len(b)} байт")
    except urllib.error.HTTPError as e:
        hd = {k: v for k, v in e.headers.items() if k.lower().startswith(("x-o3", "x-ratelimit", "ratelimit", "retry", "date"))}
        print("Ответ:", e.code, "| заголовки:", json.dumps(hd, ensure_ascii=False))
        print("Тело ответа:", e.read()[:500].decode("utf-8", "replace"))
