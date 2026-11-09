"""`python -m wsj deep <cmd>` — 3단계 코드 도구. 결과는 JSON 한 덩어리(stdout), 로그는 stderr.

  target   SYMBOL                         N10 상장 정보·시총·주가·최근 공시
  filings  SYMBOL [--years 3]             N11 받을 문서 목록과 섹션 길이 (본문은 --text 로)
  cards    SYMBOL [--years 3] [--plan]    N12 구조 카드 (미국: 캐시 → 소형 모델 추출 → research.reports, 한국: 공급망 지도)
  profile  SYMBOL [--years 3]             N13 최신 카드 + 연도별 변화 + 빈 칸 + 시세 (카드가 없으면 cards 를 먼저)
  story    SYMBOL [--days 365] [--top 8]  N14 크게 움직인 날 + 그날 공시 (번호 = 차트 표시)
  fin      SYMBOL [--years 5]             N15 연도별·TTM 재무 지표 + 크게 튄 값
  peers    SYMBOL PEER [PEER …]           N18 피어 비교표 (배수·성장·이익률, 피어 중앙값)
  valuation SYMBOL                        N19 현재·과거 배수, 역DCF 내재 성장률
  scenario --file spec.json               N20 Bear/Base/Bull 가정 → 주당가치·배수, 2배·3배 필요 이익
  chart    SYMBOL --out f.png             N24 주가 차트 PNG (story 번호 표시)
  save     --file report.json             N23 원천·리포트 저장 (research.reports kind='idea')

공통: --no-db (Supabase 를 쓰지 않음: 캐시·저장 없음), --dry (추출은 하되 저장 안 함), --compact.
비용: cards 는 미국 문서 1건당 소형 모델 1~2회 (약 $0.01). --plan 은 모델을 부르지 않고 대상만 보여 준다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

COMMANDS = ("target", "filings", "cards", "profile", "story", "fin", "peers", "valuation", "scenario", "chart", "save", "notion", "search")


def add_deep_parser(sub: Any) -> argparse.ArgumentParser:
    d = sub.add_parser("deep", help="3단계 심층 리서치 코드 도구 (대상·공시·구조 카드·프로필)",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ds = d.add_subparsers(dest="deep_cmd", required=True, metavar="{" + ",".join(COMMANDS) + "}")
    c = argparse.ArgumentParser(add_help=False)
    c.add_argument("symbol", help="미국 티커(FPS) 또는 한국 6자리 코드(001440)")
    c.add_argument("--no-db", action="store_true", help="Supabase 캐시·저장을 쓰지 않는다")
    c.add_argument("--compact", action="store_true")
    c.add_argument("-v", "--verbose", action="store_true")
    ds.add_parser("target", parents=[c], help="N10 대상 확정")
    f = ds.add_parser("filings", parents=[c], help="N11 공시 수집")
    f.add_argument("--years", type=int, default=3)
    f.add_argument("--text", action="store_true", help="번호 붙은 본문까지 출력")
    k = ds.add_parser("cards", parents=[c], help="N12 구조 카드")
    k.add_argument("--years", type=int, default=3)
    k.add_argument("--plan", action="store_true", help="모델을 부르지 않고 대상 문서·크기만")
    k.add_argument("--dry", action="store_true", help="추출은 하되 DB 에 저장하지 않는다")
    k.add_argument("--model", default=None, help="기본 claude-haiku-5-5")
    k.add_argument("--force", action="store_true", help="캐시를 무시하고 다시 뽑는다")
    p = ds.add_parser("profile", parents=[c], help="N13 종목 프로필")
    p.add_argument("--years", type=int, default=3)
    p.add_argument("--dry", action="store_true")
    st = ds.add_parser("story", parents=[c], help="N14 주가 이슈")
    st.add_argument("--days", type=int, default=365)
    st.add_argument("--top", type=int, default=8)
    st.add_argument("--series", action="store_true", help="일봉 종가 목록도 출력")
    fn = ds.add_parser("fin", parents=[c], help="N15 펀더멘탈 계산")
    fn.add_argument("--years", type=int, default=5)
    pr = ds.add_parser("peers", parents=[c], help="N18 피어 비교표")
    pr.add_argument("peers", nargs="+", help="피어 티커·코드")
    ds.add_parser("valuation", parents=[c], help="N19 현재·과거 배수, 역DCF")
    nc = argparse.ArgumentParser(add_help=False)
    nc.add_argument("--compact", action="store_true")
    nc.add_argument("-v", "--verbose", action="store_true")
    sc = ds.add_parser("scenario", parents=[nc], help="N20 향후 밸류 계산")
    sc.add_argument("--file", required=True, help="가정 JSON 파일 경로 또는 JSON 문자열")
    ch = ds.add_parser("chart", parents=[c], help="N24 주가 차트 PNG")
    ch.add_argument("--out", required=True)
    ch.add_argument("--days", type=int, default=365)
    ch.add_argument("--top", type=int, default=8)
    sv = ds.add_parser("save", parents=[nc], help="N23 리포트 저장")
    sv.add_argument("--file", required=True, help="리포트 JSON (deep.store 형식)")
    sv.add_argument("--check", action="store_true", help="검사만 하고 저장하지 않는다")
    se = ds.add_parser("search", parents=[nc], help="공시 전문검색 (EDGAR full-text search)")
    se.add_argument("q", help='검색어. 정확한 구절은 큰따옴표: \'"indium phosphide"\'')
    se.add_argument("--forms", default="10-K,10-Q,8-K,S-1,424B4")
    se.add_argument("--days", type=int, default=365)
    se.add_argument("--pages", type=int, default=3)
    nt = ds.add_parser("notion", parents=[nc], help="N24 노션 페이지 본문·속성 만들기")
    nt.add_argument("--file", required=True, help="리포트 JSON (deep.store 형식)")
    nt.add_argument("--image", help="차트 이미지 주소 (file-upload://… 또는 https)")
    nt.add_argument("--market-cap", type=float, help="시총(USD)")
    nt.add_argument("--candidate-page", help="아이디어 후보 페이지 URL")
    nt.add_argument("--out", help="본문 마크다운을 이 파일에 쓴다")
    return d


def _store(no_db: bool) -> Any | None:
    if no_db:
        return None
    from wsj.config import load_settings
    from wsj.db import make_store

    s = load_settings()
    if s.wsj_store == "postgrest" and not (s.supabase_url and s.supabase_secret_key):
        return None
    try:
        return make_store(s)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("wsj.deep").warning("store unavailable: %s", str(exc)[:160])
        return None


def _llm() -> Any | None:
    from wsj.config import load_settings

    key = load_settings().anthropic_api_key
    if not key:
        return None
    from wsj.briefs.llm import LLM

    return LLM(key)


def us_docs(ctx: Any, tgt: dict[str, Any], store: Any | None, years: int) -> dict[str, Any]:
    from wsj.deep.filings import collect
    from wsj.deep.target import sec_http, submissions

    return collect(sec_http(ctx), submissions(ctx, tgt["cik"]), tgt["cik"], store=store, years=years, as_of=ctx.today)


def card_set(ctx: Any, tgt: dict[str, Any], store: Any | None, years: int, plan: bool = False, dry: bool = False,
             model: str | None = None, force: bool = False) -> dict[str, Any]:
    if tgt["market"] == "kr":
        from wsj.deep.kr_cards import SupplyMapUnavailable, kr_cards

        try:
            return kr_cards(tgt["symbol"], years=years)
        except SupplyMapUnavailable as exc:
            return {"ticker": tgt["symbol"], "cards": [], "errors": [str(exc)]}
    if not tgt.get("cik"):
        return {"ticker": tgt["symbol"], "cards": [], "errors": tgt.get("errors", [])}
    from wsj.deep.cards import CARD_MODEL, us_cards

    docs = us_docs(ctx, tgt, store, years)
    llm = None if plan else _llm()
    res = us_cards(llm, store, tgt["symbol"], tgt.get("name") or tgt["symbol"], docs["annual"], write=not dry,
                   model=model or CARD_MODEL, force=force)
    res["errors"] = docs["errors"] + ([] if llm or plan else ["ANTHROPIC_API_KEY 없음 — 캐시에 없는 문서는 건너뜀"])
    res["recent"] = [d.meta() for d in docs["quarterly"] + docs["eightks"]]
    res["exhibit10"] = docs["exhibit10"]
    return res


def run_deep(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)-7s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.deep.target import target
    from wsj.tools.cli import emit
    from wsj.tools.context import ToolError, open_context

    cmd = args.deep_cmd
    store = None
    try:
        if cmd == "scenario":
            from wsj.deep.scenario import load_spec, run

            emit({"tool": "deep.scenario", **run(load_spec(args.file))}, args.compact)
            return 0
        if cmd == "search":
            from datetime import date, timedelta

            from wsj.deep.search import search
            from wsj.deep.target import sec_http

            with open_context(db=False) as ctx:
                end = ctx.today if isinstance(ctx.today, date) else date.today()
                emit({"tool": "deep.search", **search(sec_http(ctx), args.q, forms=args.forms,
                                                      start=end - timedelta(days=args.days), end=end, max_pages=args.pages)},
                     args.compact)
            return 0
        if cmd == "notion":
            from wsj.deep.notion_page import page
            from wsj.deep.scenario import load_spec

            pg = page(load_spec(args.file), image=args.image, market_cap_usd=args.market_cap,
                      candidate_page=args.candidate_page)
            if args.out:
                Path(args.out).write_text(pg["content"], encoding="utf-8")
                pg["content"] = f"(written to {args.out}, {len(pg['content'])} chars)"
            emit({"tool": "deep.notion", **pg}, args.compact)
            return 0
        if cmd == "save":
            from wsj.deep.scenario import load_spec
            from wsj.deep.store import ReportError, save, validate

            spec = load_spec(args.file)
            errs = validate(spec)
            if args.check or errs:
                emit({"tool": "deep.save", "ok": not errs, "errors": errs}, args.compact)
                return 1 if errs else 0
            store = _store(False)
            if store is None:
                raise ToolError("Supabase 연결 정보가 없다 (SUPABASE_URL·SUPABASE_SECRET_KEY)")
            try:
                emit({"tool": "deep.save", **save(store, spec)}, args.compact)
            except ReportError as exc:
                emit({"tool": "deep.save", "error": str(exc)}, args.compact)
                return 1
            return 0
        store = _store(args.no_db) if cmd in ("filings", "cards", "profile") else None
        with open_context(db=not args.no_db) as ctx:
            if cmd in ("story", "chart"):
                from wsj.deep.story import story

                filings = None
                if args.symbol and not args.symbol[:1].isdigit():
                    filings = target(args.symbol, ctx=ctx).get("filings")
                st = story(args.symbol, days=args.days, top=args.top, filings=filings, ctx=ctx)
                if cmd == "chart":
                    from wsj.deep.chart import render

                    path = render(st, args.out)
                    emit({"tool": "deep.chart", "symbol": st["symbol"], "path": str(path),
                          "moves": [{k: m.get(k) for k in ("n", "date", "return_pct")} for m in st["moves"]]}, args.compact)
                    return 0
                if not args.series:
                    st.pop("series", None)
                emit({"tool": "deep.story", **st}, args.compact)
                return 0
            if cmd == "fin":
                from wsj.deep.fin import fin

                res = fin(args.symbol, years=args.years, ctx=ctx)
                emit({"tool": "deep.fin", **res}, args.compact)
                return 1 if "error" in res else 0
            if cmd == "peers":
                from wsj.deep.peers_table import peers_table

                emit({"tool": "deep.peers", **peers_table(args.symbol, args.peers, ctx=ctx)}, args.compact)
                return 0
            if cmd == "valuation":
                from wsj.deep.valuation import valuation

                emit({"tool": "deep.valuation", **valuation(args.symbol, ctx=ctx)}, args.compact)
                return 0
            tgt = target(args.symbol, ctx=ctx)
            if cmd == "target":
                emit({"tool": "deep.target", **tgt}, args.compact)
                return 0
            if cmd == "filings":
                if tgt["market"] != "us" or not tgt.get("cik"):
                    raise ToolError("filings 는 미국 종목(CIK)만 — 한국은 deep cards 가 공급망 지도를 읽는다")
                docs = us_docs(ctx, tgt, store, args.years)
                out: dict[str, Any] = {"tool": "deep.filings", "symbol": tgt["symbol"], "errors": docs["errors"],
                                       "exhibit10": docs["exhibit10"]}
                for k in ("annual", "quarterly", "eightks"):
                    out[k] = [d.meta() for d in docs[k]]
                if args.text:
                    from wsj.deep.filings import numbered

                    out["text"] = {d.key: numbered(d)[0] for d in docs["annual"] + docs["quarterly"] + docs["eightks"]}
                emit(out, args.compact)
                return 0
            cs = card_set(ctx, tgt, store, args.years, plan=getattr(args, "plan", False), dry=args.dry,
                          model=getattr(args, "model", None), force=getattr(args, "force", False))
            if cmd == "cards":
                emit({"tool": "deep.cards", **cs}, args.compact)
                return 0 if cs.get("cards") or getattr(args, "plan", False) else 1
            from wsj.deep.diff import profile

            prof = profile(cs.get("cards") or [], target=tgt, recent=cs.get("recent"))
            emit({"tool": "deep.profile", "symbol": tgt["symbol"], **prof,
                  "errors": tgt.get("errors", []) + cs.get("errors", []), "usage_usd": cs.get("usage_usd")}, args.compact)
            return 0 if "error" not in prof else 1
    except ToolError as exc:
        emit({"tool": f"deep.{cmd}", "error": str(exc)}, args.compact)
        return 1
    finally:
        if store is not None:
            try:
                store.close()
            except Exception:  # noqa: BLE001
                pass
