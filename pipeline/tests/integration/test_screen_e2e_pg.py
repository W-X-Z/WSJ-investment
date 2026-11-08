"""통합 검증: 선별 에이전트 → PostgrestStore(HTTP) → PostgREST 대역 → 실제 Postgres 의 0040 research.put_reports.

각 PR 의 단위 테스트는 가짜 저장소를 쓰므로, 합친 뒤 실제 함수까지 이어지는지는 여기서 본다.
- 0040 마이그레이션 파일의 1)·3) 절을 그대로 올린다 (2) 재무 칸과 4) PostgREST 설정은 이 검증과 무관).
- LLM 만 가짜다 (비용 없음). 나머지는 실행 경로 그대로: wsj.agents.screen.cli → make_store → PostgrestStore → HTTP.
실행: WSJ_IT_PG_DSN=postgresql://postgres@127.0.0.1:54330/postgres pytest tests/integration -q
      (DSN 은 데이터베이스를 만들고 지울 수 있는 관리자 접속. 없으면 건너뛴다.)
"""

from __future__ import annotations

import json
import os
import uuid
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

DSN = os.environ.get("WSJ_IT_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="WSJ_IT_PG_DSN 이 없어 통합 검증을 건너뛴다")
psycopg = pytest.importorskip("psycopg")

from pgrst_stand_in import PgrstStandIn  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[3] / "supabase" / "migrations" / "0040_research_reports.sql"
SERVICE_KEY = "it-service-key"

STUB = """
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end $$;
create schema ideas;
create schema ops;                      -- ops.put_agent_run 은 일부러 없다 → 선별은 실행 기록을 조용히 끈다
create table ideas.clues (               -- 운영 ideas.clues 와 같은 칸 (2026-11-08 information_schema)
  clue_id bigint generated always as identity primary key,
  url text not null unique, title text not null, summary text, published_at timestamptz,
  seen_at timestamptz not null default now(), source_id text not null, source_name text, source_kind text,
  lang text, region text, companies jsonb not null default '[]'::jsonb, nodes text[] not null default '{}',
  relevant boolean not null default true, note text, extra jsonb
);
create table ideas.clue_texts (
  url text primary key, body text, chars integer not null default 0, status text not null,
  http_status integer, fetched_at timestamptz not null default now()
);
grant usage on schema ideas, ops, public to anon, authenticated, service_role;
grant select, insert, update on ideas.clues, ideas.clue_texts to service_role;
"""


def migration_sections(*names: str) -> str:
    text = MIGRATION.read_text(encoding="utf-8")
    out = []
    for n in names:
        start = text.index(f"-- ── {n})")
        nxt = text.find("-- ── ", start + 5)
        out.append(text[start: nxt if nxt != -1 else len(text)])
    return "\n".join(out)


@pytest.fixture()
def db():
    name = f"wsj_it_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(f'create database "{name}"')
    dsn = psycopg.conninfo.make_conninfo(DSN, dbname=name)
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(STUB)
            conn.execute(migration_sections("1", "3"))
        yield dsn
    finally:
        with psycopg.connect(DSN, autocommit=True) as admin:
            admin.execute(f'drop database if exists "{name}" with (force)')


@pytest.fixture()
def stand_in(db):
    s = PgrstStandIn(db, SERVICE_KEY)
    url = s.start()
    yield s, url
    s.stop()


class FakeLLM:
    """wsj.briefs.llm.LLM 자리. 받은 묶음의 첫 단서로 진행(proceed) 사건 하나를 만든다."""

    calls: list[dict] = []

    def __init__(self, api_key: str, max_retries: int = 3) -> None:
        pass

    def complete(self, system, user, model, **kw):
        from wsj.briefs.llm import Completion

        payload = json.loads(user)
        FakeLLM.calls.append(payload)
        cid = payload["clues"][0]["id"]
        events = [{"title": "센트러스 HALEU 작업지시", "summary": "DOE 가 작업지시를 냈다. 두 번째 문장.", "clue_ids": [cid],
                   "entities": ["segment:uranium_enrichment"], "novelty": "new", "overlaps": [], "proceed": True,
                   "reason": "공급 병목 구간의 새 계약", "hypothesis_seed": "서방 농축 공급 부족이 2028~30 계약가를 밀어 올린다"}]
        return Completion(text=json.dumps({"events": events}, ensure_ascii=False), model=model, input_tokens=1200,
                          output_tokens=300, cache_read_tokens=0, cache_write_tokens=800)


def seed(dsn: str, url: str) -> dict[str, int]:
    now = datetime.now(UTC)
    rows = [("https://www.sec.gov/centrus-8k", "Centrus wins DOE HALEU task order", "disclosure", "sec_8k", True, ["segment:uranium_enrichment"]),
            ("https://press.example/bloom-line", "Bloom Energy adds Fremont line", "trade_press", "press", True, []),
            ("https://news.example/stock-move", "Power stocks rally", "trade_press", "press", False, [])]
    ids = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        for u, t, kind, src, rel, nodes in rows:
            (ids[t],) = conn.execute(
                "insert into ideas.clues (url, title, source_kind, source_id, relevant, nodes, seen_at) values (%s,%s,%s,%s,%s,%s,%s) returning clue_id",
                (u, t, kind, src, rel, nodes, now - timedelta(hours=2))).fetchone()
        conn.execute("insert into ideas.clue_texts (url, body, chars, status) values (%s, %s, 40, 'ok')",
                     ("https://www.sec.gov/centrus-8k", "Centrus Energy announced a task order from DOE ..."))
    # 우리 조사 행은 실제 함수(ideas.put_research_sources)로 같은 HTTP 경로를 거쳐 넣는다 — 선별은 이 행을 건너뛰어야 한다
    from wsj.db.postgrest import PostgrestStore

    store = PostgrestStore(url, SERVICE_KEY)
    res = store.rpc("ideas.put_research_sources", {"rows": [{"url": "https://www.sec.gov/leu-10q", "title": "Centrus 10-Q",
                                                              "facts": [{"text": "센트러스 수주잔고 70억 달러", "entity": "segment:uranium_enrichment",
                                                                         "value": 7.0, "unit": "$B"}]}]})
    store.close()
    assert res["ok"] == 1 and res["rejected"] == []
    ids["agent_research"] = res["ids"][0]["clue_id"]
    return ids


def run_cli(monkeypatch, url: str) -> int:
    import wsj.briefs.llm as llm_mod
    from wsj.agents import screen as S

    monkeypatch.setenv("WSJ_STORE", "postgrest")
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_SECRET_KEY", SERVICE_KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "it-not-a-real-key")
    monkeypatch.delenv("SCREEN_REPORT_RPC", raising=False)
    monkeypatch.setattr(llm_mod, "LLM", FakeLLM)
    return S.cli(Namespace(hours=24, model=None, dry_run=False, plan=False, out=None, store="postgrest"))


def test_screen_report_reaches_research_put_reports(db, stand_in, monkeypatch, capsys):
    s, url = stand_in
    ids = seed(db, url)
    FakeLLM.calls.clear()

    assert run_cli(monkeypatch, url) == 0

    # 1) LLM 이 본 단서: 관련 행만, 우리 조사 행과 무관 행은 빠짐
    seen = {c["id"] for call in FakeLLM.calls for c in call["clues"]}
    assert seen == {ids["Centrus wins DOE HALEU task order"], ids["Bloom Energy adds Fremont line"]}

    # 2) HTTP 경로: research 스키마의 put_reports 를 service_role 로, 본문 {"rows": [...]}
    puts = [e for e in s.log if e["path"] == "rpc/put_reports"]
    assert len(puts) == 1 and puts[0]["profile"] == "research" and puts[0]["role"] == "service_role"
    assert set(puts[0]["body"]) == {"rows"} and len(puts[0]["body"]["rows"]) == 1
    agent_runs = [e for e in s.log if e["path"] == "rpc/put_agent_run"]
    assert agent_runs and agent_runs[0]["profile"] == "ops"           # 함수가 없어 404 → 한 번 시도하고 끔

    # 3) DB 에 실제로 저장됐고, 함수 검증(kind·as_of·cites 존재)을 통과했다
    with psycopg.connect(db) as conn:
        rows = conn.execute("select report_id, kind, as_of, cites, body, updated_at from research.reports").fetchall()
    assert len(rows) == 1
    report_id, kind, as_of, cites, body, first_updated = rows[0]
    assert kind == "screen" and report_id == f"screen:{as_of.isoformat()}"
    assert ids["Centrus wins DOE HALEU task order"] in cites
    assert ids["agent_research"] not in cites and ids["Power stocks rally"] not in cites
    assert body["events"][0]["proceed"] is True and body["events"][0]["clue_ids"] == [ids["Centrus wins DOE HALEU task order"]]

    # 4) 같은 날 다시 돌면 같은 report_id 를 덮어쓴다 (행 1개, updated_at 갱신). 이번엔 어제 보고서를 v_reports 로 기억한다
    assert run_cli(monkeypatch, url) == 0
    with psycopg.connect(db) as conn:
        rows = conn.execute("select report_id, updated_at from research.reports").fetchall()
    assert len(rows) == 1 and rows[0][1] > first_updated
    assert any(e["path"] == "v_reports" and e["profile"] == "public" for e in s.log)


def test_put_reports_is_not_callable_without_service_key(stand_in):
    _, url = stand_in
    r = httpx.post(f"{url}/rest/v1/rpc/put_reports", headers={"Content-Profile": "research", "Authorization": "Bearer anon"},
                   json={"rows": []})
    assert r.status_code == 401 and r.json()["code"] == "42501"           # 0040 의 revoke/grant 가 걸린다
    r = httpx.post(f"{url}/rest/v1/rpc/put_reports", headers={"Content-Profile": "nope", "Authorization": f"Bearer {SERVICE_KEY}"},
                   json={"rows": []})
    assert r.status_code == 406                                            # 노출 안 된 스키마


def test_rpc_requires_schema_qualified_name(stand_in):
    from wsj.db.postgrest import PostgrestStore

    _, url = stand_in
    store = PostgrestStore(url, SERVICE_KEY)
    try:
        with pytest.raises(ValueError):
            store.rpc("put_reports", {"rows": []})
        assert store.rpc("research.put_reports", {"rows": []}) == {"ok": 0, "rejected": []}
    finally:
        store.close()
