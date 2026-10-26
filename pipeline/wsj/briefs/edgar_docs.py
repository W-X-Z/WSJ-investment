"""EDGAR 원문: 제출 목록(submissions) → 최신 10-K / 10-Q / 8-K 문서 → 섹션 텍스트. `raw.sec_documents` 에 캐시.

- submissions JSON 은 `filings.recent` 에 최근 ~1,000건이 열 단위 배열로 들어 있다.
- 문서 URL: https://www.sec.gov/Archives/edgar/data/{cik}/{accession 숫자만}/{primaryDocument}
- 8-K 는 본문(primary document)만 읽는다. 첨부(보도자료 EX-99.1)는 Phase 2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from wsj.db.base import Store
from wsj.http import HttpClient
from wsj.parsers.sec_html import extract_10k_sections, extract_10q_mdna, html_to_text, truncate_text
from wsj.util import parse_date

log = logging.getLogger("wsj.briefs.edgar")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{acc_dash}-index.htm"

TENK_CAPS = {"item_1": 25_000, "item_1a": 15_000, "item_7": 25_000}
EIGHTK_CAP = 6_000
TENQ_CAP = 12_000


@dataclass
class Filing:
    accession_no: str
    form: str
    file_date: date
    report_date: date | None
    primary_doc: str
    items: list[str] = field(default_factory=list)
    description: str | None = None

    def doc_url(self, cik: int) -> str:
        return ARCHIVE_URL.format(cik=cik, acc=self.accession_no.replace("-", ""), doc=self.primary_doc)

    def index_url(self, cik: int) -> str:
        return INDEX_URL.format(cik=cik, acc=self.accession_no.replace("-", ""), acc_dash=self.accession_no)


@dataclass
class DocSection:
    accession_no: str
    form: str
    section: str
    file_date: date | None
    period_ending: date | None
    source_url: str
    text: str
    extracted_by: str
    truncated: bool = False

    def row(self, cik: int) -> dict[str, Any]:
        return {
            "accession_no": self.accession_no,
            "cik": cik,
            "form": self.form,
            "section": self.section,
            "file_date": self.file_date.isoformat() if self.file_date else None,
            "period_ending": self.period_ending.isoformat() if self.period_ending else None,
            "source_url": self.source_url,
            "char_count": len(self.text),
            "text": self.text,
            "extracted_by": self.extracted_by,
        }


def load_submissions(http: HttpClient, cik: int) -> dict[str, Any]:
    return http.get_json(SUBMISSIONS_URL.format(cik=cik))


def recent_filings(sub: dict[str, Any], forms: set[str] | None = None, limit: int = 1000) -> list[Filing]:
    rec = sub.get("filings", {}).get("recent", {})
    n = len(rec.get("accessionNumber", []))
    out: list[Filing] = []
    for i in range(min(n, limit)):
        form = rec["form"][i]
        if forms and form not in forms:
            continue
        fd = parse_date(rec["filingDate"][i])
        if fd is None:
            continue
        items_raw = (rec.get("items") or [""] * n)[i] or ""
        out.append(
            Filing(
                accession_no=rec["accessionNumber"][i],
                form=form,
                file_date=fd,
                report_date=parse_date(rec["reportDate"][i]) if rec.get("reportDate") else None,
                primary_doc=rec["primaryDocument"][i],
                items=[x.strip() for x in items_raw.split(",") if x.strip()],
                description=(rec.get("primaryDocDescription") or [None] * n)[i],
            )
        )
    return out


def _cached(store: Store, accession_no: str, sections: list[str]) -> dict[str, dict]:
    rows = store.select("raw.sec_documents", None, {"accession_no": accession_no, "section": sections})
    return {r["section"]: r for r in rows}


def tenk_sections(
    store: Store, http: HttpClient, cik: int, filing: Filing, caps: dict[str, int] | None = None
) -> list[DocSection]:
    """10-K (또는 20-F/S-1 폴백) 의 Item 1 / 1A / 7. 캐시 우선."""
    caps = caps or TENK_CAPS
    cached = _cached(store, filing.accession_no, list(caps))
    if set(cached) >= set(caps):
        return [
            DocSection(
                filing.accession_no,
                filing.form,
                k,
                filing.file_date,
                filing.report_date,
                r["source_url"],
                r["text"],
                r["extracted_by"],
            )
            for k, r in cached.items()
        ]
    url = filing.doc_url(cik)
    raw = http.get_text(url)
    secs = extract_10k_sections(raw, caps)
    out: list[DocSection] = []
    for key, sec in secs.items():
        out.append(
            DocSection(
                filing.accession_no,
                filing.form,
                key,
                filing.file_date,
                filing.report_date,
                url,
                sec.text,
                sec.method,
                sec.truncated,
            )
        )
    missing = [k for k in caps if k not in secs]
    if missing:
        # 섹션을 못 찾으면 문서 앞부분이라도 (S-1·20-F 등 형식이 다른 경우)
        log.warning("10-K sections missing %s for %s %s", missing, cik, filing.accession_no)
        if not out:
            text = truncate_text(html_to_text(raw), sum(caps.values()))
            out.append(
                DocSection(
                    filing.accession_no,
                    filing.form,
                    "full",
                    filing.file_date,
                    filing.report_date,
                    url,
                    text,
                    "full",
                    True,
                )
            )
    if out:
        store.upsert("raw.sec_documents", [s.row(cik) for s in out], ["accession_no", "section"])
    return out


def tenq_mdna(
    store: Store, http: HttpClient, cik: int, filing: Filing, cap: int = TENQ_CAP
) -> DocSection | None:
    """최신 10-Q 의 Part I Item 2 (MD&A) — 10-K 이후의 '현재 상황'. 캐시 우선."""
    cached = _cached(store, filing.accession_no, ["mdna"])
    if "mdna" in cached:
        r = cached["mdna"]
        return DocSection(
            filing.accession_no,
            filing.form,
            "mdna",
            filing.file_date,
            filing.report_date,
            r["source_url"],
            r["text"],
            r["extracted_by"],
        )
    url = filing.doc_url(cik)
    try:
        raw = http.get_text(url)
    except Exception as exc:  # noqa: BLE001
        log.warning("10-Q fetch failed %s: %s", url, exc)
        return None
    sec = extract_10q_mdna(raw, cap)
    if sec is None:
        log.warning("10-Q MD&A not found %s %s", cik, filing.accession_no)
        return None
    out = DocSection(
        filing.accession_no,
        filing.form,
        "mdna",
        filing.file_date,
        filing.report_date,
        url,
        sec.text,
        sec.method,
        sec.truncated,
    )
    store.upsert("raw.sec_documents", [out.row(cik)], ["accession_no", "section"])
    return out


def eightk_texts(
    store: Store, http: HttpClient, cik: int, filings: list[Filing], cap: int = EIGHTK_CAP
) -> list[DocSection]:
    out: list[DocSection] = []
    for f in filings:
        cached = _cached(store, f.accession_no, ["full"])
        if "full" in cached:
            r = cached["full"]
            out.append(
                DocSection(
                    f.accession_no,
                    f.form,
                    "full",
                    f.file_date,
                    f.report_date,
                    r["source_url"],
                    r["text"],
                    r["extracted_by"],
                )
            )
            continue
        url = f.doc_url(cik)
        try:
            raw = http.get_text(url)
        except Exception as exc:  # noqa: BLE001 - 한 문서 실패가 브리프를 막지 않게
            log.warning("8-K fetch failed %s: %s", url, exc)
            continue
        text = html_to_text(raw)
        truncated = len(text) > cap
        text = truncate_text(text, cap)
        sec = DocSection(
            f.accession_no, f.form, "full", f.file_date, f.report_date, url, text, "full", truncated
        )
        store.upsert("raw.sec_documents", [sec.row(cik)], ["accession_no", "section"])
        out.append(sec)
    return out


def pick_documents(
    filings: list[Filing], as_of: date, eightk_days: int = 180, eightk_max: int = 3
) -> dict[str, Any]:
    """최신 연차 보고서 1건, 최신 분기 보고서 1건, 최근 8-K ≤N건 (자금조달·계약·실적 항목 우선)."""
    annual = next((f for f in filings if f.form in ("10-K", "10-K405", "20-F", "40-F")), None)
    if annual is None:
        annual = next((f for f in filings if f.form in ("S-1", "S-1/A", "F-1", "10-12G")), None)
    quarterly = next(
        (f for f in filings if f.form in ("10-Q",) and (annual is None or f.file_date > annual.file_date)),
        None,
    )
    since = as_of - timedelta(days=eightk_days)
    eightks = [f for f in filings if f.form in ("8-K", "6-K") and f.file_date >= since]
    # 중요 항목 우선: 1.01 계약, 2.02 실적, 3.02 미등록 증권 판매, 5.02 임원 변동, 8.01 기타, 1.02 계약 종료
    prio = {"1.01": 0, "2.02": 1, "3.02": 1, "1.02": 1, "2.01": 1, "5.02": 2, "8.01": 2, "7.01": 3}

    def rank(f: Filing) -> tuple[int, int]:
        best = min((prio.get(i, 4) for i in f.items), default=4)
        return (best, -f.file_date.toordinal())

    eightks = sorted(eightks, key=rank)[:eightk_max]
    eightks.sort(key=lambda f: f.file_date, reverse=True)
    return {"annual": annual, "quarterly": quarterly, "eightks": eightks}
