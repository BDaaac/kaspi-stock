"""Файлы в карточках товаров МС: MODE=list — показать, MODE=replace — заменить.
PLAN (JSON): {"файл.pdf": {"name": "как назвать в МС", "codes": [...], "delete": [части имён старых файлов]}}"""
import base64, json, os, urllib.parse
from orders_sync import MS_API, http

tok = (os.environ.get("MS_ORDERS_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
H = {"Authorization": f"Bearer {tok}", "Accept-Encoding": "gzip", "Content-Type": "application/json"}
MODE = os.environ.get("MODE", "list")
PLAN = json.load(open("product_files_plan.json"))
out = [f"# Файлы карточек товаров ({MODE})", ""]


def product(code):
    f = urllib.parse.quote(f"code={code}", safe="")
    rows = http("GET", f"{MS_API}/entity/product?filter={f}&limit=1", H).get("rows") or []
    return rows[0] if rows else None


for src, p in PLAN.items():
    content = base64.b64encode(open(os.path.join("upload", src), "rb").read()).decode() if MODE == "replace" else None
    out.append(f"## {p['name']}")
    for code in p["codes"]:
        pr = product(code)
        if not pr:
            out.append(f"- {code}: товар не найден"); continue
        url = pr["meta"]["href"] + "/files"
        files = http("GET", url + "?limit=100", H).get("rows") or []
        names = [f"{x.get('filename') or x.get('title')} ({x.get('size', 0)//1024} КБ)" for x in files]
        line = f"- {code}: было {len(files)}: " + ("; ".join(names) or "—")
        if MODE == "replace":
            removed = []
            for x in files:
                fn = (x.get("filename") or x.get("title") or "")
                if fn == p["name"] or any(s.lower() in fn.lower() for s in p.get("delete", [])):
                    http("DELETE", x["meta"]["href"], H)
                    removed.append(fn)
            http("POST", url, H, [{"filename": p["name"], "content": content}])
            after = http("GET", url + "?limit=100", H).get("rows") or []
            line += f" | удалено: {'; '.join(removed) or '—'} | стало: " + "; ".join(x.get("filename") or x.get("title") for x in after)
        out.append(line)
    out.append("")
open("product_files_report.md", "w").write("\n".join(out))
print("\n".join(out))
