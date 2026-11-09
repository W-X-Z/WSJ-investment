"""N11 공시 수집·섹션 분리: 최근 n년 연차보고서 + 그 뒤 분기보고서 + 최근 8-K 보도자료 → 번호 붙은 문단.

  연차   10-K(없으면 20-F·40-F) Item 1·1A·7. 10-K 가 n개보다 적으면(신규 상장) 가장 최근 S-1/424B4 를 앞에 붙인다.
  분기   마지막 연차보고서 뒤의 10-Q MD&A (최대 2건)
  8-K    최근 365일, 실적(2.02)·계약(1.01·1.02)·인수(2.01)·임원(5.02) 우선, EX-99.1 보도자료 본문
  EX-10  연차보고서·8-K 에 붙은 중요 계약 첨부의 이름·주소 (본문은 받지 않는다)

캐시: raw.sec_documents(accession_no, section='deep:<키>') — store 가 있으면 읽고 쓰고, 없으면 실행 안에서만 기억한다.
원문 전체는 저장하지 않는다(상한까지 자른 섹션 텍스트만). 문단 번호는 카드 근거(evidence)로 쓴다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from wsj.briefs.edgar_docs import ARCHIVE_URL, Filing, recent_filings
from wsj.parsers.sec_html import extract_10k_sections, extract_10q_mdna, html_to_text, truncate_text

log = logging.getLogger("wsj.deep")

ANNUAL_FORMS = ("10-K", "20-F", "40-F")
REGISTRATION_FORMS = ("424B4", "S-1/A", "S-1", "F-1")
# 섹션 상한(문자). 합 26만 자 ≈ 6.5만 토큰 → 소형 모델 한 번 호출이 10만 토큰을 넘지 않는다.
ANNUAL_CAPS = {"item_1": 120_000, "item_1a": 60_000, "item_7": 80_000}
REGISTRATION_CAP = 160_000
TENQ_CAP = 40_000
EX99_CAP = 12_000
EIGHTK_PRIO = {"2.02": 0, "1.01": 0, "1.02": 1, "2.01": 1, "5.02": 2, "3.02": 2, "8.01": 3, "7.01": 3}
SECTION_LABEL = {"item_1": "Item 1 Business", "item_1a": "Item 1A Risk Factors", "item_7": "Item 7 MD&A",
                 "prospectus": "Prospectus", "mdna": "MD&A", "ex99": "EX-99 press release", "full": "Body"}
_EX10 = re.compile(r"ex-?10|exhibit-?10|ex10", re.I)


@dataclass
class Document:
    key: str                 # '10-K FY2026' · '10-Q 2026-09-30' · '8-K 2026-10-22' · 'S-1 2026-01-30'
    form: str
    accession_no: str
    file_date: date
    period: date | None
    url: str
    sections: dict[str, str] = field(default_factory=dict)
    truncated: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)

    @property
    def fiscal_label(self) -> str:
        return self.key.split(" ", 1)[1] if " " in self.key else self.key

    def meta(self) -> dict[str, Any]:
        return {"key": self.key, "form": self.form, "accession_no": self.accession_no,
                "file_date": self.file_date.isoformat(), "period": self.period.isoformat() if self.period else None,
                "url": self.url, "sections": {k: len(v) for k, v in self.sections.items()},
                "truncated": self.truncated, "items": self.items}


class DocCache:
    """raw.sec_documents 위의 얇은 캐시. store 가 없거나 실패하면 메모리만."""

    def __init__(self, store: Any | None = None) -> None:
        self.store = store
        self.mem: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, acc: str, section: str) -> dict[str, Any] | None:
        k = (acc, f"deep:{section}")
        if k in self.mem:
            return self.mem[k]
        if self.store is None:
            return None
        try:
            rows = self.store.select("raw.sec_documents", ["text", "source_url", "extracted_by"],
                                     {"accession_no": acc, "section": f"deep:{section}"}, limit=1)
        except Exception as exc:  # noqa: BLE001
            log.warning("sec_documents read failed: %s", str(exc)[:120])
            return None
        if rows:
            self.mem[k] = rows[0]
            return rows[0]
        return None

    def put(self, cik: int, f: Filing, section: str, url: str, text: str, method: str) -> None:
        row = {"accession_no": f.accession_no, "cik": cik, "form": f.form, "section": f"deep:{section}",
               "file_date": f.file_date.isoformat(), "period_ending": f.report_date.isoformat() if f.report_date else None,
               "source_url": url, "char_count": len(text), "text": text, "extracted_by": method}
        self.mem[(f.accession_no, f"deep:{section}")] = row
        if self.store is None or not hasattr(self.store, "upsert"):
            return
        try:
            self.store.upsert("raw.sec_documents", [row], ["accession_no", "section"])
        except Exception as exc:  # noqa: BLE001
            log.warning("sec_documents write failed: %s", str(exc)[:120])


# ── 고르기 ────────────────────────────────────────────────────────────────────

def plan(sub: dict[str, Any], years: int = 3, as_of: date | None = None, eightk_days: int = 365,
         eightk_max: int = 6, quarters_max: int = 2) -> dict[str, list[Filing]]:
    fs = recent_filings(sub)
    as_of = as_of or date.today()
    fs = [f for f in fs if f.file_date <= as_of]
    annual = [f for f in fs if f.form in ANNUAL_FORMS][:years]
    registration: list[Filing] = []
    if len(annual) < years:
        reg = next((f for f in fs if f.form in REGISTRATION_FORMS), None)
        if reg and (not annual or reg.file_date < annual[-1].file_date):
            registration = [reg]
    last_annual = annual[0].file_date if annual else (registration[0].file_date if registration else date.min)
    quarterly = [f for f in fs if f.form == "10-Q" and f.file_date > last_annual][:quarters_max]
    since = as_of - timedelta(days=eightk_days)
    eightks = [f for f in fs if f.form in ("8-K", "6-K") and f.file_date >= since]

    def rank(f: Filing) -> tuple[int, int]:
        return (min((EIGHTK_PRIO.get(i, 9) for i in f.items), default=9), -f.file_date.toordinal())

    eightks = sorted([f for f in eightks if any(i in EIGHTK_PRIO for i in f.items)], key=rank)[:eightk_max]
    eightks.sort(key=lambda f: f.file_date, reverse=True)
    return {"annual": annual, "registration": registration, "quarterly": quarterly, "eightks": eightks}


def doc_key(f: Filing) -> str:
    if f.form in ANNUAL_FORMS:
        return f"{f.form} FY{(f.report_date or f.file_date).year}"
    if f.form in REGISTRATION_FORMS:
        return f"{f.form} {f.file_date.isoformat()}"
    if f.form == "10-Q":
        return f"10-Q {(f.report_date or f.file_date).isoformat()}"
    return f"{f.form} {f.file_date.isoformat()}"


# ── 받기 ──────────────────────────────────────────────────────────────────────

def _doc(f: Filing, cik: int) -> Document:
    return Document(doc_key(f), f.form, f.accession_no, f.file_date, f.report_date, f.doc_url(cik), items=list(f.items))


def fetch_annual(http: Any, cache: DocCache, cik: int, f: Filing, caps: dict[str, int] | None = None) -> Document:
    caps = caps or ANNUAL_CAPS
    d = _doc(f, cik)
    cached = {k: cache.get(f.accession_no, k) for k in caps}
    if all(cached.values()):
        d.sections = {k: v["text"] for k, v in cached.items() if v}
        d.truncated = [k for k, v in cached.items() if v and v.get("extracted_by", "").endswith("+cut")]
        return d
    raw = http.get_text(d.url)
    secs = extract_10k_sections(raw, {k: 10**8 for k in caps})
    for k, cap in caps.items():
        s = secs.get(k)
        if s is None:
            continue
        text, cut = s.text, len(s.text) > cap
        if cut:
            text = truncate_text(text, cap, tail_ratio=0.15 if k == "item_7" else 0.0)
            d.truncated.append(k)
        d.sections[k] = text
        cache.put(cik, f, k, d.url, text, s.method + ("+cut" if cut else ""))
    if not d.sections:
        log.warning("annual sections not found %s %s — using document head", cik, f.accession_no)
        text = truncate_text(html_to_text(raw), sum(caps.values()))
        d.sections["full"] = text
        d.truncated.append("full")
        cache.put(cik, f, "full", d.url, text, "full+cut")
    return d


def fetch_registration(http: Any, cache: DocCache, cik: int, f: Filing, cap: int = REGISTRATION_CAP) -> Document:
    """S-1·424B4 는 Item 번호가 없다 → 'Business' 절을 찾고, 못 찾으면 앞부분(요약·위험·사업이 앞쪽에 있다)."""
    d = _doc(f, cik)
    hit = cache.get(f.accession_no, "prospectus")
    if hit:
        d.sections["prospectus"] = hit["text"]
        return d
    text = html_to_text(http.get_text(d.url))
    m = re.search(r"\n\s*BUSINESS\s*\n", text)
    body = text[m.start():] if m and m.start() > len(text) * 0.15 else text
    cut = len(body) > cap
    body = truncate_text(body, cap)
    d.sections["prospectus"] = body
    if cut:
        d.truncated.append("prospectus")
    cache.put(cik, f, "prospectus", d.url, body, "business_heading" if body is not text else "head")
    return d


def fetch_quarterly(http: Any, cache: DocCache, cik: int, f: Filing, cap: int = TENQ_CAP) -> Document | None:
    d = _doc(f, cik)
    hit = cache.get(f.accession_no, "mdna")
    if hit:
        d.sections["mdna"] = hit["text"]
        return d
    try:
        sec = extract_10q_mdna(http.get_text(d.url), cap)
    except Exception as exc:  # noqa: BLE001
        log.warning("10-Q fetch failed %s: %s", d.url, str(exc)[:120])
        return None
    if sec is None:
        return None
    d.sections["mdna"] = sec.text
    if sec.truncated:
        d.truncated.append("mdna")
    cache.put(cik, f, "mdna", d.url, sec.text, sec.method)
    return d


def _index(http: Any, cik: int, f: Filing) -> list[str]:
    base = ARCHIVE_URL.format(cik=cik, acc=f.accession_no.replace("-", ""), doc="")
    try:
        idx = http.get_json(base + "index.json")
    except Exception as exc:  # noqa: BLE001
        log.warning("index fetch failed %s: %s", base, str(exc)[:120])
        return []
    return [i.get("name", "") for i in (idx.get("directory") or {}).get("item", [])]


def fetch_eightk(http: Any, cache: DocCache, cik: int, f: Filing, cap: int = EX99_CAP) -> Document | None:
    """8-K 본문(항목 설명) + EX-99.1. 실적·수주 숫자는 대개 EX-99 에 있다."""
    d = _doc(f, cik)
    for sec in ("full", "ex99"):
        hit = cache.get(f.accession_no, sec)
        if hit:
            d.sections[sec] = hit["text"]
    if d.sections:
        return d
    try:
        body = truncate_text(html_to_text(http.get_text(d.url)), 6_000)
        d.sections["full"] = body
        cache.put(cik, f, "full", d.url, body, "full")
    except Exception as exc:  # noqa: BLE001
        log.warning("8-K fetch failed %s: %s", d.url, str(exc)[:120])
    names = _index(http, cik, f)
    ex = sorted((n for n in names if n.lower().endswith((".htm", ".html")) and "99" in n.lower() and "ex" in n.lower()),
                key=lambda n: ("99_1" in n or "991" in n or "99-1" in n, -len(n)), reverse=True)
    if ex:
        url = ARCHIVE_URL.format(cik=cik, acc=f.accession_no.replace("-", ""), doc=ex[0])
        try:
            text = html_to_text(http.get_text(url))
            if len(text) > cap:
                d.truncated.append("ex99")
            text = truncate_text(text, cap)
            d.sections["ex99"] = text
            cache.put(cik, f, "ex99", url, text, "full")
        except Exception as exc:  # noqa: BLE001
            log.warning("EX-99 fetch failed %s: %s", url, str(exc)[:120])
    return d if d.sections else None


def exhibit10(http: Any, cik: int, f: Filing) -> list[dict[str, str]]:
    out = []
    for n in _index(http, cik, f):
        if _EX10.search(n) and n.lower().endswith((".htm", ".html", ".txt")):
            out.append({"name": n, "url": ARCHIVE_URL.format(cik=cik, acc=f.accession_no.replace("-", ""), doc=n),
                        "filing": doc_key(f)})
    return out


def collect(http: Any, sub: dict[str, Any], cik: int, store: Any | None = None, years: int = 3,
            as_of: date | None = None, with_exhibits: bool = True) -> dict[str, Any]:
    """plan → 받기. 하나가 실패해도 나머지는 돌려주고 errors 에 남긴다."""
    cache = DocCache(store)
    p = plan(sub, years=years, as_of=as_of)
    out: dict[str, Any] = {"cik": cik, "annual": [], "quarterly": [], "eightks": [], "exhibit10": [], "errors": []}
    for f in p["registration"]:
        try:
            out["annual"].append(fetch_registration(http, cache, cik, f))
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"{doc_key(f)}: {str(exc)[:160]}")
    for f in p["annual"]:
        try:
            out["annual"].append(fetch_annual(http, cache, cik, f))
        except Exception as exc:  # noqa: BLE001
            out["errors"].append(f"{doc_key(f)}: {str(exc)[:160]}")
    out["annual"].sort(key=lambda d: d.file_date, reverse=True)
    for f in p["quarterly"]:
        d = fetch_quarterly(http, cache, cik, f)
        if d:
            out["quarterly"].append(d)
    for f in p["eightks"]:
        d = fetch_eightk(http, cache, cik, f)
        if d:
            out["eightks"].append(d)
    if with_exhibits:
        for f in p["annual"][:1] + [e for e in p["eightks"] if "1.01" in e.items]:
            out["exhibit10"] += exhibit10(http, cik, f)
    return out


# ── 문단 번호 ─────────────────────────────────────────────────────────────────

def paragraphs(text: str, min_len: int = 40, max_len: int = 2_500) -> list[str]:
    """빈 줄로 나누고, 짧은 줄(제목)은 다음 문단 앞에 붙이고, 너무 긴 문단은 문장 경계에서 자른다."""
    out: list[str] = []
    carry = ""
    for block in re.split(r"\n\s*\n", text or ""):
        b = re.sub(r"[ \t]+", " ", block).strip()
        if not b:
            continue
        if len(b) < min_len and not re.search(r"[.:;]$", b):
            carry = f"{carry} {b}".strip() if carry else b
            continue
        if carry:
            b = f"{carry} — {b}"
            carry = ""
        while len(b) > max_len:
            cut = b.rfind(". ", 0, max_len)
            cut = cut + 1 if cut > max_len // 2 else max_len
            out.append(b[:cut].strip())
            b = b[cut:].strip()
        if b:
            out.append(b)
    if carry:
        out.append(carry)
    return out


def numbered(doc: Document, start: int = 1) -> tuple[str, dict[int, str], int]:
    """문서 섹션들을 [P1] … 형태로. 반환: (본문, {번호: '10-K FY2026 Item 1 Business'}, 다음 번호)."""
    lines: list[str] = []
    where: dict[int, str] = {}
    n = start
    for sec, text in doc.sections.items():
        lines.append(f"### {doc.key} — {SECTION_LABEL.get(sec, sec)}")
        for p in paragraphs(text):
            lines.append(f"[P{n}] {p}")
            where[n] = f"{doc.key} {SECTION_LABEL.get(sec, sec)}"
            n += 1
    return "\n".join(lines), where, n
