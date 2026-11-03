"""단서 수집 (ADR-0028 2단계) — 출처 우선, 시세 기사만 규칙으로 버리고 어휘는 태깅에만."""

import json
from datetime import UTC, datetime

from wsj.ecosystems import clues as C

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>LS머트리얼즈, 데이터센터용 랙형 울트라커패시터 출시</title><link>https://x.test/a?utm_source=rss</link><pubDate>Thu, 29 Oct 2026 01:00:00 GMT</pubDate><description>신제품</description></item>
<item><title>[특징주] LS머트리얼즈 주가 급등</title><link>https://x.test/b</link><pubDate>Thu, 29 Oct 2026 02:00:00 GMT</pubDate></item>
<item><title>오래된 글</title><link>https://x.test/c</link><pubDate>Thu, 01 Jan 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""


class FakeHttp:
    def get_text(self, url, headers=None):
        return RSS


class FakeStore:
    def __init__(self):
        self.saved = []

    def select(self, table, columns=None, filters=None, limit=None, order=None):
        if table == "ideas.company_events":
            return [{"company_id": "company:ls_materials", "kind": "news", "published_at": "2026-10-29T00:00:00+00:00",
                     "title": "LS Materials Co. Ltd. News — KRX:417200", "url": "https://tv.test/x", "publisher": "TradingView", "lang": "en", "importance": 1},
                    {"company_id": "company:ls_materials", "kind": "news", "published_at": "2026-10-29T00:00:00+00:00",
                     "title": "LS머트리얼즈, 미 수소연료전지에 750억 수주", "url": "https://lead.test/y", "publisher": "리드경제", "lang": "ko", "importance": 2}]
        if table == "ideas.supply_chain_issues":
            return []
        if table == "ideas.clues":
            return [{"url": "https://lead.test/y"}]  # 이미 본 것
        return []

    def upsert(self, table, rows, conflict):
        self.saved += rows
        return len(rows)


def _src(**kw):
    return C.Source(**({"id": "thelec_kr", "name": "디일렉", "type": "rss", "url": "https://x.test/rss", "lang": "ko", "region": "KR", "kinds": ["trade_press"]} | kw))


def test_noise_rules():
    assert C.is_noise("[특징주] 티엘비 주가 급등")
    assert C.is_noise("LS Materials Co. Ltd. News — KRX:417200", "TradingView")
    assert C.is_noise("3 AI Stocks to Buy Now")
    assert not C.is_noise("티엘비, SOCAMM2 기판 수주 급증")          # 사건어가 있으면 시세어가 섞여도 남긴다
    assert not C.is_noise("Rambus unveils DDR5 MRDIMM chipset")


def test_fetch_source_keeps_new_items_and_strips_tracking():
    since = datetime(2026, 10, 28, tzinfo=UTC)
    got = C.fetch_source(FakeHttp(), _src(), since)
    assert [c.url for c in got] == ["https://x.test/a", "https://x.test/b"]   # 오래된 글은 빠지고, 시세 기사는 여기서 아직 안 버린다
    assert got[0].source_kind == "trade_press" and got[0].region == "KR"


def test_collect_marks_noise_and_rule_keep_without_llm(monkeypatch):
    monkeypatch.setattr(C, "load_graph", lambda: {"nodes": [{"id": "company:ls_materials", "kind": "company", "label": "LS Materials"}], "edges": []})
    monkeypatch.setattr(C, "load_registry", lambda path=None: [_src()])
    monkeypatch.setattr(C, "tag", lambda clues, graph: None)
    store = FakeStore()
    stats = C.run(FakeHttp(), store, days=(datetime.now(UTC) - datetime(2026, 10, 28, tzinfo=UTC)).days + 1, use_llm=False, model="haiku", api_key=None)
    by_url = {r["url"]: r for r in store.saved}
    assert "https://lead.test/y" not in by_url                                  # 이미 본 단서는 다시 쓰지 않는다
    assert by_url["https://x.test/a"]["relevant"] is True
    assert by_url["https://x.test/b"]["relevant"] is False and by_url["https://x.test/b"]["note"] == "시세·지분 기사"
    assert by_url["https://tv.test/x"]["relevant"] is False                      # 시세 집계 사이트
    assert stats["noise"] == 2 and stats["new"] == 3   # a·b·tv (y 는 이미 봤다)


def test_rule_keep_broad_sources_need_vocabulary():
    c = C.Clue("https://t.test", "New gaming laptop", "", None, "toms", "Tom's Hardware", "trade_press", broad=True)
    assert not C.rule_keep(c)
    c.nodes.add("component:hbm_stack")
    assert C.rule_keep(c)
    assert C.rule_keep(C.Clue("https://u.test", "Anything", "", None, "thelec_kr", "디일렉", "trade_press"))


def test_registry_file_is_valid():
    srcs = C.load_registry()
    assert srcs and not C.check_registry(srcs)
    assert sum(1 for s in srcs if s.enabled and s.type in C.SUPPORTED) >= 40


def test_registry_check_catches_duplicates(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"sources": [{"id": "a_b", "url": "https://x"}, {"id": "a_b", "url": "https://x"}]}), encoding="utf-8")
    errs = C.check_registry(C.load_registry(p))
    assert any("id 중복" in e for e in errs) and any("url 중복" in e for e in errs)


def test_parse_feed_reads_rss1_rdf():
    from wsj.ecosystems.sources import parse_feed

    rdf = ('<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><title>x</title></channel><item><title>HBM 新工場</title>'
           '<link>https://x.jp/a</link><dc:date>2026-10-29T10:00:00+09:00</dc:date><description>d</description></item></rdf:RDF>')
    got = parse_feed(rdf)
    assert got and got[0][0] == "https://x.jp/a" and got[0][1] == "HBM 新工場" and got[0][2] is not None


def _clue(url, title, relevant=True, broad=False):
    return C.Clue(url, title, "", None, "s", "S", "trade_press", broad=broad, relevant=relevant)


def test_mark_duplicates_keeps_one_copy_per_title():
    a = _clue("https://news.google.com/rss/articles/AAA", "SKC, 3분기 영업손실 496억원…전년比 9.7% 줄여 - 전자신문")
    b = _clue("https://www.etnews.com/1", "SKC, 3분기 영업손실 496억원…전년比 9.7% 줄여")
    c = _clue("https://news.google.com/rss/articles/BBB", "SKC, 3분기 영업손실 496억원…전년比 9.7% 줄여 - 뉴스1")
    other = _clue("https://x.test/z", "SKC, 유리기판 고객 인증 통과")
    assert C.mark_duplicates([a, b, c, other]) == 2
    assert b.relevant and not a.relevant and not c.relevant and other.relevant   # 원문 주소를 남긴다
    assert a.note == "같은 제목 중복"


def test_mark_duplicates_prefers_already_saved_copy():
    old = _clue("https://news.google.com/rss/articles/OLD", "Samsung Electronics Announces Third Quarter 2026 Results")
    new = _clue("https://news.samsung.com/global/q3", "Samsung Electronics Announces Third Quarter 2026 Results")
    assert C.mark_duplicates([new, old], seen={old.url}) == 1
    assert not new.relevant          # 어제 이미 저장한 글과 같은 제목이면 새 주소는 저장만 하고 보이지 않게
    short = [_clue("https://a.test/1", "속보"), _clue("https://a.test/2", "속보")]
    assert C.mark_duplicates(short) == 0   # 너무 짧은 제목은 비교하지 않는다


def test_apply_screen_minimal_drop_items_and_rule_fallback():
    keep, drop, missing = _clue("https://k.test", "Rambus MRDIMM"), _clue("https://d.test", "게임 노트북"), _clue("https://m.test", "디일렉 기사")
    C.apply_screen([keep, drop, missing], {"items": [
        {"i": 0, "keep": True, "note": "MRDIMM 칩셋 출시", "companies": [{"name": "Rambus", "ticker": "RMBS", "exchange": "Nasdaq"}]},
        {"i": 1, "keep": False}]})
    assert keep.relevant and keep.note == "MRDIMM 칩셋 출시" and keep.companies[0]["ticker"] == "RMBS"
    assert not drop.relevant and drop.note is None
    assert missing.relevant          # 응답에 빠진 글은 규칙으로 (전문 출처는 통과)
    gone = _clue("https://g.test", "아무 글", broad=True)
    C.apply_screen([gone], None)     # 묶음 호출이 실패하면 규칙으로
    assert not gone.relevant


def test_apply_screen_records_scope():
    core = C.Clue("https://a", "HBM4 ramp", "", None, "s", "S", "trade_press")
    far = C.Clue("https://b", "Humanoid actuator supply", "", None, "s", "S", "trade_press")
    none = C.Clue("https://c", "Old style item", "", None, "s", "S", "trade_press")
    C.apply_screen([core, far, none], {"items": [{"i": 0, "keep": True, "scope": "core", "note": "n"},
                                                 {"i": 1, "keep": True, "scope": "frontier", "note": "n"},
                                                 {"i": 2, "keep": True, "note": "n"}]})
    assert core.extra["scope"] == "core" and far.extra["scope"] == "frontier" and none.extra["scope"] == "core"
    assert far.row()["extra"]["scope"] == "frontier"


def test_llm_screen_runs_batches_concurrently_and_keeps_order(monkeypatch):
    import wsj.briefs.llm as L

    class FakeLLM:
        def __init__(self, key):
            pass

        def complete_json(self, system, user, model, repair, **kw):
            items = json.loads(user)
            return {"items": [{"i": x["i"], "keep": "keep" in x["title"], "note": x["title"]} for x in items]}, []

    monkeypatch.setattr(L, "LLM", FakeLLM)
    cs = [_clue(f"https://b.test/{n}", f"{'keep' if n % 2 else 'drop'} {n}") for n in range(7)]
    C.llm_screen(cs, "k", batch=2, workers=3)
    assert [c.relevant for c in cs] == [False, True, False, True, False, True, False]
    assert cs[3].note == "keep 3"


def test_llm_companies_resolve_to_graph_ids():
    from wsj.ecosystems.ontology import load_graph

    resolve = C.company_resolver(load_graph())
    assert resolve("테크윙", "089030", "KOSDAQ") == "company:techwing"
    assert resolve("Techwing", "089030", "KRX") == "company:techwing"             # 한국 안에서는 거래소 표기가 달라도
    assert resolve("Samsung Electronics", "005930", "KRX") == "company:samsung"
    assert resolve("Unknown Tiny", "999999", "KOSDAQ") is None
    c = _clue("https://r.test", "테크윙 공급계약")
    c.companies.append({"company": "company:techwing", "name": "Techwing (KOSDAQ 089030)"})
    C.apply_screen([c], {"items": [{"i": 0, "keep": True, "note": "n", "companies": [
        {"name": "테크윙", "ticker": "089030", "exchange": "KOSDAQ"}, {"name": "마이크론", "ticker": "MU", "exchange": "NASDAQ"}]}]}, resolve)
    assert [x["company"] for x in c.companies] == ["company:techwing", "company:mu"]   # 같은 회사는 한 번, 다른 회사는 id 로


def test_layers_from_kinds_and_override():
    assert _src(kinds=["standards"]).layer == "raw"
    assert _src(kinds=["release_notes"]).layer == "raw"
    assert _src(kinds=["company_newsroom"]).layer == "newsroom"
    assert _src(kinds=["trade_press"]).layer == "press"
    assert _src(kinds=["research", "market_data"], layer_override="press").layer == "press"   # 리서치 회사 보도자료는 업계지로
    got = C.fetch_source(FakeHttp(), _src(kinds=["standards"]), datetime(2026, 10, 28, tzinfo=UTC))
    assert got[0].layer == "raw" and got[0].row()["extra"]["layer"] == "raw"


def test_raw_specialist_sources_survive_the_topic_screen():
    raw = C.Clue("https://jedec.test/jesd", "JC-45 ballot: SOCAMM2 rev", "", None, "jedec", "JEDEC", "standards", layer="raw")
    raw_broad = C.Clue("https://arxiv.test/1", "A theorem on graphs", "", None, "arxiv", "arXiv", "research", broad=True, layer="raw")
    press = C.Clue("https://p.test/1", "New gaming laptop", "", None, "toms", "Tom's", "trade_press", broad=True)
    C.screen([raw, raw_broad, press], use_llm=False, api_key=None, model="haiku", graph={"nodes": []})
    assert raw.relevant and raw.screen == "kept"
    assert not raw_broad.relevant and raw_broad.screen == "topic_drop"        # 종합 원본(arXiv 분야 전체)은 분류기를 거친다
    assert not press.relevant and press.note == "주제 밖(분류기)"


def test_exempt_overrides_llm_drop(monkeypatch):
    raw = C.Clue("https://ercot.test/nogrr", "NOGRR 282 comments", "", None, "ercot", "ERCOT", "policy", layer="raw")
    monkeypatch.setattr(C, "llm_screen", lambda todo, *a, **k: [setattr(c, "relevant", False) for c in todo] and {})
    monkeypatch.setattr(C, "company_resolver", lambda g: None)
    C.screen([raw], use_llm=True, api_key="k", model="haiku", graph={"nodes": []})
    assert raw.relevant and raw.screen == "raw_exempt"
    many = [C.Clue(f"https://r.test/{i}", f"r{i}", "", None, "s", "S", "standards", layer="raw") for i in range(5)]
    assert len(C.mark_exempt(many, cap=3)) == 3


def test_body_targets_and_fetch_bodies():
    kept = [C.Clue("https://news.google.com/rss/articles/X", "g", "", None, "company_feed", "x", "company_feed", layer="company"),
            C.Clue("https://etnews.test/1", "p", "", None, "etnews", "전자신문", "trade_press", layer="press"),
            C.Clue("https://jedec.test/a", "s", "", None, "jedec", "JEDEC", "standards", layer="raw"),
            C.Clue("https://x.test/doc.pdf", "pdf", "", None, "s", "S", "standards", layer="raw")]
    tg = C.body_targets(kept)
    assert [c.url for c in tg] == ["https://jedec.test/a", "https://etnews.test/1"]      # 원본 먼저, 중계 주소·PDF 제외
    para = "<p>" + "SOCAMM2 는 LPDDR5X 기반 모듈로, 서버 메모리 슬롯 구성을 바꾼다. " * 8 + "</p>"
    pages = {"https://jedec.test/a": (200, "text/html; charset=utf-8", f"<html><nav>메뉴 메뉴</nav><article>{para}</article></html>"),
             "https://etnews.test/1": (403, "text/html", "")}
    rows = {r["url"]: r for r in C.fetch_bodies(tg, lambda u: pages[u], workers=2)}
    assert rows["https://jedec.test/a"]["status"] == "ok" and "LPDDR5X" in rows["https://jedec.test/a"]["body"]
    assert "메뉴" not in rows["https://jedec.test/a"]["body"]
    assert rows["https://etnews.test/1"]["status"] == "http_403" and rows["https://etnews.test/1"]["body"] is None


def test_extract_text_keeps_paragraphs_and_numeric_cells():
    from wsj.ecosystems.textract import extract_text

    html = ("<html><head><title>NOGRR 282</title><script>var a=1</script></head><body><header>Home | About</header>"
            "<h1>Voltage ride-through for large loads</h1><p>" + "ERCOT staff proposes that large electronic loads remain connected during faults. " * 3 +
            "</p><table><tr><th>Date</th><td>2026-10-28</td></tr><tr><td>Status</td><td>Pending PRS</td></tr></table>"
            "<footer>Copyright</footer></body></html>")
    title, body = extract_text(html)
    assert title == "NOGRR 282"
    assert "ride-through" in body and "2026-10-28" in body and "remain connected" in body
    assert "Copyright" not in body and "var a" not in body and "Home | About" not in body
