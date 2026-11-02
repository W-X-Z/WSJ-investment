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
