"""일봉 이력: raw.px_daily 캐시(읽기 전용) → 없거나 묵었으면 라이브 (미국 Nasdaq, 한국 Naver).

종목 표기: 6자리 숫자 = 한국 (001440). 'KRX:001440' · 'KOSDAQ:086390' · '001440.KS' 도 받는다. 그 밖은 미국 티커 (BRK.B 그대로).
가격은 수정주가가 아니다 (Nasdaq·Naver 차트 모두 분할·배당 조정 플래그가 없다) — 분할이 낀 구간의 수익률은 깨질 수 있다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from wsj.tools import parse as P
from wsj.tools.context import ToolContext, ToolError, ensure_context, parse_day

Bar = dict[str, Any]
KR_RE = re.compile(r"^(?:(?:KRX|KOSPI|KOSDAQ|KR|KS|KQ):)?(\d{6})(?:\.(?:KS|KQ|KRX))?$", re.I)
US_RE = re.compile(r"^[A-Z][A-Z0-9.\-^]{0,9}$")
CACHE_STALE_DAYS = 4      # 캐시 마지막 날짜가 (기준일 − 4일) 보다 오래되면 라이브
CACHE_COVER_SLACK = 7     # 캐시 첫 날짜가 시작일 + 7일 안이면 구간을 덮는다고 본다


@dataclass(frozen=True)
class Symbol:
    market: str     # 'us' | 'kr'
    code: str       # 'FPS' | '001440'
    raw: str

    @property
    def px_keys(self) -> list[str]:
        """raw.px_daily 의 ticker 키 후보 (wsj.ecosystems.prices.px_key 규칙)."""
        return [self.code] if self.market == "us" else [f"KRX:{self.code}", f"KOSDAQ:{self.code}"]

    @property
    def currency(self) -> str:
        return "USD" if self.market == "us" else "KRW"


def parse_symbol(s: str) -> Symbol:
    t = str(s or "").strip()
    m = KR_RE.match(t)
    if m:
        return Symbol("kr", m.group(1), t)
    u = t.upper()
    if u.startswith("US:"):
        u = u[3:]
    if not US_RE.match(u):
        raise ToolError(f"종목 표기를 읽을 수 없습니다: {s!r} (미국 티커 또는 한국 6자리 코드)")
    return Symbol("us", u, t)


def default_benchmark(sym: Symbol) -> str:
    return "SPY" if sym.market == "us" else "069500"


# ---------------------------------------------------------------- 캐시
def _from_cache(ctx: ToolContext, sym: Symbol, start: date, end: date) -> list[Bar] | None:
    if not ctx.use_px_cache:
        return None
    rows = ctx.db_select("raw.px_daily", ["ticker", "trade_date", "open", "high", "low", "close", "volume"],
                         {"ticker": sym.px_keys, "trade_date": ("gte", start.isoformat())}, order="trade_date")
    if not rows:
        return None
    bars = []
    for r in rows:
        d = str(r["trade_date"])[:10]
        if d > end.isoformat() or r.get("close") is None:
            continue
        bars.append({"date": d, "open": P.num(r.get("open")), "high": P.num(r.get("high")), "low": P.num(r.get("low")),
                     "close": float(r["close"]), "volume": int(r["volume"]) if r.get("volume") is not None else None})
    bars = P.sort_bars(bars)
    if not bars:
        return None
    need_last = min(end, ctx.today) - timedelta(days=CACHE_STALE_DAYS)
    if date.fromisoformat(bars[-1]["date"]) < need_last:
        return None
    if date.fromisoformat(bars[0]["date"]) > start + timedelta(days=CACHE_COVER_SLACK):
        return None
    return bars


# ---------------------------------------------------------------- 라이브
def _live_us(ctx: ToolContext, sym: Symbol, start: date, end: date) -> tuple[list[Bar], str]:
    """주식 → ETF 순서로 시도. 맞은 자산군은 memo 에 남겨 다음 호출(info·summary)에 쓴다."""
    classes = [ctx.memo.get(f"assetclass:{sym.code}")] if ctx.memo.get(f"assetclass:{sym.code}") else ["stocks", "etf"]
    last_err: Exception | None = None
    for ac in classes:
        try:
            payload = ctx.fetch.nasdaq_history(sym.code, start, end, ac)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
        if P.nasdaq_has_data(payload):
            ctx.memo[f"assetclass:{sym.code}"] = ac
            return P.parse_nasdaq_history(payload), f"nasdaq:{ac}"
    if last_err:
        raise ToolError(f"Nasdaq 이력 실패 {sym.code}: {str(last_err)[:120]}")
    raise ToolError(f"Nasdaq 에 없는 종목입니다: {sym.code}")


def _live_kr(ctx: ToolContext, sym: Symbol, start: date, end: date) -> tuple[list[Bar], str]:
    errs = []
    try:
        bars = P.parse_naver_chart(ctx.fetch.naver_chart(sym.code, start, end))
        if bars:
            return bars, "naver:chart"
    except Exception as exc:  # noqa: BLE001
        errs.append(str(exc)[:80])
    try:
        bars = P.parse_naver_sise(ctx.fetch.naver_sise(sym.code, start, end))
        if bars:
            return bars, "naver:siseJson"
    except Exception as exc:  # noqa: BLE001
        errs.append(str(exc)[:80])
    raise ToolError(f"Naver 이력 실패 {sym.code}: {'; '.join(errs) or '빈 응답'}")


def get_bars(ctx: ToolContext, symbol: str | Symbol, start: date, end: date) -> tuple[list[Bar], str]:
    """(일봉, 출처). 같은 실행 안에서 같은 (종목, 구간)은 한 번만 받는다."""
    sym = symbol if isinstance(symbol, Symbol) else parse_symbol(symbol)
    key = f"bars:{sym.market}:{sym.code}:{start}:{end}"
    if key in ctx.memo:
        return ctx.memo[key]
    cached = _from_cache(ctx, sym, start, end)
    if cached:
        res = (cached, "db:raw.px_daily")
    else:
        bars, src = (_live_us if sym.market == "us" else _live_kr)(ctx, sym, start, end)
        res = ([b for b in bars if start.isoformat() <= b["date"] <= end.isoformat()], src)
    ctx.memo[key] = res
    return res


# ---------------------------------------------------------------- 도구: history
def history(symbol: str, start: str | date | None = None, end: str | date | None = None, ohlc: bool = False,
            ctx: ToolContext | None = None) -> dict[str, Any]:
    """일봉 종가(·거래량) 목록. 기본 구간은 끝일 기준 1년."""
    with ensure_context(ctx) as c:
        sym = parse_symbol(symbol)
        e = parse_day(end, c.today)
        s = parse_day(start, e - timedelta(days=365))
        if s > e:
            raise ToolError(f"시작일 {s} 이 끝일 {e} 보다 늦습니다")
        bars, src = get_bars(c, sym, s, e)
        keep = ("date", "open", "high", "low", "close", "volume") if ohlc else ("date", "close", "volume")
        return {"symbol": sym.code, "market": sym.market, "currency": sym.currency, "start": s.isoformat(),
                "end": e.isoformat(), "source": src, "adjusted": False, "n": len(bars),
                "rows": [{k: b.get(k) for k in keep} for b in bars]}
