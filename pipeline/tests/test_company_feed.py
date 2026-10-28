"""기업별 최신 소식 수집기의 결정적 부분 (네트워크 없음): 날짜·목록 파싱, 헤드라인 정리, 제목 필터, 엔진 신호화. ADR-0016 개정 1."""

from datetime import UTC, date, datetime

from wsj.ecosystems import company_feed as cf
from wsj.ecosystems import ideas
from wsj.ecosystems.ontology import load_graph

NOW = datetime(2026, 10, 27, tzinfo=UTC)

TDNET_PAGE = """<div>全123件</div><table id="main-list-table">
<tr>
<td class="oddnew-L kjTime" noWrap>15:30</td>
<td class="oddnew-M kjCode" noWrap>57060</td>
<td class="oddnew-M kjName" noWrap>三井金属       </td>
<td class="oddnew-M kjTitle" align="left"><a href="140120261027500001.pdf" target="_blank">業績予想の修正に関するお知らせ</a></td>
<td class="oddnew-M kjXbrl" noWrap align="center"> </td>
</tr>
<tr>
<td class="evennew-L kjTime" noWrap>15:00</td>
<td class="evennew-M kjCode" noWrap>590A0</td>
<td class="evennew-M kjName" noWrap>ギフティ</td>
<td class="evennew-M kjTitle" align="left"><a href="140120261027500002.pdf" target="_blank">自己株式の取得状況に関するお知らせ</a></td>
</tr></table>"""


def test_roc_dates_and_tdnet_rows():
    assert cf._roc("1151026") == date(2026, 10, 26)
    assert cf._roc("115/10/26") == date(2026, 10, 26)
    assert cf._roc("") is None
    total, rows = cf.parse_tdnet(TDNET_PAGE)
    assert total == 123
    assert rows[0] == ("15:30", "5706", "140120261027500001.pdf", "業績予想の修正に関するお知らせ")
    assert rows[1][1] == "590A"


def test_exhibit_headline_strips_sgml_preamble_and_rejects_symbol_noise():
    raw = ("EX-99 2 glw-20261027xex99xq32026.htm EX-99 Document Exhibit 99 News Release FOR RELEASE -- OCTOBER 27, 2026 "
           "Corning Reports Third-Quarter 2026 Financial Results CORNING, N.Y., Oct. 27, 2026 — Corning Incorporated today")
    assert cf.exhibit_headline(raw) == "Corning Reports Third-Quarter 2026 Financial Results"
    assert cf.exhibit_headline("•••• ➜➜➜ •••• ➜➜➜ ➜➜➜➜ •• ➜") is None
    assert cf.exhibit_headline("FINANCIAL NEWS BRIEF") is None


def test_news_title_filters():
    c = {"name": "UniTest", "native": "유니테스트", "ticker": "086390", "exchange": "KOSDAQ"}
    assert cf.mentions("유니테스트, SK하이닉스와 162억원 규모 반도체 검사장비 공급계약 체결", c)
    assert not cf.mentions("SK hynix expands HBM capacity", c)
    chatter = "[MK시그널] 유니테스트, HBM 테스트 장비 기대감에 상승률 14.58%"
    event = "산일전기, 단기 실적보다 강한 수주 목표가 280,000원"
    assert cf.PRICE_CHATTER.search(chatter) and not cf.NEWS_UP.search(chatter)
    assert cf.PRICE_CHATTER.search(event) and cf.NEWS_UP.search(event)  # 수주가 있으면 남긴다


def test_listed_companies_split_native_names_and_skip_private():
    cos = {c["id"]: c for c in cf.listed_companies(load_graph())}
    assert cos["company:shijia"]["native"] == "仕佳光子" and "仕佳" not in cos["company:shijia"]["name"]
    assert cos["company:unitest"]["native"] == "유니테스트"
    assert "company:lightmatter" not in cos  # 비상장
    zeus = cf._news_queries(cos["company:zeus"])
    assert [q[4] for q in zeus] == ["ko"] and "반도체" in zeus[0][0]  # 흔한 이름: 현지 기사만, 문맥어 포함


def _ev(cid, title, d, imp=2, kind="disclosure", tier="official_issuer", url=None):
    return cf.CompanyEvent(cid, kind, datetime.fromisoformat(d).replace(tzinfo=UTC), title, url or f"https://ex.com/{abs(hash(title))}",
                           "X", tier, imp)


def test_company_events_become_fresh_signals_and_round_trip():
    g = load_graph()
    reg = ideas.Registry()
    evs = [
        _ev("company:unitest", "유니테스트, SK하이닉스와 HBM 번인 검사장비 공급계약 체결", "2026-10-21", 3),
        _ev("company:unitest", "UniTest 3Q results", "2026-10-25", 2),
        _ev("company:zeus", "제우스 신작 게임 출시", "2026-10-25", 1, "news", "third_party_report"),   # 사건성 없음 → 신호 아님
        _ev("company:axt", "AXT old news", "2026-09-01", 3),                                          # 창 밖
    ]
    sigs = ideas.company_signals(evs, g, reg, NOW)
    assert [s["subject"] for s in sigs] == ["company:unitest"]
    s = sigs[0]
    assert s["stars"] == 3 and s["date"] == "2026-10-25" and len(s["items"]) == 2
    assert "process:hbm_burn_in" in s["nodes"] and "company:skhynix" in s["companies"]
    assert all(reg.items[e].date for e in s["evidence"])
    back = cf.CompanyEvent.from_public(evs[0].public())
    assert back.event_id == evs[0].event_id and back.published_at == evs[0].published_at


def test_recency_and_fresh_evidence_rule():
    assert ideas.recency("2026-10-27", NOW) == 1.0
    assert abs(ideas.recency("2026-10-20", NOW) - 0.5) < 1e-9
    assert ideas.recency("2026-01-01", NOW) == 0.15 and ideas.recency(None, NOW) == 0.3
    g = load_graph()
    reg = ideas.Registry()
    sigs = ideas.company_signals([_ev("company:unitest", "UniTest HBM burn-in tester supply contract", "2026-10-21", 3),
                                  _ev("company:techwing", "Techwing handler order", "2026-10-02", 3)], g, reg, NOW, days=30)
    fresh_ev = next(s for s in sigs if s["subject"] == "company:unitest")["evidence"][0]
    old_ev = next(s for s in sigs if s["subject"] == "company:techwing")["evidence"][0]
    base = {"action": "new", "type": "confirmation", "thesis": "a. b.", "stars": 2, "risks": [], "watch": []}
    fresh = {**base, "title": "최신", "companies": [{"id": "company:unitest", "role": "primary"}],
             "chain": [{"claim": "c", "evidence": [fresh_ev]}, {"claim": "d", "evidence": [fresh_ev]}]}
    stale = {**base, "title": "오래됨", "companies": [{"id": "company:techwing", "role": "primary"}],
             "chain": [{"claim": "c", "evidence": [old_ev]}, {"claim": "d", "evidence": [old_ev]}]}
    stale_update = {**stale, "action": "update", "idea_key": "k"}
    stale_weaken = {**stale, "action": "weaken", "idea_key": "k", "stars": 1}
    rows, rejects = ideas.validate([fresh, stale, stale_update, stale_weaken], reg, g, sigs, {"k": {"idea_key": "k", "stars": 2}}, NOW, "m", "llm")
    assert [r["title"] for r in rows] == ["최신", "오래됨"] and len(rejects) == 2
    assert rows[0]["last_signal_at"] == "2026-10-21" and rows[1]["trend"] == "weakened"
