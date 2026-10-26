"""EDGAR 전문검색(EFTS) 공용 — 날짜 창·폼 기준으로 hit 를 돌려준다.

비공식 API. 응답은 Elasticsearch 형태이며 hit._id = '{adsh}:{filename}'.
하루 단위로 질의해 10,000 건 상한을 피한다. 페이지 크기는 100 고정.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

from wsj.http import HttpClient
from wsj.util import daterange

EFTS = "https://efts.sec.gov/LATEST/search-index"
PAGE = 100


def iter_hits(
    http: HttpClient, forms: str, start: date, end: date, q: str | None = None, max_pages: int | None = None
) -> Iterator[dict]:
    for day in daterange(start, end):
        page = 1
        offset = 0
        while True:
            params = {
                "forms": forms,
                "dateRange": "custom",
                "startdt": day.isoformat(),
                "enddt": day.isoformat(),
                "from": offset,
                "page": page,
            }
            if q:
                params["q"] = q
            data = http.get_json(EFTS, params=params)
            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break
            yield from hits
            if len(hits) < PAGE:
                break
            page += 1
            offset += PAGE
            if max_pages and page > max_pages:
                break


def archive_url(cik: int | str, adsh: str, filename: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{filename}"


def index_url(cik: int | str, adsh: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{adsh}-index.htm"
