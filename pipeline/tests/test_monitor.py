"""monitor: 경로 정리·후보·선별·실행·대기열 (네트워크·모델 없음)."""

from __future__ import annotations

from typing import Any

import pytest

from wsj.briefs.llm import Completion
from wsj.monitor import candidates as CA
from wsj.monitor import paths as PA
from wsj.monitor import pick as PK
from wsj.monitor import run as R


def test_clean_keeps_us_kr_and_valid_fields():
    raw = {"headline": "800V DC 전환에 따른 고전압 차단기 수요 확대", "paths": [
        {"axis": "bottleneck", "path": "p", "mechanism": "m", "size": "large",
         "companies": [{"name": "Vertiv", "ticker": "vrt", "market": "US", "role": "beneficiary", "why": "w"},
                       {"name": "Delta", "ticker": "2308", "market": "tw", "role": "beneficiary"},
                       {"name": "LS ELECTRIC", "ticker": "010120", "market": "kr", "role": "weird"}]},
        {"axis": "zzz", "companies": [{"name": "Hitachi", "market": "jp"}]},
    ]}
    out = PA.clean(raw)
    assert out["headline"].startswith("800V")
    assert len(out["paths"]) == 1
    cs = out["paths"][0]["companies"]
    assert [c["ticker"] for c in cs] == ["VRT", "010120"] and cs[1]["role"] == "beneficiary"


class FakeLLM:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self.replies = list(replies)
        self.systems: list[str] = []

    def complete_json(self, system, user, model, repair, **kw):
        self.systems.append(system)
        return self.replies.pop(0), [Completion(text="{}", model=model, input_tokens=3000, output_tokens=800, web_searches=2)]


class FakeStore:
    def __init__(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.saved: list[dict[str, Any]] = []

    def select(self, table, columns=None, filters=None, limit=None, order=None):
        out = []
        for r in self.rows.get(table, []):
            ok = True
            for k, v in (filters or {}).items():
                if isinstance(v, tuple):
                    ok = ok and str(r.get(k)) >= str(v[1])
                elif isinstance(v, list):
                    ok = ok and r.get(k) in v
                else:
                    ok = ok and r.get(k) == v
            if ok:
                out.append(r)
        return out

    def rpc(self, fn, args):
        self.saved += args["rows"]
        for row in args["rows"]:
            tbl = self.rows.setdefault("research.reports", [])
            tbl[:] = [x for x in tbl if x["report_id"] != row["report_id"]] + [row]
        return {"ok": len(args["rows"]), "rejected": []}

    def close(self):
        pass


def _screen() -> dict[str, Any]:
    return {"report_id": "screen:2026-11-10", "as_of": "2026-11-10", "kind": "screen", "body": {"events": [
        {"event_id": "e1", "title": "DOE 고밀도 데이터센터 전력 기준", "summary": "s", "clue_ids": [11, 12], "entities": ["company:vrt"],
         "proceed": True, "hypothesis_seed": "h"},
        {"event_id": "e2", "title": "재보도", "summary": "s", "clue_ids": [13], "entities": [], "proceed": False},
    ]}}


def test_run_end_to_end_with_fakes(monkeypatch):
    store = FakeStore({"research.reports": [_screen()],
                       "ideas.clues": [{"clue_id": 11, "published_at": "2026-11-09T13:00:00Z"}, {"clue_id": 12, "published_at": None,
                                                                                               "seen_at": "2026-11-10T01:00:00Z"}],
                       "core.graph_edges": [], "core.graph_nodes": []})
    explore = {"headline": "고밀도 랙 전환에 따른 배전 장비 수요 확대", "paths": [
        {"axis": "market_growth", "path": "p", "mechanism": "m", "size": "large",
         "companies": [{"name": "Forgent", "ticker": "FPS", "market": "us", "role": "beneficiary", "why": "w"},
                       {"name": "Vertiv", "ticker": "VRT", "market": "us", "role": "beneficiary", "why": "w"},
                       {"name": "Old UPS", "ticker": "OLD", "market": "us", "role": "loser", "why": "w"}]}]}
    llm = FakeLLM([explore, {"picks": [{"id": "e1p1-fps", "why": "시총 대비 영향 큼"}, {"id": "nope", "why": "x"}],
                             "skipped_note": "VRT 는 크다"}])
    monkeypatch.setattr(CA, "resolve_symbol", lambda ctx, c: {"symbol": c["ticker"], "market": "us", "name": c["name"],
                                                              "market_cap_usd": 6e9, "close": 22.0, "exchange": "NYSE"})
    seen = []
    monkeypatch.setattr(PK, "reaction", lambda ctx, s, d: seen.append((s, d)) or {"return_pct": -5.0})
    row = R.run(store, llm, ctx=object(), as_of="2026-11-10")
    b = row["body"]
    assert row["report_id"] == "candidates:2026-11-10" and row["kind"] == "screen"
    assert [x["event_id"] for x in b["events"]] == ["e1"]                    # proceed 만
    assert [c["id"] for c in b["candidates"]] == ["e1p1-fps", "e1p1-vrt", "e1p1-old"]
    assert ("FPS", "2026-11-09") in seen and all(s != "OLD" for s, _ in seen)  # 피해 종목은 반응을 보지 않는다
    sel = [c for c in b["candidates"] if c["status"] == "selected"]
    assert [c["symbol"] for c in sel] == ["FPS"] and sel[0]["pick_reason"]
    assert b["usage"]["cost_usd"] > 0 and "OLD" not in PK.brief_row(sel[0]).values()
    assert "최대 2건" in llm.systems[1]

    R.save(store, row)
    q = R.queue(store, as_of="2026-11-10")
    assert [c["id"] for c in q] == ["e1p1-fps"]
    R.mark(store, "e1p1-vrt", "requested", as_of="2026-11-10")
    assert [c["id"] for c in R.queue(store, as_of="2026-11-10")] == ["e1p1-vrt", "e1p1-fps"]   # 사용자 요청이 앞
    res = R.mark(store, "e1p1-fps", "done", idea="idea:us:fps:2026-11-10", as_of="2026-11-10")
    assert res["candidate"]["idea_report"] == "idea:us:fps:2026-11-10"
    assert [c["id"] for c in R.queue(store, as_of="2026-11-10")] == ["e1p1-vrt"]
    with pytest.raises(LookupError):
        R.mark(store, "zzz", "done", as_of="2026-11-10")


def test_run_without_screen_report_errors():
    assert "error" in R.run(FakeStore({}), None, object(), "2026-11-10")


def test_run_plan_mode_calls_no_model():
    store = FakeStore({"research.reports": [_screen()], "ideas.clues": []})
    row = R.run(store, None, object(), "2026-11-10")
    assert row["body"]["events"] == [{"event_id": "e1", "title": "DOE 고밀도 데이터센터 전력 기준", "planned": True}]
    assert row["body"]["candidates"] == []


def test_same_company_and_reaction_from_bars():
    assert CA.same_company("AXT Inc", "AXT Inc Common Stock")
    assert CA.same_company("Energy Fuels", "Energy Fuels Inc")
    assert not CA.same_company("Vertiv", "Cleveland-Cliffs Inc.")
    assert CA.same_company("성림첨단산업", "SJM")            # 한글·영문이 섞이면 이름만으로 판단하지 않는다
    bars = [{"date": f"2026-11-0{i}", "close": c, "volume": v} for i, c, v in
            [(2, 100, 10), (3, 100, 10), (4, 100, 10), (5, 100, 10), (6, 110, 40)]]
    bench = [{"date": b["date"], "close": 100 + (i == 4)} for i, b in enumerate(bars)]
    r = PK.reaction_from_bars(bars, bench, "2026-11-07")       # 토요일 사건 — 뒤 거래일이 없어도 값이 나온다
    assert r["pre_close"] == 110 and r["since_pct"] == 0.0 and r["last"] == "2026-11-06"
    r2 = PK.reaction_from_bars(bars, bench, "2026-11-06")
    assert r2["pre_close"] == 100 and r2["since_pct"] == 10.0 and r2["volume_ratio"] == 4.0
    assert r2["excess_since_pct"] == 9.0
