"""노출도 재료 (G-8 무료 경로) — 인라인 XBRL 의 차원별 매출·집중도와 '매출의 N%' 문장."""

from wsj.ecosystems import exposure as X

DOC = """<html><body><div style="display:none"><ix:header><ix:resources>
<xbrli:context id="c-1"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c-2"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">abc:ContactorsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c-3"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">abc:ContactorsMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c-4"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier><xbrli:segment>
 <xbrldi:explicitMember dimension="srt:MajorCustomersAxis">abc:CustomerAMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
<xbrli:context id="c-5"><xbrli:entity><xbrli:identifier scheme="x">1</xbrli:identifier></xbrli:entity>
 <xbrli:period><xbrli:startDate>2025-10-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
</ix:resources></ix:header></div>
<p>Revenue <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="c-1" unitRef="usd" scale="3" decimals="-3">58,000</ix:nonFraction></p>
<p>Contactors <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="c-2" unitRef="usd" scale="3">17,<span>400</span></ix:nonFraction></p>
<p>Contactors 2024 <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="c-3" unitRef="usd" scale="3">9,000</ix:nonFraction></p>
<p>Q4 <ix:nonFraction name="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax" contextRef="c-5" unitRef="usd" scale="3">20,000</ix:nonFraction></p>
<p>Customer A <ix:nonFraction name="us-gaap:ConcentrationRiskPercentage1" contextRef="c-4" unitRef="pure" scale="-2">35</ix:nonFraction>%</p>
<p>Sales of our silicon carbide test contactors accounted for 30.0% of our net sales in fiscal 2025, up from $9.0 million in 2024.
Interest income was 2.1% of revenue. Gross margin was 40% of revenue.</p>
</body></html>"""


def test_parse_annual_rows_with_share_of_total():
    rows = X.annual_rows(X.parse_facts(DOC, X.parse_contexts(DOC)))
    by = {(r["kind"], r["label"]): r for r in rows}
    rev = by[("revenue", "Product Or Service=Contactors")]
    assert rev["value"] == 17_400_000 and rev["pct"] == 30.0 and rev["period_end"] == "2025-12-31"   # 2024·분기 값은 빠진다
    conc = by[("concentration", "Major Customers=Customer A")]
    assert round(conc["pct"], 2) == 35.0
    assert by[("total", "총매출")]["value"] == 58_000_000
    assert sum(1 for r in rows if r["kind"] == "revenue") == 1


def test_pct_sentences_keep_decimals_and_drop_cost_ratios():
    got = X.pct_sentences(X.visible_text(DOC))
    assert got == ["Sales of our silicon carbide test contactors accounted for 30.0% of our net sales in fiscal 2025, up from $9.0 million in 2024"]


def test_label_splits_member_names():
    assert X.label("us-gaap:CustomerConcentrationRiskMember") == "Customer Concentration Risk"
    assert X.label("srt:ProductOrServiceAxis") == "Product Or Service"


def test_targets_pick_sec_filers_with_empty_exposure():
    g = {"nodes": [{"id": "company:a", "kind": "company", "label": "A", "size_band": "small", "listing": {"ticker": "A", "cik": 1}},
                   {"id": "company:b", "kind": "company", "label": "B", "size_band": "mega", "listing": {"ticker": "B", "cik": 2}},
                   {"id": "company:c", "kind": "company", "label": "C", "size_band": "small", "listing": {"ticker": "C", "exchange": "KRX"}}],
         "edges": [{"from": "component:x", "relation": "offered_by", "to": "company:a"},
                   {"from": "component:y", "relation": "offered_by", "to": "company:a", "exposure_pct": 30},
                   {"from": "component:x", "relation": "offered_by", "to": "company:b"},
                   {"from": "component:x", "relation": "offered_by", "to": "company:c"}]}
    assert [t["company"] for t in X.targets(g, {"micro", "small", "mid"})] == ["company:a"]
    assert [t["company"] for t in X.targets(g, {"small"}, only={"company:b"})] == ["company:b"]


class _Http:
    def __init__(self):
        self.got = []

    def get_json(self, url):
        self.got.append(url)
        return {"filings": {"recent": {"form": ["8-K", "10-K"], "accessionNumber": ["0000000001-26-000001", "0000000001-26-000002"],
                                       "filingDate": ["2026-02-01", "2026-01-30"], "reportDate": ["", "2025-12-31"],
                                       "primaryDocument": ["x.htm", "a-20251231.htm"]}}}

    def get_text(self, url):
        self.got.append(url)
        return DOC


class _Store:
    def __init__(self, done=()):
        self.done, self.saved = list(done), []

    def select(self, table, cols=None, filters=None, limit=None, order=None):
        return [{"url": u} for u in self.done]

    def upsert(self, table, rows, key):
        self.saved += rows
        return len(rows)


G = {"nodes": [{"id": "company:a", "kind": "company", "label": "A", "size_band": "small", "listing": {"ticker": "A", "cik": 1}}],
     "edges": [{"from": "component:x", "relation": "offered_by", "to": "company:a"}]}
URL = "https://www.sec.gov/Archives/edgar/data/1/000000000126000002/a-20251231.htm"


def test_run_reads_latest_annual_and_skips_already_read():
    st, http = _Store(), _Http()
    stats = X.run(http, st, G, {"small"})
    assert stats["read"] == 1 and URL in http.got
    kinds = {r["kind"] for r in st.saved}
    assert {"revenue", "concentration", "text", "total"} <= kinds and all(r["url"] == URL and r["form"] == "10-K" for r in st.saved)
    assert len({r["fact_key"] for r in st.saved}) == len(st.saved)
    st2, http2 = _Store(done=[URL]), _Http()
    stats2 = X.run(http2, st2, G, {"small"})
    assert stats2["already"] == 1 and not st2.saved and URL not in http2.got
