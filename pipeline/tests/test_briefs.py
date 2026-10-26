from datetime import date

from wsj.briefs import xbrl
from wsj.briefs.llm import extract_json
from wsj.marketdata.nasdaq import event_window_returns, price_metrics
from wsj.parsers.sec_html import extract_10k_sections, extract_10q_mdna, html_to_text, toc_anchor_ids


def _tenk_html(with_anchors: bool = True) -> str:
    body = "x" * 50
    para = lambda s: f"<p>{s} {body}</p>" * 20  # noqa: E731
    toc = (
        "<table><tr><td>Item 1.</td><td><a href='#i1'>Business</a></td></tr>"
        "<tr><td>Item 1A.</td><td><a href='#i1a'>Risk Factors</a></td></tr>"
        "<tr><td>Item 2.</td><td><a href='#i2'>Properties</a></td></tr>"
        "<tr><td>Item 7.</td><td><a href='#i7'>Management's Discussion and Analysis</a></td></tr>"
        "<tr><td>Item 7A.</td><td><a href='#i7a'>Quantitative and Qualitative Disclosures</a></td></tr></table>"
        if with_anchors
        else "<p>Item 1. Business 3</p><p>Item 1A. Risk Factors 9</p><p>Item 7. Management's Discussion and Analysis 40</p>"
    )
    a = (lambda i: f"<div id='{i}'></div>") if with_anchors else (lambda i: "")
    return (
        "<html><body>"
        + toc
        + a("i1")
        + "<p>It<span>em 1. Busi</span>ness</p>"
        + para("We make widgets.")
        + a("i1a")
        + "<p>Item 1A. Risk Factors</p>"
        + para("Risky.")
        + a("i2")
        + "<p>Item 2. Properties</p>"
        + para("Office.")
        + a("i7")
        + "<p>Item 7. Management's Discussion and Analysis</p>"
        + para("Revenue grew.")
        + a("i7a")
        + "<p>Item 7A. Quantitative and Qualitative Disclosures</p>"
        + para("Rates.")
        + "</body></html>"
    )


def test_inline_tags_do_not_split_words():
    assert html_to_text("<p>It<span>em 1. Busi</span>ness</p>").startswith("Item 1. Business")


def test_tenk_sections_by_anchor_with_title_only_links():
    raw = _tenk_html(True)
    assert toc_anchor_ids(raw) == {
        "item_1": "i1",
        "item_1a": "i1a",
        "item_2": "i2",
        "item_7": "i7",
        "item_7a": "i7a",
    }
    secs = extract_10k_sections(raw)
    assert {k: s.method for k, s in secs.items()} == {
        "item_1": "anchor",
        "item_1a": "anchor",
        "item_7": "anchor",
    }
    assert secs["item_1"].text.startswith("Item 1. Business") and "Risky" not in secs["item_1"].text
    assert "Rates" not in secs["item_7"].text and "Revenue grew" in secs["item_7"].text


def test_tenk_sections_regex_fallback_skips_toc():
    secs = extract_10k_sections(_tenk_html(False))
    assert set(secs) == {"item_1", "item_1a", "item_7"}
    assert all(s.method == "regex" for s in secs.values())
    assert "We make widgets" in secs["item_1"].text and "Risky" not in secs["item_1"].text


def test_tenq_mdna_regex():
    raw = (
        "<p>Item 2. Management's Discussion and Analysis 20</p>"  # 목차
        + "<p>Item 2. Management's Discussion and Analysis of Financial Condition</p>"
        + "<p>Cash burn fell. "
        + "y" * 600
        + "</p>"
        + "<p>Item 3. Quantitative and Qualitative Disclosures</p><p>none</p>"
    )
    sec = extract_10q_mdna(raw)
    assert sec and sec.method == "regex" and "Cash burn fell" in sec.text and "none" not in sec.text


def _fact(start, end, val, filed="2026-01-01"):
    return xbrl.Fact(
        date.fromisoformat(start) if start else None,
        date.fromisoformat(end),
        val,
        date.fromisoformat(filed),
        "10-Q",
        2025,
        None,
        "t",
    )


def test_quarterly_from_ytd_differences_and_q4_from_annual():
    facts = [
        _fact("2025-01-01", "2025-03-31", 10),
        _fact("2025-01-01", "2025-06-30", 25),  # 6M → Q2 = 15
        _fact("2025-01-01", "2025-09-30", 45),  # 9M → Q3 = 20
        _fact("2025-01-01", "2025-12-31", 70),  # FY → Q4 = 25
    ]
    q = xbrl.quarterly_series(facts)
    assert {k.isoformat(): v for k, v in q.items()} == {
        "2025-03-31": 10,
        "2025-06-30": 15,
        "2025-09-30": 20,
        "2025-12-31": 25,
    }
    assert xbrl.quarterly_series(facts, additive=False) == {date(2025, 3, 31): 10}


def test_latest_filed_value_wins():
    facts = [
        _fact("2025-01-01", "2025-03-31", 10, "2025-05-01"),
        _fact("2025-01-01", "2025-03-31", 12, "2026-02-01"),
    ]
    assert xbrl.quarterly_series(facts) == {date(2025, 3, 31): 12}


def test_price_metrics_and_event_window():
    rows = [
        {"trade_date": f"2026-{m:02d}-{d:02d}", "close": float(c), "volume": 1000}
        for (m, d), c in zip(
            [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (1, 12)],
            [10, 11, 12, 9, 8, 8, 9, 10, 12, 13, 14],
            strict=True,
        )
    ]
    m = price_metrics(rows, shares_outstanding=1_000_000)
    assert m["last_close"] == 14 and m["market_cap"] == 14_000_000
    assert m["high_52w"] == 14 and m["low_52w"] == 8 and abs(m["max_drawdown_1y"] - (8 / 12 - 1)) < 1e-9
    ev = event_window_returns(rows, "2026-01-06", before=3, after=3)
    assert (
        ev["t_date"] == "2026-01-06"
        and abs(ev["ret_post_3d"] - (10 / 8 - 1)) < 1e-9
        and abs(ev["ret_pre_3d"] - (8 / 11 - 1)) < 1e-9
    )


def test_extract_json_prefers_last_fenced_block_and_tolerates_prose():
    text = 'Thinking... ```json\n{"a": 1}\n``` more ```json\n{"b": 2, "c": "x\ny"}\n``` done'
    assert extract_json(text) == {"b": 2, "c": "x\ny"}
    assert extract_json('prose {"k": [1,2]} tail') == {"k": [1, 2]}


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _resp(text, stop="end_turn", searches=0, citations=None):
    block = _Obj(type="text", text=text, citations=citations or [])
    usage = _Obj(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        server_tool_use=_Obj(web_search_requests=searches),
    )
    return _Obj(content=[block], usage=usage, stop_reason=stop)


def test_llm_continues_pause_turn_and_sums_usage(monkeypatch):
    from wsj.briefs.llm import LLM

    llm = LLM.__new__(LLM)
    cit = _Obj(type="web_search_result_location", url="https://x.test/a", title="A", cited_text="quoted")
    fake = _FakeMessages(
        [
            _resp("searching...", stop="pause_turn", searches=3, citations=[cit]),
            _resp('```json\n{"ok": true}\n```', searches=2),
        ]
    )
    llm._client = _Obj(messages=fake)
    obj, comps = llm.complete_json(
        "sys", "user", "claude-sonnet-5-5", "repair {error}", web_search_max_uses=8, max_tokens=1000
    )
    assert obj == {"ok": True}
    c = comps[0]
    assert c.web_searches == 5 and c.input_tokens == 200 and c.output_tokens == 100
    assert c.citations[0]["url"] == "https://x.test/a"
    assert len(fake.calls) == 2 and fake.calls[1]["messages"][-1]["role"] == "assistant"
    assert fake.calls[0]["tools"][0]["max_uses"] == 8
    assert abs(c.cost_usd - (200 * 2 + 100 * 10) / 1e6 - 0.05) < 1e-9


def test_llm_repairs_bad_json_without_tools():
    from wsj.briefs.llm import LLM

    llm = LLM.__new__(LLM)
    fake = _FakeMessages([_resp("not json at all"), _resp('{"fixed": 1}')])
    llm._client = _Obj(messages=fake)
    obj, comps = llm.complete_json(
        "sys",
        "user",
        "claude-sonnet-5-5",
        "repair: {error}",
        web_search_max_uses=4,
        max_tokens=500,
        thinking_budget=2000,
    )
    assert obj == {"fixed": 1} and len(comps) == 2
    assert "tools" not in fake.calls[1] and fake.calls[1]["messages"][1]["role"] == "assistant"
    assert fake.calls[0]["thinking"] == {"type": "adaptive"} and fake.calls[0]["max_tokens"] == 500


def test_budget_brief_defaults():
    from wsj.briefs.build import BriefOptions
    from wsj.runner import build_parser

    opt = BriefOptions()
    assert (opt.model, opt.research_model, opt.critique_model) == ("haiku", "haiku", "haiku")
    assert opt.research_searches == 4
    assert opt.thinking_budget == 0
    args = build_parser().parse_args(["briefs", "build"])
    assert (args.model, args.research_model, args.critique_model) == (None, "haiku", "haiku")
    assert args.searches == 4 and args.effort == "medium"


def test_low_cost_thinking_mode_and_pricing():
    from wsj.briefs.llm import Completion, LLM

    haiku = Completion(text="ok", model="claude-haiku-5-5", input_tokens=10_000, output_tokens=2000)
    assert abs(haiku.cost_usd - 0.002) < 1e-9

    llm = LLM.__new__(LLM)
    fake = _FakeMessages([_resp('{"ok": true}'), _resp('{"ok": true}')])
    llm._client = _Obj(messages=fake)
    llm.complete("sys", "user", "claude-haiku-5-5", effort="low", minimize_thinking=True)
    llm.complete("sys", "user", "claude-sonnet-5-5", effort="medium", minimize_thinking=True)
    assert fake.calls[0]["thinking"] == {"type": "disabled"}
    assert fake.calls[1]["thinking"] == {"type": "between_tools"}
    assert fake.calls[1]["output_config"] == {"effort": "medium"}


def test_json_failure_preserves_cost():
    from wsj.briefs.llm import JSONGenerationError, LLM

    llm = LLM.__new__(LLM)
    fake = _FakeMessages([_resp("not json"), _resp("still not json")])
    llm._client = _Obj(messages=fake)
    try:
        llm.complete_json("sys", "user", "claude-haiku-5-5", "fix: {error}", max_tokens=1000)
        assert False, "expected JSONGenerationError"
    except JSONGenerationError as exc:
        assert len(exc.completions) == 2
        assert sum(x.output_tokens for x in exc.completions) == 100
