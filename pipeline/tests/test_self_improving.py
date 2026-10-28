"""ADR-0017: 가격 수집 파서, 판단 점수·★ 규칙, 확인 일정, 기회 스캔, 끊긴 병목 규칙, 내부자 매수, 그래프 패치."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

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


def test_clean_title_drops_company_tails():
    from wsj.ecosystems.ideas import clean_title

    cos = [{"name": "Ideal Power Inc.", "ticker": "IPWR"}, {"name": "Japan Electronic Materials", "ticker": "6855"},
           {"name": "Powertech Technology", "ticker": "6239"}, {"name": "SUSS MicroTec", "ticker": "SMHN"}]
    assert clean_title("800VDC 데이터센터는 기계식 대신 반도체 차단기가 필요하다 — Ideal Power", cos) == "800VDC 데이터센터는 기계식 대신 반도체 차단기가 필요하다"
    assert clean_title("HBM 테스트 붐은 일본 프로브카드로도 번진다 (JEM)", cos[:1] + [{"name": "JEM", "ticker": "6855"}]) == "HBM 테스트 붐은 일본 프로브카드로도 번진다"
    assert clean_title("패키징이 모자라 값이 오른다 — 고객이 가격 인상을 받아들이는 力成(Powertech)", cos) == "패키징이 모자라 값이 오른다"
    # 기업 이야기가 아닌 부제·짧은 앞부분은 그대로
    assert clean_title("전력망 연결을 못 기다리는 데이터센터는 현장 가스엔진으로", cos) == "전력망 연결을 못 기다리는 데이터센터는 현장 가스엔진으로"
    assert clean_title("AXT — Ideal Power", cos) == "AXT — Ideal Power"


# ------------------------------------------------------------------ 시가총액·텐배거 조건 (ADR-0017 개정 1)
def test_tenbagger_check_and_price_flags():
    assert A.tenbagger_check(None, 50)["candidate"] is None
    assert A.tenbagger_check(6.4e8, 40)["candidate"] is True
    assert A.tenbagger_check(4.4e9, 347)["candidate"] is False  # 크다
    assert A.tenbagger_check(2e9, 482)["candidate"] is False  # 이미 5.8배
    node = {"listing": {"exchange": "TPEx", "ticker": "6664"}}
    ctx = A.price_context({"TPEx:6664": {"close": 334, "r1m": -3.7, "r3m": -5.1, "r12m": 21, "from_high": -30.4, "from_low": 40.3,
                                         "vol_ratio": 0.9, "market_cap_usd": 6.4e8}}, node)
    assert ctx["tenbagger"]["candidate"] is True and ctx["from_low"] == 40.3 and not ctx["flags"]
    ctx = A.price_context({"TPEx:6664": {"close": 86.7, "r1m": -41.8, "r3m": -43.6, "r12m": 160.6, "from_high": -70.8, "from_low": 208.8,
                                         "vol_ratio": 1.0, "market_cap_usd": 1.1e10}}, node)
    assert ctx["tenbagger"]["candidate"] is False and any("3.1배" in f for f in ctx["flags"]) and any("3개월" in f for f in ctx["flags"])


def test_facts_parsers():
    from wsj.ecosystems import facts as F

    cf = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2026-07-30", "val": 61129640, "accn": "a", "frame": "CY2026Q2I"},
        {"end": "2026-04-30", "val": 60000000, "accn": "b"},
        {"end": "2026-07-30", "val": 1000, "accn": "a", "frame": "CY2026Q2I-B"}]}}}}}
    assert F.sec_shares(cf) == (61130640.0, "2026-07-30")  # 같은 기준일의 두 클래스 합산
    assert F.parse_tencent("v_sh603256=\"1~宏和科技~603256~" + "~".join(["86.73"] + ["0"] * 40) + "~784.55~784.55~x\";") == (86.73, 784.55)
    html = '<span>発行済株式数</span><div class="tip"><a>用語</a></div><span class="n">3,175,762,284</span><span>株</span>'
    assert F.parse_yahoo_jp_shares(html) == 3175762284.0
    assert F.parse_krw_won("2,557억") == 2.557e11 and F.parse_krw_won("6조 3,105억") == 6.3105e12 and F.parse_krw_won("N/A") is None


def test_merge_facts_adds_market_cap_to_price_rows():
    from wsj.ecosystems.ideas import merge_facts

    m = merge_facts([{"ticker": "INIO", "close": 16.98, "r12m": None, "from_low": 12.4}],
                    [{"ticker": "INIO", "market_cap_usd": 1.27e10, "shares_outstanding": 7.5e8, "from_low": 12.4},
                     {"ticker": "TWSE:8996", "market_cap_usd": 4.6e9, "close": 1585, "price_as_of": "2026-10-28", "from_low": 126}])
    assert m["INIO"]["market_cap_usd"] == 1.27e10 and m["TWSE:8996"]["close"] == 1585 and m["TWSE:8996"]["from_low"] == 126


# ------------------------------------------------------------------ 선행 추론 (ADR-0017 개정 2)
def test_anticipation_scores_path_unpriced_room_lead():
    st = A.Structure(load_graph())
    prices = {"TPEx:6664": {"close": 334, "r1m": -3.7, "r3m": -5.1, "r12m": 21, "from_high": -30, "from_low": 40, "vol_ratio": 0.9,
                            "market_cap_usd": 6.3e8, "points": 279}}
    idea = {"primary_company": "company:group_up", "companies": [{"id": "company:group_up", "name": "Group Up 群翊", "role": "primary"}],
            "chain": [], "risks": [], "nodes": ["bottleneck:substrate_capacity"],
            "anticipation": {"trigger": "S54", "path": ["bottleneck:substrate_capacity", "equipment:substrate_process_equipment", "company:group_up"],
                             "mechanism": "기판 증설은 도포·베이킹 장비 발주로 먼저 나타난다", "lead_quarters": 2,
                             "effect": {"pct_of_revenue": 40, "basis": "NT$509억 × 10% ÷ 연매출 NT$28억", "evidence": "S54"}, "priced_in": "none"}}
    a = A.anticipation(idea, st, prices, NOW, direct_last=None)
    assert a["parts"]["path"]["pts"] == 2 and a["hops"] == 2            # 최약 간선 0.6
    assert a["parts"]["unpriced"]["pts"] == 3                            # 직접 근거 없음 · 주가 조용
    assert a["parts"]["room"]["pts"] == 2 and a["parts"]["lead"]["pts"] == 2
    assert a["score"] == 9 and a["path_labels"][-1].startswith("Group Up")
    prices["TPEx:6664"]["r1m"] = 45
    a2 = A.anticipation(idea, st, prices, NOW, direct_last="2026-10-25")
    assert a2["parts"]["unpriced"]["pts"] == 0                           # 직접 근거 3일 전 + 주가 반응
    idea["anticipation"]["path"] = ["bottleneck:substrate_capacity", "company:group_up"]
    assert A.anticipation(idea, st, prices, NOW, direct_last=None)["parts"]["path"]["pts"] == 0  # 끊긴 경로


def test_price_context_ignores_range_with_few_points():
    node = {"listing": {"exchange": "KRX", "ticker": "353200"}}
    ctx = A.price_context({"KRX:353200": {"close": 140200, "r1m": None, "from_high": 0.0, "from_low": 17.4, "points": 3, "market_cap_usd": 5.2e9}}, node)
    assert ctx["from_low"] is None and ctx["from_high"] is None and ctx["tenbagger"]["candidate"] is False


def test_scan_second_order_finds_quiet_downstream_companies():
    g = load_graph()
    st = A.Structure(g)
    issues = [{"issue_key": "x", "title": "CoWoS 증설", "importance": 7, "latest_published_at": "2026-10-27", "nodes": ["bottleneck:cowos_capacity"], "companies": []}]
    out = scan.second_order(g, st, issues, recent_co=set(), covered=set(), prices={}, cut14="2026-10-14")
    assert out and all(x["hops"] >= 2 for x in out) and all(x["size_band"] in ("micro", "small", "mid") for x in out)


# ------------------------------------------------------------------ 가치평가 (ADR-0019): 결과는 가치평가, 점수는 계산기
def _ev(ids):
    return [{"id": e, "url": f"https://x/{e}", "title": e, "date": "2026-10-20"} for e in ids if e in ("S1", "S2", "G1")]


def test_parse_valuation_recomputes_mcap_and_price_and_expected_value():
    from wsj.ecosystems.ideas import parse_valuation

    money = {"close": 42.0, "currency": "TWD", "shares": 1.5e8, "market_cap_usd": 1.9e8, "as_of": "2026-10-28"}
    raw = {"horizon_months": 12, "confidence": "mid", "verdict": "가" * 130,
           "scenarios": [{"name": "bear", "prob": 0.3, "revenue": 2.8e9, "metric": "ps", "multiple": 1.5, "implied_mcap_local": 9e9, "evidence": ["S1"]},  # LLM 산수 틀림 → 4.2e9
                         {"name": "base", "prob": 0.5, "revenue": 4.5e9, "margin_pct": 14, "metric": "pe", "multiple": 20, "evidence": ["S2"]},   # 4.5e9×0.14×20 = 1.26e10
                         {"name": "bull", "prob": 0.2, "implied_price": 150, "evidence": []}],
           "assumptions": [{"claim": "a", "evidence": ["S1"]}, {"claim": "b", "evidence": ["S2"]}, {"claim": "근거 없음", "evidence": ["Z9"]},
                           {"kind": "estimate", "claim": "변화 크기 2.5배", "basis": "번인 1.8배 × 증설 2배", "evidence": ["G1"]},
                           {"claim": "basis 로만 추정", "basis": "상위 2사 과점이라 점유율 40%", "evidence": []},
                           {"kind": "estimate", "claim": "basis 짧음", "basis": "x", "evidence": []}],
           "breaks": [{"claim": "c", "evidence": ["G1"]}]}
    v, why = parse_valuation(raw, money, _ev)
    assert why is None and v is not None
    bear, base, bull = v["scenarios"]
    assert bear["implied_mcap_local"] == 4.2e9 and bear["implied_price"] == 28.0 and bear["upside_pct"] == -33.3
    assert base["implied_mcap_local"] == 1.26e10 and base["implied_price"] == 84.0 and base["upside_pct"] == 100.0
    assert bull["implied_price"] == 150.0 and bull["implied_mcap_local"] == 2.25e10
    assert v["expected_price"] == round(0.3 * 28 + 0.5 * 84 + 0.2 * 150, 4) and v["expected_upside_pct"] == 91.4
    assert [x["kind"] for x in v["assumptions"]] == ["fact", "fact", "estimate", "estimate"]  # 근거 없는 사실·basis 없는 추정은 버린다
    assert v["assumptions"][2]["basis"] == "번인 1.8배 × 증설 2배" and v["assumptions"][2]["evidence"][0]["id"] == "G1"
    assert v["calc_notes"] and "bear" in v["calc_notes"][0]
    assert v["currency"] == "TWD" and v["price"] == 42.0 and v["shares"] == 1.5e8


def test_parse_valuation_rejects_bad_inputs():
    from wsj.ecosystems.ideas import parse_valuation

    money = {"close": 10.0, "currency": "USD", "shares": 1e6}
    good = {"confidence": "high", "verdict": "v" * 130, "assumptions": [{"claim": "a", "evidence": ["S1"]}, {"claim": "b", "evidence": ["S2"]}],
            "scenarios": [{"name": "bear", "prob": 0.5, "implied_price": 8}, {"name": "bull", "prob": 0.5, "implied_price": 30}]}
    assert parse_valuation(good, money, _ev)[0]["expected_upside_pct"] == 90.0
    assert parse_valuation(good, None, _ev) == (None, "주가 없음")
    assert "확률 합" in parse_valuation(good | {"scenarios": [{"name": "bear", "prob": 0.5, "implied_price": 8}, {"name": "bull", "prob": 0.3, "implied_price": 30}]}, money, _ev)[1]
    assert "가정" in parse_valuation(good | {"assumptions": [{"claim": "a", "evidence": ["S1"]}]}, money, _ev)[1]
    # 추정만 있고 사실이 없으면 거부, 사실 1 + 추정 1 은 통과
    assert "사실 0" in parse_valuation(good | {"assumptions": [{"kind": "estimate", "claim": "e", "basis": "논리가 있다", "evidence": []}, {"kind": "estimate", "claim": "f", "basis": "논리가 있다", "evidence": []}]}, money, _ev)[1]
    assert parse_valuation(good | {"assumptions": [{"claim": "a", "evidence": ["S1"]}, {"kind": "estimate", "claim": "e", "basis": "논리가 있다", "evidence": []}]}, money, _ev)[0] is not None
    assert "verdict" in parse_valuation(good | {"verdict": "짧다"}, money, _ev)[1]
    assert "confidence" in parse_valuation(good | {"confidence": "sure"}, money, _ev)[1]
    # 주식수를 모르고 implied_price 도 없으면 시나리오를 못 만든다
    assert "시나리오" in parse_valuation(good | {"scenarios": [{"name": "bear", "prob": 0.5, "revenue": 1e9, "metric": "ps", "multiple": 2},
                                                              {"name": "bull", "prob": 0.5, "revenue": 2e9, "metric": "ps", "multiple": 3}]},
                                        {"close": 10.0, "currency": "USD"}, _ev)[1]


def test_money_context_joins_price_shares_and_fundamentals():
    from wsj.ecosystems.ideas import money_context

    g = _graph()
    by_key = {"P": {"ticker": "P", "close": 42, "as_of": "2026-10-28", "shares_outstanding": 1.5e8, "market_cap_usd": 1.9e8, "currency": "USD"},
              "Q": {"ticker": "Q", "close": None}}
    fund = [{"company_id": "company:p", "period": "ttm", "period_end": "2026-06-30", "currency": "USD", "revenue": 2.8e9, "op_margin_pct": 7.1, "ps": 2.25, "pe": None}]
    m = money_context(g, by_key, fund)
    assert set(m) == {"company:p"}
    assert m["company:p"]["close"] == 42.0 and m["company:p"]["shares"] == 1.5e8 and m["company:p"]["currency"] == "USD"
    assert m["company:p"]["fundamentals"]["revenue"] == 2.8e9 and m["company:p"]["fundamentals"]["op_margin_pct"] == 7.1 and "pe" not in m["company:p"]["fundamentals"]


def test_fundamentals_parsers():
    from wsj.ecosystems import fundamentals as FU

    # 미국: 분기 4개가 이어지면 TTM, 연간은 FY
    fin = {"quarters": [{"period_end": f"2025-{m:02d}-30", "revenue": 100.0, "op_income": 10.0, "net_income": 8.0, "gross_profit": None} for m in (3, 6, 9)]
           + [{"period_end": "2025-12-31", "revenue": 120.0, "op_income": 12.0, "net_income": 9.0, "gross_profit": None}],
           "annual": [{"fiscal_year_end": "2025-12-31", "revenue": 420.0, "op_income": 42.0, "net_income": 33.0}]}
    x = P.Listing("company:a", "NYSE", "A", "A", "us")
    rows = FU.us_rows(x, fin, cik=123)
    ttm = next(r for r in rows if r["period"] == "ttm")
    assert ttm["revenue"] == 420.0 and ttm["operating_income"] == 42.0 and ttm["gross_profit"] is None and ttm["period_end"] == "2025-12-31"
    assert ttm["source_url"].endswith("CIK0000000123.json") and any(r["period"] == "fy" and r["revenue"] == 420.0 for r in rows)
    # 대만: 월매출 12개월 합 (NT$ 천 → NT$), 끊기면 None
    pts = [(date(2025, m, 1), 1000.0) for m in range(1, 13)]
    assert FU.ttm_from_monthly(pts) == (12_000_000.0, date(2025, 12, 31))
    assert FU.ttm_from_monthly(pts[:11]) is None and FU.ttm_from_monthly(pts[:6] + pts[7:] + [(date(2026, 1, 1), 1.0)]) is None
    m = FU.parse_tw_margins([{"公司代號": "6664", "營業收入": "1000.00", "營業利益（損失）": "150.00", "本期淨利（淨損）": "120.00", "年度": "115", "季別": "2"}],
                            "公司代號", "營業收入", "營業利益（損失）", "本期淨利（淨損）")
    assert m["6664"]["op_margin"] == 0.15 and m["6664"]["net_margin"] == 0.12
    y = FU.parse_tw_ytd([{"公司代號": "6664", "資料年月": "11509", "累計營業收入-當月累計營收": "900000"}, {"公司代號": "x", "資料年月": "", "累計營業收入-當월累計營收": "1"}])
    assert y == {"6664": (9e8, date(2026, 9, 30), 9)}  # NT$ 천 → NT$, 9월 말, 9개월 누적 → 연환산은 ×12/9
    # 한국: 네이버 분기 표 (억원), 컨센서스 열 제외
    d = {"financeInfo": {"trTitleList": [{"key": "202509", "isConsensus": "N"}, {"key": "202512", "isConsensus": "N"}, {"key": "202603", "isConsensus": "N"},
                                         {"key": "202606", "isConsensus": "N"}, {"key": "202609", "isConsensus": "Y"}],
                         "rowList": [{"title": "매출액", "columns": {k: {"value": v} for k, v in (("202509", "313"), ("202512", "273"), ("202603", "224"), ("202606", "505"), ("202609", "670"))}},
                                     {"title": "영업이익", "columns": {k: {"value": v} for k, v in (("202509", "-4"), ("202512", "-123"), ("202603", "-25"), ("202606", "79"), ("202609", "140"))}},
                                     {"title": "당기순이익", "columns": {k: {"value": v} for k, v in (("202509", "2"), ("202512", "-117"), ("202603", "-8"), ("202606", "70"))}}]}}
    qs = FU.parse_naver_quarters(d)
    assert [q["period_end"] for q in qs] == ["2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
    kr = FU.kr_rows(P.Listing("company:k", "KOSDAQ", "086390", "KOSDAQ:086390", "kr"), qs)[0]
    assert kr["revenue"] == 1315e8 and kr["operating_income"] == -73e8 and kr["net_income"] == -53e8 and kr["period_end"] == "2026-06-30"


# ------------------------------------------------------------------ 가설 우선 (ADR-0020): 추론 단계와 추정 effect 를 받는다
def test_validate_accepts_inference_steps_and_estimated_effect():
    from wsj.ecosystems.ideas import Registry, validate

    g = _graph()
    reg = Registry()
    eid = reg.add("S", "https://x/s1", "10/27 P 가 Q 에 검사장비 공급계약 공시", publisher="KIND", date="2026-10-27", tier="official_issuer")
    signals = [{"sid": "sig1", "ref": "issue:1", "kind": "issue", "title": "t", "stars": 2, "date": "2026-10-27", "evidence": [eid], "nodes": ["bottleneck:b"], "companies": []}]
    now = datetime(2026, 10, 28, tzinfo=UTC)
    raw = [{"action": "new", "type": "bottleneck", "title": "병목이 조여진다", "thesis": "변화. 기업.", "stars": 1,
            "companies": [{"id": "company:p", "role": "primary"}],
            "chain": [{"claim": "10/27 P 가 공급계약을 공시했다", "evidence": [eid]},
                      {"claim": "적층이 높아지면 검사 시간이 1.8배 길어진다 (추론)", "evidence": []},
                      {"claim": "그래서 P 의 장비 매출이 2분기 뒤 +60% 가 된다", "inference": True, "evidence": ["Z9"]}],
            "watch": [{"what": "11월 월매출", "due": "2026-12-10", "metric": "YoY", "threshold": "≥ +50%", "direction": "strengthen"}],
            "anticipation": {"trigger": eid, "path": ["bottleneck:b", "component:x", "company:p"], "mechanism": "m", "lead_quarters": 2,
                             "effect": {"pct_of_revenue": 60, "basis": "검사 시간 1.8배 × 증설 2배 ÷ 연매출", "evidence": None}, "priced_in": "none"}}]
    rows, rejects = validate(raw, reg, g, signals, {}, now, "m", "session")
    assert not rejects and len(rows) == 1
    chain = rows[0]["chain"]
    assert [bool(st["evidence"]) for st in chain] == [True, False, False] and chain[1]["inference"] and chain[2]["claim"].endswith("(추론)")
    eff = rows[0]["assessment"]["anticipation"]["effect"]
    assert eff["pct_of_revenue"] == 60 and eff["estimated"] is True
    assert "(추정)" in rows[0]["assessment"]["anticipation"]["parts"]["room"]["note"]
    # 사실 단계가 하나도 없으면 거부
    raw2 = [dict(raw[0], chain=[{"claim": "a (추론)", "evidence": []}, {"claim": "b (추론)", "evidence": []}])]
    _, rej2 = validate(raw2, reg, g, signals, {}, now, "m", "session")
    assert rej2 and "fact=0" in rej2[0]


# ------------------------------------------------------------------ 시장 범위 (ADR-0021)
def _graph_tw():
    g = _graph()
    g["nodes"].append({"id": "company:t", "kind": "company", "label": "Taiwan T (6664)", "listing": {"ticker": "6664", "exchange": "TPEx"}, "size_band": "small"})
    g["edges"].append({"from": "component:x", "to": "company:t", "relation": "offered_by"})
    return g


def test_scope_helpers():
    from wsj.ecosystems.scope import in_scope, scope_note

    assert in_scope({"listing": {"exchange": "KOSDAQ"}}) and in_scope({"listing": {"exchange": "NYSE"}})
    assert not in_scope({"listing": {"exchange": "TPEx"}}) and not in_scope({}) and not in_scope(None)
    assert scope_note({"listing": {"exchange": "Xetra"}}) == "범위 밖(Xetra)" and scope_note({"listing": {"exchange": "KRX"}}) is None


def test_candidates_and_leads_keep_only_us_kr_companies():
    from wsj.ecosystems.ideas import Registry, build_candidates
    from wsj.ecosystems.scope import in_scope

    g = load_graph()
    nodes = {n["id"]: n for n in g["nodes"]}
    reg = Registry()
    eid = reg.add("S", "https://x/i", "CoWoS 증설", publisher="P", date="2026-10-27", tier="third_party_report")
    signals = [{"sid": "sig1", "ref": "issue:1", "kind": "issue", "title": "t", "stars": 3, "date": "2026-10-27", "evidence": [eid],
                "nodes": ["bottleneck:cowos_capacity"], "companies": ["company:powertech"], "subject": None}]
    cands = build_candidates(g, signals, reg, top=24, now=NOW)
    assert cands and all(in_scope(nodes[c["company_id"]]) for c in cands)  # 대만·일본·유럽 상장사는 후보가 아니다
    assert any("범위 밖(" in p for c in cands for p in c["peers"])  # 범위 밖 동종사는 맥락으로 표시
    events = [{"company_id": "company:powertech", "published_at": "2026-10-26T00:00:00+00:00", "importance": 3, "title": "力成 법설회", "url": "https://t"}]
    issues = [{"issue_key": "x", "title": "CoWoS 증설", "latest_published_at": "2026-10-27", "nodes": ["bottleneck:cowos_capacity"], "importance": 7, "companies": []}]
    prices = {"TWSE:6239": {"close": 1, "r1m": 60, "vol_ratio": 1, "as_of": "2026-10-27"}}
    ld = scan.leads(g, issues, [], events, [], prices, NOW)
    picked = [x["company_id"] for x in ld["company_leads"] + ld["price_leads"] + ld["second_order"]] + [u["company_id"] for b in ld["bottlenecks"] for u in b["uncovered"]]
    assert picked and all(in_scope(nodes[c]) for c in picked) and "company:powertech" not in picked


def test_validate_rejects_out_of_scope_primary_and_retires_existing():
    from wsj.ecosystems.ideas import Registry, validate

    g = _graph_tw()
    reg = Registry()
    eid = reg.add("S", "https://x/s1", "10/27 T 수주 공시", publisher="KIND", date="2026-10-27", tier="official_issuer")
    signals = [{"sid": "sig1", "ref": "issue:1", "kind": "issue", "title": "t", "stars": 2, "date": "2026-10-27", "evidence": [eid], "nodes": ["bottleneck:b"], "companies": []}]
    now = datetime(2026, 10, 28, tzinfo=UTC)
    base = {"type": "bottleneck", "title": "병목이 조여진다", "thesis": "변화. 기업.", "stars": 1,
            "chain": [{"claim": "10/27 T 가 수주를 공시했다", "evidence": [eid]}, {"claim": "그래서 P 의 매출이 는다 (추론)", "evidence": []}],
            "watch": [{"what": "11월 월매출", "due": "2026-12-10", "metric": "YoY", "threshold": "≥ +50%", "direction": "strengthen"}]}
    raw = [dict(base, action="new", companies=[{"id": "company:t", "role": "primary"}, {"id": "company:p", "role": "peer"}]),
           dict(base, action="new", companies=[{"id": "company:p", "role": "primary"}, {"id": "company:t", "role": "customer"}])]
    rows, rejects = validate(raw, reg, g, signals, {}, now, "m", "session")
    assert len(rows) == 1 and rows[0]["primary_company"] == "company:p" and any("out of scope (TPEx)" in r for r in rejects)
    assert [c["id"] for c in rows[0]["companies"]] == ["company:p", "company:t"]  # 범위 밖 기업은 관련 기업으로는 남는다
    # 범위 밖 주 기업의 기존 아이디어: keep 이면 종료, update 로 범위 안 기업에 옮기면 그 행을 받는다
    existing = {"k1": {"idea_key": "k1", "primary_company": "company:t", "companies": [{"id": "company:t", "exchange": "TPEx"}], "stars": 2, "type": "bottleneck"},
                "k2": {"idea_key": "k2", "primary_company": "company:t", "companies": [{"id": "company:t", "exchange": "TPEx"}], "stars": 2, "type": "bottleneck"}}
    raw2 = [{"action": "keep", "idea_key": "k1"},
            dict(base, action="update", idea_key="k2", what_changed="10/27 수주", companies=[{"id": "company:p", "role": "primary"}, {"id": "company:t", "role": "customer"}])]
    rows2, rej2 = validate(raw2, reg, g, signals, existing, now, "m", "session")
    closed = [r for r in rows2 if r.get("status") == "closed"]
    assert len(closed) == 1 and closed[0]["idea_key"] == "k1" and "ADR-0021" in closed[0]["close_reason"]
    assert any(r.get("idea_key") == "k2" and r.get("primary_company") == "company:p" for r in rows2)


# ------------------------------------------------------------------ 가설 검증 루프 (ADR-0022)
def test_verification_summary_and_star_decisions():
    from wsj.ecosystems import verification as V

    w = [{"what": "a", "status": "hit", "direction": "strengthen"}, {"what": "b", "status": "pending"},
         {"what": "c", "status": "miss", "direction": "strengthen"}, {"what": "d", "status": "void"}]
    s = V.summarize(w)
    assert (s["hits"], s["misses"], s["pending"], s["falsified"], s["stage"]) == (1, 1, 1, 0, 2)
    assert V.decide(1, s, 3, False) == ("promote", 2, "예측 1건 적중 → ★2")
    assert V.decide(2, s, 3, False)[0] == "keep"
    two = V.summarize([{"what": "a", "status": "hit"}, {"what": "b", "status": "hit", "direction": "strengthen"}])
    kind, new, note = V.decide(1, two, 4, False)
    assert (kind, new) == ("promote", 2) and "★3 은" in note          # 문턱 미달 → ★2 까지
    assert V.decide(2, two, 8, True) == ("promote", 3, "예측 2건 적중 → ★3")
    bad = V.summarize([{"what": "x", "status": "miss"}, {"what": "y", "status": "miss"}])
    assert V.decide(2, bad, 6, True) == ("demote", 1, "예측 2건 빗나감 → ★1") and V.decide(1, bad, 6, True)[0] == "keep"
    fals = V.summarize([{"what": "11월 월매출 YoY < 0", "status": "hit", "direction": "weaken", "grade_note": "-12%"}])
    kind, _, note = V.decide(3, fals, 9, True)
    assert kind == "close" and "반증 조건 성립" in note and "-12%" in note


def test_verification_audit_promotes_untouched_and_closes_falsified():
    from wsj.ecosystems import verification as V
    from wsj.ecosystems.ideas import _KEEP

    now = datetime(2026, 11, 20, tzinfo=UTC)
    ex = {"k1": {"idea_key": "k1", "status": "active", "stars": 1, "type": "bottleneck", "title": "t", "thesis": "a. b.", "primary_company": "company:p",
                 "companies": [{"id": "company:p"}], "chain": [], "last_signal_at": "2026-10-20", "stars_reason": "가설"},
          "k2": {"idea_key": "k2", "status": "active", "stars": 2, "type": "bottleneck", "title": "t2", "thesis": "a. b.", "primary_company": "company:q",
                 "companies": [{"id": "company:q"}], "chain": [], "last_signal_at": "2026-10-20"}}
    refresh = [{"idea_key": "k1", "assessment": {"score": 3}, "watch": [{"what": "a", "status": "hit", "direction": "strengthen", "evidence_url": "https://e"}]},
               {"idea_key": "k2", "assessment": {"score": 6}, "watch": [{"what": "f", "status": "hit", "direction": "weaken", "grade_note": "YoY -5%"}]}]
    extra, notes = V.audit(ex, [], refresh, now, "m", "session", _KEEP)
    assert refresh[0]["assessment"]["verification"]["hits"] == 1 and refresh[1]["assessment"]["verification"]["falsified"] == 1
    k1 = next(r for r in extra if r["idea_key"] == "k1")
    assert k1["stars"] == 2 and k1["trend"] == "strengthened" and k1["watch"][0]["status"] == "hit" and "★2" in k1["what_changed"]
    k2 = next(r for r in extra if r["idea_key"] == "k2")
    assert k2["status"] == "closed" and "반증 조건 성립" in k2["close_reason"] and "YoY -5%" in k2["close_reason"]
    # 같은 실행에서 고쳐 쓴 행은 버리지 않고 ★1 로
    row = {"idea_key": "k2", "status": "active", "stars": 2, "assessment": {"score": 6}, "chain": [], "watch": refresh[1]["watch"], "what_changed": "업계: x"}
    extra2, _ = V.audit(ex, [row], refresh, now, "m", "session", _KEEP)
    assert not [r for r in extra2 if r["idea_key"] == "k2"] and row["stars"] == 1 and "반증" in row["what_changed"]


def test_hypotheses_validate_score_select_and_plan():
    from wsj.ecosystems import hypotheses as H
    from wsj.ecosystems.ideas import Registry

    g = _graph_tw()
    reg = Registry()
    s1 = reg.add("S", "https://x/s1", "10/27 병목 B 심화", publisher="P", date="2026-10-27", tier="third_party_report")
    g1 = reg.add("G", "https://x/g1", "구조", publisher=None, date=None, tier="third_party_report")
    signals = [{"sid": "sig1", "ref": "issue-key-1", "kind": "issue", "title": "t", "stars": 3, "date": "2026-10-27", "evidence": [s1], "nodes": ["bottleneck:b"], "companies": []},
               {"sid": "sig2", "ref": "events:company:q", "kind": "company", "subject": "company:q", "title": "Q 수주", "stars": 2, "date": "2026-10-26", "evidence": [s1],
                "nodes": ["component:x"], "companies": ["company:q"], "items": [{"title": "Q 수주 공시", "ev": s1}]}]
    prices = {"P": {"close": 10, "r1m": 2, "from_low": 20, "market_cap_usd": 3e8, "as_of": "2026-10-27"}, "Q": {"close": 5, "r1m": 45, "from_low": 300, "as_of": "2026-10-27"}}
    # 이슈 단위 출력: 이슈마다 경로 ≤3, 기업 없는 경로(업계 영향)도 받는다
    raw = {"issues": [{"trigger": s1, "change": "10/27 병목 B 심화", "paths": [
        {"id": "H1", "path": ["bottleneck:b", "component:x", "company:p"], "company": "company:p",
         "claim": "병목 B 가 부품 X 수요를 2배로 늘려 P 매출을 2분기 뒤 +40% 바꾼다 (추론)", "effect_pct": 40, "lead_quarters": 2,
         "why_unpriced": "주가 조용, 자기 소식 없음", "falsifier": "2026-12-10 11월 월매출 YoY < +10% 면 폐기", "research": ["P 의 3Q IR 에서 X 매출 비중"], "extends": None},
        {"id": "H2", "path": ["bottleneck:b", "company:q"], "company": "company:q",
         "claim": "병목 B 가 Q 매출을 늘린다", "effect_pct": None, "lead_quarters": None, "why_unpriced": "", "falsifier": "실적이 나쁘면 폐기", "research": [], "extends": None},
        {"id": "H0", "path": ["bottleneck:b", "component:x"], "company": None, "claim": "병목 B 가 부품 X 가격을 2027년 +20% 올린다 (추론)", "effect_pct": 20, "lead_quarters": 2,
         "why_unpriced": "가격 지표 없음", "falsifier": "2027-03-31 까지 X 가격 인상 보도 없으면 폐기", "research": ["X 가격 동향"]},
        {"id": "H9", "path": ["bottleneck:b"], "company": None, "claim": "네 번째 경로는 이슈당 3개 제한으로 잘린다", "falsifier": "x"}]}],
           "candidates": [
        {"id": "H3", "trigger": s1, "change": "x", "path": ["bottleneck:b", "component:x", "company:t"], "company": "company:t", "claim": "대만 기업 T 가 수혜를 본다 — 범위 밖", "falsifier": "x"},
        {"id": "H4", "trigger": g1, "change": "x", "path": ["company:p"], "company": "company:p", "claim": "G 근거를 변화로 쓴 잘못된 후보 — 거부", "falsifier": "x"}]}
    cands, rejects = H.validate_candidates(raw, g, reg, signals, [], prices, NOW)
    assert [c["id"] for c in cands] == ["H1", "H2", "H0"] and len(rejects) == 2 and any("out of scope" in r for r in rejects) and any("trigger" in r for r in rejects)
    h1, h2, h0 = cands
    assert h1["score"] == 11 and h1["criteria"] == {"specific": 3, "bold": 3, "falsifiable": 3, "explanatory": 2} and not h1["flags"] and h1["issue_key"] == "issue-key-1"
    assert h2["score"] < 6 and h2["criteria"]["bold"] == 0 and any("이미 움직임" in f for f in h2["flags"])  # 가격이 뛰었고 자기 소식도 있다
    assert h0["company"] is None and h0["path_labels"] == ["병목 B", "부품 X"] and any("기업 없음" in f for f in h0["flags"])
    sel = H.select(cands, k=3)
    assert [c["id"] for c in sel] == ["H1"] and sel[0]["rank"] == 1  # 기업 없는 경로는 리포트 후보가 아니다
    plan = H.research_plan(sel, g, signals)
    assert plan[0]["company"] == "Primary" and plan[0]["ticker"] == "P" and plan[0]["confirm"] == ["P 의 3Q IR 에서 X 매출 비중"]
    rows = H.by_issue(cands, sel, NOW, "m", "session")
    assert len(rows) == 1 and rows[0]["issue_key"] == "issue-key-1" and [(p["id"], p["selected"]) for p in rows[0]["paths"]] == [("H1", True), ("H2", False), ("H0", False)]
    out = H.write_issue_sql(rows, Path(__file__).parent / ".tmp_issue_sql")
    assert out and out.read_text().startswith("select ideas.put_issue_hypotheses($wsj$[")
    out.unlink()
    out.parent.rmdir()
    reg2 = Registry()
    s1b = reg2.add("S", "https://x/s1", "같은 출처, 새 레지스트리", publisher="P", date="2026-10-27", tier="third_party_report")
    v = H.stage2_view(sel, reg2)
    assert v[0]["trigger"] == s1b and v[0]["id"] == "H1" and v[0]["issue_key"] == "issue-key-1"


def test_validate_records_hypothesis_provenance():
    from wsj.ecosystems.ideas import Registry, validate

    g = _graph()
    reg = Registry()
    eid = reg.add("S", "https://x/s1", "10/27 병목 B 심화", publisher="P", date="2026-10-27", tier="third_party_report")
    signals = [{"sid": "sig1", "ref": "issue:1", "kind": "issue", "title": "t", "stars": 2, "date": "2026-10-27", "evidence": [eid], "nodes": ["bottleneck:b"], "companies": []}]
    raw = [{"action": "new", "hypothesis": "H1", "type": "bottleneck", "title": "병목이 조여진다", "thesis": "변화. 기업.", "stars": 1,
            "companies": [{"id": "company:p", "role": "primary"}],
            "chain": [{"claim": "10/27 병목 B 가 심해졌다", "evidence": [eid]}, {"claim": "그래서 P 의 매출이 는다 (추론)", "evidence": []}]}]
    ctx = {"hypotheses": {"H1": {"id": "H1", "rank": 1, "score": 11, "criteria": {"specific": 3}, "claim": "c", "falsifier": "f"}}}
    rows, rejects = validate(raw, reg, g, signals, {}, datetime(2026, 10, 28, tzinfo=UTC), "m", "session", ctx)
    assert not rejects and rows[0]["assessment"]["hypothesis"] == {"id": "H1", "rank": 1, "score": 11, "criteria": {"specific": 3}, "claim": "c", "falsifier": "f"}
