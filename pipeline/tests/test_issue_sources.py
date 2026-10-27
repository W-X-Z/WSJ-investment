from datetime import UTC, date, datetime, timedelta

from wsj.ecosystems import indicators, issues, sources
from wsj.ecosystems.ontology import load_graph

DX_PAGE = """
<div>Last Update: Oct.26 2026    18:10 (GMT+8)</div>
<table><tr><th>Item</th><th>Daily High</th><th>Daily Low</th><th>Session High</th><th>Session Low</th><th>Session Average</th><th>Session Change</th><th>History</th></tr>
<tr><td><a href="#">DDR5 16Gb (2Gx8) 4800/5600</a></td><td>72.00</td><td>47.00</td><td>72.00</td><td>47.00</td><td>61.333</td><td>0.11 %</td><td></td></tr>
<tr><td>DDR4 8Gb (1Gx8) 3200</td><td>85.00</td><td>25.50</td><td>85.00</td><td>25.50</td><td>47.000</td><td>-4.23 %</td><td></td></tr></table>
<div>Last Update: Oct.19 2026    14:40 (GMT+8)</div>
<table><tr><th>Item</th><th>Weekly High</th><th>Weekly Low</th><th>Session High</th><th>Session Low</th><th>Session Average</th><th>Average Change</th><th>History</th></tr>
<tr><td>512Gb TLC</td><td>21.00</td><td>16.80</td><td>21.00</td><td>16.80</td><td>18.592</td><td>-1.28 %</td><td></td></tr></table>
"""


def test_all_indicator_nodes_exist_in_graph():
    ids = {n["id"] for n in load_graph()["nodes"]}
    assert not [(i.indicator_id, n) for i in indicators.INDICATORS for n in i.nodes + i.companies if n not in ids]
    assert len({i.indicator_id for i in indicators.INDICATORS}) == len(indicators.INDICATORS)


def test_parse_dramexchange_attaches_table_dates():
    rows = indicators.parse_dramexchange(DX_PAGE)
    assert rows["DDR5 16Gb (2Gx8) 4800/5600"] == (date(2026, 10, 26), 61.333, 0.11)
    assert rows["512Gb TLC"][0] == date(2026, 10, 19)


def test_parse_fred_and_tw_revenue():
    s = indicators.parse_fred_csv("observation_date,PCOPPUSDM\n2026-08-01,9800.5\n2026-09-01,.\n2026-10-01,10100\n")
    assert s == [(date(2026, 8, 1), 9800.5), (date(2026, 10, 1), 10100.0)]
    rows = [{"資料年月": "11509", "公司代號": "2308", "公司名稱": "台達電", "營業收入-當月營收": "65399563",
             "營業收入-上月比較增減(%)": "1.25", "營業收入-去年同月增減(%)": "14.6", "累計營業收入-當月累計營收": "1", "累計營業收入-前期比較增減(%)": "37.2"},
            {"資料年月": "11509", "公司代號": "9999", "營業收入-當月營收": "1"}]
    pts = indicators.parse_tw_revenue(rows, {"2308"})
    assert len(pts) == 1 and pts[0].as_of == date(2026, 9, 1) and pts[0].yoy_pct == 14.6


def test_notable_thresholds():
    P = indicators.Point
    pts = [P("tw:6223", date(2026, 9, 1), 1000, 3.0, 82.2), P("tw:2308", date(2026, 9, 1), 1000, 1.2, 14.6),
           P("dx:ddr5_16gb", date(2026, 10, 26), 66.0, 0.1), P("fred:PCOPPUSDM", date(2026, 9, 1), 10000, 2.0, 4.0)]
    hist = {"dx:ddr5_16gb": [(date(2026, 10, 19), 60.0), (date(2026, 10, 26), 66.0)]}
    out = {n["indicator_id"]: n for n in indicators.notable(pts, hist)}
    assert "tw:6223" in out and "YoY +82.2%" in out["tw:6223"]["title"]
    assert "tw:2308" not in out
    assert "1주 +10.0%" in out["dx:ddr5_16gb"]["title"]
    assert "전월 +2.0%" in out["fred:PCOPPUSDM"]["title"]


def test_parse_feed_rss_and_atom():
    rss = """<rss><channel><item><title>SK hynix ships HBM4</title><link>https://a/1</link><pubDate>Mon, 26 Oct 2026 01:00:00 GMT</pubDate>
             <description>&lt;p&gt;12-high&lt;/p&gt;</description></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Hybrid bonding yield</title><link href="https://b/2"/>
              <published>2026-10-20T00:00:00Z</published><summary>Cu-Cu</summary></entry></feed>"""
    a = sources.parse_feed(rss)
    b = sources.parse_feed(atom)
    assert a[0][0] == "https://a/1" and a[0][3] == "12-high" and a[0][2].day == 26
    assert b[0][:2] == ("https://b/2", "Hybrid bonding yield")


def test_select_candidates_keeps_quota_types():
    now = datetime(2026, 10, 27, tzinfo=UTC)

    def cand(st, imp):
        m = issues.Item(f"https://x/{st}{imp}{id(object())}", "t", now - timedelta(days=1), "p", st)
        return {"rule_importance": imp, "raw": imp, "members": [m]}

    cands = [cand("news", 6) for _ in range(100)] + [cand("research", 2), cand("data", 3)]
    out = issues.select_candidates(cands, 40)
    types = {m.source_type for c in out for m in c["members"]}
    assert {"research", "data"} <= types
    assert len(out) <= 40 + sum(issues.QUOTA.values()) // 2


def test_research_filter_requires_phrase_and_relevant_venue():
    now = datetime(2026, 10, 27, tzinfo=UTC)
    ok = issues.Item("https://arxiv.org/abs/1", "Hybrid bonding yield", now, "arXiv", "research", "Cu-Cu hybrid bonding pitch", "hybrid bonding")
    loose = issues.Item("https://doi.org/2", "Battery cathodes", now, "IEEE Access", "research", "uses hybrid bonding once", "hybrid bonding")
    offtopic = issues.Item("https://doi.org/3", "Hybrid bonding in timber", now, "Wood Science", "research", "", "hybrid bonding")
    assert issues.phrase_in(ok) and not issues.phrase_in(loose) and not issues.phrase_in(offtopic)
    assert not sources.INDUSTRY.search("State Key Laboratory for Advanced Metals") and sources.INDUSTRY.search("Samsung Electronics")
