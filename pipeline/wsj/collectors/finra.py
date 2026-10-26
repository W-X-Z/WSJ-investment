"""finra — FINRA Data API (무인증). 유니버스 티커만 domainFilters 로 받는다.

세 데이터셋, 각자 워터마크:
- regShoDaily          → raw.finra_short_daily     (T+1, 일간)
- consolidatedShortInterest → raw.finra_short_interest (월 2회, settlementDate 15일/말일)
- weeklySummary (ATS)  → raw.finra_ats_weekly      (주간, 2~4주 지연, weekStartDate = 월요일)

규칙: 정렬·limit 는 파티션 키 EQUAL 필터가 전부 있어야 한다 → 날짜를 돌며 질의.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import chunked, daterange, dedupe, parse_date

BASE = "https://api.finra.org/data/group/otcMarket/name"
SYMBOL_CHUNK = 100
PAGE = 5000


def _query(http, dataset: str, equal: dict[str, str], symbols: list[str], symbol_field: str) -> list[dict]:
    out: list[dict] = []
    for syms in chunked(symbols, SYMBOL_CHUNK):
        offset = 0
        while True:
            body = {
                "limit": PAGE,
                "offset": offset,
                "compareFilters": [
                    {"compareType": "EQUAL", "fieldName": k, "fieldValue": v} for k, v in equal.items()
                ],
                "domainFilters": [{"fieldName": symbol_field, "values": syms}],
            }
            resp = http.request(
                "POST", f"{BASE}/{dataset}", json=body, headers={"Accept": "application/json"}
            )
            if resp.status_code == 404:
                break  # 해당 파티션 없음 (아직 미발행 날짜)
            resp.raise_for_status()
            rows = resp.json() if resp.content else []  # 미발행 파티션은 204/빈 본문
            out.extend(rows)
            if len(rows) < PAGE:
                break
            offset += PAGE
    return out


def _post_rows(http, dataset: str, body: dict) -> list[dict] | None:
    """404 → None(파티션 없음), 204/빈 본문 → [], 202/HTML(비동기·스로틀) → 재시도 후 실패."""
    for attempt in range(4):
        resp = http.request("POST", f"{BASE}/{dataset}", json=body, headers={"Accept": "application/json"})
        if resp.status_code == 404:
            return None
        if resp.status_code == 204 or not resp.content:
            return []
        ctype = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "json" in ctype:
            return resp.json()
        time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"FINRA {dataset}: non-JSON response {resp.status_code} ({ctype[:40]})")


def _settlement_dates(start: date, end: date) -> list[date]:
    """월 2회 결제일: 15일과 말일. (공휴일이면 FINRA 가 앞당기지만 데이터는 공식 날짜로 발행된다)"""
    out = []
    for d in daterange(start, end):
        nxt = d + timedelta(days=1)
        if d.day == 15 or nxt.month != d.month:
            out.append(d)
    return out


def _mondays(start: date, end: date) -> list[date]:
    d = start - timedelta(days=start.weekday())
    out = []
    while d <= end:
        out.append(d)
        d += timedelta(days=7)
    return out


class FinraCollector(Collector):
    name = "finra"
    tables = ("raw.finra_short_daily", "raw.finra_short_interest", "raw.finra_ats_weekly")
    schedule = "daily"
    description = "일별 공매도 거래량, 공매도 잔고(월 2회), ATS 다크풀 주간 — 유니버스 티커"
    needs_universe = True

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        symbols = sorted({r["ticker"] for r in self.universe(ctx, ("ticker",)) if r.get("ticker")})
        if ctx.limit:
            symbols = symbols[: ctx.limit]
        end = ctx.today()
        wm = dict(ctx.watermark)

        # 1) regShoDaily
        start = self.start_date(ctx, "short_daily_last", default_lookback_days=10)
        n_days = 0
        for day in daterange(start, end):
            if day.weekday() >= 5:
                continue
            rows = _query(
                http,
                "regShoDaily",
                {"tradeReportDate": day.isoformat()},
                symbols,
                "securitiesInformationProcessorSymbolIdentifier",
            )
            if not rows:
                continue
            n_days += 1
            res.add(
                store.upsert(
                    "raw.finra_short_daily",
                    dedupe(
                        [
                            {
                                "trade_report_date": r["tradeReportDate"],
                                "symbol": r["securitiesInformationProcessorSymbolIdentifier"],
                                "market_code": r.get("marketCode") or "",
                                "reporting_facility_code": r.get("reportingFacilityCode") or "",
                                "short_par_quantity": r.get("shortParQuantity"),
                                "short_exempt_par_quantity": r.get("shortExemptParQuantity"),
                                "total_par_quantity": r.get("totalParQuantity"),
                            }
                            for r in rows
                        ],
                        ["trade_report_date", "symbol", "market_code", "reporting_facility_code"],
                    ),
                    ["trade_report_date", "symbol", "market_code", "reporting_facility_code"],
                )
            )
            wm["short_daily_last"] = day.isoformat()
        log.info("regShoDaily days with data: %d", n_days)

        # 2) consolidatedShortInterest
        start = self.start_date(ctx, "short_interest_last", default_lookback_days=45)
        n_si = 0
        for sd in _settlement_dates(start, end):
            rows = _query(
                http, "consolidatedShortInterest", {"settlementDate": sd.isoformat()}, symbols, "symbolCode"
            )
            if not rows:
                continue
            n_si += 1
            res.add(
                store.upsert(
                    "raw.finra_short_interest",
                    dedupe(
                        [
                            {
                                "settlement_date": r["settlementDate"],
                                "symbol": r["symbolCode"],
                                "issue_name": r.get("issueName"),
                                "market_class_code": r.get("marketClassCode"),
                                "current_short_position_quantity": r.get("currentShortPositionQuantity"),
                                "previous_short_position_quantity": r.get("previousShortPositionQuantity"),
                                "average_daily_volume_quantity": r.get("averageDailyVolumeQuantity"),
                                "days_to_cover_quantity": r.get("daysToCoverQuantity"),
                                "change_percent": r.get("changePercent"),
                                "change_previous_number": r.get("changePreviousNumber"),
                                "stock_split_flag": r.get("stockSplitFlag"),
                                "revision_flag": r.get("revisionFlag"),
                            }
                            for r in rows
                        ],
                        ["settlement_date", "symbol"],
                    ),
                    ["settlement_date", "symbol"],
                )
            )
            wm["short_interest_last"] = sd.isoformat()
        log.info("short interest settlement dates with data: %d", n_si)

        # 3) weeklySummary (ATS, T1+T2) — 발행 지연이 커서 6주 전부터 다시 본다
        start = self.start_date(ctx, "ats_last_week", default_lookback_days=60)
        start = min(start, end - timedelta(days=56))  # T2 는 4주 지연이라 넉넉히
        n_wk = 0
        for monday in _mondays(start, end):
            for tier in ("T1", "T2"):
                rows = _query(
                    http,
                    "weeklySummary",
                    {"weekStartDate": monday.isoformat(), "tierIdentifier": tier},
                    symbols,
                    "issueSymbolIdentifier",
                )
                if not rows:
                    continue
                n_wk += 1
                res.add(
                    store.upsert(
                        "raw.finra_ats_weekly",
                        dedupe(
                            [
                                {
                                    "week_start_date": r["weekStartDate"],
                                    "tier_identifier": r["tierIdentifier"],
                                    "symbol": r["issueSymbolIdentifier"],
                                    # OTC_W_SMBL_FIRM 행은 MPID 가 없고 firmCRDNumber 만 있다 → PK 충돌 방지
                                    "mpid": r.get("MPID")
                                    or (
                                        f"CRD{r['firmCRDNumber']}"
                                        if r.get("firmCRDNumber") is not None
                                        else ""
                                    ),
                                    "summary_type_code": r.get("summaryTypeCode") or "",
                                    "issue_name": r.get("issueName"),
                                    "market_participant_name": r.get("marketParticipantName"),
                                    "firm_crd_number": str(r["firmCRDNumber"])
                                    if r.get("firmCRDNumber") is not None
                                    else None,
                                    "total_weekly_trade_count": r.get("totalWeeklyTradeCount"),
                                    "total_weekly_share_quantity": r.get("totalWeeklyShareQuantity"),
                                    "total_notional_sum": r.get("totalNotionalSum"),
                                    "last_update_date": parse_date(r.get("lastUpdateDate")),
                                }
                                for r in rows
                            ],
                            ["week_start_date", "tier_identifier", "symbol", "mpid", "summary_type_code"],
                        ),
                        ["week_start_date", "tier_identifier", "symbol", "mpid", "summary_type_code"],
                    )
                )
                wm["ats_last_week"] = monday.isoformat()
        log.info("ATS weekly partitions with data: %d", n_wk)

        res.notes.append(
            f"symbols={len(symbols)} short_daily_days={n_days} short_interest_dates={n_si} ats_partitions={n_wk}"
        )
        res.watermark = wm
        return res
