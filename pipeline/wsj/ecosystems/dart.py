"""OpenDART — 그래프의 한국 상장사 재무(TTM·FY)와 최근 공시.

    python -m wsj.ecosystems.dart run [--days 14] [--only company:a,company:b] [--no-financials] [--no-disclosures] [--dry-run]
    python -m wsj.ecosystems.dart probe        # 한 종목으로 키·엔드포인트 확인 (저장하지 않는다)

DART_API_KEY 가 없으면 아무것도 하지 않고 끝난다 (exit 0). 대상은 그래프의 기업 노드 중 거래소가 KRX·KOSDAQ 인 상장사 (후보 포함).

- 종목코드 → 고유번호: corpCode.xml (zip 안의 XML).
- 재무: fnlttSinglAcntAll (전체 재무제표 — 연결 CFS, 없으면 별도 OFS). 최신 정기보고서를 3분기 → 반기 → 1분기 → 사업보고서 순으로 찾고,
  그 전 사업보고서를 함께 읽는다. 손익·현금흐름의 TTM = 올해 누적 + 직전 연도 − 전년 같은 기간 누적, 현금·총차입은 최신 보고서 기말.
  유통 보통주식수는 stockTotqySttus (주식의 총수 현황). → raw.company_fundamentals (미국 SEC 와 같은 모양: period ttm·fy, 통화 KRW,
  source opendart_fnltt). fundamentals 수집기(네이버 분기 표)는 OpenDART 가 넣은 같은 기간의 TTM 을 덮지 않는다.
- 공시: list.json 최근 N일 → ideas.clues (source_id opendart, source_kind disclosure, 층 disclosure). 지분·주총 같은 정형 공시는
  기업 소식(company_feed)과 같은 규칙으로 버리고, 이미 있는 URL 은 건너뛴다.

보고서 기간은 12월 결산을 가정한다 (1분기 3/31 · 반기 6/30 · 3분기 9/30 · 사업 12/31). 금액은 원 단위 그대로, capex(유형자산의 취득)는 양수.
총차입 = 단기차입금 + 유동성장기차입금·사채 + 장기차입금 + 사채 (리스부채 제외) — 미국 debt_st + debt_lt 와 맞춘다.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import zipfile
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET

from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger("wsj.ecosystems.dart")

HOST_RPS.setdefault("opendart.fss.or.kr", 5.0)
DART = "https://opendart.fss.or.kr/api"
CORPCODE_URL = f"{DART}/corpCode.xml"
LIST_URL = f"{DART}/list.json"
FNLTT_URL = f"{DART}/fnlttSinglAcntAll.json"
SHARES_URL = f"{DART}/stockTotqySttus.json"
VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
KST = timezone(timedelta(hours=9))
KR_EX = ("KRX", "KOSDAQ", "KOSPI")
SOURCE = "opendart_fnltt"

# 기말 월 → 정기보고서 코드 (12월 결산)
REPORT_CODE = {3: "11013", 6: "11012", 9: "11014", 12: "11011"}
REPORT_KO = {"11013": "1분기보고서", "11012": "반기보고서", "11014": "3분기보고서", "11011": "사업보고서"}
# 이 상태면 키·한도 문제라 다른 기업도 실패한다 → 실행을 멈춘다
FATAL = {"010": "등록되지 않은 키", "011": "사용할 수 없는 키", "012": "접근할 수 없는 IP", "020": "요청 한도 초과", "901": "기간이 지난 키"}

IS_DIVS = ("IS", "CIS")
# 개념 → (재무제표 구분, account_id 별칭, 계정명 별칭(공백 제거)) — 앞에 있는 것이 우선
ACCOUNTS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = {
    "revenue": (IS_DIVS, ("ifrs-full_Revenue", "ifrs_Revenue"), ("매출액", "수익(매출액)", "영업수익", "매출")),
    "gross_profit": (IS_DIVS, ("ifrs-full_GrossProfit", "ifrs_GrossProfit"), ("매출총이익", "매출총이익(손실)")),
    "operating_income": (IS_DIVS, ("dart_OperatingIncomeLoss",), ("영업이익", "영업이익(손실)", "영업손익")),
    # 미국 NetIncomeLoss(지배주주) 와 맞춘다 — 없으면 연결 당기순이익
    "net_income": (IS_DIVS, ("ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs_ProfitLossAttributableToOwnersOfParent",
                             "ifrs-full_ProfitLoss", "ifrs_ProfitLoss"),
                   ("지배기업의소유주에게귀속되는당기순이익", "당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익")),
    "operating_cash_flow": (("CF",), ("ifrs-full_CashFlowsFromUsedInOperatingActivities", "ifrs_CashFlowsFromUsedInOperatingActivities"),
                            ("영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동으로부터의현금흐름")),
    "capex": (("CF",), ("ifrs-full_PurchaseOfPropertyPlantAndEquipment", "ifrs_PurchaseOfPropertyPlantAndEquipment"),
              ("유형자산의취득", "유형자산취득")),
    "cash": (("BS",), ("ifrs-full_CashAndCashEquivalents", "ifrs_CashAndCashEquivalents"), ("현금및현금성자산",)),
}
FLOW = ("revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "capex")
DEBT_IDS = {"ifrs-full_ShortTermBorrowings", "ifrs_ShortTermBorrowings", "dart_ShortTermBorrowings",
            "ifrs-full_CurrentPortionOfLongtermBorrowings", "ifrs_CurrentPortionOfLongtermBorrowings",
            "dart_CurrentPortionOfLongTermBorrowings", "dart_CurrentPortionOfBonds", "ifrs-full_CurrentPortionOfBondsIssued",
            "ifrs-full_LongtermBorrowings", "ifrs_LongtermBorrowings", "dart_LongTermBorrowingsGross",
            "ifrs-full_BondsIssued", "ifrs_BondsIssued", "dart_BondsIssued"}
DEBT_NAMES = {"단기차입금", "유동성장기차입금", "유동성장기부채", "유동성사채", "장기차입금", "사채", "단기사채"}


class DartError(RuntimeError):
    def __init__(self, status: str, message: str = "") -> None:
        super().__init__(f"OpenDART {status}: {message}")
        self.status = status


def _num(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "N/A"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        x = float(s.strip("()"))
    except ValueError:
        return None
    return -x if neg else x


def _norm(name: str | None) -> str:
    return re.sub(r"\s+|\(주\d*\)|\[주석?\d*\]", "", name or "")


# ---------------------------------------------------------------- 고유번호
def parse_corp_codes(zip_bytes: bytes) -> dict[str, str]:
    """corpCode.xml(zip) → 종목코드(6자리) → 고유번호(8자리). 상장사만 (stock_code 가 있는 것)."""
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    root = ET.fromstring(zf.read(zf.namelist()[0]))
    out = {}
    for e in root.iter("list"):
        code = (e.findtext("stock_code") or "").strip()
        cc = (e.findtext("corp_code") or "").strip()
        if code and cc:
            out[code.zfill(6)] = cc
    return out


def load_corp_codes(http: HttpClient, key: str) -> dict[str, str]:
    """키가 틀리면 OpenDART 는 zip 대신 상태 코드(XML·JSON)를 돌려준다 → DartError."""
    resp = http.request("GET", CORPCODE_URL, params={"crtfc_key": key})
    try:
        return parse_corp_codes(resp.content)
    except zipfile.BadZipFile:
        text = resp.content[:2000].decode("utf-8", "replace")
        st = re.search(r'<status>(\d+)</status>|"status"\s*:\s*"(\d+)"', text)
        msg = re.search(r"<message>([^<]*)</message>|\"message\"\s*:\s*\"([^\"]*)\"", text)
        raise DartError(next((g for g in (st.groups() if st else ()) if g), f"http {resp.status_code}"),
                        next((g for g in (msg.groups() if msg else ()) if g), "corpCode.xml 이 zip 이 아니다")) from None


def _check(d: dict[str, Any]) -> bool:
    """status 000 = 자료 있음, 013 = 없음 → False. 키·한도 문제는 DartError (실행을 멈춘다), 나머지도 DartError."""
    st = str(d.get("status") or "")
    if st == "000":
        return True
    if st == "013":
        return False
    raise DartError(st, str(d.get("message") or FATAL.get(st, "")))


# ---------------------------------------------------------------- 대상 기업
def kr_companies(graph: dict[str, Any], only: set[str] | None = None) -> list[dict[str, Any]]:
    from wsj.ecosystems.company_feed import listed_companies

    out = []
    for c in listed_companies(graph):
        tk = (c.get("ticker") or "").strip()
        if c["exchange"] in KR_EX and tk.isdigit() and (not only or c["id"] in only):
            out.append({**c, "ticker": tk.zfill(6)})
    return out


# ---------------------------------------------------------------- 재무
def report_candidates(today: date, n: int = 5) -> list[tuple[int, str, date]]:
    """오늘 이전에 끝난 분기부터 거꾸로 n 개: (사업연도, 보고서 코드, 기말)."""
    y, q = today.year, (today.month - 1) // 3 * 3
    if q == 0:
        y, q = y - 1, 12
    out = []
    while len(out) < n:
        out.append((y, REPORT_CODE[q], date(y, q, monthrange(y, q)[1])))
        q -= 3
        if q == 0:
            y, q = y - 1, 12
    return out


def fetch_statements(http: HttpClient, key: str, corp_code: str, year: int, reprt_code: str) -> tuple[list[dict[str, Any]], str] | None:
    """(전체 재무제표 행, 'CFS'|'OFS'). 연결이 없으면 별도. 둘 다 없으면 None."""
    for fs in ("CFS", "OFS"):
        d = http.get_json(FNLTT_URL, params={"crtfc_key": key, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs})
        if _check(d) and d.get("list"):
            return d["list"], fs
    return None


def _pick(rows: list[dict[str, Any]], concept: str) -> dict[str, Any] | None:
    divs, ids, names = ACCOUNTS[concept]
    for div in divs:
        part = [r for r in rows if r.get("sj_div") == div]
        for aid in ids:
            hit = next((r for r in part if r.get("account_id") == aid), None)
            if hit:
                return hit
        for nm in names:
            hit = next((r for r in part if _norm(r.get("account_nm")) == nm), None)
            if hit:
                return hit
    return None


def _first(r: dict[str, Any], fields: tuple[str, ...]) -> float | None:
    for f in fields:
        v = _num(r.get(f))
        if v is not None:
            return v
    return None


def _flow_fields(concept: str, reprt_code: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(올해 누적 칸, 전년 같은 기간 누적 칸). 손익계산서의 반기·3분기는 thstrm_amount 가 3개월이라 누적(add) 칸만 믿는다.
    현금흐름표는 분기에도 누적을 thstrm_amount 에 낸다."""
    if ACCOUNTS[concept][0] == IS_DIVS and reprt_code in ("11012", "11014"):
        return ("thstrm_add_amount",), ("frmtrm_add_amount",)
    if ACCOUNTS[concept][0] == IS_DIVS:
        return ("thstrm_add_amount", "thstrm_amount"), ("frmtrm_add_amount", "frmtrm_q_amount", "frmtrm_amount")
    return ("thstrm_add_amount", "thstrm_amount"), ("frmtrm_add_amount", "frmtrm_amount")


def parse_statements(rows: list[dict[str, Any]], reprt_code: str) -> dict[str, Any]:
    """전체 재무제표 행 → {ytd: {개념: 올해 누적}, prior_ytd: {...}, cash, total_debt, rcept_no}.
    사업보고서(11011)면 ytd = 그 회계연도, prior_ytd = 전년도."""
    ytd: dict[str, float | None] = {}
    prior: dict[str, float | None] = {}
    for c in FLOW:
        r = _pick(rows, c)
        if r is None:
            ytd[c] = prior[c] = None
            continue
        if reprt_code == "11011":
            ytd[c], prior[c] = _num(r.get("thstrm_amount")), _num(r.get("frmtrm_amount"))
        else:
            now_f, prev_f = _flow_fields(c, reprt_code)
            ytd[c], prior[c] = _first(r, now_f), _first(r, prev_f)
    cash_r = _pick(rows, "cash")
    seen: set[str] = set()
    debt = None
    for r in rows:
        if r.get("sj_div") != "BS":
            continue
        k = r.get("account_id") if r.get("account_id") in DEBT_IDS else (_norm(r.get("account_nm")) if _norm(r.get("account_nm")) in DEBT_NAMES else None)
        if not k:
            continue
        nm = _norm(r.get("account_nm"))
        if k in seen or nm in seen:
            continue
        seen |= {k, nm}
        v = _num(r.get("thstrm_amount"))
        if v is not None:
            debt = (debt or 0.0) + v
    return {"ytd": ytd, "prior_ytd": prior, "cash": _num(cash_r.get("thstrm_amount")) if cash_r else None, "total_debt": debt,
            "rcept_no": next((r.get("rcept_no") for r in rows if r.get("rcept_no")), None)}


def parse_shares(d: dict[str, Any]) -> float | None:
    """stockTotqySttus → 보통주 유통주식수 (없으면 발행주식 − 자기주식)."""
    for r in d.get("list") or []:
        if "보통" in str(r.get("se") or ""):
            v = _num(r.get("distb_stock_co"))
            if v is None:
                iss, tre = _num(r.get("istc_totqy")), _num(r.get("tesstk_co"))
                v = iss - (tre or 0.0) if iss is not None else None
            return v
    return None


def _capex(v: float | None) -> float | None:
    return abs(v) if v is not None else None


def financial_rows(cid: str, latest: dict[str, Any], latest_code: str, latest_end: date, fs: str,
                   annual_prev: dict[str, Any] | None, shares: float | None) -> list[dict[str, Any]]:
    """최신 정기보고서(+ 직전 사업보고서) → raw.company_fundamentals 행 (ttm, fy). 손익·현금흐름이 하나라도 비면 그 칸은 None."""
    now = datetime.now(UTC).isoformat()
    basis = "연결" if fs == "CFS" else "별도"

    def row(period: str, end: date, vals: dict[str, float | None], rep: dict[str, Any], note: str, sh: float | None) -> dict[str, Any]:
        return {"company_id": cid, "period": period, "period_end": end.isoformat(), "currency": "KRW", "source": SOURCE,
                "source_url": VIEWER.format(rcept_no=rep["rcept_no"]) if rep.get("rcept_no") else None, "note": note,
                "revenue": vals.get("revenue"), "gross_profit": vals.get("gross_profit"), "operating_income": vals.get("operating_income"),
                "net_income": vals.get("net_income"), "operating_cash_flow": vals.get("operating_cash_flow"), "capex": _capex(vals.get("capex")),
                "cash": rep.get("cash"), "total_debt": rep.get("total_debt"), "diluted_shares": None, "shares_outstanding": sh, "fetched_at": now}

    out = []
    if latest_code == "11011":
        out.append(row("fy", latest_end, latest["ytd"], latest, f"OpenDART 사업보고서 {latest_end.year} ({basis})", shares))
        out.append(row("ttm", latest_end, latest["ytd"], latest, f"TTM = 사업보고서 {latest_end.year} ({basis})", shares))
        return out
    if annual_prev is not None:
        fy_end = date(latest_end.year - 1, 12, 31)
        out.append(row("fy", fy_end, annual_prev["ytd"], annual_prev, f"OpenDART 사업보고서 {fy_end.year} ({basis})", None))
        ttm: dict[str, float | None] = {}
        for c in FLOW:
            a, fy, p = latest["ytd"].get(c), annual_prev["ytd"].get(c), latest["prior_ytd"].get(c)
            if c == "capex" and None not in (a, fy, p):
                a, fy, p = abs(a), abs(fy), abs(p)
            ttm[c] = a + fy - p if None not in (a, fy, p) else None
        out.append(row("ttm", latest_end, ttm, latest,
                       f"TTM = {latest_end.year} {REPORT_KO[latest_code]} 누적 + {fy_end.year} 사업보고서 − 전년 같은 기간 누적 ({basis})", shares))
    return out


def fetch_financials(http: HttpClient, key: str, cid: str, corp_code: str, today: date) -> list[dict[str, Any]]:
    for year, code, end in report_candidates(today):
        got = fetch_statements(http, key, corp_code, year, code)
        if not got:
            continue
        rows, fs = got
        latest = parse_statements(rows, code)
        annual_prev = None
        if code != "11011":
            prev = fetch_statements(http, key, corp_code, year - 1, "11011")
            if prev:
                # 연결·별도가 갈리면 TTM 을 섞지 않는다
                annual_prev = parse_statements(prev[0], "11011") if prev[1] == fs else None
        shares = None
        try:
            d = http.get_json(SHARES_URL, params={"crtfc_key": key, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": code})
            shares = parse_shares(d) if _check(d) else None
        except DartError as exc:
            if exc.status in FATAL:
                raise
        return financial_rows(cid, latest, code, end, fs, annual_prev, shares)
    return []


# ---------------------------------------------------------------- 공시 → 단서
def disclosure_clues(rows: list[dict[str, Any]], c: dict[str, Any]) -> list[Any]:
    """list.json 의 공시 → Clue (정형 공시는 버린다 — company_feed 와 같은 규칙)."""
    from wsj.ecosystems.clues import Clue
    from wsj.ecosystems.company_feed import DART_SKIP, DART_UP2, DART_UP3

    out = []
    for r in rows:
        name = re.sub(r"\s+", " ", r.get("report_nm") or "").strip()
        if not name or not r.get("rcept_no") or any(w in name for w in DART_SKIP):
            continue
        try:
            pub = datetime.strptime(str(r.get("rcept_dt")), "%Y%m%d").replace(tzinfo=KST)
        except ValueError:
            pub = None
        imp = 3 if any(w in name for w in DART_UP3) else 2 if any(w in name for w in DART_UP2) else 1
        cl = Clue(VIEWER.format(rcept_no=r["rcept_no"]), f"{c.get('native') or c['name']} 공시: {name}", "", pub, "opendart", "DART 전자공시",
                  "disclosure", "ko", "kr", [{"company": c["id"], "name": c.get("native") or c["name"], "ticker": c["ticker"], "exchange": c["exchange"]}])
        cl.extra = {"rcept_no": r["rcept_no"], "corp_code": r.get("corp_code"), "report_nm": name, "flr_nm": r.get("flr_nm"),
                    "rm": r.get("rm") or None, "importance": imp, "publisher": "DART 전자공시", "kind": "disclosure"}
        cl.layer, cl.screen = "disclosure", "kept"
        out.append(cl)
    return out


def fetch_disclosures(http: HttpClient, key: str, corp_code: str, since: date, until: date) -> list[dict[str, Any]]:
    d = http.get_json(LIST_URL, params={"crtfc_key": key, "corp_code": corp_code, "bgn_de": f"{since:%Y%m%d}", "end_de": f"{until:%Y%m%d}",
                                        "page_count": "100"})
    if not _check(d):
        return []
    return d.get("list") or []


# ---------------------------------------------------------------- 실행
def run(http: HttpClient, store: Any | None, graph: dict[str, Any], key: str, days: int = 14, only: set[str] | None = None,
        financials: bool = True, disclosures: bool = True, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(KST).date()
    cos = kr_companies(graph, only)
    stats: dict[str, Any] = {"companies": len(cos), "mapped": 0, "financials": {"ok": 0, "empty": 0, "error": 0}, "disclosures": {"seen": 0, "new": 0}}
    corp = load_corp_codes(http, key)
    fin_rows: list[dict[str, Any]] = []
    clues: list[Any] = []
    for c in cos:
        cc = corp.get(c["ticker"])
        if not cc:
            continue
        stats["mapped"] += 1
        if financials:
            try:
                got = fetch_financials(http, key, c["id"], cc, today)
                fin_rows += got
                stats["financials"]["ok" if got else "empty"] += 1
            except DartError as exc:
                if exc.status in FATAL:
                    raise
                stats["financials"]["error"] += 1
                log.warning("dart financials %s: %s", c["id"], exc)
            except Exception as exc:  # noqa: BLE001 - 한 기업 실패가 나머지를 막지 않게
                stats["financials"]["error"] += 1
                log.warning("dart financials %s: %s", c["id"], str(exc)[:160])
        if disclosures:
            try:
                clues += disclosure_clues(fetch_disclosures(http, key, cc, today - timedelta(days=days), today), c)
            except DartError as exc:
                if exc.status in FATAL:
                    raise
                log.warning("dart list %s: %s", c["id"], exc)
            except Exception as exc:  # noqa: BLE001
                log.warning("dart list %s: %s", c["id"], str(exc)[:160])
    stats["disclosures"]["seen"] = len(clues)
    stats["fundamental_rows"] = len(fin_rows)
    if store is None:
        stats["rows"] = fin_rows
        stats["clues"] = [cl.row() for cl in clues]
        return stats
    if fin_rows:
        from wsj.ecosystems.fundamentals import save_rows

        save_rows(store, fin_rows)
    if clues:
        from wsj.ecosystems.clues import already_seen, tag

        seen = already_seen(store, [cl.url for cl in clues])
        new = list({cl.url: cl for cl in clues if cl.url not in seen}.values())
        tag(new, graph)
        if new:
            store.upsert("ideas.clues", [cl.row() for cl in new], ["url"])
        stats["disclosures"]["new"] = len(new)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "probe"])
    ap.add_argument("--days", type=int, default=14, help="공시 목록을 볼 최근 일수")
    ap.add_argument("--only", help="기업 id 쉼표 목록 (company:a,company:b)")
    ap.add_argument("--no-financials", action="store_true")
    ap.add_argument("--no-disclosures", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 쓰지 않고 결과를 출력")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.config import load_settings
    from wsj.ecosystems.ontology import load_graph

    settings = load_settings()
    key = settings.dart_api_key.strip()
    if not key:
        print(json.dumps({"skipped": "DART_API_KEY 없음"}, ensure_ascii=False))
        return 0
    graph = load_graph()
    http = HttpClient("WSJ-investment research (OpenDART)", timeout=40, max_retries=1)
    only = set(args.only.split(",")) if args.only else None
    try:
        if args.cmd == "probe":
            cos = kr_companies(graph, only)[:1]
            res = run(http, None, graph, key, days=7, only={cos[0]["id"]} if cos else None)
            res["rows"] = res.get("rows", [])[:2]
            res["clues"] = res.get("clues", [])[:3]
            print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
            return 0
        if args.dry_run:
            res = run(http, None, graph, key, args.days, only, not args.no_financials, not args.no_disclosures)
            print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
            return 0
        from wsj.db import make_store
        from wsj.runlog import logged_run

        store = make_store(settings)
        try:
            with logged_run(store, "dart", {"days": args.days, "only": args.only}) as lr:
                res = run(http, store, graph, key, args.days, only, not args.no_financials, not args.no_disclosures)
                lr["rows"] = res["fundamental_rows"] + res["disclosures"]["new"]
                lr["notes"] = json.dumps(res, ensure_ascii=False)[:1500]
            print(json.dumps(res, ensure_ascii=False))
        finally:
            store.close()
    finally:
        http.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
