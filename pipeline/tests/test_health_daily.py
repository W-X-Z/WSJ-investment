from datetime import UTC, datetime

from wsj.ecosystems import health
from wsj.ecosystems.ideas import merge_facts

NOW = datetime(2026, 11, 2, 1, 30, tzinfo=UTC)  # 월요일 KST 10:30


def _problems(runs):
    graph = {"nodes": [], "edges": []}
    return [p["what"] for p in health.report(graph, {"runs": runs}, NOW)["problems"]]


def test_daily_set_is_morning_chain_not_legacy_ideas():
    assert "ideas" not in health.DAILY
    assert {"agent:collect", "agent:interpret", "agent:enrich", "agent:report"} <= health.DAILY


def test_agent_saturday_run_not_alarm_on_monday():
    runs = [{"collector": "agent:report", "status": "succeeded", "started_at": "2026-10-30T22:39:00+00:00"}]
    assert not any("agent:report" in w and "성공하지 못함" in w for w in _problems(runs))


def test_agent_skipped_counts_as_ran_but_old_run_alarms():
    skipped = [{"collector": "agent:collect", "status": "skipped", "started_at": "2026-11-01T20:00:00+00:00"}]
    assert not any("agent:collect" in w and "성공하지 못함" in w for w in _problems(skipped))
    old = [{"collector": "agent:collect", "status": "succeeded", "started_at": "2026-10-27T20:00:00+00:00"}]
    assert any("agent:collect" in w and "성공하지 못함" in w for w in _problems(old))


def test_scan_prices_carry_market_cap():
    by_key = merge_facts([{"ticker": "AEHR", "close": 54.89, "r1m": -46.0}], [{"ticker": "AEHR", "market_cap_usd": 1.6e9, "close": 54.89}])
    assert by_key["AEHR"]["market_cap_usd"] == 1.6e9 and by_key["AEHR"]["r1m"] == -46.0
