from datetime import date

from wsj.ecosystems import comove
from wsj.ecosystems.clues import POLICY_CAUSE, Clue, apply_screen, is_noise
from wsj.ecosystems.comove import Quote, basket_clue, baskets, short_name


def q(i: int, pct: float) -> Quote:
    return Quote(f"company:c{i}", f"Company{i} Inc (C{i})", f"C{i}", pct, 10.0, date(2026, 11, 4))


def test_basket_flags_broad_move_against_index():
    qs = {"power": [q(i, p) for i, p in enumerate([-18, -12, -11, -9, -7, -6, -2])]}
    out = baskets(qs, spy=1.6)
    assert len(out) == 1 and out[0]["direction"] == "down" and out[0]["n"] == 7
    assert out[0]["movers"][0]["pct"] == -18 and out[0]["median"] == -9


def test_basket_ignores_index_move_and_narrow_move():
    assert baskets({"power": [q(i, p) for i, p in enumerate([-3, -2, -2.5, -3.1, -2.8])]}, spy=-2.5) == []      # 지수와 같이 빠짐
    assert baskets({"power": [q(i, p) for i, p in enumerate([-20, -15, 0, 0.5, 1, 0.2])]}, spy=0.3) == []       # 두 종목만
    assert baskets({"power": [q(i, -10) for i in range(4)]}, spy=0) == []                                      # 4곳은 묶음이 아님


def test_basket_clue_shape():
    b = baskets({"power": [q(i, p) for i, p in enumerate([-18, -12, -11, -9, -7])]}, spy=1.6)[0]
    row = basket_clue(b)
    assert row["source_kind"] == "market_move" and row["relevant"] and row["extra"]["comove"]["ecosystem"] == "power"
    assert "동반 급락" in row["title"] and "S&P500 +1.6%" in row["title"] and row["url"].endswith("?move=2026-11-04")
    assert row["companies"][0]["company"] == "company:c0"


def test_short_name():
    assert short_name("Modine Manufacturing (MOD)") == "Modine"
    assert short_name("AXT (AXTI)") == "AXT"
    assert short_name("TE Connectivity (TEL)") == "TE Connectivity"


def test_day_parse():
    assert comove._day("Nov 4, 2026 4:00 PM ET") == date(2026, 11, 4)
    assert comove._day(None) is None


def test_policy_cause_keeps_price_story_with_policy_reason():
    assert not is_noise("Vertiv Sinks 9%, GE Vernova Down 8% as Democrats Win Congress, Reviving Data Center Fears", "TIKR")
    assert not is_noise("Applied Materials shares slide after new China export rule", "x")
    assert is_noise("Why Vertiv stock is down today", "x")
    assert is_noise("Micron stock falls as memory prices drop", "x")
    assert POLICY_CAUSE.search("데이터센터 관련주 급락…미 중간선거 영향")


def test_screen_keeps_policy_themes():
    c = Clue("https://x/1", "Data Centers, Affordability, and the Ballot Box", "", None, "s", "POWER", "trade_press")
    apply_screen([c], {"items": [{"i": 0, "keep": True, "scope": "core", "themes": ["politics", "power_prices", "bogus"], "note": "n"}]})
    assert c.relevant and c.extra["themes"] == ["politics", "power_prices"]
