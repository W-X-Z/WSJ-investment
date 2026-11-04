"""발행주식수 — 표지 값이 없는 다중 클래스·40-F·신규 상장사도 대체 태그로 받는다."""

from wsj.ecosystems import facts as F


def _f(**ns):
    return {"facts": {k.replace("_", "-"): v for k, v in ns.items()}}


def _tag(*rows):
    return {"units": {"shares": [{"end": e, "val": v, "accn": f"a{i}", "frame": None} for i, (e, v) in enumerate(rows)]}}


def test_cover_value_wins_when_latest():
    d = _f(dei={"EntityCommonStockSharesOutstanding": _tag(("2026-10-02", 1_131_423_212))},
           us_gaap={"CommonStockSharesOutstanding": _tag(("2026-08-28", 1_120_000_000))})
    assert F.sec_shares(d) == (1_131_423_212.0, "2026-10-02")


def test_falls_back_to_balance_sheet_ifrs_and_weighted_counts():
    googl = _f(dei={"EntityPublicFloat": {"units": {"USD": []}}}, us_gaap={"CommonStockSharesOutstanding": _tag(("2026-09-30", 12_294_000_000))})
    assert F.sec_shares(googl) == (12_294_000_000.0, "2026-09-30")
    teck = _f(ifrs_full={"NumberOfSharesOutstanding": _tag(("2025-12-31", 488_500_000))})
    assert F.sec_shares(teck) == (488_500_000.0, "2025-12-31")
    mair = _f(us_gaap={"CommonStockSharesOutstanding": _tag(("2026-03-31", 1000)),          # 상장 전 서류의 1,000주는 버린다
                       "WeightedAverageNumberOfDilutedSharesOutstanding": _tag(("2026-06-30", 396_562_288))})
    assert F.sec_shares(mair) == (396_562_288.0, "2026-06-30")
    assert F.sec_shares(_f()) is None


def test_adr_listings_count_ads_not_ordinary_shares():
    from wsj.ecosystems.prices import Listing

    class _Http:
        def get_json(self, url, headers=None):
            assert headers and "research" in headers["User-Agent"]      # SEC 는 연락처 든 UA 가 아니면 403
            return _f(dei={"EntityCommonStockSharesOutstanding": _tag(("2025-12-31", 25_932_524_521))})

    tsm = Listing("company:tsmc", "NYSE", "TSM", "TSM", "us")
    mu = Listing("company:mu", "Nasdaq", "MU", "MU", "us")
    nodes = {"company:tsmc": {"listing": {"cik": 1046179}}, "company:mu": {"listing": {"cik": 723125}}}
    rows = {r["company_id"]: r for r in F.fetch_us(_Http(), [tsm, mu], nodes, use_cover=False)}
    assert rows["company:tsmc"]["shares_outstanding"] == round(25_932_524_521 / 5) and rows["company:tsmc"]["source"] == "sec_companyfacts_ads"
    assert rows["company:mu"]["shares_outstanding"] == 25_932_524_521 and rows["company:mu"]["source"] == "sec_companyfacts"


def test_us_candidate_without_cik_is_resolved_by_ticker():
    """후보 노드는 티커·거래소만 있다 — SEC 티커 목록으로 CIK 를 이어 시총·규모를 채운다 (ADR-0033 뒤 frontier 후보도 같은 길)."""
    from wsj.ecosystems.prices import Listing

    class _Http:
        def __init__(self):
            self.urls = []

        def get_json(self, url, headers=None):
            self.urls.append(url)
            if url == F.SEC_TICKERS_URL:
                return {"0": {"cik_str": 1051627, "ticker": "AXTI", "title": "AXT INC"}, "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE"}}
            return _f(dei={"EntityCommonStockSharesOutstanding": _tag(("2026-09-30", 65_000_000))})

    http = _Http()
    axti = Listing("company:axt", "Nasdaq", "AXTI", "AXTI", "us")
    nobody = Listing("company:nobody", "Nasdaq", "ZZZZ", "ZZZZ", "us")
    rows = F.fetch_us(http, [axti, nobody], {"company:axt": {"listing": {"ticker": "AXTI", "exchange": "Nasdaq"}}, "company:nobody": {}}, use_cover=False)
    assert [r["company_id"] for r in rows] == ["company:axt"] and rows[0]["shares_outstanding"] == 65_000_000
    assert http.urls.count(F.SEC_TICKERS_URL) == 1 and any("CIK0001051627" in u for u in http.urls)
    assert F.sec_cik_by_ticker(http)["BRK-B"] == 1067983


INSTANCE = """<xbrl><dei:EntityCommonStockSharesOutstanding contextRef="c-3" decimals="INF" id="f-30" unitRef="shares">274,527,094</dei:EntityCommonStockSharesOutstanding>
<dei:EntityCommonStockSharesOutstanding contextRef="c-4" decimals="INF" id="f-31" unitRef="shares">29901795</dei:EntityCommonStockSharesOutstanding></xbrl>"""


def test_cover_shares_sums_share_classes_and_wins_over_companyfacts():
    """다중 클래스 회사(Forgent: Class A + Class B, Vicor: 보통주 + Class B)는 표지의 클래스별 주식수를 합산한다 — companyfacts 는 한 클래스만 준다."""
    from wsj.ecosystems.prices import Listing

    assert F.cover_shares(INSTANCE) == 274_527_094 + 29_901_795
    assert F.cover_shares("<xbrl/>") is None

    class _Http:
        def __init__(self):
            self.urls = []

        def get_json(self, url, headers=None):
            self.urls.append(url)
            if "submissions" in url:
                return {"filings": {"recent": {"form": ["8-K", "10-K"], "accessionNumber": ["0002080126-26-000040", "0002080126-26-000035"],
                                               "primaryDocument": ["d1.htm", "fps-20260630.htm"], "reportDate": ["2026-10-22", "2026-06-30"]}}}
            return _f(dei={"EntityCommonStockSharesOutstanding": _tag(("2026-06-30", 243_802_000))})

        def get_text(self, url, headers=None):
            self.urls.append(url)
            assert url.endswith("/000208012626000035/fps-20260630_htm.xml")
            return INSTANCE

    http = _Http()
    fps = Listing("company:fps", "NYSE", "FPS", "FPS", "us")
    rows = F.fetch_us(http, [fps], {"company:fps": {"listing": {"cik": 2080126}}})
    assert rows[0]["shares_outstanding"] == 304_428_889 and rows[0]["source"] == "sec_cover"
    assert not any("companyfacts" in u for u in http.urls)                     # 표지에서 구했으면 companyfacts 는 부르지 않는다
