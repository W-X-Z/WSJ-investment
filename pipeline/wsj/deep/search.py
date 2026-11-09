"""공시 전문검색 (EDGAR full-text search) — 상상 단계·심층 리서치가 '누가 이 말을 공시에 썼나'를 찾는다.

산업 그래프 조회를 대신한다. 구절은 큰따옴표로 묶으면 정확히 그 구절을 찾는다("indium phosphide").
결과는 회사별로 묶어 건수·최근 공시·폼 종류를 돌려준다. 원문 링크는 SEC Archives 경로.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

EFTS = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"


def _url(src: dict[str, Any], hit_id: str) -> str | None:
    ciks = src.get("ciks") or []
    adsh = src.get("adsh") or hit_id.split(":")[0]
    fname = hit_id.split(":", 1)[1] if ":" in hit_id else None
    if not ciks or not adsh or not fname:
        return None
    return f"{ARCHIVES}/{int(ciks[0])}/{adsh.replace('-', '')}/{fname}"


def search(http: Any, q: str, forms: str = "10-K,10-Q,8-K,S-1,424B4", start: date | None = None,
           end: date | None = None, max_pages: int = 3) -> dict[str, Any]:
    end = end or date.today()
    start = start or end - timedelta(days=365)
    companies: dict[str, dict[str, Any]] = defaultdict(lambda: {"hits": 0, "forms": defaultdict(int), "filings": []})
    total = None
    for page in range(max_pages):
        data = http.get_json(EFTS, params={"q": q, "forms": forms, "dateRange": "custom", "startdt": start.isoformat(),
                                           "enddt": end.isoformat(), "from": page * 100})
        hits = (data.get("hits") or {})
        total = total if total is not None else (hits.get("total") or {}).get("value")
        rows = hits.get("hits") or []
        for h in rows:
            src = h.get("_source") or {}
            name = (src.get("display_names") or ["?"])[0]
            c = companies[name]
            c["hits"] += 1
            form = src.get("form") or src.get("file_type") or "?"
            c["forms"][form] += 1
            if len(c["filings"]) < 3:
                c["filings"].append({"form": form, "file_date": src.get("file_date"), "url": _url(src, h.get("_id", ""))})
        if len(rows) < 100:
            break
    ranked = sorted(companies.items(), key=lambda kv: (-kv[1]["hits"], kv[0]))
    return {"q": q, "forms": forms, "start": start.isoformat(), "end": end.isoformat(), "total_hits": total,
            "companies": [{"name": n, "hits": c["hits"], "forms": dict(c["forms"]),
                           "latest": sorted(c["filings"], key=lambda f: f.get("file_date") or "", reverse=True)}
                          for n, c in ranked[:40]]}
