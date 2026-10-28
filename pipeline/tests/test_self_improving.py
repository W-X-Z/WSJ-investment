"""ADR-0017: 가격 수집 파서, 판단 점수·★ 규칙, 확인 일정, 기회 스캔, 끊긴 병목 규칙, 내부자 매수, 그래프 패치."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from wsj.ecosystems import assess as A
from wsj.ecosystems import prices as P
from wsj.ecosystems import scan
from wsj.ecosystems.ontology import dead_end_bottlenecks, load_graph

NOW = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)


# ------------------------------------------------------------------ 가격
def test_px_key_by_exchange():
    assert P.px_key("NYSE", "glw") == "GLW"
    assert P.px_key("TWSE", "2467") == "TWSE:2467"
    assert P.px_key("KOSDAQ", "086390") == "KOSDAQ:086390"
    assert P.px_key("Xetra", "SMHN") is None  # 출처 없는 거래소


def test_listings_cover_major_exchanges_and_report_the_rest():
    items, uncovered = P.listings(load_graph())
    markets = {x.market for x in items}
    assert {"us", "twse", "tpex", "kr", "cn", "jp"} <= markets
    assert uncovered.get("Xetra", 0) > 0
    assert len({x.key for x in items}) == len(items)


def test_parsers():
    twse = {"stat": "OK", "data": [["115/10/01", "878,273", "477,361,559", "545.00", "555.00", "537.00", "550.00", "+5.00", "1,004", ""]]}
    r = P.parse_twse(twse, "TWSE:2467")[0]
    assert r["trade_date"] == "2026-10-01" and r["close"] == 550.0 and r["volume"] == 878273
    tpex = {"tables": [{"data": [["115/10/02", "442", "166,422", "375.00", "380.00", "371.00", "378.00", "6.50", "910"]]}]}
    r = P.parse_tpex(tpex, "TPEx:6664")[0]
    assert r["close"] == 378.0 and r["volume"] == 442000  # 仟股
    naver = "[['날짜', '시가', '고가', '저가', '종가', '거래량', '외국인소진율'],\n[\"20260901\", 13920, 13920, 13200, 13310, 3932742, 2.2],"
    r = P.parse_naver(naver, "KOSDAQ:010170")[0]
    assert r["trade_date"] == "2026-09-01" and r["close"] == 13310.0
    tencent = {"data": {"sh603256": {"qfqday": [["2026-09-01", "150.210", "138.600", "151.990", "134.870", "229139.000"]]}}}
    r = P.parse_tencent(tencent, "sh603256", "SSE:603256")[0]
    assert r["open"] == 150.21 and r["close"] == 138.6 and r["high"] == 151.99 and r["low"] == 134.87
    kabu = ('<table class="stock_kabuka_dwm"><tbody><tr><th scope="row"><time datetime="2026-09-10">26/09/10</time></th>'
            "<td>5,393</td>\n<td>5,394</td>\n<td>5,125</td>\n<td>5,209</td>\n<td><span class=\"down\">-284</span></td>\n"
            "<td><span class=\"down\">-5.17</span></td>\n<td>35,034,000</td>\n</tr></tbody></table>")
    r = P.parse_kabutan(kabu, "TSE:5803")[0]
    assert r["trade_date"] == "2026-09-10" and r["close"] == 5209.0 and r["volume"] == 35034000


def test_backfill_plan_prioritizes_focus_and_rests_failing_tickers():
    items = [P.Listing("company:a", "NYSE", "A", "A", "us", "large"), P.Listing("company:b", "TWSE", "1", "TWSE:1", "twse", "small"),
             P.Listing("company:c", "NYSE", "C", "C", "us", "mid")]
    state = {"fails": {"C": {"n": 3, "at": "2026-10-27"}}}
    inc, back = P.plan(items, {"A": "2026-10-27"}, set(), state, date(2026, 10, 28), {"company:a"})
    assert [x.key for x, _ in inc] == ["A"]
    assert [x.key for x in back] == ["A", "TWSE:1"]  # C 는 실패 3번 → 일주일 쉼, 포커스(A) 먼저


# ------------------------------------------------------------------ 판단
def _graph():
    return {"nodes": [{"id": "bottleneck:b", "kind": "bottleneck", "label": "병목 B"}, {"id": "component:x", "kind": "component", "label": "부품 X"},
                      {"id": "company:p", "kind": "company", "label": "Primary (P)", "listing": {"ticker": "P", "exchange": "NYSE"}, "size_band": "small"},
                      {"id": "company:q", "kind": "company", "label": "Q (Q)", "listing": {"ticker": "Q", "exchange": "NYSE"}, "size_band": "mid"}],
            "edges": [{"from": "bottleneck:b", "to": "component:x", "relation": "mitigated_by"},
                      {"from": "component:x", "to": "company:p", "relation": "offered_by"}, {"from": "component:x", "to": "company:q", "relation": "offered_by"}]}


def _idea(direct_date="2026-10-25", note="3분기 매출 2.18억 달러 (+72%)", exposure=None, risk_date=None):
    comps = [{"id": "company:p", "role": "primary"}]
    if exposure:
        comps[0]["exposure"] = exposure
    return {"primary_company": "company:p", "companies": comps, "nodes": ["component:x"],
            "chain": [{"claim": "c", "evidence": [{"id": "S1", "rel": "direct", "date": direct_date, "note": note}]},
                      {"claim": "d", "evidence": [{"id": "G1", "rel": "background"}]}],
            "risks": [{"claim": "r", "evidence": [{"id": "S2", "date": risk_date, "rel": "direct"}]}, {"claim": "업계 위험", "evidence": [{"id": "S3", "date": risk_date, "rel": "industry"}]}] if risk_date else []}


def test_assessment_parts_and_score():
    st = A.Structure(_graph())
    issues = [{"latest_published_at": "2026-10-20", "nodes": ["bottleneck:b"], "sources": [{"publisher": "A"}]},
              {"latest_published_at": "2026-10-21", "nodes": ["component:x"], "sources": [{"publisher": "B"}]}]
    obs = [{"indicator_id": "obs:x", "category": "observation", "nodes": ["bottleneck:b"], "as_of": "2026-10-19", "value": 5, "label": "현물가 배수"}]
    prices = {"P": {"close": 10, "r1m": -30, "r12m": 250, "from_high": -40, "vol_ratio": 1.0, "as_of": "2026-10-27"}}
    a = A.assess(_idea(exposure={"share_pct": 55, "segment": "X"}), st, issues, obs, prices, NOW)
    p = a["parts"]
    assert p["company"]["pts"] == 4 and p["confirm"]["pts"] == 1 and p["structure"]["pts"] == 3 and p["exposure"]["pts"] == 2
    assert a["score"] == 10 and a["bottlenecks"][0]["label"] == "병목 B"
    assert any("12개월" in f for f in a["price"]["flags"]) and any("급락" in f for f in a["price"]["flags"])
    b = A.assess(_idea(direct_date="2026-09-05", note="", risk_date="2026-10-20"), st, [], [], {}, NOW)
    assert b["parts"]["company"]["pts"] == 1 and b["parts"]["counter"]["pts"] == -1 and b["price"] is None


def test_star_rule():
    assert A.apply_star_rule(3, 6)[0] == 2
    assert A.apply_star_rule(3, 8) == (3, "")
    assert A.apply_star_rule(2, 2)[0] == 1


def test_watch_normalize_carry_expire_and_grade():
    prev = [{"what": "10월 월매출", "due": "2026-11-10", "status": "hit", "graded_at": "2026-11-11", "evidence_url": "https://x"}]
    w = A.normalize_watch(["10월 월매출", {"what": "16단 양산", "due": "2027-09-01"}, {"what": "x", "due": "2026-11-20", "direction": "weaken"}], NOW, prev)
    assert w[0]["status"] == "hit" and "due" not in w[1] and w[2]["direction"] == "weaken"  # 6개월 넘는 기한은 버린다
    old = [{"what": "a", "due": "2026-10-01", "status": "pending"}, {"what": "b", "due": "2026-10-25", "status": "pending"}]
    out, changed = A.expire_watch(old, NOW)
    assert changed and out[0]["status"] == "expired" and out[1]["status"] == "pending"

    class Reg:
        items = {"S9": type("E", (), {"url": "https://ev"})()}
    ex = {"k": {"watch": [{"what": "a", "status": "pending"}, {"what": "b", "status": "pending"}]}}
    g = A.apply_grades(ex, [{"idea_key": "k", "index": 0, "status": "hit", "evidence": "S9"}, {"idea_key": "k", "what": "b", "status": "miss"}], Reg, NOW)
    assert g["k"][0]["status"] == "hit" and g["k"][0]["evidence_url"] == "https://ev" and g["k"][1]["status"] == "pending"  # 근거 없는 miss 는 무시


# ------------------------------------------------------------------ 스캔
def test_scan_leads():
    g = _graph()
    events = [{"company_id": "company:q", "published_at": "2026-10-26T00:00:00+00:00", "importance": 2, "title": "Q 수주 공시", "url": "https://q"}]
    issues = [{"title": "병목 B 심화", "latest_published_at": "2026-10-25", "nodes": ["bottleneck:b"], "importance": 7},
              {"title": "노드 없는 이슈", "latest_published_at": "2026-10-25", "nodes": []}]
    existing = [{"primary_company": "company:p", "companies": [{"id": "company:p"}]}]
    prices = {"P": {"close": 1, "r1m": 45, "vol_ratio": 1, "as_of": "2026-10-27"}}
    ld = scan.leads(g, issues, [], events, existing, prices, NOW)
    assert ld["company_leads"][0]["company_id"] == "company:q" and ld["company_leads"][0]["bottlenecks"] == ["병목 B"]
    assert ld["bottlenecks"][0]["uncovered"][0]["company_id"] == "company:q"
    assert ld["price_leads"][0]["company_id"] == "company:p"  # 소식 없이 1개월 +45%
    assert ld["untagged_issues"][0]["title"] == "노드 없는 이슈"


# ------------------------------------------------------------------ 그래프
def test_no_dead_end_bottlenecks_in_graph():
    assert dead_end_bottlenecks(load_graph()) == []


def test_dead_end_rule_detects_unconnected_bottleneck():
    g = {"nodes": [{"id": "bottleneck:z", "kind": "bottleneck", "label": "z"}], "edges": []}
    assert dead_end_bottlenecks(g) == ["bottleneck:z"]


def test_graph_patch_is_idempotent(capsys):
    from wsj.ecosystems.graph_patches import apply
    from wsj.ecosystems.graph_patches.p20261028_dead_ends_fiber_substrate import EDGES, NODES

    assert apply(NODES, EDGES, "x-si", dry_run=True) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["nodes_added"] == 0 and out["edges_added"] == 0


# ------------------------------------------------------------------ 기업 소식·지표
def test_form4_purchase_only_open_market_buys():
    from wsj.ecosystems.company_feed import form4_purchase

    xml = """<ownershipDocument><documentType>4</documentType><issuer><issuerCik>1</issuerCik><issuerName>X</issuerName><issuerTradingSymbol>X</issuerTradingSymbol></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>2</rptOwnerCik><rptOwnerName>Kim</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>CEO</officerTitle></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable><nonDerivativeTransaction><securityTitle><value>Common</value></securityTitle><transactionDate><value>2026-10-20</value></transactionDate>
    <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>P</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>10000</value></transactionShares><transactionPricePerShare><value>25</value></transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction>
    <nonDerivativeTransaction><securityTitle><value>Common</value></securityTitle><transactionDate><value>2026-10-20</value></transactionDate>
    <transactionCoding><transactionFormType>4</transactionFormType><transactionCode>S</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>500</value></transactionShares><transactionPricePerShare><value>26</value></transactionPricePerShare>
    <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode></transactionAmounts></nonDerivativeTransaction></nonDerivativeTable>
    </ownershipDocument>"""
    b = form4_purchase(xml)
    assert b["shares"] == 10000 and b["usd"] == 250000 and b["title"] == "CEO"
    assert form4_purchase(xml.replace("<transactionCode>P</transactionCode>", "<transactionCode>A</transactionCode>")) is None


def test_graph_taiwan_companies_get_revenue_history_indicators():
    from wsj.ecosystems import indicators as I

    extra = I.graph_tw_indicators()
    have = {i.match for i in I.INDICATORS}
    assert len(extra) >= 30 and not ({i.match for i in extra} & have)
    assert all(i.indicator_id.startswith("tw:") and i.companies[0].startswith("company:") for i in extra)


def test_japan_and_tpex_fallback_parsers():
    yj = ('<th class="x">2026/10/27</th><td><span class="_StyledNumber__value_1arhg_9">4,176</span></td><td><span class="_StyledNumber__value_1arhg_9">4,220</span></td>'
          '<td><span class="_StyledNumber__value_1arhg_9">4,041</span></td><td><span class="_StyledNumber__value_1arhg_9">4,092</span></td>'
          '<td><span class="_StyledNumber__value_1arhg_9">28,086,200</span></td><td><span class="_StyledNumber__value_1arhg_9">4,092</span></td></tr>')
    r = P.parse_yahoo_jp(yj, "TSE:5803")[0]
    assert r["trade_date"] == "2026-10-27" and r["close"] == 4092.0 and r["volume"] == 28086200
    t = P.parse_tpex_daily([{"Date": "1151027", "SecuritiesCompanyCode": "6664", "Open": "332.50", "High": "337.50", "Low": "324.00", "Close": "325.50",
                              "TradingShares": "218305"}])
    assert t["6664"]["trade_date"] == "2026-10-27" and t["6664"]["close"] == 325.5


def test_star3_audit_rows_still_get_an_assessment():
    from wsj.ecosystems.ideas import judged_keys

    rows = [
        {"idea_key": "a", "status": "active", "assessment": {"score": 7}},  # 작성·갱신한 행 — 판단 있음
        {"idea_key": "b", "status": "active", "stars": 2},  # ★3 점검으로 ★만 내린 행 — 판단 없음
        {"idea_key": "c", "status": "closed"},  # 종료 행
    ]
    assert judged_keys(rows) == {"a", "c"}


def test_star_rule_audit_demotes_untouched_ideas_but_never_promotes():
    from wsj.ecosystems.ideas import star_rule_audit

    ex = {k: {"idea_key": k, "status": "active", "stars": s, "title": k, "last_signal_at": "2026-10-20"}
          for k, s in [("low", 2), ("ok", 2), ("hi", 2), ("s3", 3), ("aud", 3)]}
    refresh = [{"idea_key": k, "assessment": {"score": v}} for k, v in [("low", 2), ("ok", 5), ("hi", 9), ("s3", 6), ("aud", 1)]]
    audited = [{"idea_key": "aud", "status": "active", "stars": 2, "what_changed": "직접 근거 없음"}]  # star3_audit 가 만든 행
    out = star_rule_audit(ex, audited, refresh, NOW, "m", "session")
    got = {r["idea_key"]: r["stars"] for r in out}
    assert got == {"low": 1, "s3": 2}  # ok·hi 는 그대로 (올리지 않는다)
    assert audited[0]["stars"] == 1 and "1/10" in audited[0]["what_changed"]  # 이미 있는 행은 고친다 (중복 행 없음)
