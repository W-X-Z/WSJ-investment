"""sec_filings — 유니버스 종목의 공시 인덱스 (8-K items, 10-K/Q, 13D/G, S-1 ...).

본문은 저장하지 않는다. 8-K 의 items 배열이 핵심 (1.01 중요 계약, 2.02 실적, 5.02 임원 변경 ...).
워터마크: last_file_date.
"""

from __future__ import annotations

from datetime import timedelta

from wsj.collectors._efts import index_url, iter_hits
from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import parse_date

# 주의: "/A"(정정) 폼을 목록에 섞으면 EFTS 가 0건을 돌려준다 (2026-10 확인). 정정은 별도 수집 (BACKLOG).
FORMS = "8-K,10-K,10-Q,SCHEDULE 13D,SCHEDULE 13G,S-1,S-3,424B5,DEF 14A"


class SecFilingsCollector(Collector):
    name = "sec_filings"
    tables = ("raw.sec_filings",)
    schedule = "daily"
    description = "유니버스 발행인의 공시 인덱스 (8-K items 포함)"
    needs_universe = True

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        universe = {int(r["cik"]) for r in self.universe(ctx, ("cik",))}
        start = self.start_date(ctx, "last_file_date", default_lookback_days=7)
        end = ctx.today()
        log.info("filings window %s..%s, universe=%d", start, end, len(universe))

        rows: dict[str, dict] = {}
        scanned = 0
        for hit in iter_hits(http, FORMS, start, end):
            scanned += 1
            src = hit["_source"]
            adsh = src.get("adsh")
            if not adsh or adsh in rows:
                continue
            ciks = [int(c) for c in src.get("ciks", [])]
            hit_universe = [c for c in ciks if c in universe]
            if not hit_universe:
                continue
            fname = hit["_id"].split(":", 1)[1] if ":" in hit["_id"] else None
            rows[adsh] = {
                "accession_no": adsh,
                "cik": hit_universe[0],
                "ciks": ciks,
                "form": src.get("form"),
                "root_form": (src.get("root_forms") or [None])[0],
                "file_date": parse_date(src.get("file_date")),
                "period_ending": parse_date(src.get("period_ending")),
                "items": src.get("items") or [],
                "display_names": src.get("display_names") or [],
                "primary_doc": fname,
                "sics": src.get("sics") or [],
                "biz_states": src.get("biz_states") or [],
                "inc_states": src.get("inc_states") or [],
                "file_url": index_url(ciks[0], adsh),
                "payload": {
                    k: src.get(k)
                    for k in ("file_num", "film_num", "xsl", "schema_version", "file_description")
                },
            }
            if ctx.limit and len(rows) >= ctx.limit:
                break
        res.add(store.upsert("raw.sec_filings", list(rows.values()), ["accession_no"]))
        res.notes.append(f"scanned={scanned} universe_filings={len(rows)}")
        res.watermark = {"last_file_date": (end - timedelta(days=1)).isoformat()}
        return res
