"""`python -m wsj tools <cmd>` — 결과는 항상 JSON 한 덩어리를 stdout 으로 (로그는 stderr).

실패하면 {"error": "...", "tool": "..."} 를 내고 종료코드 1. 인자 오류는 argparse 가 종료코드 2.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date
from decimal import Decimal
from typing import Any

COMMANDS = ("quote", "history", "lookup", "fx", "rates", "event", "exposure", "reverse-dcf", "peers", "incremental")


def _common() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("공통")
    g.add_argument("--no-db", action="store_true", help="Supabase(raw.px_daily 등)를 보지 않고 라이브 출처만")
    g.add_argument("--live", action="store_true", help="가격 캐시(raw.px_daily)를 건너뛰고 라이브로 받기 (다른 DB 조회는 유지)")
    g.add_argument("--today", help="기준일 덮어쓰기 YYYY-MM-DD (기본 오늘)")
    g.add_argument("--compact", action="store_true", help="JSON 을 한 줄로")
    g.add_argument("-v", "--verbose", action="store_true", help="경고·디버그 로그를 stderr 로")
    return p


def add_tools_parser(sub: Any) -> argparse.ArgumentParser:
    """runner.build_parser 가 부른다: sub = 최상위 add_subparsers()."""
    t = sub.add_parser("tools", help="리서치 계산 도구 (시세·환율·금리·이벤트·베타·DCF·동종비교·증분수요)",
                       description="리서치 에이전트용 결정론적 도구. 결과는 JSON. 자세한 예시는 pipeline/wsj/tools/README.md")
    ts = t.add_subparsers(dest="tool", required=True, metavar="{" + ",".join(COMMANDS) + "}")
    c = _common()

    q = ts.add_parser("quote", parents=[c], help="마지막 종가·시총(USD/KRW)·1m/3m/6m/YTD 등락",
                      description="미국 티커 또는 한국 6자리 코드. 예: quote FPS · quote 001440 · quote VRT --as-of 2026-11-05")
    q.add_argument("symbols", nargs="+", help="FPS · BRK.B · 001440 · KOSDAQ:086390")
    q.add_argument("--as-of", help="이 날짜(포함) 이전 마지막 거래일 기준")

    h = ts.add_parser("history", parents=[c], help="기간 일봉 종가(·거래량)",
                      description="예: history FPS --start 2026-10-01 --end 2026-11-06 --ohlc")
    h.add_argument("symbol")
    h.add_argument("--start", help="시작일 (기본 끝일 − 365일)")
    h.add_argument("--end", help="끝일 (기본 오늘)")
    h.add_argument("--ohlc", action="store_true", help="시가·고가·저가도 포함")

    lk = ts.add_parser("lookup", parents=[c], help="이름·티커 → 상장 정보(거래소, CIK, 가격 키)",
                       description="예: lookup forgent · lookup ETN · lookup 효성 · lookup 001440 · lookup 엔비디아")
    lk.add_argument("query", nargs="+")
    lk.add_argument("--market", choices=["us", "kr"], help="한 시장만")
    lk.add_argument("--limit", type=int, default=10)

    f = ts.add_parser("fx", parents=[c], help="환율 (기본 USDKRW)",
                      description="rate = 기준통화 1단위의 상대통화 가격. 예: fx · fx USDJPY · fx EURUSD --date 2026-11-04")
    f.add_argument("pair", nargs="?", default="USDKRW", help="USDKRW · USD/JPY · EURUSD")
    f.add_argument("--date", help="과거 날짜 (Frankfurter/ECB 기준, 휴일이면 직전 영업일)")

    r = ts.add_parser("rates", parents=[c], help="미 국채 수익률 곡선 (3m·2y·10y·30y + 전체·스프레드)",
                      description="예: rates · rates 2026-11-06 (휴일이면 직전 공시일)")
    r.add_argument("date", nargs="?", help="기준일 (기본 오늘)")

    e = ts.add_parser("event", parents=[c], help="지정일 전후 주가·거래량 반응, 벤치마크 대비",
                      description="d-1→d, d→d+1, d-1→d+1, d-5→d+5 수익률 / 거래량 ÷ 직전 20일 평균 / 초과·비정상 수익률. "
                                  "예: event FPS 2026-11-04 · event 001440 2026-11-05 --benchmark 069500")
    e.add_argument("symbol")
    e.add_argument("date")
    e.add_argument("--benchmark", help="기본 미국 SPY, 한국 069500(KODEX200)")
    e.add_argument("--vol-lookback", type=int, default=20)
    e.add_argument("--beta-window", type=int, default=120)

    x = ts.add_parser("exposure", parents=[c], help="베타·상관 (묶음·벤치마크 대비) + 구간 수익률",
                      description="예: exposure FPS POWL ETN --period 2026-05-15:2026-10-06 --period 2026-10-06:2026-11-06")
    x.add_argument("tickers", nargs="+")
    x.add_argument("--basket", help="쉼표 목록 (기본 NVDA,AVGO,VRT,GEV,PWR)")
    x.add_argument("--benchmark", help="기본 SPY (첫 종목이 한국이면 069500)")
    x.add_argument("--window", type=int, default=126, help="거래일 수 (기본 126 ≈ 6개월)")
    x.add_argument("--end", help="창의 끝일 (기본 오늘)")
    x.add_argument("--period", action="append", default=[], help="시작:끝 구간 수익률, 여러 번 가능")

    d = ts.add_parser("reverse-dcf", parents=[c], help="시총이 요구하는 FCF CAGR (역DCF) / 성장 경로 → 가치 (정DCF)",
                      description="금액 단위는 자유(모두 같은 단위). 비율은 소수(0.09 = 9%%). "
                                  "예: reverse-dcf --market-cap 5.93e9 --net-debt 0.4e9 --fcf 0.15e9 --discount 0.10 --terminal 0.03 "
                                  "· reverse-dcf --forward --growth 0.30,0.25,0.20,0.15,0.12 --years 10 --fcf 0.15e9 --discount 0.10 --terminal 0.03")
    d.add_argument("--market-cap", type=float)
    d.add_argument("--price", type=float)
    d.add_argument("--shares", type=float, help="희석주식수 (price 와 함께, 정DCF 에서는 주당가치)")
    d.add_argument("--net-debt", type=float, default=0.0, help="순차입금 (현금이 많으면 음수)")
    d.add_argument("--fcf", type=float, required=True, help="기준 FCF (0년차)")
    d.add_argument("--discount", type=float, required=True, help="할인율 (예 0.10)")
    d.add_argument("--terminal", type=float, required=True, help="영구성장률 (예 0.03)")
    d.add_argument("--years", type=int, default=10, help="명시적 예측 기간 (기본 10)")
    d.add_argument("--forward", action="store_true", help="정방향: --growth 로 가치 계산")
    d.add_argument("--growth", help="정방향 성장률: 0.15 (매년) 또는 0.3,0.25,0.2 (연도별, 모자라면 마지막 값 반복)")

    p = ts.add_parser("peers", parents=[c], help="동종 비교: 시총·EV·매출·영업이익·P/E·EV/Sales·EV/EBIT",
                      description="예: peers FPS POWL ETN VRT · peers 001440 298040. 값이 없으면 null (추정 안 함)")
    p.add_argument("tickers", nargs="+")
    p.add_argument("--no-sec", action="store_true", help="SEC companyfacts 조회 생략 (순차입금·EV 는 null)")

    n = ts.add_parser("incremental", parents=[c], help="증분 수요 엔진: 시나리오 → 부품별 Δ$ → 회사별 Δ매출·Δ순이익·÷시총",
                      description="입력 JSON 형식은 wsj/tools/incremental.py 상단과 README. "
                                  "예: incremental tests/fixtures/tools/incremental_8gw.json --top 15")
    n.add_argument("file", help="JSON 파일 경로 (- 이면 stdin)")
    n.add_argument("--case", action="append", help="이 케이스만 (central 또는 sensitivities 의 이름), 여러 번 가능")
    n.add_argument("--no-sensitivity", action="store_true", help="central 만")
    n.add_argument("--top", type=int, help="회사·부품 상위 N 개만")
    n.add_argument("--drivers", action="store_true", help="풀어낸 기초 드라이버 수량도 출력")
    return t


def _json_default(o: Any) -> Any:
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"not serializable: {type(o)}")


def _clean(o: Any) -> Any:
    """NaN/inf → null, 부동소수 꼬리 정리(12자리 유효숫자)."""
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            return None
        return float(f"{o:.12g}")
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def emit(obj: Any, compact: bool = False) -> None:
    print(json.dumps(_clean(obj), ensure_ascii=False, default=_json_default, indent=None if compact else 1))


def _floats(s: str) -> list[float]:
    return [float(x) for x in s.split(",") if x.strip()]


def run_tools(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR,
                        format="%(levelname)-7s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.tools.context import ToolError, open_context, parse_day

    tool = args.tool
    try:
        if tool == "reverse-dcf":
            from wsj.tools.dcf import dcf_value, reverse_dcf

            if args.forward:
                if not args.growth:
                    raise ToolError("--forward 에는 --growth 가 필요합니다")
                g = _floats(args.growth)
                res = dcf_value(args.fcf, args.discount, args.terminal, g[0] if len(g) == 1 else g, args.years,
                                args.net_debt, args.shares)
                if args.market_cap or (args.price and args.shares):
                    mc = args.market_cap or args.price * args.shares
                    res["market_cap"] = mc
                    res["upside_vs_market_cap_pct"] = round((res["equity_value"] / mc - 1) * 100, 3)
            else:
                res = reverse_dcf(args.fcf, args.discount, args.terminal, args.years, args.market_cap, args.price,
                                  args.shares, args.net_debt)
            emit({"tool": tool, **res}, args.compact)
            return 0
        if tool == "incremental":
            from wsj.tools.incremental import load_spec, run

            res = run(load_spec(args.file), cases=args.case, sensitivity=not args.no_sensitivity, top=args.top,
                      include_drivers=args.drivers)
            emit({"tool": tool, **res}, args.compact)
            return 0

        with open_context(db=not args.no_db, live=args.live, today=parse_day(args.today)) as ctx:
            if tool == "quote":
                from wsj.tools.quote import quote

                outs = []
                for s in args.symbols:
                    try:
                        outs.append(quote(s, as_of=args.as_of, ctx=ctx))
                    except ToolError as exc:
                        outs.append({"symbol": s, "error": str(exc)})
                res: Any = outs[0] if len(outs) == 1 else {"results": outs}
                emit({"tool": tool, **res}, args.compact)
                return 1 if all("error" in o for o in outs) else 0
            if tool == "history":
                from wsj.tools.prices import history

                res = history(args.symbol, args.start, args.end, ohlc=args.ohlc, ctx=ctx)
            elif tool == "lookup":
                from wsj.tools.lookup import lookup

                res = lookup(" ".join(args.query), market=args.market, limit=args.limit, ctx=ctx)
            elif tool == "fx":
                from wsj.tools.fx import fx

                res = fx(args.pair, day=args.date, ctx=ctx)
            elif tool == "rates":
                from wsj.tools.rates import rates

                res = rates(args.date, ctx=ctx)
            elif tool == "event":
                from wsj.tools.event import event

                res = event(args.symbol, args.date, args.benchmark, args.vol_lookback, args.beta_window, ctx=ctx)
            elif tool == "exposure":
                from wsj.tools.exposure import exposure

                basket = [b.strip() for b in args.basket.split(",") if b.strip()] if args.basket else None
                res = exposure(args.tickers, basket, args.benchmark, args.window, args.end, args.period, ctx=ctx)
            elif tool == "peers":
                from wsj.tools.peers import peers

                res = peers(args.tickers, use_sec=not args.no_sec, ctx=ctx)
            else:
                raise ToolError(f"알 수 없는 도구: {tool}")
            emit({"tool": tool, **res}, args.compact)
            return 0
    except ToolError as exc:
        emit({"tool": tool, "error": str(exc)}, args.compact)
        return 1


def main(argv: list[str] | None = None) -> int:
    """`python -m wsj.tools <cmd>` 도 같은 동작."""
    p = argparse.ArgumentParser(prog="python -m wsj.tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    add_tools_parser(sub)
    return run_tools(p.parse_args(["tools", *(sys.argv[1:] if argv is None else argv)]))
