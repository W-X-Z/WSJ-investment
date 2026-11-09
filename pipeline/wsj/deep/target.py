"""N10 대상 확정: 티커 → 상장 정보 · 시총 · 주가 · 공시 식별자.

  미국  SEC 티커표로 CIK, submissions 로 최근 공시 목록(10-K·10-Q·8-K·S-1 등)
  한국  6자리 코드 → OpenDART 고유번호(DART_API_KEY 가 있을 때). 공급망 지도 조회는 고유번호로 한다.
시세·시총은 tools.quote 를 그대로 쓴다 (실패해도 나머지는 돌려주고 errors 에 남긴다).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from wsj.tools.context import ToolContext, ToolError, ensure_context
from wsj.tools.lookup import sec_cik
from wsj.tools.prices import parse_symbol

log = logging.getLogger("wsj.deep")

FILING_FORMS = {"10-K", "10-K/A", "10-Q", "8-K", "S-1", "S-1/A", "424B4", "20-F", "40-F", "6-K", "DEF 14A"}


_SHARE_CLASS = re.compile(r"\s+(class\s+[a-z]\s+)?(common\s+stock|ordinary\s+shares|american\s+depositary\s+shares)\b.*$", re.I)


def clean_name(name: str | None) -> str | None:
    """'Centrus Energy Corp. Class A Common Stock' → 'Centrus Energy Corp.'"""
    return _SHARE_CLASS.sub("", name).strip() if name else name


def sec_http(ctx: ToolContext) -> Any:
    """SEC 전용 HttpClient (연락처 UA 필수). ctx.memo 에 하나만 둔다."""
    if "sec_http" not in ctx.memo:
        from wsj.config import load_settings
        from wsj.http import HttpClient

        h = HttpClient(load_settings().sec_user_agent, timeout=60.0, max_retries=3)
        ctx.memo["sec_http"] = h
        ctx._closers.append(h)
    return ctx.memo["sec_http"]


def submissions(ctx: ToolContext, cik: int) -> dict[str, Any]:
    key = f"sec_sub:{cik}"
    if key not in ctx.memo:
        from wsj.briefs.edgar_docs import load_submissions

        ctx.memo[key] = load_submissions(sec_http(ctx), cik)
    return ctx.memo[key]


def dart_corp_code(ctx: ToolContext, stock_code: str) -> str | None:
    from wsj.config import load_settings

    key = load_settings().dart_api_key
    if not key:
        return None
    if "dart_corp_codes" not in ctx.memo:
        from wsj.ecosystems.dart import load_corp_codes
        from wsj.http import HttpClient

        h = HttpClient("WSJ-investment research", timeout=60.0, max_retries=2)
        ctx._closers.append(h)
        try:
            ctx.memo["dart_corp_codes"] = load_corp_codes(h, key)
        except Exception as exc:  # noqa: BLE001
            log.warning("DART corp codes failed: %s", str(exc)[:160])
            ctx.memo["dart_corp_codes"] = {}
    return ctx.memo["dart_corp_codes"].get(stock_code)


def target(symbol: str, ctx: ToolContext | None = None, filings_limit: int = 40) -> dict[str, Any]:
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        out: dict[str, Any] = {"symbol": sym.code, "market": sym.market, "currency": sym.currency, "errors": []}
        try:
            from wsj.tools.quote import quote

            q = quote(sym.code, ctx=c)
            out.update(name=clean_name(q.get("name")), exchange=q.get("exchange"), sector=q.get("sector"), industry=q.get("industry"),
                       price=q.get("price"), market_cap=q.get("market_cap"), changes=q.get("changes"),
                       range_52w=q.get("range_52w"), history_from=q.get("history_from"))
        except ToolError as exc:
            out["errors"].append(f"quote: {exc}")
        if sym.market == "us":
            cik = sec_cik(c, sym.code)
            out["cik"] = cik
            if cik is None:
                out["errors"].append("sec: 티커표에 CIK 없음")
                return out
            try:
                from wsj.briefs.edgar_docs import recent_filings

                sub = submissions(c, cik)
                out["name"] = out.get("name") or sub.get("name")
                out["sic"] = sub.get("sic")
                out["sic_description"] = sub.get("sicDescription")
                out["fiscal_year_end"] = sub.get("fiscalYearEnd")
                fs = recent_filings(sub, FILING_FORMS)
                out["filings"] = [{"form": f.form, "file_date": f.file_date.isoformat(),
                                   "report_date": f.report_date.isoformat() if f.report_date else None,
                                   "accession_no": f.accession_no, "items": f.items, "url": f.doc_url(cik)}
                                  for f in fs[:filings_limit]]
            except Exception as exc:  # noqa: BLE001
                out["errors"].append(f"sec submissions: {str(exc)[:160]}")
        else:
            out["corp_code"] = dart_corp_code(c, sym.code)
            if out["corp_code"] is None:
                out["errors"].append("dart: 고유번호 없음(DART_API_KEY 확인) — 공급망 지도는 종목코드로 찾는다")
        return out
