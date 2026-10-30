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
