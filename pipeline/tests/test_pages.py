"""원본 페이지 변화 감지 — 처음엔 기준선만, 다음부터 새 링크는 하나씩, 본문 변화는 페이지마다 하나로."""

from wsj.ecosystems import pages as P
from wsj.ecosystems.clues import Source

V1 = """<html><head><title>JC-45</title></head><body><nav><a href="/about">About</a></nav>
<h2>Recent Documents</h2><ul>
<li><a href="/standards/jesd328">JESD328 SOCAMM2 module standard</a> Oct 2026</li>
<li><a href="/standards/jesd318">JESD318 CAMM2 common standard</a> Sep 2026</li></ul>
<p>Committee JC-45 develops standards for DRAM modules used in servers and client systems worldwide.</p></body></html>"""

V2 = V1.replace("<ul>", '<ul><li><a href="/standards/jesd330">JESD330 CXL memory module raw card annex</a> Nov 2026</li>').replace(
    "</ul>", "</ul><p>Ballot JC-45.6 opened for the LPDDR6 SOCAMM variant with a new 14-layer raw card reference design.</p>")


def _src(**kw):
    return Source(**({"id": "jedec_jc45", "name": "JEDEC JC-45", "type": "html_diff", "url": "https://www.jedec.org/committees/jc-45",
                      "kinds": ["standards"]} | kw))


def test_snapshot_skips_nav_and_absolutizes_links():
    s = P.snapshot(V1, "https://www.jedec.org/committees/jc-45")
    urls = [u for u, _ in s.links]
    assert "https://www.jedec.org/standards/jesd328" in urls and not any("about" in u for u in urls)
    assert any("DRAM modules" in x for x in s.lines)


def test_first_run_is_baseline_then_changes_become_clues():
    base = "https://www.jedec.org/committees/jc-45"
    assert P.diff(None, P.snapshot(V1, base)) == ([], [])
    prev = P.state_of(P.snapshot(V1, base))
    new_lines, new_links = P.diff(prev, P.snapshot(V2, base))
    assert [u for u, _ in new_links] == ["https://www.jedec.org/standards/jesd330"]
    assert len(new_lines) == 1 and "LPDDR6 SOCAMM" in new_lines[0]        # 새 링크가 든 목록 줄은 본문 변화로 다시 세지 않는다
    clues, bodies = P.to_clues(_src(), base, P.snapshot(V2, base), new_lines, new_links)
    link_clue, page_clue = clues
    assert link_clue.url.endswith("/jesd330") and link_clue.layer == "raw" and "CXL memory module" in link_clue.title
    assert page_clue.url.startswith(base + "#changed-") and page_clue.title.startswith("JEDEC JC-45 페이지 변경")
    assert bodies[0]["url"] == page_clue.url and "14-layer" in bodies[0]["body"]


def test_mass_new_links_become_one_page_change():
    many = [(f"https://x.test/doc{i}", f"Document number {i} title") for i in range(P.MAX_NEW_LINKS + 5)]
    clues, _ = P.to_clues(_src(), "https://x.test/list", P.Snapshot(), [], many)
    assert len(clues) == 1 and "새 링크" in clues[0].summary


class _Http:
    def __init__(self, html):
        self.html = html

    def get_text(self, url, headers=None):
        return self.html


class _Store:
    def __init__(self):
        self.state = {}

    def get_watermark(self, key):
        return self.state.get(key, {})

    def set_watermark(self, key, wm):
        self.state[key] = wm


def test_collect_pages_commits_state_only_when_asked():
    store = _Store()
    clues, bodies, states, stats = P.collect_pages(_Http(V1), store, [_src()])
    assert clues == [] and stats["baseline"] == ["jedec_jc45"]
    P.commit_states(store, states)
    clues, bodies, states, stats = P.collect_pages(_Http(V2), store, [_src()])
    assert len(clues) == 2 and stats["pages"]["jedec_jc45"]["new_links"] == 1
    clues_again, *_ = P.collect_pages(_Http(V2), store, [_src()])
    assert len(clues_again) == 2          # 상태를 쓰지 않았으면 다음 실행이 같은 변화를 다시 낸다


CARDS = """<html><body><h2>News releases</h2><div class="list">
<a href="/news/q1-fy27"><div class="cat">Financial</div><div class="t">Lumentum Announces First Quarter of Fiscal Year 2027 Financial Results</div><span class="d">November 02, 2026</span><span>Read More</span></a>
<a href="/news/ocp-demo"><div class="cat">Financial</div><div class="t">Lumentum, Astera Labs, and Corning to Demonstrate 1060 nm VCSEL-Based PCIe over Optics</div><span class="d">October 12, 2026</span><span>Read More</span></a>
<a href="/news/hbm"><span>HBM4</span> memory update</a>
<a href="/news?page=2">next ›</a><a href="/news?page=20">last »</a><a href="/news?page=0">« first</a>
</div></body></html>"""


def test_card_links_split_title_date_and_skip_pagination():
    s = P.snapshot(CARDS, "https://www.lumentum.com/news")
    links = dict(s.links)
    assert links["https://www.lumentum.com/news/q1-fy27"] == "Lumentum Announces First Quarter of Fiscal Year 2027 Financial Results"
    assert links["https://www.lumentum.com/news/hbm"] == "HBM4 memory update"         # 제목 안 강조는 잇는다
    assert not any("page=" in u for u in links)                                          # next › · last » · « first
    assert s.dates["https://www.lumentum.com/news/ocp-demo"].date().isoformat() == "2026-10-12"


def test_old_dated_link_is_not_a_new_item():
    from datetime import UTC, datetime

    base = "https://www.lumentum.com/news"
    cur = P.snapshot(CARDS, base)
    clues, _ = P.to_clues(_src(), base, cur, [], [(u, t) for u, t in cur.links if "page=" not in u], now=datetime(2026, 11, 3, tzinfo=UTC))
    got = {c.url: c for c in clues}
    assert base + "/q1-fy27" in got and base + "/ocp-demo" not in got                    # 3주 전 글은 목록이 밀려 다시 보인 것
    assert got[base + "/q1-fy27"].published_at.date().isoformat() == "2026-11-02"


def test_parse_date_text_formats():
    assert P.parse_date_text("Oct. 7, 2026").day == 7 and P.parse_date_text("7 Oct 2026").month == 10
    assert P.parse_date_text("2026.10.06").day == 6 and P.parse_date_text("Lumentum results 2026") is None


def test_korean_pagination_links_are_not_clues():
    """산업통상부 보도자료 목록의 '마지막페이지' 같은 쪽수 이동 링크가 단서로 올라왔다 (2026-11-04)."""
    html = ('<html><body><ul><li><a href="/bbs/view?id=1">해외 생산제품과 달라도 기술·기능 유사하면 국내복귀 인정</a></li></ul>'
            '<div class="paging"><a href="?page=1">처음</a><a href="?page=1">첫페이지</a><a href="?page=2">다음페이지</a>'
            '<a href="?page=99">마지막페이지</a><a href="/bbs/list">목록</a></div></body></html>')
    s = P.snapshot(html, "https://www.motie.go.kr/kor/article/ATCL_list")
    texts = [t for _, t in s.links]
    assert texts == ["해외 생산제품과 달라도 기술·기능 유사하면 국내복귀 인정"]
