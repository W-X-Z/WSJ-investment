"""`python -m wsj deep <cmd>` — 3단계 코드 도구. 결과는 JSON 한 덩어리(stdout), 로그는 stderr.

  target   SYMBOL                         N10 상장 정보·시총·주가·최근 공시
  filings  SYMBOL [--years 3]             N11 받을 문서 목록과 섹션 길이 (본문은 --text 로)
  cards    SYMBOL [--years 3] [--plan]    N12 구조 카드 (미국: 캐시 → 소형 모델 추출 → research.reports, 한국: 공급망 지도)
  profile  SYMBOL [--years 3]             N13 최신 카드 + 연도별 변화 + 빈 칸 + 시세 (카드가 없으면 cards 를 먼저)

공통: --no-db (Supabase 를 쓰지 않음: 캐시·저장 없음), --dry (추출은 하되 저장 안 함), --compact.
비용: cards 는 미국 문서 1건당 소형 모델 1~2회 (약 $0.01). --plan 은 모델을 부르지 않고 대상만 보여 준다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

COMMANDS = ("target", "filings", "cards", "profile")


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
    p = ds.add_parser("profile", parents=[c], help="N13 종목 프로필")
    p.add_argument("--years", type=int, default=3)
    p.add_argument("--dry", action="store_true")
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
             model: str | None = None) -> dict[str, Any]:
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
                   model=model or CARD_MODEL)
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
        store = _store(args.no_db) if cmd in ("filings", "cards", "profile") else None
        with open_context(db=not args.no_db) as ctx:
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
                          model=getattr(args, "model", None))
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
