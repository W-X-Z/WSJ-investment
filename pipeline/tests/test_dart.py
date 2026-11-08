"""OpenDART 수집기 — 고정 파일만 쓴다 (opendart.fss.or.kr 에 닿지 않는다)."""

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from wsj.ecosystems import dart as D

FIX = Path(__file__).parent / "fixtures"


def _fx(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _corp_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", (FIX / "dart_corpcode.xml").read_text(encoding="utf-8"))
    return buf.getvalue()


class _Resp:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content, self.status_code, self.headers = content, status_code, {"content-type": "application/x-msdownload"}


class FakeHttp:
    """(엔드포인트, 사업연도, 보고서 코드, 연결/별도) → 고정 응답. 없는 조합은 013(자료 없음)."""

    def __init__(self, fnltt: dict | None = None, corp: bytes | None = None, list_resp: dict | None = None):
        self.fnltt = fnltt if fnltt is not None else {("2026", "11014", "CFS"): _fx("dart_fnltt_2026_11014.json"),
                                                      ("2025", "11011", "CFS"): _fx("dart_fnltt_2025_11011.json")}
        self.corp = corp if corp is not None else _corp_zip()
        self.list_resp = list_resp if list_resp is not None else _fx("dart_list.json")
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((url, kw.get("params")))
        return _Resp(self.corp)

    def get_json(self, url, params=None, headers=None):
        self.calls.append((url, params))
        if url == D.FNLTT_URL:
            return self.fnltt.get((params["bsns_year"], params["reprt_code"], params["fs_div"]), {"status": "013", "message": "조회된 데이타가 없습니다."})
        if url == D.SHARES_URL:
            return _fx("dart_stock_totqy.json")
        if url == D.LIST_URL:
            return self.list_resp
        raise AssertionError(url)


GRAPH = {"nodes": [
    {"id": "company:zz_kr", "kind": "company", "label": "ZZ Test 지지테스트 (KOSDAQ 123456, 비SEC)", "ecosystem": "power",
     "listing": {"ticker": "123456", "exchange": "KOSDAQ", "cik": None, "filer_type": "non_sec_listed"}, "size_band": "small", "role": "supplier"},
    {"id": "company:zz_us", "kind": "company", "label": "ZZ US (ZZUS)", "ecosystem": "power",
     "listing": {"ticker": "ZZUS", "exchange": "NYSE", "cik": 1, "filer_type": "10-K"}, "size_band": "small", "role": "supplier"},
    {"id": "company:zz_unmapped", "kind": "company", "label": "ZZ Unmapped (KRX 654321)", "ecosystem": "power",
     "listing": {"ticker": "654321", "exchange": "KRX", "cik": None, "filer_type": "non_sec_listed"}, "size_band": "small", "role": "supplier"},
], "edges": []}


def test_corp_codes_and_report_candidates():
    assert D.parse_corp_codes(_corp_zip()) == {"123456": "00123456"}     # 비상장(종목코드 없음)은 뺀다
    assert D.report_candidates(date(2026, 11, 8))[:4] == [(2026, "11014", date(2026, 9, 30)), (2026, "11012", date(2026, 6, 30)),
                                                          (2026, "11013", date(2026, 3, 31)), (2025, "11011", date(2025, 12, 31))]
    assert D.report_candidates(date(2026, 2, 1))[0] == (2025, "11011", date(2025, 12, 31))
    assert [c["id"] for c in D.kr_companies(GRAPH)] == ["company:zz_kr", "company:zz_unmapped"]


def test_parse_statements_quarter_and_annual():
    q = D.parse_statements(_fx("dart_fnltt_2026_11014.json")["list"], "11014")
    assert q["ytd"]["revenue"] == 800e6 and q["prior_ytd"]["revenue"] == 650e6          # 3분기는 누적(add) 칸
    assert q["ytd"]["net_income"] == 52e6                                              # 지배주주 귀속이 우선 (미국 NetIncomeLoss 와 같게)
    assert q["ytd"]["operating_cash_flow"] == 90e6 and q["prior_ytd"]["operating_cash_flow"] == 70e6
    assert q["cash"] == 120e6 and q["total_debt"] == 160e6                             # 단기 50 + 유동성 장기 10(계정명) + 장기 80 + 사채 20, 리스 제외
    assert q["rcept_no"] == "20261113000123"
    a = D.parse_statements(_fx("dart_fnltt_2025_11011.json")["list"], "11011")
    assert a["ytd"]["revenue"] == 1000e6 and a["prior_ytd"]["revenue"] == 900e6 and a["total_debt"] == 130e6
    assert D.parse_shares(_fx("dart_stock_totqy.json")) == 9.5e6


def test_parse_statements_refuses_three_month_values_as_ytd():
    """반기·3분기 손익에 누적 칸이 없으면 3개월 값을 누적으로 쓰지 않는다 (TTM 이 틀린다)."""
    rows = [r | {"thstrm_add_amount": ""} if r["sj_div"] == "IS" else r for r in _fx("dart_fnltt_2026_11014.json")["list"]]
    q = D.parse_statements(rows, "11014")
    assert q["ytd"]["revenue"] is None and q["ytd"]["operating_cash_flow"] == 90e6


def test_run_writes_ttm_fy_and_disclosure_clues(tmp_path):
    from wsj.db.sqlite import SqliteStore

    store = SqliteStore(tmp_path / "t.sqlite")
    http = FakeHttp()
    res = D.run(http, store, GRAPH, "KEY", days=14, today=date(2026, 11, 20))
    assert res["companies"] == 2 and res["mapped"] == 1 and res["financials"] == {"ok": 1, "empty": 0, "error": 0}
    rows = {r["period"]: r for r in store.select("raw.company_fundamentals")}
    ttm, fy = rows["ttm"], rows["fy"]
    assert ttm["period_end"] == "2026-09-30" and ttm["currency"] == "KRW" and ttm["source"] == "opendart_fnltt"
    # TTM = 2026 누적 + 2025 연간 − 2025 같은 기간 누적
    assert ttm["revenue"] == 1150e6 and ttm["gross_profit"] == 230e6 and ttm["operating_income"] == 100e6 and ttm["net_income"] == 76e6
    assert ttm["operating_cash_flow"] == 140e6 and ttm["capex"] == 60e6                 # capex 는 양수
    assert ttm["cash"] == 120e6 and ttm["total_debt"] == 160e6 and ttm["shares_outstanding"] == 9.5e6
    assert ttm["source_url"].endswith("rcpNo=20261113000123") and "연결" in ttm["note"]
    assert fy["period_end"] == "2025-12-31" and fy["revenue"] == 1000e6 and fy["capex"] == 50e6 and fy["total_debt"] == 130e6
    clues = store.select("ideas.clues")
    assert res["disclosures"] == {"seen": 2, "new": 2} and len(clues) == 2                # 임원·주요주주 보고는 버린다
    c = next(x for x in clues if "공급계약" in x["title"])
    assert c["source_id"] == "opendart" and c["source_kind"] == "disclosure" and c["region"] == "kr" and c["relevant"]
    assert c["url"] == "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261118000111"
    assert c["companies"][0]["company"] == "company:zz_kr" and c["extra"]["layer"] == "disclosure" and c["extra"]["importance"] == 3
    # 다시 돌려도 같은 단서를 또 넣지 않는다
    again = D.run(FakeHttp(), store, GRAPH, "KEY", days=14, today=date(2026, 11, 20))
    assert again["disclosures"]["new"] == 0 and len(store.select("ideas.clues")) == 2


def test_run_falls_back_to_previous_report_and_separate_statements(tmp_path):
    """3분기 보고서가 아직 없으면 반기 보고서, 연결이 없으면 별도 재무제표."""
    fn = {("2026", "11012", "OFS"): _fx("dart_fnltt_2026_11014.json"), ("2025", "11011", "OFS"): _fx("dart_fnltt_2025_11011.json")}
    res = D.run(FakeHttp(fnltt=fn), None, GRAPH, "KEY", disclosures=False, today=date(2026, 11, 8))
    ttm = next(r for r in res["rows"] if r["period"] == "ttm")
    assert ttm["period_end"] == "2026-06-30" and ttm["revenue"] == 1150e6 and "별도" in ttm["note"]


def test_run_annual_latest_writes_fy_and_ttm():
    fn = {("2025", "11011", "CFS"): _fx("dart_fnltt_2025_11011.json")}
    res = D.run(FakeHttp(fnltt=fn), None, GRAPH, "KEY", disclosures=False, today=date(2026, 3, 20))
    by = {r["period"]: r for r in res["rows"]}
    assert by["fy"]["period_end"] == by["ttm"]["period_end"] == "2025-12-31" and by["ttm"]["revenue"] == 1000e6


def test_bad_key_stops_the_run():
    class BadKey(FakeHttp):
        def get_json(self, url, params=None, headers=None):
            return {"status": "010", "message": "등록되지 않은 키입니다."}

    with pytest.raises(D.DartError):
        D.run(BadKey(), None, GRAPH, "KEY", today=date(2026, 11, 20))
    bad_zip = FakeHttp(corp='<?xml version="1.0"?><result><status>011</status><message>사용할 수 없는 키</message></result>'.encode())
    with pytest.raises(D.DartError) as e:
        D.run(bad_zip, None, GRAPH, "KEY", today=date(2026, 11, 20))
    assert e.value.status == "011"


def test_cli_skips_without_key(monkeypatch, capsys):
    from types import SimpleNamespace

    monkeypatch.setattr("wsj.config.load_settings", lambda: SimpleNamespace(dart_api_key=""))
    assert D.main(["run"]) == 0
    assert "DART_API_KEY 없음" in capsys.readouterr().out
