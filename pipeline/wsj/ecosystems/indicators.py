"""공급망 가격·실적 지표 — 메모리 현물가, 미국 PPI·원자재, 대만 공급사 월매출. ADR-0014 개정.

    python -m wsj.ecosystems.indicators run [--no-save] [--out PATH]

출처 (무료·무인증):
  DRAMeXchange   메모리 현물가 표 (홈페이지, 일 1회 갱신, GMT+8). 세션 평균값만 저장한다.
  FRED           fredgraph.csv — 미국 생산자물가(PPI)·원자재 월간 시계열
  TWSE / TPEx    OpenAPI 월매출 (上市 t187ap05_L, 上櫃 mopsfin_t187ap05_O) — 대만 공급사 실적

지표 변화가 임계치를 넘으면 이슈 후보(source_type='data')를 만든다 → issues.run 이 다른 출처와 함께 선별한다.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from wsj.http import HttpClient

log = logging.getLogger("wsj.ecosystems.indicators")
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
DRAMX = "https://www.dramexchange.com/"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
BLS_API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"  # 무인증 v1: 하루 25회·요청당 25개 시리즈
TWSE_REV = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_REV = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"

MEM = ["company:mu", "company:samsung", "company:skhynix"]


@dataclass
class Indicator:
    indicator_id: str
    label: str
    category: str
    unit: str
    frequency: str
    source: str
    source_url: str
    ecosystem: str
    nodes: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)
    note: str | None = None
    match: str | None = None  # DRAMeXchange 행 이름 / FRED 시리즈 / 대만 종목코드

    def row(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("indicator_id", "label", "category", "unit", "frequency", "source", "source_url", "ecosystem", "nodes", "companies", "note")}


def _dx(slug: str, label: str, match: str, freq: str = "daily", nodes: list[str] | None = None, note: str | None = None) -> Indicator:
    # 범용 메모리 현물가는 특정 병목 노드가 아니라 메모리 3사(HBM 캐파 배분 압력)의 맥락 지표다 — 노드 없이 기업에만 잇는다
    return Indicator(f"dx:{slug}", label, "memory_spot", "USD", freq, "DRAMeXchange", DRAMX, "hbm", nodes or [], MEM, note, match)


def _bls(sid: str, label: str, eco: str, nodes: list[str], note: str | None = None) -> Indicator:
    return Indicator(f"bls:{sid}", label, "ppi", "index", "monthly", "BLS", f"https://data.bls.gov/timeseries/{sid}", eco, nodes, [], note, sid)


def _fred(sid: str, label: str, eco: str, nodes: list[str], unit: str = "index", cat: str = "ppi", note: str | None = None) -> Indicator:
    return Indicator(f"fred:{sid}", label, cat, unit, "monthly", "FRED", f"https://fred.stlouisfed.org/series/{sid}", eco, nodes, [], note, sid)


# 대만 월매출 공시 기업 — 지표의 companies 와 이슈 태깅에 쓴다. 그래프에 같은 id 의 기업 노드가 있으면 그래프가 원본.
TW_ENTITIES: dict[str, dict[str, Any]] = {}


def _tw(code: str, name: str, eco: str, nodes: list[str], role: str, market: str = "TWSE", entity: str | None = None) -> Indicator:
    eid = entity or "company:" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    TW_ENTITIES[eid] = {"entity_id": eid, "name": name, "exchange": market, "local_code": code, "listing": "non_sec_listed",
                        "ecosystems": [eco], "role": "supplier", "attrs": {"role_note": role, "country": "TW"}}
    return Indicator(f"tw:{code}", f"{name} 월매출", "tw_revenue", "NT$ 천", "monthly", market,
                     f"https://mops.twse.com.tw/mops/#/web/t146sb05?companyId={code}", eco, nodes, [eid], role, code)


INDICATORS: list[Indicator] = [
    # 메모리 현물가 — HBM 증설은 범용 DRAM 캐파를 잠식한다 (가격 = 캐파 배분 압력의 신호)
    _dx("ddr5_16gb", "DDR5 16Gb 현물 (4800/5600)", "DDR5 16Gb (2Gx8) 4800/5600"),
    _dx("ddr4_16gb", "DDR4 16Gb 현물 (3200)", "DDR4 16Gb (2Gx8) 3200"),
    _dx("ddr4_8gb", "DDR4 8Gb 현물 (3200)", "DDR4 8Gb (1Gx8) 3200"),
    _dx("ddr5_rdimm_32gb", "DDR5 RDIMM 32GB 현물 (서버)", "DDR5 RDIMM 32GB 4800/5600", "weekly"),
    _dx("gddr6_8gb", "GDDR6 8Gb 현물", "GDDR6 8Gb", "weekly"),
    _dx("nand_512gb_tlc", "NAND 512Gb TLC 웨이퍼 현물", "512Gb TLC", "weekly", None, "메모리 사이클 확인용"),
    # 미국 PPI·원자재 — 부품 가격 압력
    _bls("PCU334413334413", "미국 PPI: 반도체·관련 소자", "hbm", ["gen:hbm4"]),
    _bls("PCU335311335311", "미국 PPI: 전력·배전 변압기", "power", ["component:planar_transformer", "tech:directmv"], note="데이터센터 전력 병목(변압기 리드타임)의 가격 쪽 신호"),
    _bls("PCU334417334417", "미국 PPI: 전자 커넥터", "optics", ["component:fiber_connector", "component:osfp"]),
    _bls("PCU334412334412", "미국 PPI: 인쇄회로기판(베어)", "hbm", ["component:package_substrate"]),
    _bls("PCU335313335313", "미국 PPI: 개폐기·배전반", "power", ["component:dc_breaker", "bottleneck:dc_protection"]),
    _bls("PCU331420331420", "미국 PPI: 구리 압연·인발", "power", ["bottleneck:copper", "component:dc_busbar"]),
    _fred("PCOPPUSDM", "구리 국제가격", "power", ["bottleneck:copper", "component:dc_busbar"], "USD/톤", "commodity"),
    _fred("PALUMUSDM", "알루미늄 국제가격", "power", ["component:dc_busbar"], "USD/톤", "commodity"),
    # 대만 공급사 월매출 — 매월 10일 전후 공시, 미국 실적보다 2~3개월 빠른 공급망 수요 신호
    _tw("2330", "TSMC", "hbm", ["req:hbm_io"], "CoWoS·HBM 베이스 다이 파운드리"),
    _tw("3711", "ASE Technology", "hbm", ["tech:tcb", "component:microbump"], "OSAT·첨단 패키징"),
    _tw("3037", "Unimicron", "hbm", ["component:package_substrate", "material:abf"], "ABF 기판"),
    _tw("2449", "KYEC", "hbm", ["process:kgd_test", "bottleneck:hbm_kged"], "AI 칩 최종 테스트"),
    _tw("6515", "WinWay", "hbm", ["process:kgd_test"], "테스트 소켓"),
    _tw("6223", "MPI", "hbm", ["process:kgd_test"], "프로브카드", "TPEx"),
    _tw("6510", "Chunghwa Precision Test", "hbm", ["process:kgd_test"], "프로브카드", "TPEx"),
    _tw("2345", "Accton", "optics", ["gen:800g", "gen:1p6t"], "AI 스위치·네트워크 장비"),
    _tw("3081", "LandMark Optoelectronics", "optics", ["material:inp", "component:eml"], "InP 에피웨이퍼", "TPEx"),
    _tw("4979", "Luxnet", "optics", ["component:optical_laser", "component:photodiode"], "광 소자(레이저·수광)", "TPEx"),
    _tw("3363", "FOCI", "optics", ["tech:cpo", "component:fiber_connector"], "CPO 광 커넥터·FAU", "TPEx"),
    _tw("3163", "Browave", "optics", ["component:fiber_connector"], "광 수동부품", "TPEx"),
    _tw("2308", "Delta Electronics", "power", ["gen:800vdc", "component:power_converter", "tech:sidecar"], "800VDC 전원·냉각"),
    _tw("2301", "Lite-On", "power", ["gen:800vdc", "component:power_converter"], "서버 전원"),
    _tw("3665", "BizLink", "power", ["gen:800vdc", "component:aec"], "800VDC 전력·고속 케이블"),
    _tw("3017", "Asia Vital Components", "power", ["bottleneck:liquidcool", "component:coldplate"], "액체냉각 콜드플레이트"),
    _tw("3324", "Auras", "power", ["bottleneck:liquidcool", "component:coldplate", "tech:cdu"], "액체냉각", "TPEx"),
]
BY_ID = {i.indicator_id: i for i in INDICATORS}

# 이슈 후보로 올리는 임계치
SPOT_WEEKLY = 8.0      # 현물가 1주 변화 ±%
SPOT_DAILY = 3.0       # 이력이 없을 때 출처의 일간 변화 ±%
REV_YOY_HIGH = 60.0    # 월매출 YoY ≥ %
REV_YOY_LOW = -15.0    # 월매출 YoY ≤ %
REV_MOM = 25.0         # 월매출 MoM ±%
PPI_MOM = 1.5          # PPI·원자재 전월 대비 ±%
PPI_YOY = 10.0         # PPI·원자재 전년 대비 ±%


@dataclass
class Point:
    indicator_id: str
    as_of: date
    value: float
    change_pct: float | None = None
    yoy_pct: float | None = None
    meta: dict[str, Any] | None = None

    def row(self) -> dict[str, Any]:
        return {"indicator_id": self.indicator_id, "as_of": self.as_of.isoformat(), "value": self.value, "change_pct": self.change_pct,
                "yoy_pct": self.yoy_pct, "meta": self.meta}


def _num(s: Any) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------- DRAMeXchange
_TD = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
_UPD = re.compile(r"Last Update:\s*([A-Z][a-z]{2})\.?\s*(\d{1,2})\s+(\d{4})")
_MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_dramexchange(page: str) -> dict[str, tuple[date | None, float, float | None]]:
    """행 이름 → (갱신일, 세션 평균, 세션 변화%). 표마다 바로 앞의 'Last Update' 날짜를 붙인다."""
    out: dict[str, tuple[date | None, float, float | None]] = {}
    updates = [(m.start(), date(int(m.group(3)), _MON[m.group(1)], int(m.group(2)))) for m in _UPD.finditer(page) if m.group(1) in _MON]
    for tm in re.finditer(r"<table[^>]*>(.*?)</table>", page, re.S):
        body = tm.group(1)
        if "Session Average" not in body:
            continue
        d = next((u for pos, u in reversed(updates) if pos < tm.start()), None)
        for rm in re.finditer(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip() for c in _TD.findall(rm.group(1))]
            if len(cells) >= 7 and cells[0] and cells[0] != "Item":
                avg, chg = _num(cells[5]), _num(cells[6])
                if avg is not None:
                    out[cells[0]] = (d, avg, chg)
    return out


def fetch_dramexchange(http: HttpClient, today: date) -> list[Point]:
    try:
        rows = parse_dramexchange(http.get_text(DRAMX, headers=BROWSER_UA))
    except Exception as exc:  # noqa: BLE001
        log.warning("dramexchange failed: %s", exc)
        return []
    pts = []
    for ind in INDICATORS:
        if ind.category != "memory_spot" or ind.match not in rows:
            continue
        d, avg, chg = rows[ind.match]
        pts.append(Point(ind.indicator_id, d or today, avg, chg, None, {"row": ind.match}))
    log.info("dramexchange points: %d/%d", len(pts), sum(1 for i in INDICATORS if i.category == "memory_spot"))
    return pts


# ---------------------------------------------------------------------- FRED
def parse_fred_csv(text: str, keep: int = 30) -> list[tuple[date, float]]:
    rows = list(csv.reader(io.StringIO(text)))
    out = []
    for r in rows[1:]:
        if len(r) < 2:
            continue
        v = _num(r[1])
        try:
            d = date.fromisoformat(r[0])
        except ValueError:
            continue
        if v is not None:
            out.append((d, v))
    return out[-keep:]


def fetch_fred(http: HttpClient) -> list[Point]:
    """FRED 는 클라우드 IP 에서 응답 없이 끊기는 일이 잦다 — 재시도 없는 짧은 타임아웃 전용 클라이언트로 시도한다."""
    http = HttpClient(user_agent=BROWSER_UA["User-Agent"], timeout=15.0, max_retries=0)
    pts: list[Point] = []
    fails = 0
    for ind in INDICATORS:
        if ind.source != "FRED":
            continue
        if fails >= 2 and not pts:  # 호스트가 막혀 있으면 나머지는 시도하지 않는다
            log.warning("fred unreachable, skipping remaining series")
            break
        try:
            series = parse_fred_csv(http.get_text(FRED_CSV.format(sid=ind.match), headers=BROWSER_UA))
        except Exception as exc:  # noqa: BLE001
            fails += 1
            log.warning("fred %s failed: %s", ind.match, exc)
            continue
        by_date = dict(series)
        for i, (d, v) in enumerate(series):
            prev = series[i - 1][1] if i else None
            ly = by_date.get(date(d.year - 1, d.month, d.day))
            pts.append(Point(ind.indicator_id, d, v, round((v / prev - 1) * 100, 3) if prev else None, round((v / ly - 1) * 100, 3) if ly else None))
    http.close()
    log.info("fred points: %d", len(pts))
    return pts


def parse_bls(data: dict[str, Any]) -> list[Point]:
    pts: list[Point] = []
    for s in (data.get("Results") or {}).get("series") or []:
        sid = s.get("seriesID")
        rows = []
        for r in s.get("data") or []:
            per, v = r.get("period", ""), _num(r.get("value"))
            if per.startswith("M") and per != "M13" and v is not None:
                rows.append((date(int(r["year"]), int(per[1:]), 1), v))
        rows.sort()
        by = dict(rows)
        for i, (d, v) in enumerate(rows):
            prev = rows[i - 1][1] if i else None
            ly = by.get(date(d.year - 1, d.month, 1))
            pts.append(Point(f"bls:{sid}", d, v, round((v / prev - 1) * 100, 3) if prev else None, round((v / ly - 1) * 100, 3) if ly else None))
    return pts


def fetch_bls(http: HttpClient, today: date) -> list[Point]:
    ids = [i.match for i in INDICATORS if i.source == "BLS"]
    if not ids:
        return []
    try:
        data = http.post_json(BLS_API, {"seriesid": ids, "startyear": str(today.year - 2), "endyear": str(today.year)})
    except Exception as exc:  # noqa: BLE001
        log.warning("bls failed: %s", exc)
        return []
    if data.get("status") != "REQUEST_SUCCEEDED" or data.get("message"):
        log.warning("bls status %s: %s", data.get("status"), "; ".join(data.get("message") or [])[:300])
    pts = [p for p in parse_bls(data) if p.as_of >= date(today.year - 1, 1, 1)]
    log.info("bls points: %d (%d series)", len(pts), len({p.indicator_id for p in pts}))
    return pts


# ---------------------------------------------------------------------- 대만 월매출
def _roc_month(s: str) -> date | None:
    """'11509' (민국 115년 9월) → 2026-09-01."""
    s = (s or "").strip()
    if len(s) < 4:
        return None
    try:
        return date(int(s[:-2]) + 1911, int(s[-2:]), 1)
    except ValueError:
        return None


def parse_tw_revenue(rows: list[dict[str, Any]], codes: set[str]) -> list[Point]:
    pts = []
    for r in rows:
        code = str(r.get("公司代號", "")).strip()
        if code not in codes:
            continue
        d = _roc_month(str(r.get("資料年月", "")))
        v = _num(r.get("營業收入-當月營收"))
        if not d or v is None:
            continue
        pts.append(Point(f"tw:{code}", d, v, _num(r.get("營業收入-上月比較增減(%)")), _num(r.get("營業收入-去年同月增減(%)")),
                         {"name": r.get("公司名稱"), "ytd": _num(r.get("累計營業收入-當月累計營收")), "ytd_yoy": _num(r.get("累計營業收入-前期比較增減(%)")),
                          "note": (r.get("備註") or "").strip().strip("-") or None}))
    return pts


def fetch_tw(http: HttpClient) -> list[Point]:
    pts: list[Point] = []
    for market, url in (("TWSE", TWSE_REV), ("TPEx", TPEX_REV)):
        codes = {i.match for i in INDICATORS if i.category == "tw_revenue" and i.source == market}
        try:
            pts += parse_tw_revenue(http.get_json(url, headers=BROWSER_UA), codes)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s revenue failed: %s", market, exc)
    log.info("tw revenue points: %d/%d", len(pts), sum(1 for i in INDICATORS if i.category == "tw_revenue"))
    return pts


# ---------------------------------------------------------------------- 이슈 후보
def _pct(a: float | None, b: float | None) -> float | None:
    return round((a / b - 1) * 100, 2) if a is not None and b else None


def notable(points: list[Point], history: dict[str, list[tuple[date, float]]]) -> list[dict[str, Any]]:
    """임계치를 넘은 최신 변화 → 이슈 후보 dict (issues.Item 으로 바뀐다)."""
    latest: dict[str, Point] = {}
    for p in points:
        if p.indicator_id not in latest or p.as_of > latest[p.indicator_id].as_of:
            latest[p.indicator_id] = p
    out = []
    for iid, p in latest.items():
        ind = BY_ID.get(iid)
        if not ind:
            continue
        reasons = []
        if ind.category == "memory_spot":
            past = [v for d, v in history.get(iid, []) if d <= p.as_of - timedelta(days=6)]
            wk = _pct(p.value, past[-1]) if past else None
            if wk is not None and abs(wk) >= SPOT_WEEKLY:
                reasons.append(f"1주 {wk:+.1f}%")
            elif wk is None and p.change_pct is not None and abs(p.change_pct) >= SPOT_DAILY:
                reasons.append(f"일간 {p.change_pct:+.1f}%")
        elif ind.category == "tw_revenue":
            if p.yoy_pct is not None and (p.yoy_pct >= REV_YOY_HIGH or p.yoy_pct <= REV_YOY_LOW):
                reasons.append(f"YoY {p.yoy_pct:+.1f}%")
            if p.change_pct is not None and abs(p.change_pct) >= REV_MOM:
                reasons.append(f"MoM {p.change_pct:+.1f}%")
        else:
            if p.change_pct is not None and abs(p.change_pct) >= PPI_MOM:
                reasons.append(f"전월 {p.change_pct:+.1f}%")
            if p.yoy_pct is not None and abs(p.yoy_pct) >= PPI_YOY:
                reasons.append(f"전년 {p.yoy_pct:+.1f}%")
        if not reasons:
            continue
        period = p.as_of.strftime("%Y-%m") if ind.frequency == "monthly" else p.as_of.isoformat()
        value = f"{p.value:,.0f}" if ind.category == "tw_revenue" else f"{p.value:,.3f}".rstrip("0").rstrip(".")
        title = f"{ind.label} {period}: {value} {ind.unit} ({', '.join(reasons)})"
        snippet = f"{ind.note or ''} 출처 {ind.source}. 연결 노드: {', '.join(ind.nodes)}".strip()
        out.append({"indicator_id": iid, "title": title, "snippet": snippet, "url": f"{ind.source_url}#{iid}-{period}",
                    "as_of": p.as_of, "monthly": ind.frequency == "monthly", "publisher": ind.source, "ecosystem": ind.ecosystem,
                    "nodes": ind.nodes, "companies": ind.companies})
    return out


# ---------------------------------------------------------------------- 실행
def load_history(store, ids: list[str], since: date) -> dict[str, list[tuple[date, float]]]:
    hist: dict[str, list[tuple[date, float]]] = {}
    try:
        rows = store.select("ideas.indicator_points", ["indicator_id", "as_of", "value"], {"as_of": ("gte", since.isoformat())})
    except Exception as exc:  # noqa: BLE001 - 첫 실행·로컬 sqlite
        log.warning("indicator history unavailable: %s", exc)
        return hist
    for r in rows:
        if r["indicator_id"] in ids:
            hist.setdefault(r["indicator_id"], []).append((date.fromisoformat(str(r["as_of"])[:10]), float(r["value"])))
    for v in hist.values():
        v.sort()
    return hist


def run(http: HttpClient, store, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(UTC).date()
    points = fetch_dramexchange(http, today) + fetch_bls(http, today) + fetch_fred(http) + fetch_tw(http)
    history = load_history(store, [i.indicator_id for i in INDICATORS], today - timedelta(days=60)) if store else {}
    for p in points:  # 이번 수집분도 이력에 (FRED 처럼 한 번에 여러 점이 오는 경우)
        history.setdefault(p.indicator_id, []).append((p.as_of, p.value))
    for v in history.values():
        v.sort()
    return {"as_of": today.isoformat(), "points": points, "notable": notable(points, history),
            "stats": {"points": len(points), "indicators": len({p.indicator_id for p in points})}}


def save(store, points: list[Point]) -> int:
    store.upsert("ideas.indicators", [i.row() | {"updated_at": datetime.now(UTC).isoformat()} for i in INDICATORS], ["indicator_id"])
    uniq = {(p.indicator_id, p.as_of): p.row() for p in points}
    return store.upsert("ideas.indicator_points", list(uniq.values()), ["indicator_id", "as_of"]) if uniq else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    from wsj.config import load_settings
    from wsj.db import make_store

    settings = load_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = None if args.no_save else make_store(settings)
    http = HttpClient(user_agent=settings.sec_user_agent)
    try:
        res = run(http, store)
        if store:
            log.info("saved %d points", save(store, res["points"]))
    finally:
        http.close()
        if store:
            store.close()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({**res, "points": [p.row() for p in res["points"]]}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res["stats"], ensure_ascii=False))
    for n in res["notable"]:
        print("  *", n["title"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
