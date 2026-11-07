"""선별 에이전트 (wsj.agents.screen) — Anthropic·Supabase 는 가짜로. 묶음·예산·JSON 검증/재시도·겹침 규칙·보고서 모양."""

import json
from argparse import Namespace
from datetime import UTC, datetime

import pytest

from wsj.agents import screen as S
from wsj.briefs.llm import Completion
from wsj.db.postgrest import PostgrestError

NOW = datetime(2026, 11, 7, 21, 0, tzinfo=UTC)          # KST 2026-11-08 06:00
GRAPH = {"company:mu", "company:skh", "component:hbm_stack", "component:mlb_pcb", "company:isu_petasys"}


def clue(cid, title, kind="trade_press", companies=(), nodes=(), layer=None, url=None, relevant=True, extra=None):
    ex = dict(extra or {})
    if layer:
        ex["layer"] = layer
    return {"clue_id": cid, "url": url or f"https://x.test/{cid}", "title": title, "summary": f"{title} 요약", "published_at": "2026-11-07T10:00:00+00:00",
            "seen_at": "2026-11-07T12:00:00+00:00", "source_id": "src", "source_name": "출처", "source_kind": kind,
            "companies": [{"company": c, "name": c.split(":")[1]} if ":" in c else {"name": c} for c in companies], "nodes": list(nodes),
            "note": None, "extra": ex, "relevant": relevant}


CLUES = [
    clue(1, "Micron HBM4 12-high qualification at NVIDIA", companies=["company:mu"], nodes=["component:hbm_stack"]),
    clue(2, "JEDEC publishes HBM4E draft", kind="standards", nodes=["component:hbm_stack"]),
    clue(3, "Isu Petasys adds MLB capacity", companies=["company:isu_petasys"], nodes=["component:mlb_pcb"]),
    clue(4, "SK hynix 10-Q: HBM capex raised", kind="disclosure", companies=["company:skh"]),
    clue(5, "Stock moves on chip rally", relevant=False),
]


class FakeStore:
    def __init__(self, clues=CLUES, bodies=None, reports=None, opportunities=None, rpc_schemas=("research",), agent_run=True):
        self.clues, self.bodies = clues, bodies or {}
        self.reports, self.opportunities = reports, opportunities if opportunities is not None else []
        self.rpc_schemas, self.agent_run = rpc_schemas, agent_run
        self.selects, self.rpcs = [], []

    def select(self, table, columns=None, filters=None, limit=None, order=None):
        self.selects.append((table, columns, filters))
        if table == "ideas.clues":
            if columns == ["clue_id"]:
                return [{"clue_id": c["clue_id"]} for c in self.clues]
            assert filters["relevant"] is True and filters["seen_at"][0] == "gte"
            return [c for c in self.clues if c["relevant"]]
        if table == "ideas.clue_texts":
            assert filters["status"] == "ok" and len(filters["url"]) <= 40
            return [{"url": u, "body": b} for u, b in self.bodies.items() if u in filters["url"]]
        if table == "public.v_reports":
            if self.reports is None:
                raise PostgrestError("PostgREST GET public.v_reports -> 404: PGRST205", 404, "PGRST205")
            kinds = filters["kind"] if isinstance(filters["kind"], list) else [filters["kind"]]
            return [r for r in self.reports if r["kind"] in kinds]
        if table == "ideas.opportunities":
            return self.opportunities
        raise AssertionError(table)

    def rpc(self, fn, args, schema="public"):
        self.rpcs.append((schema, fn, args))
        if fn == "put_agent_run":
            if not self.agent_run:
                raise PostgrestError("PostgREST POST ops.rpc/put_agent_run -> 404", 404, "PGRST202")
            return {"id": 1}
        if schema in self.rpc_schemas:
            return {"upserted": len(args["rows"]), "rejected": []}
        raise PostgrestError(f"PostgREST POST {schema}.rpc/{fn} -> 404: not found", 404, "PGRST202")

    def close(self):
        pass


def ev(ids, title="변화", proceed=False, novelty="new", entities=(), overlaps=(), seed=None, reason="근거"):
    return {"title": title, "summary": f"{title}. 두 번째 문장.", "clue_ids": list(ids), "entities": list(entities), "novelty": novelty,
            "overlaps": list(overlaps), "proceed": proceed, "reason": reason, "hypothesis_seed": seed if proceed else None}


class FakeLLM:
    """responses: 문자열 또는 user(dict)→문자열/객체 함수. 호출마다 하나씩 쓴다."""

    def __init__(self, responses, usage=(1000, 500, 0, 0)):
        self.responses, self.calls, self.usage = list(responses), [], usage

    def complete(self, system, user, model, **kw):
        self.calls.append({"system": system, "user": user, "model": model, **kw})
        r = self.responses.pop(0)
        if callable(r):
            r = r(json.loads(user) if user.startswith("{") else user)
        text = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        i, o, cr, cw = self.usage
        if len(self.calls) == 1:
            cr, cw = 0, cw or 800                       # 첫 호출은 캐시 쓰기
        else:
            cr = cr or 800
        return Completion(text=text, model=model, input_tokens=i, output_tokens=o, cache_read_tokens=cr, cache_write_tokens=cw)


def cfg(**kw):
    return S.ScreenConfig(**({"model": "claude-sonnet-5-5", "effort": "medium"} | kw))


def prep(store=None, **kw):
    return S.prepare(store or FakeStore(), cfg(**kw), now=NOW, graph_ids=GRAPH)


# ---------------------------------------------------------------- 가격·토큰
def test_price_table_and_token_estimate():
    s = S.price_for("claude-sonnet-5-5")
    assert (s.cost(1e6), s.cost(0, 1e6), s.cost(cache_read=1e6), s.cost(cache_write=1e6)) == (2.0, 10.0, 0.10, 2.50)
    h = S.price_for("claude-haiku-5-5")
    assert (h.cost(1e6), h.cost(0, 1e6), h.cost(cache_read=1e6), h.cost(cache_write=1e6)) == (0.10, 0.50, 0.01, 0.125)
    o = S.price_for("claude-opus-5-5")
    assert (o.cost(1e6), o.cost(0, 1e6), o.cost(cache_read=1e6), o.cost(cache_write=1e6)) == (4.0, 20.0, 0.20, 5.0)
    assert S.price_for("claude-unknown-9") == o                     # 모르는 모델은 비싼 쪽으로 어림
    assert S.estimate_tokens("a" * 35) == 11 and S.estimate_tokens("가" * 10) == 11
    assert S.kst_date(NOW) == "2026-11-08"


# ---------------------------------------------------------------- 묶음
def test_order_puts_primary_first_and_keeps_same_subject_together():
    items = [S.clue_item(c, None, 4000) for c in CLUES if c["relevant"]]
    items.append(S.clue_item(clue(6, "Micron Boise fab update", companies=["company:mu"]), "본문 " * 10, 4000))
    ordered = [it["id"] for it in S.order_items(items)]
    assert ordered[0] in (2, 4)                                     # 원본(표준·공시)이 맨 앞
    assert abs(ordered.index(1) - ordered.index(6)) == 1            # 같은 기업(company:mu) 단서는 붙어 있다
    assert ordered.index(3) > ordered.index(2)


def test_make_batches_respects_token_and_item_caps():
    items = [{"id": i, "t": "x" * 350} for i in range(10)]          # 하나 ≈ 110 토큰
    assert [len(b.items) for b in S.make_batches(items, batch_tokens=300, max_items=50)] == [2, 2, 2, 2, 2]
    assert [len(b.items) for b in S.make_batches(items, batch_tokens=10_000, max_items=4)] == [4, 4, 2]
    one = S.make_batches([{"id": 1, "t": "x" * 5000}], batch_tokens=100, max_items=5)
    assert len(one) == 1 and one[0].clue_ids == [1]                 # 상한보다 큰 단서도 혼자 한 묶음


def test_clue_item_truncates_body_and_carries_tags():
    row = clue(7, "Policy", kind="policy", companies=["company:mu", "Private Co"], nodes=["component:hbm_stack"], extra={"themes": ["tariffs"]})
    it = S.clue_item(row, "가" * 9000, 4000)
    assert it["layer"] == "raw" and it["co"] == ["company:mu", "Private Co"] and it["nodes"] == ["component:hbm_stack"]
    assert len(it["body"]) == 4000 and it["themes"] == ["tariffs"]
    assert S.clue_layer({"source_kind": "market_move", "extra": {"layer": "issue"}}) == "market"


# ---------------------------------------------------------------- 실행: 한 묶음
def test_single_batch_report_shape_and_prompt_caching():
    store = FakeStore(bodies={"https://x.test/2": "JEDEC 본문 " * 500},
                      opportunities=[{"opportunity_key": "mu_hbm_share", "title": "마이크론 HBM 점유 확대", "status": "active", "stars": 3,
                                      "nodes": ["component:hbm_stack"], "companies": [{"company": "company:mu", "name": "Micron"}],
                                      "status_note": None, "updated_at": "2026-11-01"}])
    p = prep(store)
    assert p.relevant == 4 and p.clues_in == 5 and len(p.batches) == 1 and p.memory_source == "opportunities"
    llm = FakeLLM([lambda u: {"events": [
        ev([2, 1, 999], "HBM4E 표준 초안 공개", proceed=True, novelty="update", entities=["component:hbm_stack", "company:mu", "company:made_up"],
           overlaps=["opportunity:mu_hbm_share", "idea:unknown"], seed="HBM4E 채택이 마이크론 판가를 올린다"),
        ev([3], "이수페타시스 MLB 증설", entities=["company:isu_petasys"]),
    ]}])
    row = S.screen(p, llm, cfg())
    assert set(row) == {"report_id", "kind", "title", "subjects", "as_of", "body", "cites", "created_by"}
    assert row["report_id"] == "screen:2026-11-08" and row["kind"] == "screen" and row["as_of"] == "2026-11-08"
    assert row["created_by"] == "screen-agent" and row["cites"] == [1, 2, 3]
    assert row["subjects"] == ["component:hbm_stack", "company:mu", "company:isu_petasys"]   # 진행 사건 먼저, 그래프 id 만
    body = row["body"]
    assert set(body) == {"window", "events", "stats", "usage"}
    assert body["window"] == {"from": "2026-11-06T21:00:00+00:00", "to": "2026-11-07T21:00:00+00:00"}
    e1 = body["events"][0]
    assert set(e1) == {"event_id", "title", "summary", "clue_ids", "entities", "novelty", "overlaps", "proceed", "reason", "hypothesis_seed"}
    assert e1["event_id"] == "e1" and e1["proceed"] and e1["clue_ids"] == [2, 1]           # 모르는 id 999 는 빠진다
    assert e1["entities"] == ["component:hbm_stack", "company:mu"] and e1["overlaps"] == ["opportunity:mu_hbm_share"]
    st = body["stats"]
    assert st["clues_in"] == 5 and st["relevant"] == 4 and st["bodies_read"] == 1 and st["merge"] == "none"
    assert st["proceed"] == 1 and st["truncated"] is False and any("999" in w for w in st["warnings"])
    u = body["usage"]
    assert u["model"] == "claude-sonnet-5-5" and u["calls"] == 1 and u["cache_write_tokens"] == 800
    assert u["est_usd"] == round((1000 * 2 + 500 * 10 + 800 * 2.5) / 1e6, 4)
    call = llm.calls[0]
    assert "opportunity:mu_hbm_share" in call["system"] and call["effort"] == "medium"
    assert json.loads(call["user"])["task"] == "A" and "body" in next(c for c in json.loads(call["user"])["clues"] if c["id"] == 2)


def test_no_relevant_clues_makes_empty_report_without_llm():
    p = prep(FakeStore(clues=[clue(5, "noise", relevant=False)]))
    row = S.empty_report(p, cfg())
    assert p.items == [] and row["body"]["events"] == [] and row["body"]["stats"]["clues_in"] == 1 and row["body"]["usage"]["est_usd"] == 0


# ---------------------------------------------------------------- 실행: 여러 묶음 + 병합
def test_multi_batch_merge_unions_clues_and_keeps_unmentioned_events():
    p = prep(batch_max_items=2)
    assert len(p.batches) == 2
    first, second = p.batches[0].clue_ids, p.batches[1].clue_ids

    def batch(u):
        ids = [c["id"] for c in u["clues"]]
        return {"events": [ev([ids[0]], f"사건 {ids[0]}", entities=[]), ev([ids[1]], f"사건 {ids[1]}")]}

    merged = {"events": [{"from": ["b1e1", "b2e1", "b9e9"], "title": "합친 사건", "summary": "합쳤다. 끝.", "novelty": "new", "overlaps": [],
                          "proceed": True, "reason": "1년 안 실적", "hypothesis_seed": "가설"}]}
    llm = FakeLLM([batch, batch, merged])
    row = S.screen(p, llm, cfg())
    evs = row["body"]["events"]
    assert [e["event_id"] for e in evs] == ["e1", "e2", "e3"]
    assert evs[0]["title"] == "합친 사건" and evs[0]["clue_ids"] == [first[0], second[0]] and evs[0]["proceed"]
    assert {tuple(e["clue_ids"]) for e in evs[1:]} == {(first[1],), (second[1],)}         # 병합이 말하지 않은 사건은 그대로
    st = row["body"]["stats"]
    assert st["merge"] == "llm" and st["batches_done"] == 2 and st["clues_screened"] == 4
    assert json.loads(llm.calls[2]["user"])["task"] == "B"
    assert len({c["system"] for c in llm.calls}) == 1                                        # 모든 호출이 같은 시스템 블록 → 캐시
    assert row["body"]["usage"]["cache_read_tokens"] == 1600 and row["body"]["usage"]["calls"] == 3


def test_merge_failure_falls_back_to_local_merge():
    p = prep(batch_max_items=2)

    def batch(u):
        return {"events": [ev([c["id"] for c in u["clues"]], "같은 제목")]}

    row = S.screen(p, FakeLLM([batch, batch, "깨진 응답", "또 깨짐"]), cfg())
    evs = row["body"]["events"]
    assert row["body"]["stats"]["merge"] == "local" and len(evs) == 1 and len(evs[0]["clue_ids"]) == 4


# ---------------------------------------------------------------- 예산
def test_budget_cutoff_stops_adding_batches_and_still_reports():
    p = prep(batch_max_items=1)
    assert len(p.batches) == 4
    llm = FakeLLM([lambda u: {"events": [ev([u["clues"][0]["id"]], "첫 사건")]}] * 4, usage=(9_000, 300, 0, 0))
    row = S.screen(p, llm, cfg(max_input_tokens=12_000))
    st = row["body"]["stats"]
    assert len(llm.calls) == 1 and st["batches_done"] == 1 and st["truncated"] is True
    assert st["truncation_reason"] == "max_input_tokens" and st["skipped_clues"] == 3 and st["merge"] == "none"
    assert row["title"].endswith("(일부만 처리)") and len(row["body"]["events"]) == 1


def test_budget_usd_cap_and_merge_reserve():
    p = prep(batch_max_items=2)
    price = S.price_for("claude-sonnet-5-5")
    budget = S.Budget(400_000, 1.0, price)
    usage = S.Usage("claude-sonnet-5-5", input_tokens=100_000, output_tokens=60_000)   # $0.8 썼다
    assert budget.exceeded(usage, [S.PlannedCall(1000, 5000, 5000)], cache_warm=True) is None
    assert budget.exceeded(usage, [S.PlannedCall(1000, 5000, 5000)] * 5, cache_warm=True) == "max_usd"
    # 첫 묶음이 예산에 안 들어가면 LLM 을 부르지 않고 빈 보고서(truncated)
    row = S.screen(p, FakeLLM([]), cfg(max_usd=0.0001))
    assert row["body"]["events"] == [] and row["body"]["stats"]["truncated"] and row["body"]["stats"]["skipped_clues"] == 4


# ---------------------------------------------------------------- JSON 검증·재시도
def test_parse_failure_retries_once_with_prior_turn():
    llm = FakeLLM(["이건 JSON 이 아니다", lambda u: {"events": [ev([1], "고친 응답")]}])
    p = prep()
    row = S.screen(p, llm, cfg())
    assert len(llm.calls) == 2 and row["body"]["events"][0]["title"] == "고친 응답"
    second = llm.calls[1]
    assert second["prior"][1] == {"role": "assistant", "content": "이건 JSON 이 아니다"}
    assert second["user"].startswith("직전 응답이 형식에 맞지 않는다")
    assert row["body"]["usage"]["calls"] == 2


def test_structural_error_retries_and_double_failure_fails_batch():
    bad = {"events": [{**ev([1], proceed=True), "hypothesis_seed": None}]}         # proceed 인데 가설이 없다
    llm = FakeLLM([bad, {"events": [ev([1], "ok", proceed=True, seed="가설")]}])
    assert S.screen(prep(), llm, cfg())["body"]["events"][0]["proceed"] is True
    assert "hypothesis_seed" in llm.calls[1]["user"]
    with pytest.raises(S.ScreenError):                                             # 묶음 하나뿐인데 두 번 다 틀림
        S.screen(prep(), FakeLLM(["{}", '{"events": "x"}']), cfg())
    # 두 묶음 중 하나만 실패 → 보고서는 쓰고 실패를 남긴다
    p = prep(batch_max_items=2)
    row = S.screen(p, FakeLLM(["nope", "nope", lambda u: {"events": [ev([u["clues"][0]["id"]])]}]), cfg())
    st = row["body"]["stats"]
    assert st["truncated"] and st["failed_batches"][0]["batch"] == 1 and st["skipped_clues"] == 2 and st["merge"] == "none"


def test_validate_batch_sanitizes_soft_errors():
    warn = []
    out = S.validate_batch({"events": [ev([1, "2", 7], entities=["company:mu", "bad id", "company:nope"], overlaps=["x", "idea:a"]),
                                       ev([2], "중복 단서만"), ev([3], novelty="dup")]},
                           {1, 2, 3}, {"idea:a"}, {"company:mu"}, warn)
    assert [e["clue_ids"] for e in out] == [[1, 2], [3]]                           # 7 은 모름, 두 번째 사건은 단서가 앞에서 쓰여 빠짐
    assert out[0]["entities"] == ["company:mu"] and out[0]["overlaps"] == ["idea:a"]
    assert len(warn) == 5 and any("남는 단서가 없어" in w for w in warn)
    for bad in ([], {"events": [{"title": "t"}]}, {"events": [ev([1], novelty="maybe")]}, {"events": [{**ev([1]), "clue_ids": ["a"]}]},
                {"events": [{**ev([1]), "proceed": "yes"}]}):
        with pytest.raises(S.ScreenFormatError):
            S.validate_batch(bad, {1}, set(), set())


# ---------------------------------------------------------------- 겹침·중복 규칙
IDEAS = [S.Idea("opportunity:mu_hbm", "마이크론 HBM", ["company:mu", "component:hbm_stack"], "active", 3),
         S.Idea("opportunity:skh_dropped", "하이닉스 증설", ["company:skh", "component:hbm_stack"], "dropped", 2, "캐파 증설이 이미 반영"),
         S.Idea("idea:nvda", "엔비디아", ["company:nvda"], "rejected", None, "밸류에이션")]


def _rule(e):
    return S.apply_rules([e], IDEAS)[0]


def test_dup_never_proceeds():
    e = _rule(ev([1], novelty="dup", proceed=True, seed="x"))
    assert e["proceed"] is False and e["hypothesis_seed"] is None and "재보도" in e["reason"]


def test_overlap_with_rejected_idea_needs_update():
    blocked = _rule(ev([1], proceed=True, seed="x", novelty="new", overlaps=["opportunity:skh_dropped"]))
    assert blocked["proceed"] is False and "기각된 opportunity:skh_dropped" in blocked["reason"]
    assert blocked["novelty"] == "update"                                          # 표시는 고친다
    ok = _rule(ev([1], proceed=True, seed="x", novelty="update", overlaps=["opportunity:skh_dropped"]))
    assert ok["proceed"] is True and ok["hypothesis_seed"] == "x"


def test_graph_overlap_adds_related_ideas_and_blocks_only_when_strong():
    weak = _rule(ev([1], proceed=True, seed="x", entities=["company:nvda"]))     # 기업 하나만 공유 (점수 2) → 표시만
    assert weak["overlaps"] == ["idea:nvda"] and weak["proceed"] is True and weak["novelty"] == "new"
    strong = _rule(ev([1], proceed=True, seed="x", entities=["company:skh", "component:hbm_stack"]))   # 기업+노드 (점수 3)
    assert strong["overlaps"][0] == "opportunity:skh_dropped" and strong["proceed"] is False
    active = _rule(ev([1], proceed=True, seed="x", entities=["company:mu", "component:hbm_stack"]))
    assert active["proceed"] is False and "기존 opportunity:mu_hbm" in active["reason"]
    upd = _rule(ev([1], proceed=True, seed="x", novelty="update", entities=["company:mu", "component:hbm_stack"]))
    assert upd["proceed"] is True and upd["overlaps"] == ["opportunity:mu_hbm"]       # skh 와는 노드 하나만 공유 → 겹침 아님
    assert S.rule_overlaps(["component:hbm_stack"], IDEAS) == []                  # 노드 하나만으로는 겹침이 아니다


def test_finalize_orders_proceed_first_and_renumbers():
    out = S.finalize([ev([1], "b", novelty="dup"), ev([2, 3], "a", proceed=True, seed="s"), ev([4], "c", novelty="update")])
    assert [(e["event_id"], e["title"]) for e in out] == [("e1", "a"), ("e2", "c"), ("e3", "b")]


# ---------------------------------------------------------------- 기억(기존 아이디어·최근 선별)
def test_memory_falls_back_to_opportunities_when_v_reports_missing():
    store = FakeStore(reports=None, opportunities=[
        {"opportunity_key": "old_one", "title": "옛 아이디어", "status": "dropped", "status_note": "근거 약함", "stars": 1, "nodes": ["component:mlb_pcb"],
         "companies": [{"company": "company:isu_petasys", "name": "이수페타시스"}, {"name": "비상장"}], "updated_at": "2026-10-01"}])
    ideas, recent, src = S.load_memory(store, "2026-11-08")
    assert src == "opportunities" and recent == []
    assert ideas[0].report_id == "opportunity:old_one" and ideas[0].rejected and ideas[0].reason == "근거 약함"
    assert ideas[0].subjects == ["company:isu_petasys", "component:mlb_pcb"]


def test_memory_reads_v_reports_and_recent_screens_but_not_today():
    reports = [
        {"report_id": "idea:a", "kind": "idea", "title": "A", "subjects": ["company:mu"], "verdict": "rejected", "stars": 2,
         "body": {"rejection_reason": "이미 반영"}, "as_of": "2026-11-01"},
        {"report_id": "screen:2026-11-07", "kind": "screen", "as_of": "2026-11-07",
         "body": {"events": [{"title": "어제 사건", "novelty": "new", "proceed": True, "entities": ["company:mu"]}]}},
        {"report_id": "screen:2026-11-08", "kind": "screen", "as_of": "2026-11-08", "body": {"events": [{"title": "오늘 다시 돌림"}]}},
    ]
    store = FakeStore(reports=reports)
    ideas, recent, src = S.load_memory(store, "2026-11-08")
    assert src == "v_reports" and ideas[0].report_id == "idea:a" and ideas[0].reason == "이미 반영" and ideas[0].rejected
    assert [r["t"] for r in recent] == ["어제 사건"] and recent[0]["report"] == "screen:2026-11-07"
    assert not any(t == "ideas.opportunities" for t, _, _ in store.selects)
    p = S.prepare(store, cfg(), now=NOW, graph_ids=GRAPH)
    assert {"idea:a", "screen:2026-11-07"} <= p.known_reports and "어제 사건" in p.system


# ---------------------------------------------------------------- 저장
def test_save_report_falls_back_across_schemas():
    row = {"report_id": "screen:2026-11-08"}
    store = FakeStore(rpc_schemas=("ideas",))
    res = S.save_report(store, row)
    assert res["rpc"] == "ideas.put_reports" and [s for s, _, _ in store.rpcs] == ["research", "ideas"]
    assert store.rpcs[-1][2] == {"rows": [row]}
    store = FakeStore(rpc_schemas=("public",))
    assert S.save_report(store, row, "public.put_reports")["rpc"] == "public.put_reports" and len(store.rpcs) == 1
    assert S.rpc_targets("ideas.put_reports") == [("ideas", "put_reports"), ("research", "put_reports"), ("public", "put_reports")]


def test_save_report_missing_rpc_is_a_clear_error():
    with pytest.raises(S.ReportRpcMissing, match="0040"):
        S.save_report(FakeStore(rpc_schemas=()), {"report_id": "x"})

    class Rejecting(FakeStore):
        def rpc(self, fn, args, schema="public"):
            return {"upserted": 0, "rejected": [{"i": 1, "reason": "kind"}]}

    with pytest.raises(RuntimeError, match="거부"):
        S.save_report(Rejecting(), {"report_id": "x"})

    class Broken(FakeStore):
        def rpc(self, fn, args, schema="public"):
            raise PostgrestError("PostgREST POST -> 500: boom", 500)

    with pytest.raises(PostgrestError):
        S.save_report(Broken(), {"report_id": "x"})


def test_agent_run_log_disables_itself_when_rpc_missing():
    store = FakeStore(agent_run=False)
    log = S.AgentRunLog(store)
    log.put("running")
    log.put("succeeded", rows=2)
    assert len(store.rpcs) == 1 and log.store is None
    ok = FakeStore()
    S.AgentRunLog(ok).put("succeeded", rows=3, counts={"events": 3}, note="n")
    assert ok.rpcs == [("ops", "put_agent_run", {"row_in": {"task": "screen", "status": "succeeded", "rows": 3, "counts": {"events": 3}, "note": "n"}})]


# ---------------------------------------------------------------- 실제 LLM 래퍼 (가짜 Anthropic 클라이언트)
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_real_wrapper_sends_cached_system_block_and_effort():
    from wsj.briefs.llm import LLM

    sent = []

    class Messages:
        def create(self, **kw):
            sent.append(kw)
            text = json.dumps({"events": [ev([1], "사건")]}, ensure_ascii=False)
            return _Obj(content=[_Obj(type="text", text=text)], stop_reason="end_turn",
                        usage=_Obj(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=3000, server_tool_use=None))

    llm = LLM.__new__(LLM)
    llm._client = _Obj(messages=Messages())
    row = S.screen(prep(), llm, cfg())
    assert sent[0]["system"][0]["cache_control"] == {"type": "ephemeral"} and sent[0]["output_config"] == {"effort": "medium"}
    assert sent[0]["system"][0]["text"].startswith("너는 개인 투자 리서치") and sent[0]["model"] == "claude-sonnet-5-5"
    assert row["body"]["usage"]["cache_write_tokens"] == 3000


# ---------------------------------------------------------------- CLI
def _args(**kw):
    return Namespace(**({"hours": 24, "model": None, "dry_run": False, "plan": False, "out": None, "store": None} | kw))


def _patch_cli(monkeypatch, store, llm):
    import wsj.briefs.llm as L
    import wsj.db as D

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(D, "make_store", lambda settings: store)
    monkeypatch.setattr(L, "LLM", lambda key: llm)


def test_cli_dry_run_prints_report_and_writes_nothing(monkeypatch, capsys):
    store = FakeStore()
    _patch_cli(monkeypatch, store, FakeLLM([lambda u: {"events": [ev([1], "사건")]}]))
    assert S.cli(_args(dry_run=True)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kind"] == "screen" and out["body"]["events"][0]["title"] == "사건"
    assert store.rpcs == []                                                        # 보고서도 실행 기록도 쓰지 않는다


def test_cli_plan_calls_no_llm(monkeypatch, capsys):
    store = FakeStore()
    _patch_cli(monkeypatch, store, FakeLLM([]))
    assert S.cli(_args(plan=True)) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["relevant"] == 4 and out["batches"][0]["items"] == 4 and out["est_usd"] > 0 and store.rpcs == []


def test_cli_saves_report_and_logs_run(monkeypatch, capsys, tmp_path):
    store = FakeStore()
    summary = tmp_path / "summary.md"
    _patch_cli(monkeypatch, store, FakeLLM([lambda u: {"events": [ev([1], "사건", proceed=True, seed="가설")]}]))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert S.cli(_args(out=str(tmp_path / "r.json"))) == 0
    calls = [(s, f) for s, f, _ in store.rpcs]
    assert calls == [("ops", "put_agent_run"), ("research", "put_reports"), ("ops", "put_agent_run")]
    final = store.rpcs[-1][2]["row_in"]
    assert final["status"] == "succeeded" and final["rows"] == 1 and final["counts"]["proceed"] == 1
    assert json.loads((tmp_path / "r.json").read_text())["report_id"].startswith("screen:")
    assert "| e1 | ✅ |" in summary.read_text()


def test_cli_missing_rpc_keeps_report_file_and_exits_3(monkeypatch, capsys, tmp_path):
    store = FakeStore(rpc_schemas=())
    _patch_cli(monkeypatch, store, FakeLLM([lambda u: {"events": [ev([1], "사건")]}]))
    out = tmp_path / "keep.json"
    assert S.cli(_args(out=str(out))) == 3
    assert json.loads(out.read_text())["kind"] == "screen"
    final = store.rpcs[-1][2]["row_in"]
    assert final["status"] == "failed" and "0040" in final["note"]


def test_cli_all_batches_failing_exits_1_without_report(monkeypatch, capsys):
    store = FakeStore()
    _patch_cli(monkeypatch, store, FakeLLM(["x", "y"]))
    assert S.cli(_args()) == 1
    assert [f for _, f, _ in store.rpcs] == ["put_agent_run", "put_agent_run"]     # running → failed, 보고서는 없음
    assert store.rpcs[-1][2]["row_in"]["status"] == "failed"


def test_runner_has_screen_command():
    from wsj.runner import build_parser

    a = build_parser().parse_args(["screen", "--hours", "12", "--dry-run", "--model", "haiku"])
    assert (a.cmd, a.hours, a.dry_run, a.model, a.plan) == ("screen", 12, True, "haiku", False)
