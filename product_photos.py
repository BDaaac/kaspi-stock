"""Добавить фото в карточки товаров МС. photos/plan.json: {"файл.jpg": "код товара"}.
Внимание: POST /images заменяет весь список фото, поэтому существующие фото передаются вместе с новым."""
import base64, json, os, time, urllib.parse
from orders_sync import MS_API, http

tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip", "Content-Type": "application/json"}
CHECK = [c for c in os.environ.get("CHECK", "").split(",") if c.strip()]
if CHECK:  # только показать фото карточек
    for code in CHECK:
        f = urllib.parse.quote(f"code={code}", safe="")
        p = http("GET", f"{MS_API}/entity/product?filter={f}&limit=1", H)["rows"][0]
        im = http("GET", p["meta"]["href"] + "/images?limit=100", H).get("rows") or []
        print("IMG", code, [(x.get("filename"), x.get("size"), x.get("updated")) for x in im])
    raise SystemExit
plan = json.load(open("photos/plan.json"))
for fn, code in plan.items():
    f = urllib.parse.quote(f"code={code}", safe="")
    rows = http("GET", f"{MS_API}/entity/product?filter={f}&limit=1", H).get("rows") or []
    if not rows:
        print(f"НЕ НАЙДЕН {code}"); continue
    url = rows[0]["meta"]["href"] + "/images"
    before = http("GET", url + "?limit=100", H).get("rows") or []
    content = base64.b64encode(open(os.path.join("photos", fn), "rb").read()).decode()
    name = f"{code}_{len(before) + 1}.jpg"
    for attempt in range(4):
        try:
            http("POST", url, H, [{"meta": x["meta"]} for x in before] + [{"filename": name, "content": content}])  # POST заменяет весь список — старые передаём явно
            break
        except Exception as e:
            time.sleep(10)
            now = http("GET", url + "?limit=100", H).get("rows") or []
            if len(now) > len(before):
                break
            if attempt == 3:
                print(f"ОШИБКА {code}: {str(e)[:200]}")
    after = http("GET", url + "?limit=100", H).get("rows") or []
    print(f"OK {code}: было {len(before)}, стало {len(after)}")
