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
