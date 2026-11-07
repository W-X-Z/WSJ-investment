"""네트워크 페처 — 출처마다 '원본 응답'만 돌려주는 얇은 함수. 파싱은 parse.py, 계산은 calc.py.

테스트는 같은 메서드 이름을 가진 가짜 객체(픽스처 반환)를 ToolContext.fetch 에 꽂는다 → 테스트에 네트워크가 없다.

호스트별 주의 (2026-11-08 확인):
  api.nasdaq.com     브라우저 UA + Origin/Referer 가 있어야 한다. ETF 는 assetclass=etf.
  *.naver.com        Origin 을 붙이면 'Invalid CORS request' 로 거절 → UA·Accept 만 보낸다.
  www.sec.gov        연락처가 든 UA(SEC_USER_AGENT) 필수. 브라우저 UA 는 403. 이 컨테이너에서는 'Request Rate Threshold' 403 이 났다
                     → 로컬 파일 캐시(7일) + 실패 시 Nasdaq·Naver 자동완성으로 대체.
  home.treasury.gov  키 없음, 연도별 CSV.
  api.frankfurter.dev  ECB 기준 환율(키 없음, 날짜 지정 가능). 실패하면 open.er-api.com (최신값만).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

from wsj.http import HOST_RPS, HttpClient
from wsj.marketdata.nasdaq import BROWSER_HEADERS

log = logging.getLogger("wsj.tools")

BROWSER_UA = BROWSER_HEADERS["User-Agent"]
NAVER_HEADERS = {"User-Agent": BROWSER_UA, "Accept": "application/json, text/plain, */*"}

for _host, _rps in {"api.nasdaq.com": 2.0, "m.stock.naver.com": 2.0, "api.stock.naver.com": 2.0,
                    "api.finance.naver.com": 2.0, "ac.stock.naver.com": 2.0, "home.treasury.gov": 1.0,
                    "api.frankfurter.dev": 2.0, "open.er-api.com": 1.0}.items():
    HOST_RPS.setdefault(_host, _rps)

NASDAQ = "https://api.nasdaq.com/api"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TREASURY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
                "{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
SEC_CACHE_TTL_DAYS = 7


class Fetchers:
    """실제 네트워크. 각 메서드는 실패 시 예외를 던진다 (호출하는 도구가 잡아서 다음 출처로 넘어간다)."""

    def __init__(self, http: HttpClient, sec_user_agent: str, cache_dir: Path) -> None:
        self.http = http
        self.sec_headers = {"User-Agent": sec_user_agent, "Accept": "application/json"}
        self.cache_dir = cache_dir

    # --- Nasdaq -------------------------------------------------------------
    def nasdaq_history(self, ticker: str, start: date, end: date, assetclass: str = "stocks") -> dict[str, Any]:
        params = {"assetclass": assetclass, "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": 9999}
        return self.http.get_json(f"{NASDAQ}/quote/{ticker.upper()}/historical", params=params, headers=BROWSER_HEADERS)

    def nasdaq_info(self, ticker: str, assetclass: str = "stocks") -> dict[str, Any]:
        return self.http.get_json(f"{NASDAQ}/quote/{ticker.upper()}/info", params={"assetclass": assetclass},
                                  headers=BROWSER_HEADERS)

    def nasdaq_summary(self, ticker: str, assetclass: str = "stocks") -> dict[str, Any]:
        return self.http.get_json(f"{NASDAQ}/quote/{ticker.upper()}/summary", params={"assetclass": assetclass},
                                  headers=BROWSER_HEADERS)

    def nasdaq_autocomplete(self, query: str) -> dict[str, Any]:
        return self.http.get_json(f"{NASDAQ}/autocomplete/slookup/10", params={"search": query}, headers=BROWSER_HEADERS)

    # --- Naver --------------------------------------------------------------
    def naver_basic(self, code: str) -> dict[str, Any]:
        return self.http.get_json(f"https://m.stock.naver.com/api/stock/{code}/basic", headers=NAVER_HEADERS)

    def naver_integration(self, code: str) -> dict[str, Any]:
        return self.http.get_json(f"https://m.stock.naver.com/api/stock/{code}/integration", headers=NAVER_HEADERS)

    def naver_chart(self, code: str, start: date, end: date) -> list[dict[str, Any]]:
        params = {"startDateTime": start.strftime("%Y%m%d") + "0000", "endDateTime": end.strftime("%Y%m%d") + "2359"}
        return self.http.get_json(f"https://api.stock.naver.com/chart/domestic/item/{code}/day", params=params,
                                  headers=NAVER_HEADERS)

    def naver_sise(self, code: str, start: date, end: date) -> str:
        params = {"symbol": code, "requestType": "1", "startTime": start.strftime("%Y%m%d"),
                  "endTime": end.strftime("%Y%m%d"), "timeframe": "day"}
        return self.http.get_text("https://api.finance.naver.com/siseJson.naver", params=params, headers=NAVER_HEADERS)

    def naver_autocomplete(self, query: str) -> dict[str, Any]:
        return self.http.get_json("https://ac.stock.naver.com/ac", params={"q": query, "target": "stock"},
                                  headers=NAVER_HEADERS)

    def naver_quarters(self, code: str) -> dict[str, Any]:
        return self.http.get_json(f"https://m.stock.naver.com/api/stock/{code}/finance/quarter", headers=NAVER_HEADERS)

    # --- SEC ----------------------------------------------------------------
    def sec_tickers(self) -> tuple[dict[str, Any], str]:
        """(payload, 출처 설명). 캐시가 7일 안이면 캐시, 아니면 받아서 캐시. 받기 실패 시 묵은 캐시라도 쓴다."""
        path = self.cache_dir / "sec_company_tickers_exchange.json"
        age_days = (time.time() - path.stat().st_mtime) / 86400 if path.exists() else None
        if age_days is not None and age_days <= SEC_CACHE_TTL_DAYS:
            return json.loads(path.read_text()), f"cache:{path.name} ({age_days:.1f}d)"
        try:
            data = self.http.get_json(SEC_TICKERS_URL, headers=self.sec_headers)
        except Exception:
            if path.exists():
                log.warning("SEC tickers fetch failed — using stale cache (%.0fd)", age_days or 0)
                return json.loads(path.read_text()), f"stale_cache:{path.name} ({age_days:.0f}d)"
            raise
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        except OSError as exc:
            log.warning("SEC tickers cache write failed: %s", exc)
        return data, "sec.gov"

    def sec_companyfacts(self, cik: int) -> dict[str, Any] | None:
        resp = self.http.request("GET", COMPANYFACTS_URL.format(cik=cik), headers=self.sec_headers)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} for companyfacts CIK{cik:010d}")
        return resp.json()

    # --- 금리·환율 ------------------------------------------------------------
    def treasury_csv(self, year: int) -> str:
        return self.http.get_text(TREASURY_URL.format(year=year), headers={"User-Agent": BROWSER_UA, "Accept": "text/csv"})

    def fx_frankfurter(self, base: str, quote: str, day: date | None = None) -> dict[str, Any]:
        path = day.isoformat() if day else "latest"
        return self.http.get_json(f"https://api.frankfurter.dev/v1/{path}", params={"from": base, "to": quote},
                                  headers={"User-Agent": BROWSER_UA})

    def fx_er_api(self, base: str) -> dict[str, Any]:
        return self.http.get_json(f"https://open.er-api.com/v6/latest/{base}", headers={"User-Agent": BROWSER_UA})
