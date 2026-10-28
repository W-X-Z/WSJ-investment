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
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from wsj.ecosystems.prices import UA, Listing, listings
from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger(__name__)
HOST_RPS.update({"data.sec.gov": 4.0, "qt.gtimg.cn": 0.5, "finance.yahoo.co.jp": 0.5, "m.stock.naver.com": 1.0})

CURRENCY = {"us": "USD", "twse": "TWD", "tpex": "TWD", "kr": "KRW", "cn": "CNY", "hk": "HKD", "jp": "JPY"}
# FRED 환율 계열: (계열, 'USD 당 외화' 인지)
FX_SERIES = {"TWD": ("DEXTAUS", True), "KRW": ("DEXKOUS", True), "CNY": ("DEXCHUS", True), "JPY": ("DEXJPUS", True), "HKD": ("DEXHKUS", True),
             "EUR": ("DEXUSEU", False), "GBP": ("DEXUSUK", False), "INR": ("DEXINUS", True), "CAD": ("DEXCAUS", True)}
FRED_UA = "WSJ-investment research (github.com/W-X-Z/WSJ-investment)"
US_REFRESH_DAYS = 30


def _num(v: Any) -> float | None:
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s and s not in ("-", "－", "N/A") else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 시장별 주식수
def sec_shares(facts: dict[str, Any]) -> tuple[float, str] | None:
    """companyfacts → (주식수, 기준일). 같은 기준일에 여러 클래스가 있으면 합산."""
    units = (((facts.get("facts") or {}).get("dei") or {}).get("EntityCommonStockSharesOutstanding") or {}).get("units") or {}
    rows = units.get("shares") or []
    if not rows:
        return None
    end = max(r["end"] for r in rows if r.get("end"))
    same = {(r.get("frame"), r.get("accn"), r.get("val")) for r in rows if r.get("end") == end}
    return float(sum(v for _, _, v in same if v)), end


def fetch_us(http: HttpClient, xs: list[Listing], graph_nodes: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for x in xs:
        cik = ((graph_nodes.get(x.company_id) or {}).get("listing") or {}).get("cik")
        if not cik:
            continue
        try:
            facts = http.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
            r = sec_shares(facts)
        except Exception as exc:  # noqa: BLE001
            log.warning("sec %s: %s", x.key, str(exc)[:100])
            continue
        if r:
            out.append(_row(x, r[0], r[1], "sec_companyfacts"))
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
    return {"rows": len(rows), "fx": n_fx, "by_market": stats}


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
    finally:
        http.close()
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
