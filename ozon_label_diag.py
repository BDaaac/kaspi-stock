"""Диагностика этикетки Ozon по новой схеме: v3 create -> v2 get."""
import json, os, time, urllib.request, urllib.error
from orders_sync import OZON_API, ozon_headers
pn = os.environ["PN"]
h = ozon_headers()
def post(path, body):
    req = urllib.request.Request(OZON_API + path, data=json.dumps(body).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read(); print(path, r.status, b[:600].decode("utf-8", "replace")); return json.loads(b)
    except urllib.error.HTTPError as e:
        print(path, e.code, e.read()[:600].decode("utf-8", "replace")); return {}
d = post("/v3/posting/fbs/package-label/create", {"posting_number": [pn]})
r = d.get("result") or d
tasks = r.get("tasks") or ([r] if r.get("task_id") else [])
for t in tasks:
    for _ in range(6):
        time.sleep(5)
        g = post("/v2/posting/fbs/package-label/get", {"task_id": t.get("task_id")})
        if ((g.get("result") or g).get("file_url")): break
