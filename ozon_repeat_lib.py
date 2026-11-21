from datetime import datetime, timedelta, timezone
def fbs_full(o, H, days):
    now = datetime.now(timezone.utc); out = []; end = now; start_all = now - timedelta(days=days)
    while end > start_all:
        beg = max(start_all, end - timedelta(days=90)); cursor = ""
        for _ in range(200):
            d = o.http("POST", f"{o.OZON_API}/v4/posting/fbs/list", H, {"sort_dir": "asc", "cursor": cursor, "limit": 100,
                       "filter": {"since": o.iso(beg), "to": o.iso(end)}})
            res = d.get("result") if isinstance(d.get("result"), dict) else d
            out += res.get("postings") or []
            if not res.get("has_next"): break
            cursor = res.get("cursor") or ""
        end = beg
    seen = {}; [seen.setdefault(p["posting_number"], p) for p in out]
    return list(seen.values())
