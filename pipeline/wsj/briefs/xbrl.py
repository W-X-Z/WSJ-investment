"""companyfacts (XBRL) → 분기 시계열과 파생 지표. ADR-0009 §2 "매출·사업구조 변화".

companyfacts 는 회사가 쓴 태그 그대로다. 회사마다 매출 태그가 다르므로 (Revenues vs
RevenueFromContractWithCustomerExcludingAssessedTax ...) 개념별 별칭 목록을 두고 합친다.
기간(duration) 값은 분기(75~105일)만 쓰고, Q4 는 연간 − (9M YTD 또는 3분기 합) 으로 만든다.
시점(instant) 값은 기말 기준. 같은 기간이 여러 공시에 나오면 가장 늦게 제출된 값(정정 반영)을 쓴다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from wsj.http import HttpClient
from wsj.util import parse_date

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# 개념 → (태그 별칭, 단위, duration|instant)
CONCEPTS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "revenue": (
        (
            "us-gaap:Revenues",
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
            "us-gaap:SalesRevenueNet",
            "us-gaap:SalesRevenueGoodsNet",
            "us-gaap:RevenuesNetOfInterestExpense",
            "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
        ),
        "USD",
        "duration",
    ),
    "gross_profit": (("us-gaap:GrossProfit",), "USD", "duration"),
    "rnd": (
        (
            "us-gaap:ResearchAndDevelopmentExpense",
            "us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
        ),
        "USD",
        "duration",
    ),
    "sga": (
        ("us-gaap:SellingGeneralAndAdministrativeExpense", "us-gaap:GeneralAndAdministrativeExpense"),
        "USD",
        "duration",
    ),
    "op_income": (("us-gaap:OperatingIncomeLoss",), "USD", "duration"),
    "net_income": (
        (
            "us-gaap:NetIncomeLoss",
            "us-gaap:ProfitLoss",
            "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic",
        ),
        "USD",
        "duration",
    ),
    "ocf": (
        (
            "us-gaap:NetCashProvidedByUsedInOperatingActivities",
            "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        "USD",
        "duration",
    ),
    "capex": (("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",), "USD", "duration"),
    "sbc": (
        ("us-gaap:ShareBasedCompensation", "us-gaap:AllocatedShareBasedCompensationExpense"),
        "USD",
        "duration",
    ),
    "cash": (
        (
            "us-gaap:CashAndCashEquivalentsAtCarryingValue",
            "us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
            "us-gaap:Cash",
        ),
        "USD",
        "instant",
    ),
    "st_investments": (
        (
            "us-gaap:ShortTermInvestments",
            "us-gaap:MarketableSecuritiesCurrent",
            "us-gaap:AvailableForSaleSecuritiesDebtSecuritiesCurrent",
            "us-gaap:CashCashEquivalentsAndShortTermInvestments",
        ),
        "USD",
        "instant",
    ),
    "total_assets": (("us-gaap:Assets",), "USD", "instant"),
    "equity": (
        (
            "us-gaap:StockholdersEquity",
            "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "USD",
        "instant",
    ),
    "debt_lt": (
        (
            "us-gaap:LongTermDebtNoncurrent",
            "us-gaap:LongTermDebt",
            "us-gaap:LongTermDebtAndCapitalLeaseObligations",
            "us-gaap:ConvertibleNotesPayableNoncurrent",
            "us-gaap:LongTermNotesPayable",
        ),
        "USD",
        "instant",
    ),
    "debt_st": (
        ("us-gaap:LongTermDebtCurrent", "us-gaap:DebtCurrent", "us-gaap:ShortTermBorrowings"),
        "USD",
        "instant",
    ),
    "deferred_revenue": (
        ("us-gaap:ContractWithCustomerLiabilityCurrent", "us-gaap:DeferredRevenueCurrent"),
        "USD",
        "instant",
    ),
    "shares_out": (
        ("dei:EntityCommonStockSharesOutstanding", "us-gaap:CommonStockSharesOutstanding"),
        "shares",
        "instant",
    ),
    "diluted_shares": (("us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",), "shares", "duration"),
    "eps_diluted": (("us-gaap:EarningsPerShareDiluted",), "USD/shares", "duration"),
}


NON_ADDITIVE = {"eps_diluted", "diluted_shares"}  # YTD 차분이 의미 없는 개념
INSTANT_TOLERANCE_DAYS = {"shares_out": 50}  # dei 주식수는 표지 날짜(분기말 +30~45일) 기준


@dataclass
class Fact:
    start: date | None
    end: date
    val: float
    filed: date
    form: str
    fy: int | None
    fp: str | None
    tag: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days if self.start else 0


def load_companyfacts(http: HttpClient, cik: int) -> dict[str, Any] | None:
    return http.get_json_or_none(COMPANYFACTS_URL.format(cik=cik))


def _facts(cf: dict[str, Any], tags: tuple[str, ...], unit: str) -> list[Fact]:
    facts_root = cf.get("facts", {})
    out: list[Fact] = []
    for tag in tags:
        ns, name = tag.split(":", 1)
        node = facts_root.get(ns, {}).get(name)
        if not node:
            continue
        units = node.get("units", {})
        arr = units.get(unit) or []
        for f in arr:
            end = parse_date(f.get("end"))
            filed = parse_date(f.get("filed"))
            if end is None or filed is None or f.get("val") is None:
                continue
            out.append(
                Fact(
                    start=parse_date(f.get("start")),
                    end=end,
                    val=float(f["val"]),
                    filed=filed,
                    form=f.get("form", ""),
                    fy=f.get("fy"),
                    fp=f.get("fp"),
                    tag=tag,
                )
            )
    return out


def _dedupe_latest(facts: list[Fact]) -> dict[tuple[date | None, date], Fact]:
    best: dict[tuple[date | None, date], Fact] = {}
    for f in facts:
        k = (f.start, f.end)
        if k not in best or f.filed > best[k].filed:
            best[k] = f
    return best


def quarterly_series(facts: list[Fact], additive: bool = True) -> dict[date, float]:
    """기간 값 → 분기말 → 값.

    직접 보고된 3개월 값을 우선 쓰고, 없는 분기는 같은 회계연도 시작일을 공유하는 YTD 값의 차분으로 만든다
    (현금흐름표는 10-Q 에서 YTD 만 보고하는 회사가 대부분): Q2 = 6M−3M, Q3 = 9M−6M, Q4 = 12M−9M.
    9M 이 없으면 Q4 = 연간 − 3분기 합. additive=False (EPS·가중평균주식수) 는 차분하지 않는다.
    """
    by_period = _dedupe_latest(facts)
    quarters: dict[date, float] = {}
    # 회계연도 시작일 → {누적 개월 버킷(3/6/9/12): (end, val)}
    ytd: dict[date, dict[int, tuple[date, float]]] = defaultdict(dict)
    for (start, end), f in by_period.items():
        if start is None:
            continue
        d = f.days
        if 75 <= d <= 105:
            quarters[end] = f.val
            ytd[start][3] = (end, f.val)
        elif 165 <= d <= 200:
            ytd[start][6] = (end, f.val)
        elif 255 <= d <= 290:
            ytd[start][9] = (end, f.val)
        elif 350 <= d <= 380:
            ytd[start][12] = (end, f.val)
    if not additive:
        return quarters
    for start, buckets in ytd.items():
        for months in (6, 9, 12):
            if months not in buckets:
                continue
            end, val = buckets[months]
            if end in quarters:
                continue
            prev = months - 3
            if prev in buckets:
                quarters[end] = val - buckets[prev][1]
                continue
            inside = [v for e, v in quarters.items() if start <= e < end]
            if len(inside) == months // 3 - 1:
                quarters[end] = val - sum(inside)
    return quarters


def annual_series(facts: list[Fact]) -> dict[date, float]:
    by_period = _dedupe_latest(facts)
    return {end: f.val for (start, end), f in by_period.items() if start and 350 <= f.days <= 380}


def instant_series(facts: list[Fact]) -> dict[date, float]:
    by_period = _dedupe_latest(facts)
    return {end: f.val for (_, end), f in by_period.items()}


def _nearest(series: dict[date, float], target: date, tol_days: int = 20) -> float | None:
    best = None
    for d, v in series.items():
        gap = abs((d - target).days)
        if gap <= tol_days and (best is None or gap < best[0]):
            best = (gap, v)
    return best[1] if best else None


def build_financials(cf: dict[str, Any], n_quarters: int = 12) -> dict[str, Any]:
    """분기 표 + 연간 표 + 파생 지표. 값이 없는 칸은 None 으로 남긴다 (프롬프트가 '없음' 으로 읽는다)."""
    q_series: dict[str, dict[date, float]] = {}
    a_series: dict[str, dict[date, float]] = {}
    i_series: dict[str, dict[date, float]] = {}
    tags_used: dict[str, str] = {}
    for concept, (tags, unit, kind) in CONCEPTS.items():
        facts = _facts(cf, tags, unit)
        if not facts:
            continue
        # 가장 최근 end 를 가진 태그를 대표로 기록
        tags_used[concept] = max(facts, key=lambda f: f.end).tag
        if kind == "duration":
            q_series[concept] = quarterly_series(facts, additive=concept not in NON_ADDITIVE)
            a_series[concept] = annual_series(facts)
        else:
            i_series[concept] = instant_series(facts)

    # 분기말 축: 매출·순이익·OCF 중 하나라도 있는 분기말
    ends: set[date] = set()
    for c in ("revenue", "net_income", "ocf", "op_income", "rnd"):
        ends |= set(q_series.get(c, {}).keys())
    period_ends = sorted(ends)[-n_quarters:]
    rows: list[dict[str, Any]] = []
    for end in period_ends:
        row: dict[str, Any] = {"period_end": end.isoformat()}
        for c in q_series:
            row[c] = q_series[c].get(end)
        for c in i_series:
            row[c] = _nearest(i_series[c], end, INSTANT_TOLERANCE_DAYS.get(c, 20))
        rows.append(row)

    # 연간 (최근 5년)
    a_ends: set[date] = set()
    for c in ("revenue", "net_income", "ocf"):
        a_ends |= set(a_series.get(c, {}).keys())
    annual_rows: list[dict[str, Any]] = []
    for end in sorted(a_ends)[-6:]:
        row = {"fiscal_year_end": end.isoformat()}
        for c in a_series:
            row[c] = a_series[c].get(end)
        for c in i_series:
            row[c] = _nearest(i_series[c], end, INSTANT_TOLERANCE_DAYS.get(c, 20))
        annual_rows.append(row)

    derived = _derive(rows, i_series)
    latest_shares = _latest(i_series.get("shares_out", {}))
    return {
        "quarters": rows,
        "annual": annual_rows,
        "derived": derived,
        "shares_outstanding": latest_shares,
        "tags_used": tags_used,
    }


def _latest(series: dict[date, float]) -> dict[str, Any] | None:
    if not series:
        return None
    d = max(series)
    return {"as_of": d.isoformat(), "value": series[d]}


def _sum_last(rows: list[dict], key: str, n: int, min_present: int | None = None) -> float | None:
    """마지막 n 분기 합. min_present 를 주면 그만큼만 있어도 합산한다 (매출 0 을 보고 안 하는 초기 기업용)."""
    vals = [r.get(key) for r in rows[-n:]]
    if len(vals) < n:
        return None
    present = [v for v in vals if v is not None]
    need = n if min_present is None else min_present
    if len(present) < need:
        return None
    return float(sum(present))


def _derive(rows: list[dict[str, Any]], inst: dict[str, dict[date, float]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    if not rows:
        return d
    last = rows[-1]
    d["latest_period_end"] = last["period_end"]
    ttm_rev = _sum_last(rows, "revenue", 4, min_present=3)
    d["ttm_revenue_quarters_reported"] = sum(1 for r in rows[-4:] if r.get("revenue") is not None)
    prev_ttm_rev = _sum_last(rows[:-4], "revenue", 4, min_present=3) if len(rows) >= 8 else None
    d["ttm_revenue"] = ttm_rev
    d["ttm_revenue_yoy"] = (ttm_rev / prev_ttm_rev - 1) if ttm_rev is not None and prev_ttm_rev else None
    if last.get("revenue") is not None and len(rows) >= 5 and rows[-5].get("revenue"):
        d["latest_quarter_revenue_yoy"] = last["revenue"] / rows[-5]["revenue"] - 1
    d["ttm_net_income"] = _sum_last(rows, "net_income", 4)
    d["ttm_ocf"] = _sum_last(rows, "ocf", 4)
    d["ttm_rnd"] = _sum_last(rows, "rnd", 4)
    d["ttm_sbc"] = _sum_last(rows, "sbc", 4)
    gp = _sum_last(rows, "gross_profit", 4)
    d["ttm_gross_margin"] = (gp / ttm_rev) if gp is not None and ttm_rev else None
    cash = last.get("cash") or 0.0
    sti = last.get("st_investments") or 0.0
    liquidity = (
        cash + sti if (last.get("cash") is not None or last.get("st_investments") is not None) else None
    )
    d["liquidity_cash_and_st_investments"] = liquidity
    d["debt_total"] = (
        (last.get("debt_lt") or 0.0) + (last.get("debt_st") or 0.0)
        if (last.get("debt_lt") is not None or last.get("debt_st") is not None)
        else None
    )
    ocf = d["ttm_ocf"]
    if ocf is not None and ocf < 0 and liquidity:
        d["monthly_burn"] = -ocf / 12.0
        d["runway_months"] = liquidity / (-ocf / 12.0)
    else:
        d["monthly_burn"] = None
        d["runway_months"] = None
    sh = inst.get("shares_out", {})
    if sh:
        dates = sorted(sh)
        now_d = dates[-1]
        two_years = [x for x in dates if (now_d - x).days >= 700]
        one_year = [x for x in dates if (now_d - x).days >= 340]
        d["shares_latest"] = {"as_of": now_d.isoformat(), "value": sh[now_d]}
        if one_year:
            d["dilution_1y"] = sh[now_d] / sh[one_year[-1]] - 1 if sh[one_year[-1]] else None
        if two_years:
            d["dilution_2y"] = sh[now_d] / sh[two_years[-1]] - 1 if sh[two_years[-1]] else None
    return d
