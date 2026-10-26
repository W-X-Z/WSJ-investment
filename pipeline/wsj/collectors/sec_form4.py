"""sec_form4 — 유니버스 종목의 Form 4 를 EFTS 로 찾아 XML 을 파싱해 적재한다.

- 워터마크: last_file_date (그날부터 다시 — 멱등이므로 중복 안전)
- 유니버스 밖 발행인은 건너뛴다 (과거 전체 커버리지는 C-08 DERA 백필 담당)
- 하루 ~1,000 건 중 유니버스는 보통 수십 건 → XML 요청은 그만큼만
"""

from __future__ import annotations

from datetime import timedelta

from wsj.collectors._efts import archive_url, index_url, iter_hits
from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.parsers.form4_xml import parse_form4
from wsj.util import parse_date


class SecForm4Collector(Collector):
    name = "sec_form4"
    tables = ("raw.sec_form4_filings", "raw.sec_form4_transactions")
    schedule = "daily"
    description = "유니버스 발행인의 Form 4 (EFTS → ownershipDocument XML)"
    needs_universe = True

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        universe = {int(r["cik"]) for r in self.universe(ctx, ("cik",))}
        start = self.start_date(ctx, "last_file_date", default_lookback_days=7)
        end = ctx.today()
        log.info("form4 window %s..%s, universe=%d", start, end, len(universe))

        seen: set[str] = set()
        filings: list[dict] = []
        txs: list[dict] = []
        scanned = 0
        last_date = start
        for hit in iter_hits(http, "4", start, end, max_pages=None):
            scanned += 1
            src = hit["_source"]
            adsh = src.get("adsh")
            fname = hit["_id"].split(":", 1)[1] if ":" in hit["_id"] else "primary_doc.xml"
            if not adsh or adsh in seen or not fname.lower().endswith(".xml"):
                continue
            ciks = [int(c) for c in src.get("ciks", [])]
            if not (set(ciks) & universe):
                continue
            seen.add(adsh)
            url = archive_url(ciks[0], adsh, fname)
            try:
                xml_text = http.get_text(url)
                parsed = parse_form4(xml_text)
            except Exception as exc:  # noqa: BLE001 - 한 건 실패가 하루치를 막지 않게
                res.notes.append(f"parse fail {adsh}: {exc}")
                log.warning("form4 parse fail %s (%s)", url, exc)
                continue
            if parsed.header["issuer_cik"] not in universe:
                continue
            if not parsed.header.get("document_type"):
                res.notes.append(f"skip {adsh}: documentType 없음")
                continue
            fd = parse_date(src.get("file_date"))
            header = {
                **parsed.header,
                "accession_no": adsh,
                "file_date": fd,
                "file_url": index_url(ciks[0], adsh),
            }
            filings.append(header)
            for row in parsed.rows:
                txs.append({**row, "accession_no": adsh})
            if fd and fd > last_date:
                last_date = fd
            if ctx.limit and len(filings) >= ctx.limit:
                break

        # 헤더 먼저 (FK), 거래는 같은 adsh 의 기존 행을 지우고 다시 넣는다 (정정으로 행 수가 줄 수 있음)
        if filings:
            res.add(store.upsert("raw.sec_form4_filings", filings, ["accession_no"]))
            store.delete("raw.sec_form4_transactions", {"accession_no": [f["accession_no"] for f in filings]})
            res.add(store.upsert("raw.sec_form4_transactions", txs, ["accession_no", "seq"]))
        res.notes.insert(0, f"scanned={scanned} universe_filings={len(filings)} rows={len(txs)}")
        # 다음 실행은 마지막 처리일부터 다시 (공시가 늦게 색인되는 경우 대비 하루 겹침)
        res.watermark = {"last_file_date": (max(last_date, end) - timedelta(days=1)).isoformat()}
        return res
