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
