from wsj.ecosystems import quiet


def px(r12, r3=0.0, fh=-10.0, r1=0.0):
    return {"r1m": r1, "r3m": r3, "r12m": r12, "from_high": fh, "as_of": "2026-10-28", "points": 250}


def test_company_verdicts_cover_moved_reset_sold_off_and_quiet():
    assert quiet.company_verdict(None) == "unmeasured"
    assert quiet.company_verdict(px(212, fh=-48.9)) == "moved_reset"   # SK hynix 2026-10: 7배 뒤 절반
    assert quiet.company_verdict(px(146, fh=-10)) == "moved"
    assert quiet.company_verdict(px(60, fh=-15)) == "moved"
    assert quiet.company_verdict(px(-46.5, fh=-66.6)) == "sold_off"    # 시장이 보고 버린 것
    assert quiet.company_verdict(px(4.1, fh=-68.8)) == "sold_off"
    assert quiet.company_verdict(px(14.9, r3=5, fh=-40)) == "quiet"
    assert quiet.company_verdict(px(40, r3=5, fh=-30)) == "mixed"


def test_thesis_verdict_uses_primary_and_universe_baseline():
    keys = {"company:a": "A", "company:b": "B", "company:c": "C"}
    prices = {"A": px(212, fh=-49), "B": px(10, r3=2, fh=-20), "C": px(5, r3=1, fh=-30)}
    qc = quiet.quiet_check([{"company": "company:a", "role": "secondary"}, {"company": "company:b", "role": "primary"},
                            {"company": "company:c", "role": "primary"}, {"company": "company:zzz", "role": "primary"}],
                           keys, prices, "2026-10-28", quiet.universe_stats(prices, min_points=1))
    assert qc["verdict"] == "quiet"  # primary 둘이 quiet, 측정 안 된 primary 는 판정에서 빠진다
    assert qc["counts"]["unmeasured"] == 1 and qc["counts"]["moved_reset"] == 1
    assert qc["universe"]["n"] == 3 and qc["universe"]["median_12m_pct"] == 10.0
    assert [c["note"] for c in qc["companies"] if c["verdict"] == "unmeasured"] == ["비상장"]


def test_listing_keys_follow_price_keys():
    g = {"nodes": [{"id": "company:x", "kind": "company", "listing": {"exchange": "KRX", "ticker": "000660"}},
                   {"id": "company:y", "kind": "company", "listing": {"exchange": "Nasdaq", "ticker": "mu"}},
                   {"id": "company:z", "kind": "company", "listing": {"exchange": None, "ticker": None}}]}
    assert quiet.listing_keys(g) == {"company:x": "KRX:000660", "company:y": "MU"}


def test_update_sql_goes_through_put_theses_only():
    sql = quiet.update_sql({"k1": {"verdict": "quiet"}})
    assert sql.startswith("select ideas.put_theses(") and "$q${\"k1\":{\"verdict\":\"quiet\"}}$q$" in sql and "update " not in sql.lower()


def test_price_focus_includes_thesis_companies():
    from wsj.ecosystems import prices

    class Store:
        def select(self, table, columns=None, filters=None, limit=None, order=None):
            if table == "ideas.theses":
                return [{"beneficiaries": [{"company": "company:samsung"}, {"company": "company:mu"}], "losers": [{"node": "component:x"}, {"company": "company:y"}]}]
            return []

    assert prices.thesis_companies(Store()) == {"company:samsung", "company:mu", "company:y"}
    assert {"company:samsung", "company:mu"} <= prices.focus_companies(Store())
