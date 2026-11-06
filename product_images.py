"""Скачать фото товаров МС, у которых путь группы содержит GROUP, в папку images/<код>/."""
import os, re, urllib.error, urllib.parse, urllib.request
from orders_sync import MS_API, http

tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def download(href):
    """МС отдаёт файл редиректом на хранилище: туда токен слать нельзя (иначе 415)."""
    req = urllib.request.Request(href, headers={"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"})
    try:
        with _opener.open(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        if e.code in (301, 302, 303, 307, 308) and loc:
            with urllib.request.urlopen(urllib.request.Request(loc), timeout=60) as r:
                return r.read()
        raise

GROUP = os.environ["GROUP"].lower()
os.makedirs("images", exist_ok=True)
rows, off = [], 0
while True:
    d = http("GET", f"{MS_API}/entity/product?limit=1000&offset={off}", H)
    rows += d.get("rows") or []
    print("товары:", len(rows), flush=True)
    if len(d.get("rows") or []) < 1000:
        break
    off += 1000
sel = [p for p in rows if GROUP in (p.get("pathName") or "").lower() and not p.get("archived")]
print("выбрано:", len(sel), flush=True)
log = []
for p in sel:
    code = re.sub(r'[\\/:*?"<>|]', "_", p.get("code") or p["id"])
    imgs = http("GET", p["meta"]["href"] + "/images?limit=100", H).get("rows") or []
    log.append(f"{code}\t{p.get('pathName')}\t{len(imgs)}\t{p.get('name')}")
    print(code, len(imgs), flush=True)
    for i, im in enumerate(imgs, 1):
        href = im["meta"]["downloadHref"]
        ext = os.path.splitext(im.get("filename") or "")[1] or ".jpg"
        d = os.path.join("images", code); os.makedirs(d, exist_ok=True)
        for attempt in range(4):
            try:
                data = download(href)
                with open(os.path.join(d, f"{code}_{i}{ext}"), "wb") as f:
                    f.write(data)
                break
            except Exception as e:
                print("  ошибка", code, i, attempt, repr(e)[:200], flush=True)
                if attempt == 3:
                    log.append(f"{code}\tОШИБКА фото {i}: {e}")
                import time; time.sleep(3)
open("images/_список.tsv", "w").write("код\tгруппа\tфото\tнаименование\n" + "\n".join(log) + "\n")
print(f"товаров: {len(sel)}, с фото: {sum(1 for l in log if len(l.split(chr(9))) > 3 and l.split(chr(9))[2] != '0')}")
