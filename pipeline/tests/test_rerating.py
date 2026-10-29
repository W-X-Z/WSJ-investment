from wsj.ecosystems import rerating as rr

F = {"company_id": "company:x", "currency": "KRW", "period_end": "2026-06-30", "revenue": 100.0, "operating_income": 60.0, "shares_outstanding": 10.0}


def test_implied_margin_and_scenarios_are_consistent():
    # 시총 = 가격 × 주식수 = 50 × 10 = 500. 배수 12, 세율 0.2 → 내재 마진 = 500 / (12 × 100 × 0.8) = 52.1%
    o = rr.evaluate(F, 50.0, bands={"mid": {"margin": 0.25, "pe": 10.0}}, tax=0.2)
    assert o["ttm_op_margin_pct"] == 60.0
    assert o["implied_durable_margin_pct"]["pe_12"] == 52.1
    assert o["pe_on_after_tax_op"] == round(500 / (60 * 0.8), 1)
    mid = o["scenarios"]["mid"]
    assert mid["price"] == 20.0 and mid["vs_price_pct"] == -60.0   # 100 × 0.25 × 0.8 × 10 / 10
    assert mid["required_revenue_multiple"] == 2.5                  # 500 / (0.25 × 0.8 × 10) / 100
    # 시나리오 가격에 필요 매출 배수를 곱하면 현재가로 돌아온다
    assert round(mid["price"] * mid["required_revenue_multiple"], 6) == 50.0


def test_missing_price_or_revenue_degrades_gracefully():
    assert "implied_durable_margin_pct" not in rr.evaluate(F, None)
    assert rr.evaluate({**F, "revenue": None}, 50.0)["note"] == "매출·주식수 없음"
    assert set(rr.evaluate(F, 50.0)["scenarios"]) == {"trough", "mid", "regime"}
