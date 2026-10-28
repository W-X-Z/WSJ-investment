"""투자 아이디어 엔진의 결정적 부분: 신호 → 후보 사슬 → 검증. LLM 은 부르지 않는다. ADR-0016."""

from datetime import UTC, datetime

from wsj.ecosystems import ideas
from wsj.ecosystems.ontology import load_graph

NOW = datetime(2026, 10, 27, tzinfo=UTC)
ISSUE = {
    "issue_key": "k1", "status": "active", "title": "AI 칩 테스트 공급사 9월 매출 급증", "summary": "프로브카드 수요", "why_it_matters": None,
    "importance": 7, "nodes": ["process:kgd_test"], "companies": [{"company_id": "company:form", "direction": "+"}],
    "sources": [{"url": "https://example.com/a", "title": "HBM probe card demand surges", "publisher": "X", "published_at": "2026-10-26T00:00:00Z",
                 "source_type": "trade"}],
    "latest_published_at": "2026-10-26T00:00:00+00:00",
}
INDICATOR = {"indicator_id": "tw:6223", "label": "MPI 월매출", "category": "tw_revenue", "source_url": "https://mops.twse.com.tw/x",
             "nodes": ["process:kgd_test"], "companies": [], "as_of": "2026-09-01", "yoy_pct": 82.2}


def _prepare():
    g = load_graph()
    reg, signals, cands, payload = ideas.prepare([ISSUE], [INDICATOR], g, NOW, 21, [], 8, 20)
    return g, reg, signals, cands, payload


def test_signals_keep_sources_and_map_tw_company():
    _, reg, signals, _, _ = _prepare()
    issue = next(s for s in signals if s["kind"] == "issue")
    assert issue["evidence"] and all(e in reg.items for e in issue["evidence"])
    assert "company:form" in issue["companies"]
    mpi = next(s for s in signals if s["kind"] == "indicator")
    assert "company:mpi" in mpi["companies"] and mpi["stars"] == 3  # +82% YoY


def test_old_and_one_star_issues_are_not_signals():
    g = load_graph()
    reg = ideas.Registry()
    old = {**ISSUE, "issue_key": "old", "latest_published_at": "2026-08-01T00:00:00+00:00"}
    weak = {**ISSUE, "issue_key": "weak", "importance": 3}
    assert ideas.load_signals([old, weak], [], g, reg, NOW, 21) == []


def test_candidates_reach_probe_card_suppliers_with_evidence():
    _, reg, _, cands, payload = _prepare()
    ids = [c["company_id"] for c in cands]
    assert "company:jem" in ids or "company:form" in ids
    for c in cands:
        assert c["size_band"] != "private"
        for ch in c["chains"]:
            assert all(st["ev"] is None or st["ev"] in reg.items for st in ch["steps"])
    cited = {e["id"] for e in payload["evidence"]}
    assert all(e in cited for s in payload["signals"] for e in s["evidence"])


def test_validate_drops_invented_evidence_unknown_company_and_signal_free_ideas():
    g, reg, signals, _, _ = _prepare()
    s_ev = signals[0]["evidence"][0]
    g_ev = next(e for e in reg.items if e.startswith("G"))
    good = {"action": "new", "type": "bottleneck", "title": "HBM 테스트 붐 — JEM", "thesis": "a. b.", "stars": 2,
            "companies": [{"id": "company:jem", "role": "primary", "why": "x"}],
            "chain": [{"claim": "c1", "evidence": [s_ev]}, {"claim": "c2", "evidence": [g_ev, "G9999"]}], "risks": [], "watch": ["w"]}
    invented = {**good, "title": "가짜", "chain": [{"claim": "c1", "evidence": ["S999"]}, {"claim": "c2", "evidence": ["G9999"]}]}
    unknown = {**good, "title": "없는 회사", "companies": [{"id": "company:nope", "role": "primary"}]}
    no_signal = {**good, "title": "신호 없음", "chain": [{"claim": "c1", "evidence": [g_ev]}, {"claim": "c2", "evidence": [g_ev]}]}
    rows, rejects = ideas.validate([good, invented, unknown, no_signal], reg, g, signals, {}, NOW, "m", "llm")
    assert [r["title"] for r in rows] == ["HBM 테스트 붐 — JEM"] and len(rejects) == 3
    r = rows[0]
    assert r["primary_company"] == "company:jem" and r["trend"] == "new" and r["companies"][0]["ticker"] == "6855"
    assert all(e["url"].startswith("https://") for st in r["chain"] for e in st["evidence"])
    assert {e["id"] for e in r["chain"][1]["evidence"]} == {g_ev}  # 없는 id 는 빠진다


def test_update_keeps_key_and_close_touches_only_status():
    g, reg, signals, _, _ = _prepare()
    s_ev = signals[0]["evidence"][0]  # 이슈: company:form 이 이름으로 나온다
    existing = {"abc": {"idea_key": "abc", "stars": 1}}
    upd = {"action": "update", "idea_key": "abc", "type": "bottleneck", "title": "t", "thesis": "a. b.", "stars": 2,
           "companies": [{"id": "company:form", "role": "primary"}], "chain": [{"claim": "c", "evidence": [s_ev]}, {"claim": "d", "evidence": [s_ev]}]}
    close = {"action": "close", "idea_key": "abc", "reason": "반증"}
    rows, _ = ideas.validate([upd, close], reg, g, signals, existing, NOW, "m", "llm")
    assert rows[0]["idea_key"] == "abc" and rows[0]["trend"] == "strengthened" and rows[0]["stars"] == 2
    assert rows[0]["chain"][0]["evidence"][0]["rel"] == "direct"
    assert set(rows[1]) == {"idea_key", "status", "trend", "close_reason", "updated_at"} and rows[1]["status"] == "closed"


def test_industry_news_alone_does_not_strengthen_or_earn_three_stars():
    """주 기업 이야기가 아닌 업계 소식으로는 '강화'·★ 상향·★3 이 안 된다 (미쓰이금속 사례)."""
    g, reg, signals, _, _ = _prepare()
    s_ev = signals[0]["evidence"][0]  # FormFactor 를 말하는 이슈 → JEM 에게는 업계 근거
    g_ev = next(e for e in reg.items if e.startswith("G"))
    existing = {"abc": {"idea_key": "abc", "stars": 1, "primary_company": "company:jem", "companies": [{"id": "company:jem", "name": "Japan Electronic Materials"}],
                        "chain": [{"claim": "x", "evidence": [{"id": "S1", "date": "2026-09-01", "title": "Japan Electronic Materials orders"}]}]}}
    base = {"type": "bottleneck", "title": "t", "thesis": "a. b.", "companies": [{"id": "company:jem", "role": "primary"}],
            "chain": [{"claim": "c", "evidence": [s_ev]}, {"claim": "d", "evidence": [g_ev]}]}
    upd = {**base, "action": "update", "idea_key": "abc", "stars": 2, "what_changed": "프로브카드 수요 급증"}
    new3 = {**base, "action": "new", "title": "새 아이디어", "stars": 3}
    rows, _ = ideas.validate([upd, new3], reg, g, signals, existing, NOW, "m", "llm")
    assert rows[0]["trend"] == "unchanged" and rows[0]["stars"] == 1 and rows[0]["what_changed"].startswith("업계:")
    assert [e["rel"] for e in rows[0]["chain"][0]["evidence"]] == ["industry"] and rows[0]["chain"][1]["evidence"][0]["rel"] == "background"
    assert rows[1]["stars"] == 1 and "★2" in rows[1]["stars_reason"] and "★1" in rows[1]["stars_reason"]  # 업계 근거만 → 근거 점수 2점 이하 → ★1
    assert ideas.company_signal_date(existing["abc"]) == "2026-09-01"


def test_session_mode_pins_snapshot_time_and_writes_guarded_sql(tmp_path):
    """예약작업 경로: 같은 스냅샷으로 프롬프트와 검증을 따로 돌려도 근거 id 가 같고, 검증된 행은 put_ideas SQL 로 나온다."""
    import json

    snap = tmp_path / "snap"
    ideas.write_snapshot(snap, {"issues": [ISSUE], "indicators": [INDICATOR], "existing": [], "events": []}, NOW)
    p1, p2 = tmp_path / "p1.json", tmp_path / "p2.json"
    assert ideas.main(["--snapshot", str(snap), "--emit-prompt", str(p1), "--emit-research", str(tmp_path / "r.json")]) == 0
    assert ideas.main(["--snapshot", str(snap), "--emit-prompt", str(p2)]) == 0
    a, b = json.loads(p1.read_text())["payload"], json.loads(p2.read_text())["payload"]
    assert a["today"] == "2026-10-27" and [e["id"] for e in a["evidence"]] == [e["id"] for e in b["evidence"]]
    s_ev = a["signals"][0]["evidence"][0]
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({"model": "claude-opus-5-5", "ideas": [
        {"action": "new", "type": "bottleneck", "title": "HBM 테스트 붐 — JEM", "thesis": "a. b.", "stars": 2,
         "companies": [{"id": "company:jem", "role": "primary"}], "chain": [{"claim": "c", "evidence": [s_ev]}, {"claim": "d", "evidence": [s_ev]}]}]}))
    out_sql = tmp_path / "sql"
    assert ideas.main(["--snapshot", str(snap), "--from-llm-json", str(raw), "--method", "session", "--emit-sql", str(out_sql)]) == 0
    files = sorted(out_sql.glob("*.sql"))
    assert len(files) == 1
    sql = files[0].read_text()
    assert sql.startswith("select ideas.put_ideas($wsj$[") and sql.rstrip().endswith("$wsj$::jsonb);")
    row = json.loads(sql[len("select ideas.put_ideas($wsj$"):sql.rindex("$wsj$")])[0]
    assert row["method"] == "session" and row["model"] == "claude-opus-5-5" and row["last_signal_at"] == "2026-10-26"


def test_kept_three_star_idea_without_company_evidence_drops_to_two():
    g, reg, signals, _, _ = _prepare()
    ex = {"k3": {"idea_key": "k3", "stars": 3, "type": "bottleneck", "title": "기판 소재 독점", "thesis": "a. b.", "primary_company": "company:mitsui_kinzoku",
                 "companies": [{"id": "company:mitsui_kinzoku", "name": "Mitsui Mining & Smelting"}], "last_signal_at": "2026-10-27",
                 "chain": [{"claim": "업계", "evidence": [{"id": "S1", "date": "2026-10-27", "title": "Unimicron September revenue +64.7%", "url": "https://x"}]}]},
          "ok3": {"idea_key": "ok3", "stars": 3, "primary_company": "company:jem", "companies": [{"id": "company:jem", "name": "Japan Electronic Materials"}],
                  "last_signal_at": "2026-10-20", "chain": [{"claim": "c", "evidence": [{"id": "S2", "date": "2026-10-20", "title": "Japan Electronic Materials orders", "url": "https://y", "rel": "direct"}]}]}}
    rows, _ = ideas.validate([{"action": "keep", "idea_key": "k3"}], reg, g, signals, ex, NOW, "m", "session")
    assert [r["idea_key"] for r in rows] == ["k3"]
    r = rows[0]
    assert r["stars"] == 2 and r["trend"] == "weakened" and "★3→★2" in r["what_changed"] and r["chain"] == ex["k3"]["chain"]
