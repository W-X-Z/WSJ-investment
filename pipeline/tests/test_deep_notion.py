from wsj.deep.notion_page import esc, markdown, page

SPEC = {
    "symbol": "AXTI", "market": "us", "as_of": "2026-11-09", "title": "AXT — 테스트", "stars": 3,
    "verdict": "v", "candidate": {"report_id": "candidates:2026-11-09", "id": "e4p1-axti"},
    "sections": {"summary": "★3 · NASDAQ AXTI · 시총 $25.7억\n본문 11~13배", "conclusion": "- a",
                 "price_story": "**x**", "risks": "r <script>"},
    "sources": [{"url": "https://e.com/a", "title": "T [1]", "published_at": "2026-10-29"}],
}


def test_escape_dollar_tilde_tags():
    assert esc("$5 1~2 <x> <b>ok</b>") == "\\$5 1\\~2 &lt;x> <b>ok</b>"


def test_markdown_order_and_memo():
    md = markdown(SPEC, image="file-upload://abc")
    assert md.index("## 결론") < md.index("## 주가 이슈") < md.index("## 리스크")
    assert md.index('<image source="file-upload://abc"') < md.index("**x**")
    assert md.rstrip().endswith("## 사용자 메모")
    assert "[T (1)](https://e.com/a) · 2026-10-29" in md
    assert "\\$25.7억" in md and "&lt;script>" in md


def test_page_properties():
    pg = page(SPEC, market_cap_usd=2.57e9, candidate_page="https://app.notion.com/p/x")
    p = pg["properties"]
    assert pg["report_id"] == "idea:us:axti:2026-11-09"
    assert p["★"] == "★3" and p["시장"] == "미국" and p["후보 ID"] == "e4p1-axti"
    assert p["시총(USD)"] == 2570000000 and p["후보"] == ["https://app.notion.com/p/x"]
