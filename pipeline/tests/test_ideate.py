from wsj.ideate.check import report_row, validate
from wsj.ideate.digest import render, select

ROWS = [
    {"clue_id": 1, "title": "KV cache drives SSD demand", "summary": "agentic AI", "source_kind": "trade_press",
     "source_name": "DIGITIMES", "relevant": True, "published_at": "2026-11-06"},
    {"clue_id": 2, "title": "KV cache drives SSD demand!", "summary": "dup", "source_kind": "trade_press",
     "source_name": "Other", "relevant": True, "published_at": "2026-11-06"},
    {"clue_id": 3, "title": "Some arXiv paper", "summary": "abstract", "source_kind": "research",
     "source_name": "arXiv", "relevant": False, "published_at": "2026-11-06"},
    {"clue_id": 4, "title": "Noise headline", "summary": "x", "source_kind": "trade_press",
     "source_name": "X", "relevant": False, "published_at": "2026-11-06"},
    {"clue_id": 5, "title": "my own research", "summary": "x", "source_kind": "agent_research",
     "source_name": "sec", "relevant": True, "published_at": "2026-11-06"},
]


def test_digest_rules():
    g = select(ROWS)
    assert [r["clue_id"] for r in g["trade_press"]] == [1]          # 중복 제거, 비관련 업계지 제외
    assert [r["clue_id"] for r in g["research"]] == [3]             # 논문은 관련 표시 없어도 제목
    assert "agent_research" not in g
    md = render(ROWS, 3, "2026-11-09")
    assert "[c1]" in md and "— agentic AI" in md
    assert "[c3]" in md and "abstract" not in md                    # 비관련 논문은 제목만


SPEC = {"as_of": "2026-11-09", "seeds": [
    {"id": "s1", "headline": "h", "hypothesis": "x", "archetype": "bottleneck", "status": "selected",
     "companies": [{"name": "A", "ticker": "AAA", "market": "us",
                    "resolved": {"symbol": "AAA", "market": "us", "name": "A", "exchange": "NYSE"}}]}]}


def test_validate_and_row():
    assert validate(SPEC) == []
    bad = {"as_of": "x", "seeds": [{"id": "s1", "headline": "h", "hypothesis": "x", "archetype": "nope",
                                    "companies": [{"name": "B", "market": "jp"}]}]}
    errs = validate(bad)
    assert any("archetype" in e for e in errs) and any("market" in e for e in errs)
    row = report_row(SPEC)
    assert row["report_id"] == "seeds:2026-11-09" and row["kind"] == "screen"
    assert row["subjects"] == ["ticker:us:aaa"] and "선택 1" in row["title"]
