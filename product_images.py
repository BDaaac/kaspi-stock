"""Скачать фото товаров МС, у которых путь группы содержит GROUP, в папку images/<код>/."""
import os, re, urllib.parse, urllib.request
from orders_sync import MS_API, http

tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip"}
GROUP = os.environ["GROUP"].lower()
os.makedirs("images", exist_ok=True)
rows, off = [], 0
while True:
    d = http("GET", f"{MS_API}/entity/product?limit=1000&offset={off}", H)
    rows += d.get("rows") or []
    if len(d.get("rows") or []) < 1000:
        break
    off += 1000
sel = [p for p in rows if GROUP in (p.get("pathName") or "").lower() and not p.get("archived")]
log = []
for p in sel:
    code = re.sub(r'[\\/:*?"<>|]', "_", p.get("code") or p["id"])
    imgs = http("GET", p["meta"]["href"] + "/images?limit=100", H).get("rows") or []
    log.append(f"{code}\t{p.get('pathName')}\t{len(imgs)}\t{p.get('name')}")
    for i, im in enumerate(imgs, 1):
        href = im["meta"]["downloadHref"]
        req = urllib.request.Request(href, headers={"Authorization": f"Bearer {tok}"})
        ext = os.path.splitext(im.get("filename") or "")[1] or ".jpg"
        d = os.path.join("images", code); os.makedirs(d, exist_ok=True)
        with urllib.request.urlopen(req, timeout=120) as r, open(os.path.join(d, f"{code}_{i}{ext}"), "wb") as f:
            f.write(r.read())
open("images/_список.tsv", "w").write("код\tгруппа\tфото\tнаименование\n" + "\n".join(log) + "\n")
print(f"товаров: {len(sel)}, с фото: {sum(1 for l in log if l.split(chr(9))[2] != '0')}")
