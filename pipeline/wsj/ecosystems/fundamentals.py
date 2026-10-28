"""상장사 재무 — 매출·영업이익·순이익 (TTM) → raw.company_fundamentals (ADR-0019: 가치평가의 분모).

    python -m wsj.ecosystems.fundamentals run [--only us,twse,tpex,kr] [--max-us 40]
    python -m wsj.ecosystems.fundamentals probe

가치평가(시나리오별 내재 시총 = 매출 × 마진 × 배수)에는 '지금 이 회사가 얼마나 버는가'가 있어야 한다. 시장별 공식·공개 출처:

  미국     data.sec.gov companyfacts (wsj.briefs.xbrl 가 분기 표를 만든다) → 최근 4분기 합 = TTM, 회계연도 = FY. 하루 --max-us 개, 30일 지난 것부터.
  대만     TTM 매출 = ideas.indicator_points 의 월매출(tw:<code>, NT$ 천) 최근 12개월 합.
           마진 = TWSE openapi t187ap06_L_ci(상장) · TPEx mopsfin_t187ap14_O(상계) 의 YTD 손익 비율 → TTM 매출에 곱한다 (note 에 남김).
  한국     m.stock.naver.com finance/quarter (억원, 컨센서스 열 제외) 최근 4분기 합.
  일본·중국 아직 없음 — LLM 이 근거(IR·공시)에서 읽은 숫자를 가정으로 쓴다.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from wsj.ecosystems.prices import UA, Listing, listings
from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger(__name__)
HOST_RPS.setdefault("data.sec.gov", 4.0)
HOST_RPS.setdefault("m.stock.naver.com", 1.0)

CURRENCY = {"us": "USD", "twse": "TWD", "tpex": "TWD", "kr": "KRW", "cn": "CNY", "hk": "HKD", "jp": "JPY"}
US_REFRESH_DAYS = 30
TWSE_PL = "https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci"
TPEX_PL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O"
NAVER_Q = "https://m.stock.naver.com/api/stock/{code}/finance/quarter"


def _num(v: Any) -> float | None:
    try:
        s = str(v).replace(",", "").strip()
        return float(s) if s and s not in ("-", "－", "N/A", "") else None
    except (TypeError, ValueError):
        return None


def _row(x: Listing, period: str, end: str, source: str, **kw: Any) -> dict[str, Any]:
    return {"company_id": x.company_id, "period": period, "period_end": end[:10], "currency": CURRENCY[x.market], "source": source,
            "fetched_at": datetime.now(UTC).isoformat()} | kw


# ---------------------------------------------------------------- 미국 (SEC companyfacts)
def us_rows(x: Listing, fin: dict[str, Any], cik: int | None = None) -> list[dict[str, Any]]:
    """xbrl.build_financials 결과 → TTM(최근 4분기 모두 매출이 있을 때) + 최근 FY."""
    out = []
    q = [r for r in fin.get("quarters") or [] if r.get("revenue") is not None]
    if len(q) >= 4:
        last4 = q[-4:]
        ends = [date.fromisoformat(r["period_end"]) for r in last4]
        if (ends[-1] - ends[0]).days <= 300:  # 빠진 분기 없이 이어진 4개
            def tot(k: str) -> float | None:
                vs = [r.get(k) for r in last4]
                return float(sum(vs)) if all(v is not None for v in vs) else None
            out.append(_row(x, "ttm", last4[-1]["period_end"], "sec_companyfacts", revenue=tot("revenue"), gross_profit=tot("gross_profit"),
                            operating_income=tot("op_income"), net_income=tot("net_income"),
                            source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json" if cik else None))
    for a in (fin.get("annual") or [])[-2:]:
        if a.get("revenue") is not None:
            out.append(_row(x, "fy", a["fiscal_year_end"], "sec_companyfacts", revenue=a.get("revenue"), gross_profit=a.get("gross_profit"),
                            operating_income=a.get("op_income"), net_income=a.get("net_income")))
    return out


def fetch_us(http: HttpClient, xs: list[Listing], graph_nodes: dict[str, Any]) -> list[dict[str, Any]]:
    from wsj.briefs.xbrl import build_financials, load_companyfacts

    out = []
    for x in xs:
        cik = ((graph_nodes.get(x.company_id) or {}).get("listing") or {}).get("cik")
        if not cik:
            continue
        try:
            cf = load_companyfacts(http, int(cik))
            if not cf:
                continue
            out += us_rows(x, build_financials(cf), int(cik))
        except Exception as exc:  # noqa: BLE001
            log.warning("sec %s: %s", x.key, str(exc)[:100])
    return out


# ---------------------------------------------------------------- 대만 (월매출 TTM + YTD 손익 비율)
def ttm_from_monthly(points: list[tuple[date, float]], unit: float = 1000.0) -> tuple[float, date] | None:
    """월매출 점(날짜 = 기준월 1일) 최근 12개 합. 12개월이 이어지지 않으면 None."""
    pts = sorted(points)[-12:]
    if len(pts) < 12:
        return None
    first, last = pts[0][0], pts[-1][0]
    if (last.year - first.year) * 12 + last.month - first.month != 11:
        return None
    end = (last.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)  # 기준월 말일
    return sum(v for _, v in pts) * unit, end


def parse_tw_margins(rows: list[dict[str, Any]], code_key: str, rev_key: str, op_key: str, ni_key: str) -> dict[str, dict[str, Any]]:
    out = {}
    for r in rows:
        code = str(r.get(code_key) or "").strip()
        rev, op, ni = _num(r.get(rev_key)), _num(r.get(op_key)), _num(r.get(ni_key))
        if code and rev and rev > 0:
            out[code] = {"op_margin": (op / rev) if op is not None else None, "net_margin": (ni / rev) if ni is not None else None,
                         "year": r.get("年度") or r.get("Year"), "quarter": r.get("季別")}
    return out


def fetch_tw(http: HttpClient, xs: list[Listing], monthly: dict[str, list[tuple[date, float]]], market: str) -> list[dict[str, Any]]:
    margins: dict[str, dict[str, Any]] = {}
    try:
        if market == "twse":
            margins = parse_tw_margins(http.get_json(TWSE_PL, headers=UA), "公司代號", "營業收入", "營業利益（損失）", "本期淨利（淨損）")
        else:
            margins = parse_tw_margins(http.get_json(TPEX_PL, headers=UA), "SecuritiesCompanyCode", "營業收入", "營業利益", "稅後淨利")
    except Exception as exc:  # noqa: BLE001
        log.warning("%s 손익표: %s", market, str(exc)[:100])
    out = []
    for x in xs:
        t = ttm_from_monthly(monthly.get(f"tw:{x.ticker}") or [])
        if not t:
            continue
        rev, end = t
        m = margins.get(x.ticker) or {}
        note = None
        op = ni = None
        if m.get("op_margin") is not None:
            op = round(rev * m["op_margin"])
            ni = round(rev * m["net_margin"]) if m.get("net_margin") is not None else None
            note = f"영업이익·순이익 = {m.get('year')}년 {m.get('quarter')}분기 누적 손익 비율 × TTM 매출"
        out.append(_row(x, "ttm", end.isoformat(), f"{market}_monthly" + ("+pl" if op is not None else ""), revenue=round(rev),
                        operating_income=op, net_income=ni, note=note,
                        source_url="https://openapi.twse.com.tw/v1/opendata/t187ap05_L" if market == "twse" else "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"))
    return out


# ---------------------------------------------------------------- 한국 (네이버 분기 재무, 억원)
def parse_naver_quarters(d: dict[str, Any]) -> list[dict[str, Any]]:
    """finance/quarter → [{period_end, revenue, operating_income, net_income}] (원 단위, 컨센서스 열 제외, 오래된 순)."""
    fi = d.get("financeInfo") or {}
    cols = [c["key"] for c in fi.get("trTitleList") or [] if c.get("isConsensus") != "Y" and c.get("key")]
    rows = {r.get("title"): r.get("columns") or {} for r in fi.get("rowList") or []}

    def val(title: str, key: str) -> float | None:
        v = _num(((rows.get(title) or {}).get(key) or {}).get("value"))
        return v * 1e8 if v is not None else None

    out = []
    for k in sorted(cols):
        y, m = int(k[:4]), int(k[4:6])
        end = (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        rev = val("매출액", k)
        if rev is None:
            continue
        out.append({"period_end": end.isoformat(), "revenue": rev, "operating_income": val("영업이익", k), "net_income": val("당기순이익", k)})
    return out


def kr_rows(x: Listing, qs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(qs) < 4:
        return []
    last4 = qs[-4:]
    ends = [date.fromisoformat(r["period_end"]) for r in last4]
    if (ends[-1] - ends[0]).days > 300:
        return []

    def tot(k: str) -> float | None:
        vs = [r.get(k) for r in last4]
        return float(sum(vs)) if all(v is not None for v in vs) else None
    return [_row(x, "ttm", last4[-1]["period_end"], "naver_finance", revenue=tot("revenue"), operating_income=tot("operating_income"),
                 net_income=tot("net_income"), source_url=NAVER_Q.format(code=x.ticker))]


def fetch_kr(http: HttpClient, xs: list[Listing]) -> list[dict[str, Any]]:
    out = []
    for x in xs:
        try:
            out += kr_rows(x, parse_naver_quarters(http.get_json(NAVER_Q.format(code=x.ticker), headers=UA)))
        except Exception as exc:  # noqa: BLE001
            log.warning("naver %s: %s", x.key, str(exc)[:100])
    return out


# ---------------------------------------------------------------- 실행
def run(http: HttpClient, store, graph: dict[str, Any], only: set[str] | None = None, max_us: int = 40) -> dict[str, Any]:
    from wsj.ecosystems.indicators import load_history

    items, _ = listings(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    if only:
        items = [x for x in items if x.market in only]
    by_m: dict[str, list[Listing]] = {}
    for x in items:
        by_m.setdefault(x.market, []).append(x)
    have: dict[str, str] = {}
    try:
        for r in store.select("raw.company_fundamentals", ["company_id", "fetched_at"], {"period": "ttm"}):
            have[r["company_id"]] = max(have.get(r["company_id"], ""), str(r.get("fetched_at") or "")[:10])
    except Exception as exc:  # noqa: BLE001
        log.warning("company_fundamentals unavailable: %s", exc)
    stats: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    monthly: dict[str, list[tuple[date, float]]] | None = None
    for m, xs in by_m.items():
        try:
            if m == "us":
                cut = (date.today() - timedelta(days=US_REFRESH_DAYS)).isoformat()
                xs = sorted((x for x in xs if have.get(x.company_id, "") < cut), key=lambda x: have.get(x.company_id, ""))[:max_us]
                got = fetch_us(http, xs, nodes)
            elif m in ("twse", "tpex"):
                if monthly is None:
                    monthly = load_history(store, [f"tw:{x.ticker}" for x in by_m.get("twse", []) + by_m.get("tpex", [])], date.today() - timedelta(days=420))
                got = fetch_tw(http, xs, monthly, m)
            elif m == "kr":
                got = fetch_kr(http, xs)
            else:
                continue
            rows += got
            stats[m] = {"tried": len(xs), "ok": len({r["company_id"] for r in got})}
        except Exception as exc:  # noqa: BLE001
            stats[m] = {"tried": len(xs), "ok": 0, "error": str(exc)[:120]}
    if rows:
        store.upsert("raw.company_fundamentals", rows, ["company_id", "period", "period_end"])
    return {"rows": len(rows), "by_market": stats}


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
        res: dict[str, Any] = {}
        for m in ("us", "kr"):
            xs = [x for x in items if x.market == m][:1]
            if not xs:
                continue
            try:
                got = fetch_us(http, xs, nodes) if m == "us" else fetch_kr(http, xs)
                res[m] = {"key": xs[0].key, "ttm": next((r for r in got if r["period"] == "ttm"), None)}
            except Exception as exc:  # noqa: BLE001
                res[m] = {"key": xs[0].key, "error": str(exc)[:160]}
        for m, url in (("twse", TWSE_PL), ("tpex", TPEX_PL)):
            try:
                res[m] = {"pl_rows": len(http.get_json(url, headers=UA))}
            except Exception as exc:  # noqa: BLE001
                res[m] = {"error": str(exc)[:160]}
        print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        return 0
    from wsj.config import load_settings
    from wsj.db import make_store
    from wsj.runlog import logged_run

    store = make_store(load_settings())
    try:
        with logged_run(store, "fundamentals", {"only": args.only, "max_us": args.max_us}) as lr:
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
