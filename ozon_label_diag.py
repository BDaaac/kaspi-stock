"""Диагностика: одна попытка скачать этикетку Ozon с паузами, печать заголовков ответа."""
import json, os, time, urllib.request, urllib.error
from orders_sync import OZON_API, ozon_headers
pn = os.environ["PN"]
for i, path in enumerate(["/v2/posting/fbs/package-label", "/v2/posting/fbs/package-label/create", "/v1/posting/fbs/package-label/create"]):
    time.sleep(20)
    req = urllib.request.Request(OZON_API + path, data=json.dumps({"posting_number": [pn]}).encode(),
                                 headers=ozon_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            print(path, r.status, dict(r.headers), b[:300])
    except urllib.error.HTTPError as e:
        print(path, e.code, dict(e.headers), e.read()[:500])
