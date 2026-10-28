"""그래프 상장사의 일봉 → raw.px_daily (ADR-0017). 가격은 근거가 아니라 '이미 얼마나 움직였나'의 맥락과
'설명 안 된 급변' 탐지(조사 단서)에만 쓴다.

키: 미국 = 티커(GLW), 그 밖 = '거래소:코드' (TWSE:2467, TPEx:6664, KRX:000660, KOSDAQ:086390, TSE:5803, SSE:603256, HKEX:0522).
출처 (모두 무료 공개, 2026-10-28 컨테이너에서 확인):
  미국       api.nasdaq.com historical (wsj.marketdata.nasdaq)
  대만 상장  www.twse.com.tw exchangeReport/STOCK_DAY (종목·월 단위)
  대만 상장  www.tpex.org.tw afterTrading/tradingStock (종목·월 단위)
  한국       api.finance.naver.com siseJson (기간 지정)
  중국·홍콩  web.ifzq.gtimg.cn fqkline (A주는 전일 기준 수정주가 qfq)
  일본       kabutan.jp 株価 표 (30일/쪽, 10쪽까지)
유럽·캐나다 등은 아직 없다 (점검 화면에 '가격 미수집 거래소'로 남는다).

매 실행: 모든 종목의 최근분(증분)을 먼저 받고, 남은 시간으로 1년 이력 백필을 한다 (대만·일본은 요청이 많아 여러 실행에 나눈다).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger("wsj.ecosystems.prices")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
HOST_RPS.update({"www.twse.com.tw": 0.5, "www.tpex.org.tw": 0.8, "kabutan.jp": 1.0, "api.finance.naver.com": 2.0,
                 "web.ifzq.gtimg.cn": 0.5, "api.nasdaq.com": 2.0})

US = {"Nasdaq", "NYSE", "NYSE American"}
MARKET = {"TWSE": "twse", "TPEx": "tpex", "KRX": "kr", "KOSDAQ": "kr", "SSE": "cn", "SZSE": "cn", "BJSE": "cn", "HKEX": "hk", "TSE": "jp"}
BACKFILL_DAYS = 380
STATE_KEY = "prices"


@dataclass
class Listing:
    company_id: str
    exchange: str
    ticker: str
    key: str
    market: str
    size_band: str | None = None


def px_key(exchange: str | None, ticker: str | None) -> str | None:
    if not exchange or not ticker:
        return None
    t = str(ticker).strip().upper()
    if exchange in US:
        return t
    if exchange in MARKET:
        return f"{exchange}:{t}"
    return None


def listings(graph: dict[str, Any]) -> tuple[list[Listing], dict[str, int]]:
    """그래프의 상장 기업 → 가격 키. 두 번째 값은 가격 출처가 없는 거래소별 기업 수."""
    out, uncovered = [], defaultdict(int)
    seen = set()
    for n in graph["nodes"]:
        if n.get("kind") != "company":
            continue
        lst = n.get("listing") or {}
        ex, tk = lst.get("exchange"), lst.get("ticker")
        key = px_key(ex, tk)
        if not ex or not tk:
            continue
        if not key:
            uncovered[ex] += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(Listing(n["id"], ex, str(tk).strip().upper(), key, "us" if ex in US else MARKET[ex], n.get("size_band")))
    return out, dict(uncovered)


def _num(s: Any) -> float | None:
    if s is None:
        return None
    t = str(s).replace(",", "").replace("$", "").strip()
    if t in ("", "--", "---", "N/A", "X0.00"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _row(key: str, d: date, o: Any, h: Any, lo: Any, c: Any, v: Any, source: str, vol_mult: float = 1.0) -> dict[str, Any] | None:
    close = _num(c)
    if close is None or close <= 0:
        return None
    vol = _num(v)
    return {"ticker": key, "trade_date": d.isoformat(), "open": _num(o), "high": _num(h), "low": _num(lo), "close": close,
            "volume": int(vol * vol_mult) if vol is not None else None, "source": source}


def _roc(s: str) -> date | None:
    """'115/10/01' → 2026-10-01 (민국)."""
    m = re.match(r"\s*(\d{2,3})/(\d{1,2})/(\d{1,2})", s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)) + 1911, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _months(start: date, end: date) -> list[date]:
    out, d = [], date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


# ------------------------------------------------------------------ 시장별 수집
def fetch_us(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    from wsj.marketdata.nasdaq import fetch_daily

    return fetch_daily(http, x.ticker, start, end)


def parse_twse(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    out = []
    if data.get("stat") != "OK":
        return out
    for r in data.get("data") or []:
        d = _roc(r[0])
        # 日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, 漲跌價差, 成交筆數
        row = _row(key, d, r[3], r[4], r[5], r[6], r[1], "twse") if d else None
        if row:
            out.append(row)
    return out


def fetch_twse(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    out = []
    for m in _months(start, end):
        data = http.get_json("https://www.twse.com.tw/exchangeReport/STOCK_DAY",
                             params={"response": "json", "date": m.strftime("%Y%m01"), "stockNo": x.ticker}, headers=UA)
        out += parse_twse(data, x.key)
    return out


def parse_tpex(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    out = []
    for t in data.get("tables") or []:
        for r in t.get("data") or []:
            d = _roc(r[0])
            # 日期, 成交仟股, 成交仟元, 開盤, 最高, 最低, 收盤, 漲跌, 筆數
            row = _row(key, d, r[3], r[4], r[5], r[6], r[1], "tpex", 1000.0) if d else None
            if row:
                out.append(row)
    return out


_TPEX_DAILY: dict[str, Any] = {}


def parse_tpex_daily(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for r in rows:
        d = _roc(f"{str(r.get('Date', ''))[:-4]}/{str(r.get('Date', ''))[-4:-2]}/{str(r.get('Date', ''))[-2:]}")
        code = str(r.get("SecuritiesCompanyCode") or "").strip()
        if d and code:
            out[code] = _row(f"TPEx:{code}", d, r.get("Open"), r.get("High"), r.get("Low"), r.get("Close"), r.get("TradingShares"), "tpex")
    return {k: v for k, v in out.items() if v}


def fetch_tpex(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    """대만 상櫃: 최근분은 OpenAPI 일괄 시세 한 번(요청 1개), 이력은 종목·월 단위. TPEx 는 요청이 몰리면 403 으로 막으니 아껴 쓴다."""
    if (end - start).days <= 7:
        if "rows" not in _TPEX_DAILY:
            _TPEX_DAILY["rows"] = parse_tpex_daily(http.get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes", headers=UA))
        r = _TPEX_DAILY["rows"].get(x.ticker)
        return [r] if r and r["trade_date"] >= start.isoformat() else []
    out = []
    for m in _months(start, end):
        data = http.get_json("https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
                             params={"code": x.ticker, "date": m.strftime("%Y/%m/01"), "response": "json"}, headers=UA)
        out += parse_tpex(data, x.key)
    return out


NAVER_ROW = re.compile(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)')


def parse_naver(text: str, key: str) -> list[dict[str, Any]]:
    out = []
    for m in NAVER_ROW.finditer(text):
        d = datetime.strptime(m.group(1), "%Y%m%d").date()
        row = _row(key, d, m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), "naver")
        if row:
            out.append(row)
    return out


def fetch_kr(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    text = http.get_text("https://api.finance.naver.com/siseJson.naver",
                         params={"symbol": x.ticker.zfill(6), "requestType": "1", "startTime": start.strftime("%Y%m%d"),
                                 "endTime": end.strftime("%Y%m%d"), "timeframe": "day"}, headers=UA)
    return parse_naver(text, x.key)


def tencent_code(x: Listing) -> str:
    if x.exchange == "HKEX":
        return "hk" + x.ticker.zfill(5)
    if x.exchange == "BJSE":
        return "bj" + x.ticker
    return ("sh" if x.exchange == "SSE" else "sz") + x.ticker


def parse_tencent(data: dict[str, Any], code: str, key: str) -> list[dict[str, Any]]:
    d = ((data or {}).get("data") or {}).get(code) or {}
    rows = d.get("qfqday") or d.get("day") or []
    out = []
    for r in rows:
        try:
            dd = date.fromisoformat(r[0])
        except (ValueError, IndexError, TypeError):
            continue
        # [날짜, 시가, 종가, 고가, 저가, 거래량]
        row = _row(key, dd, r[1], r[3], r[4], r[2], r[5] if len(r) > 5 else None, "tencent")
        if row:
            out.append(row)
    return out


def fetch_cn(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    code = tencent_code(x)
    n = max(5, min(640, (end - start).days + 5))
    # 쉼표를 %2C 로 바꾸면 방화벽이 막는다 — 쿼리를 그대로 붙인다
    data = http.get_json(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,{start.isoformat()},{end.isoformat()},{n},qfq",
                         headers=UA)
    return parse_tencent(data, code, x.key)


KABU_ROW = re.compile(r'<time datetime="(\d{4}-\d{2}-\d{2})">.*?</time></th>\s*<td>([\d,.]+)</td>\s*<td>([\d,.]+)</td>\s*<td>([\d,.]+)</td>'
                      r'\s*<td>([\d,.]+)</td>.*?<td>([\d,]+)</td>\s*</tr>', re.S)


def parse_kabutan(html: str, key: str) -> list[dict[str, Any]]:
    i = html.find("stock_kabuka_dwm")
    out = []
    for m in KABU_ROW.finditer(html[i:] if i >= 0 else ""):
        row = _row(key, date.fromisoformat(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6), "kabutan")
        if row:
            out.append(row)
    return out


YJ_ROW = re.compile(r">(\d{4}/\d{2}/\d{2})</th>(.*?)</tr>", re.S)
YJ_VAL = re.compile(r'_StyledNumber__value_\w+">([\d,.]+)<')


def parse_yahoo_jp(html: str, key: str) -> list[dict[str, Any]]:
    """Yahoo!ファイナンス 時系列 표: 날짜 | 시가 | 고가 | 저가 | 종가 | 거래량 | 조정 종가."""
    out = []
    for d, cells in YJ_ROW.findall(html):
        v = YJ_VAL.findall(cells)
        if len(v) >= 5:
            row = _row(key, datetime.strptime(d, "%Y/%m/%d").date(), v[0], v[1], v[2], v[3], v[4], "yahoo_jp")
            if row:
                out.append(row)
    return out


def _paged(fetch_page, start: date, pages: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        rows = fetch_page(page)
        new = [r for r in rows if r["trade_date"] not in seen]
        out += new
        seen |= {r["trade_date"] for r in new}
        if not new or min(r["trade_date"] for r in new) <= start.isoformat():
            break  # 쪽 번호를 무시하고 같은 쪽을 돌려주는 출처면 여기서 멈춘다
    return [r for r in out if r["trade_date"] >= start.isoformat()]



_KABUTAN_BLOCKED: list[str] = []


def fetch_jp(http: HttpClient, x: Listing, start: date, end: date) -> list[dict[str, Any]]:
    """일본: kabutan 먼저(1년 이력), 막히면(GitHub Actions 러너는 405) Yahoo!ファイナンス. 한 번 막히면 그 실행에서는 kabutan 을 건너뛴다."""
    if not _KABUTAN_BLOCKED:
        try:
            return _paged(lambda pg: parse_kabutan(http.get_text("https://kabutan.jp/stock/kabuka", params={"code": x.ticker, "ashi": "day", "page": str(pg)},
                                                                 headers=UA), x.key), start, 10)
        except Exception as exc:  # noqa: BLE001
            _KABUTAN_BLOCKED.append(str(exc)[:80])
            log.info("kabutan blocked (%s) → yahoo jp for this run", str(exc)[:60])
    # Yahoo!ファイナンス 는 서버에서 최근 약 12거래일만 그린다 (기간·쪽 지정은 무시되는 경우가 많다, 2026-10-28 확인).
    # 그래서 러너에서는 일본 종목의 1년 이력을 한 번에 채우지 못하고, 매일 증분으로 쌓는다.
    rows = parse_yahoo_jp(http.get_text(f"https://finance.yahoo.co.jp/quote/{x.ticker}.T/history", headers=UA), x.key)
    return [r for r in rows if r["trade_date"] >= start.isoformat()]


FETCH = {"us": fetch_us, "twse": fetch_twse, "tpex": fetch_tpex, "kr": fetch_kr, "cn": fetch_cn, "hk": fetch_cn, "jp": fetch_jp}


# ------------------------------------------------------------------ 실행
def last_dates(store, keys: list[str], today: date) -> tuple[dict[str, str], set[str]]:
    """종목별 마지막 거래일(최근 20일 안)과 1년 전 이력이 있는 종목 집합."""
    last: dict[str, str] = {}
    for r in store.select("raw.px_daily", ["ticker", "trade_date"], {"trade_date": ("gte", (today - timedelta(days=20)).isoformat())}):
        t, d = r["ticker"], str(r["trade_date"])[:10]
        if d > last.get(t, ""):
            last[t] = d
    old = {r["ticker"] for r in store.select("raw.px_daily", ["ticker"], {"trade_date": ("lte", (today - timedelta(days=340)).isoformat())})}
    return last, old & set(keys)


def load_state(store) -> dict[str, Any]:
    try:
        rows = store.select("ops.collector_state", ["watermark"], {"collector": STATE_KEY})
        return (rows[0]["watermark"] if rows else None) or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("collector_state unavailable: %s", exc)
        return {}


def save_state(store, state: dict[str, Any]) -> None:
    try:
        store.upsert("ops.collector_state", [{"collector": STATE_KEY, "watermark": state, "updated_at": datetime.now(UTC).isoformat()}], ["collector"])
    except Exception as exc:  # noqa: BLE001
        log.warning("collector_state save failed: %s", exc)


def plan(items: list[Listing], last: dict[str, str], has_year: set[str], state: dict[str, Any], today: date,
         focus: set[str]) -> tuple[list[tuple[Listing, date]], list[Listing]]:
    """(증분 목록, 백필 목록). 백필은 아이디어 기업 → 소형·중형 → 나머지 순. 실패가 3번 쌓인 종목은 일주일 쉰다."""
    inc, back = [], []
    fails = state.get("fails") or {}
    done = set(state.get("backfilled") or [])
    for x in items:
        f = fails.get(x.key) or {}
        if f.get("n", 0) >= 3 and f.get("at", "") > (today - timedelta(days=7)).isoformat():
            continue
        if x.key in last:
            inc.append((x, date.fromisoformat(last[x.key]) + timedelta(days=1)))
        if x.key not in has_year and x.key not in done:
            back.append(x)
    order = {"micro": 0, "small": 1, "mid": 2, "unknown": 3, "large": 4, "mega": 5}
    back.sort(key=lambda x: (x.company_id not in focus, order.get(x.size_band or "unknown", 3)))
    return inc, back


def run(http: HttpClient, store, graph: dict[str, Any], budget_s: float = 720.0, focus: set[str] | None = None,
        only: set[str] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    t0 = time.monotonic()
    items, uncovered = listings(graph)
    if only:
        items = [x for x in items if x.market in only]
    last, has_year = last_dates(store, [x.key for x in items], today)
    state = load_state(store)
    inc, back = plan(items, last, has_year, state, today, focus or set())
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0, "rows": 0})
    fails = state.setdefault("fails", {})
    done = set(state.get("backfilled") or [])
    buf: list[dict[str, Any]] = []

    def flush() -> None:
        if buf:
            uniq = {(r["ticker"], r["trade_date"]): r for r in buf}
            store.upsert("raw.px_daily", list(uniq.values()), ["ticker", "trade_date"])
            buf.clear()

    streak: dict[str, int] = defaultdict(int)

    def one(x: Listing, start: date, mode: str) -> None:
        if streak[x.market] >= 3:  # 시장별 차단기: 연달아 3번 실패하면 이번 실행에서는 그 시장을 더 두드리지 않는다
            stats[x.market]["skipped"] = stats[x.market].get("skipped", 0) + 1
            return
        try:
            rows = FETCH[x.market](http, x, start, today)
            streak[x.market] = 0
        except Exception as exc:  # noqa: BLE001 - 한 종목 실패가 전체를 막지 않게
            streak[x.market] += 1
            stats[x.market]["fail"] += 1
            f = fails.setdefault(x.key, {"n": 0})
            f["n"], f["at"], f["err"] = f.get("n", 0) + 1, today.isoformat(), str(exc)[:120]
            log.warning("%s %s %s failed: %s", mode, x.market, x.key, exc)
            return
        fails.pop(x.key, None)
        stats[x.market]["ok"] += 1
        stats[x.market]["rows"] += len(rows)
        buf.extend(rows)
        if mode == "backfill":
            done.add(x.key)
        if len(buf) >= 2000:
            flush()

    for x, start in inc:
        if start <= today:
            one(x, start, "inc")
    n_back = 0
    for x in back:
        if time.monotonic() - t0 > budget_s:
            break
        one(x, today - timedelta(days=BACKFILL_DAYS), "backfill")
        n_back += 1
    flush()
    state["backfilled"] = sorted(done)
    state["fails"] = fails
    save_state(store, state)
    return {"listings": len(items), "incremental": len(inc), "backfill_done": n_back, "backfill_left": max(0, len(back) - n_back),
            "by_market": dict(stats), "uncovered_exchanges": uncovered, "elapsed_s": round(time.monotonic() - t0, 1)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "probe"])
    ap.add_argument("--budget-min", type=float, default=12.0, help="백필에 쓸 최대 시간(분). 증분은 항상 한다")
    ap.add_argument("--only", help="쉼표로: us,twse,tpex,kr,cn,hk,jp")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.config import load_settings
    from wsj.ecosystems.ontology import load_graph

    graph = load_graph()
    http = HttpClient(UA["User-Agent"], timeout=25, max_retries=1)
    if args.cmd == "probe":  # 시장마다 한 종목씩 받아 도달 가능 여부만 본다 (저장 없음)
        items, _ = listings(graph)
        res = {}
        today = datetime.now(UTC).date()
        rank = {"mega": 0, "large": 1, "mid": 2, "small": 3, "micro": 4}
        for m in sorted({x.market for x in items}):
            tries = sorted((i for i in items if i.market == m), key=lambda i: rank.get(i.size_band or "", 5))[:3]
            for x in tries:  # 상장폐지 등으로 빈 종목이면 다음 종목
                try:
                    rows = FETCH[m](http, x, today - timedelta(days=20), today)
                    res[m] = {"key": x.key, "rows": len(rows), "last": max(r["trade_date"] for r in rows) if rows else None}
                except Exception as exc:  # noqa: BLE001
                    res[m] = {"key": x.key, "error": str(exc)[:160]}
                if res[m].get("rows"):
                    break
        http.close()
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0 if all("error" not in v for v in res.values()) else 1
    from wsj.db import make_store
    from wsj.runlog import logged_run

    store = make_store(load_settings())
    try:
        focus: set[str] = set()
        try:
            for r in store.select("ideas.investment_ideas", ["companies"], {"status": "active"}):
                focus |= {c.get("id") for c in r.get("companies") or []}
        except Exception:  # noqa: BLE001
            pass
        with logged_run(store, "prices", {"budget_min": args.budget_min}) as lr:
            res = run(http, store, graph, args.budget_min * 60, focus, set(args.only.split(",")) if args.only else None)
            lr["rows"] = sum(v["rows"] for v in res["by_market"].values())
            lr["notes"] = json.dumps(res, ensure_ascii=False)[:1500]
        print(json.dumps(res, ensure_ascii=False))
    finally:
        http.close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
