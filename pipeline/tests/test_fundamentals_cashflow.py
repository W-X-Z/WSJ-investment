"""재무 확장 (0040): SEC companyfacts → 영업현금흐름·capex·현금·총차입·희석 주식수 (네트워크 없음, 고정 파일)."""

import json
from pathlib import Path

import pytest

from wsj.briefs.xbrl import build_financials
from wsj.ecosystems import fundamentals as FU
from wsj.ecosystems import prices as P

FIX = Path(__file__).parent / "fixtures"


def _rows():
    cf = json.loads((FIX / "sec_companyfacts_mini.json").read_text(encoding="utf-8"))
    return FU.us_rows(P.Listing("company:mini", "NYSE", "MINI", "MINI", "us"), build_financials(cf), cik=123)


def test_us_ttm_has_cash_flow_balance_sheet_and_shares():
    ttm = next(r for r in _rows() if r["period"] == "ttm")
    assert ttm["period_end"] == "2025-12-31" and ttm["currency"] == "USD" and ttm["source"] == "sec_companyfacts"
    assert (ttm["revenue"], ttm["operating_income"], ttm["net_income"]) == (460.0, 46.0, 37.0)
    # 현금흐름표는 누적(3·6·9·12개월)만 보고 → 분기 차분의 4분기 합 = 연간
    assert ttm["operating_cash_flow"] == 110.0 and ttm["capex"] == 26.0
    # 기말 값: 현금 70, 총차입 = 유동성 장기부채 15 + 장기부채 200
    assert ttm["cash"] == 70.0 and ttm["total_debt"] == 215.0
    # 4분기 희석 주식수는 10-K 에 연간 값만 → 같은 날 끝나는 연간 값, 유통주식수는 표지(dei)의 50일 안 값
    assert ttm["diluted_shares"] == 1015.0 and ttm["shares_outstanding"] == 1030.0


def test_us_fy_row_has_same_new_fields():
    fy = next(r for r in _rows() if r["period"] == "fy")
    assert fy["period_end"] == "2025-12-31" and fy["revenue"] == 460.0
    assert (fy["operating_cash_flow"], fy["capex"], fy["cash"], fy["total_debt"], fy["diluted_shares"]) == (110.0, 26.0, 70.0, 215.0, 1015.0)


def test_us_rows_without_new_concepts_stay_backward_compatible():
    """새 개념이 없는 회사도 예전처럼 손익 칸만 채우고 새 칸은 None."""
    fin = {"quarters": [{"period_end": f"2025-{m:02d}-30", "revenue": 100.0, "op_income": 10.0, "net_income": 8.0} for m in (3, 6, 9)]
           + [{"period_end": "2025-12-31", "revenue": 120.0, "op_income": 12.0, "net_income": 9.0}], "annual": []}
    ttm = FU.us_rows(P.Listing("company:a", "NYSE", "A", "A", "us"), fin)[0]
    assert ttm["revenue"] == 420.0 and all(ttm[c] is None for c in FU.NEW_COLS)


class _OldDbStore:
    """0040 전 DB 흉내: 새 칸이 있으면 PostgREST 처럼 거절한다."""

    def __init__(self):
        self.calls = []

    def upsert(self, table, rows, conflict):
        bad = [c for c in FU.NEW_COLS if any(c in r for r in rows)]
        self.calls.append(sorted({k for r in rows for k in r}))
        if bad:
            raise RuntimeError(f"PostgREST POST {table} -> 400: Could not find the '{bad[0]}' column of 'company_fundamentals' in the schema cache")
        return len(rows)


def test_save_rows_falls_back_before_migration():
    store = _OldDbStore()
    rows = _rows()
    assert FU.save_rows(store, rows) == len(rows)
    assert len(store.calls) == 2 and not set(FU.NEW_COLS) & set(store.calls[1])


def test_save_rows_reraises_other_errors():
    class Broken:
        def upsert(self, *a):
            raise RuntimeError("PostgREST POST raw.company_fundamentals -> 401: invalid key")

    with pytest.raises(RuntimeError):
        FU.save_rows(Broken(), _rows())


def test_naver_rows_do_not_overwrite_dart_ttm(monkeypatch):
    """OpenDART 가 넣은 같은 기말의 TTM 은 네이버 값으로 덮지 않는다 (새 분기는 그대로 넣는다)."""
    g = {"nodes": [{"id": "company:k", "kind": "company", "label": "K (KOSDAQ 086390)", "listing": {"ticker": "086390", "exchange": "KOSDAQ"}}]}

    class Store:
        written: list = []

        def select(self, table, cols, filters):
            return [{"company_id": "company:k", "fetched_at": "2026-11-01", "source": "opendart_fnltt", "period_end": "2026-06-30"}]

        def upsert(self, table, rows, conflict):
            Store.written += rows
            return len(rows)

    def fake_kr(http, xs):
        return [{"company_id": "company:k", "period": "ttm", "period_end": "2026-06-30", "revenue": 1.0, "source": "naver_finance"},
                {"company_id": "company:k", "period": "ttm", "period_end": "2026-09-30", "revenue": 2.0, "source": "naver_finance"}]

    monkeypatch.setattr(FU, "fetch_kr", fake_kr)
    res = FU.run(None, Store(), g, only={"kr"})
    assert res["rows"] == 1 and [r["period_end"] for r in Store.written] == ["2026-09-30"]


def test_postgrest_rpc_targets_schema_profile():
    """GitHub Actions 경로: store.rpc('research.put_reports', …) → POST /rest/v1/rpc/put_reports + Content-Profile: research."""
    import httpx

    from wsj.db.postgrest import PostgrestStore

    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(path=req.url.path, profile=req.headers.get("content-profile"), body=json.loads(req.content))
        return httpx.Response(200, json={"ok": 1, "rejected": []})

    store = PostgrestStore("https://example.supabase.co", "secret")
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    out = store.rpc("research.put_reports", {"rows": [{"report_id": "screen:2026-11-08"}]})
    assert out == {"ok": 1, "rejected": []}
    assert seen == {"path": "/rest/v1/rpc/put_reports", "profile": "research", "body": {"rows": [{"report_id": "screen:2026-11-08"}]}}
