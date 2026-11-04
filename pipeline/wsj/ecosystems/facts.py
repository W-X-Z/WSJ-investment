"""상장사 기초 사실 — 발행주식수·통화·환율 → 시가총액 (ADR-0017 개정 1).

    python -m wsj.ecosystems.facts run [--only us,twse,tpex,kr,cn,hk,jp] [--max-us 40]
    python -m wsj.ecosystems.facts probe

텐배거 발굴은 '아직 작은가(시가총액)'와 '아직 안 갔는가(저점 대비)'에서 출발한다. 주식수는 시장별 공식·공개 출처에서 받고,
시가총액은 DB 뷰(v_company_facts)가 마지막 종가 × 주식수 × 환율로 계산한다 — 주가가 갱신되면 시총도 따라간다.

  미국     data.sec.gov companyfacts dei:EntityCommonStockSharesOutstanding (같은 기준일의 여러 클래스는 합산). 파일이 커서 한 번에 --max-us 개,
           30일 지난 것부터.
  대만 상장 openapi.twse.com.tw t187ap03_L 已發行普通股數 (일괄)
  대만 상계 www.tpex.org.tw openapi tpex_mainboard_quotes Capitals = 주식수 (일괄)
  한국     m.stock.naver.com 모바일 API 시총('2,557억') ÷ 종가 → 주식수
  중국·홍콩 qt.gtimg.cn 總市值(億) ÷ 종가 → 주식수
  일본     finance.yahoo.co.jp 종목 페이지의 発行済株式数
  환율     FRED DEX* (USD 기준) → ref.fx_rates
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from wsj.ecosystems.prices import UA, Listing, listings
from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger(__name__)
HOST_RPS.update({"data.sec.gov": 4.0, "www.sec.gov": 4.0, "qt.gtimg.cn": 0.5, "finance.yahoo.co.jp": 0.5, "m.stock.naver.com": 1.0})
# SEC 는 연락처가 든 UA 를 요구한다 — 브라우저 UA(네이버·텐센트용)로는 www.sec.gov/Archives 가 403. data.sec.gov 는 통과해서 표지 경로만 조용히 죽는다 (2026-11-04).
SEC_UA = {"User-Agent": os.environ.get("SEC_USER_AGENT") or "WSJ-investment research (github.com/W-X-Z/WSJ-investment)"}

CURRENCY = {"us": "USD", "twse": "TWD", "tpex": "TWD", "kr": "KRW", "cn": "CNY", "hk": "HKD", "jp": "JPY"}
# FRED 환율 계열: (계열, 'USD 당 외화' 인지)
FX_SERIES = {"TWD": ("DEXTAUS", True), "KRW": ("DEXKOUS", True), "CNY": ("DEXCHUS", True), "JPY": ("DEXJPUS", True), "HKD": ("DEXHKUS", True),
             "EUR": ("DEXUSEU", False), "GBP": ("DEXUSUK", False), "INR": ("DEXINUS", True), "CAD": ("DEXCAUS", True)}
FRED_UA = "WSJ-investment research (github.com/W-X-Z/WSJ-investment)"
US_REFRESH_DAYS = 10          # 다중 클래스 회사의 묵은 값(VICR 2015년 주식수)이 한 달씩 남지 않게


def _num(v: Any) -> float | None:
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s and s not in ("-", "－", "N/A") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 시장별 주식수
# 주식수 태그 — 앞쪽이 표지(cover)의 시점 값, 뒤쪽은 대체값. 다중 클래스 회사(GOOGL·META)는 표지 값이 클래스별이라
# companyfacts 에 안 나오고, 40-F 회사(TECK)는 IFRS 태그만 있다. 가장 최근 기준일을 쓰고, 같은 날이면 앞쪽 태그.
SHARE_TAGS = [("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "CommonStockSharesOutstanding"),
              ("ifrs-full", "NumberOfSharesOutstanding"), ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"),
              ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic")]
MIN_SHARES = 100_000          # 상장 전 서류의 1,000주 같은 값은 버린다
# 미국 예탁증권(ADS) 1주가 대표하는 보통주 수 — 20-F 표지의 주식수는 보통주라 ADS 가격을 곱하려면 나눠야 한다.
# 출처: 각 사 2025 회계연도 20-F ("each ADS represents five (5) common shares" 등, 2026-11-03 확인). 1:1 인 곳은 적지 않는다.
SHARES_PER_ADS = {"TSM": 5.0, "UMC": 5.0, "ASX": 2.0, "HIMX": 2.0, "PKX": 0.25}


def sec_shares(facts: dict[str, Any]) -> tuple[float, str] | None:
    """companyfacts → (주식수, 기준일). 같은 기준일에 여러 클래스·행이 있으면 합산 (같은 서류·같은 값은 한 번)."""
    best: tuple[str, int, float] | None = None
    for rank, (ns, tag) in enumerate(SHARE_TAGS):
        units = (((facts.get("facts") or {}).get(ns) or {}).get(tag) or {}).get("units") or {}
        rows = [r for r in units.get("shares") or [] if r.get("end") and r.get("val")]
        if not rows:
            continue
        end = max(r["end"] for r in rows)
        same = {(r.get("frame"), r.get("accn"), r.get("val")) for r in rows if r.get("end") == end}
        val = float(sum(v for _, _, v in same if v)) if rank == 0 else float(max(v for _, _, v in same if v))
        if val < MIN_SHARES:
            continue
        if best is None or end > best[0] or (end == best[0] and rank < best[1]):
            best = (end, rank, val)
    return (best[2], best[0]) if best else None


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def sec_cik_by_ticker(http: HttpClient) -> dict[str, int]:
    """SEC 전체 상장 티커 → CIK. 후보 노드(candidates.py 가 올린 그래프 밖 상장사)는 티커·거래소만 있고 CIK 가 없어서 여기서 잇는다."""
    data = http.get_json(SEC_TICKERS_URL, headers=SEC_UA)
    rows = data.values() if isinstance(data, dict) else data
    out: dict[str, int] = {}
    for r in rows:
        tk, cik = str(r.get("ticker") or "").upper().replace(".", "-"), r.get("cik_str")
        if tk and cik:
            out[tk] = int(cik)
    return out


COVER_RE = re.compile(r"<dei:EntityCommonStockSharesOutstanding\b([^>]*)>\s*([\d,]+)\s*<")
CTX_RE = re.compile(r'contextRef="([^"]+)"')


def cover_shares(text: str) -> float | None:
    """10-Q/10-K 인라인 XBRL 인스턴스의 표지 주식수 — 클래스별 사실을 합산한다 (Forgent: Class A 274.5M + Class B 29.9M).
    companyfacts API 는 차원(클래스)이 붙은 사실을 빼고 주기 때문에 다중 클래스 회사는 거기서 한 클래스만 보이거나(FPS) 2015년 값이 남는다(VICR)."""
    by_ctx: dict[str, float] = {}
    for attrs, val in COVER_RE.findall(text):
        m = CTX_RE.search(attrs)
        by_ctx[m.group(1) if m else f"_{len(by_ctx)}"] = float(val.replace(",", ""))
    total = sum(by_ctx.values())
    return total if total >= MIN_SHARES else None


def sec_cover(http: HttpClient, cik: int) -> tuple[float, str] | None:
    """가장 최근 10-Q/10-K 의 표지 주식수 (주식수, 보고 기준일). 인스턴스 파일이 없으면 None → companyfacts 로."""
    sub = http.get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", headers=SEC_UA)
    rec = (sub.get("filings") or {}).get("recent") or {}
    forms, accs, docs, dates = rec.get("form") or [], rec.get("accessionNumber") or [], rec.get("primaryDocument") or [], rec.get("reportDate") or []
    for i, form in enumerate(forms):
        if form not in ("10-Q", "10-K") or i >= len(accs) or not docs[i].endswith(".htm"):
            continue
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accs[i].replace('-', '')}/{docs[i][:-4]}_htm.xml"
        try:
            n = cover_shares(http.get_text(url, headers=SEC_UA))
        except Exception as exc:  # noqa: BLE001 - 인스턴스 이름이 관행과 다르면 companyfacts 로
            log.info("sec cover %s: %s", cik, str(exc)[:80])
            return None
        return (n, dates[i] if i < len(dates) else "") if n else None
    return None


def fetch_us(http: HttpClient, xs: list[Listing], graph_nodes: dict[str, Any], cik_lookup: dict[str, int] | None = None,
             use_cover: bool = True) -> list[dict[str, Any]]:
    out = []
    lookup = cik_lookup
    for x in xs:
        cik = ((graph_nodes.get(x.company_id) or {}).get("listing") or {}).get("cik")
        if not cik:
            if lookup is None:
                try:
                    lookup = sec_cik_by_ticker(http)          # 필요할 때 한 번만
                except Exception as exc:  # noqa: BLE001
                    log.warning("sec company_tickers: %s", str(exc)[:100])
                    lookup = {}
            cik = lookup.get(x.ticker.upper().replace(".", "-"))
        if not cik:
            continue
        r, src = None, "sec_cover"
        if use_cover:
            try:
                r = sec_cover(http, cik)                       # 표지 주식수가 우선 — 클래스를 전부 센다
            except Exception as exc:  # noqa: BLE001
                log.info("sec cover %s: %s", x.key, str(exc)[:80])
        if not r:
            src = "sec_companyfacts"
            try:
                facts = http.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", headers=SEC_UA)
                r = sec_shares(facts)
            except Exception as exc:  # noqa: BLE001
                log.warning("sec %s: %s", x.key, str(exc)[:100])
                continue
        if r:
            per_ads = SHARES_PER_ADS.get(x.ticker.upper())
            out.append(_row(x, r[0] / per_ads, r[1], src + "_ads") if per_ads else _row(x, r[0], r[1], src))
    return out


def fetch_twse(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    data = http.get_json("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=UA)
    shares = {str(r.get("公司代號")).strip(): _num(r.get("已發行普通股數或TDR原股發行股數")) for r in data}
    today = date.today().isoformat()
    return [_row(x, shares[x.ticker], today, "twse_t187ap03") for x in xs if shares.get(x.ticker)]


def fetch_tpex(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    data = http.get_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=UA)
    shares = {str(r.get("SecuritiesCompanyCode")).strip(): _num(r.get("Capitals")) for r in data}
    today = date.today().isoformat()
    return [_row(x, shares[x.ticker], today, "tpex_quotes") for x in xs if shares.get(x.ticker)]


def parse_krw_won(s: str) -> float | None:
    """'2,557억' · '6조 3,105억' · '1조' → 원."""
    s = str(s).replace(",", "").replace(" ", "")
    m = re.fullmatch(r"(?:(\d+)조)?(?:(\d+)억)?", s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return float(m.group(1) or 0) * 1e12 + float(m.group(2) or 0) * 1e8


def fetch_kr(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    """네이버 모바일 API: integration.totalInfos[marketValue] = '2,557억', basic.closePrice = '12,100' → 주식수 = 시총 ÷ 종가."""
    out = []
    for x in xs:
        try:
            d = http.get_json(f"https://m.stock.naver.com/api/stock/{x.ticker}/integration", headers=UA)
            mv = next((i.get("value") for i in d.get("totalInfos") or [] if i.get("code") == "marketValue"), None)
            b = http.get_json(f"https://m.stock.naver.com/api/stock/{x.ticker}/basic", headers=UA)
            mcap, close = parse_krw_won(mv or ""), _num(b.get("closePrice"))
            if mcap and close:
                out.append(_row(x, mcap / close, date.today().isoformat(), "naver_mobile"))
        except Exception as exc:  # noqa: BLE001
            log.warning("naver %s: %s", x.key, str(exc)[:100])
    return out


def parse_tencent(text: str) -> tuple[float, float] | None:
    """qt.gtimg.cn 한 줄 → (종가, 총시총 억). 필드 3 = 현재가, 45 = 總市值(億)."""
    f = text.split("~")
    if len(f) < 46:
        return None
    px, mv = _num(f[3]), _num(f[45])
    return (px, mv) if px and mv else None


def fetch_cn(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    out = []
    for x in xs:
        code = x.ticker
        q = {"SSE": f"sh{code}", "SZSE": f"sz{code}", "BJSE": f"bj{code}", "HKEX": f"hk{int(code):05d}"}.get(x.exchange)
        if not q:
            continue
        try:
            r = parse_tencent(http.get_text(f"https://qt.gtimg.cn/q={q}", headers=UA))
            if r:
                out.append(_row(x, r[1] * 1e8 / r[0], date.today().isoformat(), "tencent_qt"))
        except Exception as exc:  # noqa: BLE001
            log.warning("tencent %s: %s", x.key, str(exc)[:100])
    return out


def parse_yahoo_jp_shares(html: str) -> float | None:
    """'発行済株式数 … 3,175,762,284 株' — 라벨 뒤 태그를 걷어내고 첫 숫자."""
    i = html.find("発行済株式数")
    if i < 0:
        return None
    seg = re.sub(r"<[^>]+>", " ", html[i:i + 4000])
    m = re.search(r"([0-9][0-9,]{3,})\s*株", seg)
    return _num(m.group(1)) if m else None


def fetch_jp(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    out = []
    for x in xs:
        try:
            n = parse_yahoo_jp_shares(http.get_text(f"https://finance.yahoo.co.jp/quote/{x.ticker}.T", headers=UA))
            if n:
                out.append(_row(x, n, date.today().isoformat(), "yahoo_jp"))
        except Exception as exc:  # noqa: BLE001
            log.warning("yahoo jp %s: %s", x.key, str(exc)[:100])
    return out


def _row(x: Listing, shares: float, as_of: str, source: str) -> dict[str, Any]:
    return {"company_id": x.company_id, "ticker": x.key, "exchange": x.exchange, "currency": CURRENCY[x.market],
            "shares_outstanding": round(shares), "shares_as_of": as_of[:10], "source": source, "fetched_at": datetime.now(UTC).isoformat()}


# ---------------------------------------------------------------- 환율
def fetch_fx(http: HttpClient) -> list[dict[str, Any]]:
    out = [{"currency": "USD", "usd_per_unit": 1.0, "as_of": date.today().isoformat()}]
    for cur, (sid, per_usd) in FX_SERIES.items():
        try:
            txt = http.get_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", headers={"User-Agent": FRED_UA, "Accept": "text/csv"})
        except Exception as exc:  # noqa: BLE001
            log.warning("fx %s: %s", cur, str(exc)[:100])
            continue
        last = None
        for line in txt.splitlines()[1:]:
            d, _, v = line.partition(",")
            if v.strip() not in ("", "."):
                last = (d.strip(), float(v))
        if last:
            out.append({"currency": cur, "usd_per_unit": round(1 / last[1], 8) if per_usd else round(last[1], 8), "as_of": last[0]})
    return out


# ---------------------------------------------------------------- 실행
def run(http: HttpClient, store, graph: dict[str, Any], only: set[str] | None = None, max_us: int = 40) -> dict[str, Any]:
    items, _ = listings(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if only:
        items = [x for x in items if x.market in only]
    by_m: dict[str, list[Listing]] = {}
    for x in items:
        by_m.setdefault(x.market, []).append(x)
    have: dict[str, str] = {}
    try:
        for r in store.select("raw.company_facts", ["company_id", "fetched_at"]):
            have[r["company_id"]] = str(r.get("fetched_at") or "")[:10]
    except Exception as exc:  # noqa: BLE001
        log.warning("company_facts unavailable: %s", exc)
    stats: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for m, xs in by_m.items():
        try:
            if m == "us":
                cut = (date.today() - timedelta(days=US_REFRESH_DAYS)).isoformat()
                xs = sorted((x for x in xs if have.get(x.company_id, "") < cut), key=lambda x: have.get(x.company_id, ""))[:max_us]
                got = fetch_us(http, xs, nodes)
            elif m == "twse":
                got = fetch_twse(http, xs)
            elif m == "tpex":
                got = fetch_tpex(http, xs)
            elif m == "kr":
                got = fetch_kr(http, xs)
            elif m in ("cn", "hk"):
                got = fetch_cn(http, xs)
            elif m == "jp":
                got = fetch_jp(http, xs)
            else:
                continue
            rows += got
            stats[m] = {"tried": len(xs), "ok": len(got)}
        except Exception as exc:  # noqa: BLE001
            stats[m] = {"tried": len(xs), "ok": 0, "error": str(exc)[:120]}
    if rows:
        store.upsert("raw.company_facts", rows, ["company_id"])
    fx = fetch_fx(http)
    n_fx = save_fx(store, fx) if fx else 0
    # 시도했는데 하나도 못 받은 시장은 실패로 — 성공 표시 뒤에 조용히 비는 일을 막는다 (11/02 미국 0/6 이 며칠 숨어 있었다)
    failed = sorted(m for m, v in stats.items() if v.get("tried") and not v.get("ok"))
    return {"rows": len(rows), "fx": n_fx, "by_market": stats, "failed_markets": failed}


def save_fx(store, fx: list[dict[str, Any]]) -> int:
    """환율 저장. ref 스키마는 PostgREST 에 노출되지 않으므로(PGRST106) 0026 의 raw.put_fx_rates RPC 로 쓰고,
    RPC 가 아직 없으면(0026 전) 예전 경로를 시도한 뒤 실패해도 발행주식수 저장은 지키고 경고만 남긴다."""
    try:
        resp = store._req("POST", "raw.rpc/put_fx_rates", body={"rows": fx})
        return int((resp.json() or {}).get("upserted") or 0)
    except Exception as exc:  # noqa: BLE001
        log.warning("put_fx_rates 실패 (0026 전?): %s", str(exc)[:160])
    try:
        return store.upsert("ref.fx_rates", [dict(r, updated_at=datetime.now(UTC).isoformat()) for r in fx], ["currency"])
    except Exception as exc:  # noqa: BLE001
        log.warning("ref.fx_rates upsert 실패 — 환율은 지난 값 유지: %s", str(exc)[:160])
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "probe"])
    ap.add_argument("--only")
    ap.add_argument("--max-us", type=int, default=40)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.ecosystems.ontology import load_graph

    graph = load_graph()
    http = HttpClient(UA["User-Agent"], timeout=40, max_retries=1)
    if args.cmd == "probe":
        items, _ = listings(graph)
        nodes = {n["id"]: n for n in graph["nodes"]}
        res = {}
        for m in sorted({x.market for x in items}):
            xs = [x for x in items if x.market == m][:1]
            try:
                got = {"us": lambda: fetch_us(http, xs, nodes), "twse": lambda: fetch_twse(http, xs), "tpex": lambda: fetch_tpex(http, xs),
                       "kr": lambda: fetch_kr(http, xs), "cn": lambda: fetch_cn(http, xs), "hk": lambda: fetch_cn(http, xs),
                       "jp": lambda: fetch_jp(http, xs)}[m]()
                res[m] = {"key": xs[0].key, "shares": got[0]["shares_outstanding"] if got else None}
            except Exception as exc:  # noqa: BLE001
                res[m] = {"key": xs[0].key, "error": str(exc)[:160]}
        res["fx"] = {r["currency"]: r["usd_per_unit"] for r in fetch_fx(http)}
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    from wsj.config import load_settings
    from wsj.db import make_store
    from wsj.runlog import logged_run

    store = make_store(load_settings())
    try:
        with logged_run(store, "facts", {"only": args.only, "max_us": args.max_us}) as lr:
            res = run(http, store, graph, set(args.only.split(",")) if args.only else None, args.max_us)
            lr["rows"] = res["rows"]
            lr["notes"] = json.dumps(res, ensure_ascii=False)[:1500]
            print(json.dumps(res, ensure_ascii=False))
            if res["failed_markets"]:     # 받은 행은 이미 저장했다 — 기록만 실패로 남겨 알림·점검이 보게
                raise RuntimeError(f"시도했지만 하나도 못 받은 시장: {', '.join(res['failed_markets'])} — {json.dumps(res['by_market'], ensure_ascii=False)[:600]}")
    finally:
        http.close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
