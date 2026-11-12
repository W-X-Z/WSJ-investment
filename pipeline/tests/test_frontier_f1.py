"""F0/F1 offline contracts, gating, crash recovery and end-to-end agent tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from wsj.frontier.contracts import InputPack, EconomicHypothesis, Company
from wsj.frontier.economics import estimate
from wsj.frontier.flow import FrontierPipeline, EvidenceError
from wsj.frontier.sources import load_recent_clues
from wsj.frontier.storage import SQLiteRunStore

TIME = "2026-11-12T12:00:00+00:00"
DATE = "2026-11-11T12:00:00+00:00"

def pack():
    return {
        "as_of": TIME,
        "evidence": [
            {"id": "e1", "title": "Technical result", "url": "https://research.example.org/paper",
             "text": "A newly tested process reduces the number of measurements per wafer by half.",
             "published_at": DATE, "observed_at": DATE, "source_kind": "paper"},
            {"id": "e2", "title": "Independent customer test", "url": "https://customer.example.com/report",
             "text": "A customer independently tested the new process and reported improved output.",
             "published_at": DATE, "observed_at": DATE, "source_kind": "customer"},
        ],
        "companies": [{"ticker": "ABC", "name": "Example Corp", "exchange": "NASDAQ",
                       "market_cap_usd": 200_000_000, "price_usd": 10, "as_of": DATE}],
    }

def responses():
    return [
        {"signals": [{"signal_id": "s1", "title": "Inspection equipment shift",
                      "change": "New process halves inspection passes, potentially altering equipment budgets.",
                      "novelty": "new", "evidence_ids": ["e1", "e2"]}]},
        {"theses": [{"thesis_id": "t1", "title": "Measurement supplier profit",
                     "mechanism": "A new inspection process might concentrate revenue at specialized suppliers.",
                     "value_transfer": "Existing inspection expenditure shifts toward one equipment class.",
                     "horizon": "two years", "evidence_ids": ["e1", "e2"],
                     "critical_assumptions": ["customer adoption", "equipment capture rate"],
                     "economics": [{"ticker": "ABC", "annual_affected_units": 1_000_000,
                                    "usd_per_unit": 500, "company_capture_share": 0.2,
                                    "incremental_operating_margin": 0.2, "tax_rate": 0.25,
                                    "earnings_multiple": 10, "years_to_earnings": 2,
                                    "discount_rate": 0.12,
                                    "assumption_rationale": "Scenario only, not a sourced industry estimate",
                                    "evidence_ids": []}]}]},
        {"thesis_id": "t1", "findings": [{"statement": "The supplier's customer trial was independently documented.",
            "status": "supported", "evidence_ids": ["e2"]}],
         "objections": ["The provided evidence has no supplier contract"],
         "open_questions": ["How many systems must be purchased?"],
         "conclusion": "supported"},
        {"views": [{"thesis_id": "t1", "ticker": "ABC", "stance": "candidate",
                     "rationale": "The estimated profit opportunity is material but commercially unproven.",
                     "catalysts": ["binding supply agreement"],
                     "invalidation": ["yield fails to scale"], "evidence_ids": ["e1", "e2"]}]},
    ]

class FakeLLM:
    model = "fake-v1"
    def __init__(self, outputs):
        self.outputs = deepcopy(outputs)
        self.calls = []
    def generate(self, stage, instructions, payload):
        self.calls.append(stage)
        return self.outputs.pop(0)

def test_e2e_and_idempotent_resume(tmp_path):
    agent = FakeLLM(responses())
    with SQLiteRunStore(tmp_path / "f.sqlite") as db:
        pipe = FrontierPipeline(agent, db)
        result = pipe.run(InputPack.model_validate(pack()))
        assert agent.calls == ["discovery", "opportunity", "research:t1", "investment"]
        assert result["investment"][0]["stance"] == "candidate"
        assert result["monitoring"][0]["status"] == "candidate"
        assert any(t["type"] == "invalidation" for t in result["monitoring"][0]["triggers"])
        assert result["triage"][0]["status"] == "research"
        assert round(result["triage"][0]["company_impacts"][0]["delta_value_to_market_cap_pct"]) == 60
        assert db.status(result["run_id"]) == "completed"
        again = pipe.run(InputPack.model_validate(pack()))
        assert result == again
        assert len(agent.calls) == 4

def test_missing_numeric_data_means_watch_not_zero(tmp_path):
    input_ = pack()
    outputs = responses()[:2]
    outputs[1]["theses"][0]["economics"][0]["usd_per_unit"] = None
    agent = FakeLLM(outputs)
    with SQLiteRunStore(tmp_path / "f.sqlite") as db:
        result = FrontierPipeline(agent, db).run(InputPack.model_validate(input_))
    assert result["triage"][0]["status"] == "watch"
    assert result["triage"][0]["company_impacts"][0]["missing"] == ["usd_per_unit"]
    assert result["investment"] == []
    assert result["monitoring"][0]["status"] == "watch"
    assert any(t["type"] == "assumption" for t in result["monitoring"][0]["triggers"])
    assert len(agent.calls) == 2

def test_future_evidence_rejected():
    payload = pack()
    payload["evidence"][0]["published_at"] = "2026-11-13T12:00:00+00:00"
    with pytest.raises(ValidationError):
        InputPack.model_validate(payload)

def test_unknown_citation_fails_before_cache(tmp_path):
    outputs = responses()
    outputs[0]["signals"][0]["evidence_ids"] = ["e1", "fake"]
    with SQLiteRunStore(tmp_path / "f.sqlite") as db:
        with pytest.raises(EvidenceError):
            FrontierPipeline(FakeLLM(outputs), db).run(InputPack.model_validate(pack()))
        rows = db.conn.execute("SELECT stage FROM frontier_artifacts").fetchall()
        assert not rows

def test_ticker_not_in_registry_can_never_be_invested(tmp_path):
    outputs = responses()[:2]
    outputs[1]["theses"][0]["economics"][0]["ticker"] = "UNKNOWN"
    with SQLiteRunStore(tmp_path / "f.sqlite") as db:
        r = FrontierPipeline(FakeLLM(outputs), db).run(InputPack.model_validate(pack()))
    assert r["triage"][0]["company_impacts"][0]["status"] == "unverified_listing"
    assert r["investment"] == []

def test_insufficient_independent_sources_downgrades_candidate(tmp_path):
    p = pack()
    p["evidence"][1]["url"] = "https://research.example.org/second"
    with SQLiteRunStore(tmp_path / "f.sqlite") as db:
        r = FrontierPipeline(FakeLLM(responses()), db).run(InputPack.model_validate(p))
    assert r["investment"][0]["stance"] == "watch"

def test_negative_margin_does_not_create_tax_credit():
    c = Company.model_validate(pack()["companies"][0])
    h = EconomicHypothesis(
        ticker="ABC", annual_affected_units=100, usd_per_unit=500,
        company_capture_share=0.5, incremental_operating_margin=-0.1,
        earnings_multiple=10, years_to_earnings=1,
        assumption_rationale="Explicit downside only, no future tax shield assumed",
    )
    r = estimate(h, c)
    assert r["incremental_after_tax_profit_usd"] == -2500

def test_recent_clues_reader_excludes_self_generated_research():
    class Store:
        def select(self, table, columns=None, filters=None, limit=None, order=None):
            if table == "ideas.clues":
                return [
                    {"clue_id": 1, "title": "Technical paper", "url": "https://research.example.org/one",
                     "summary": "A customer could require twice the number of test probes next year.",
                     "published_at": DATE, "seen_at": DATE, "source_kind": "research",
                     "source_id": "journal"},
                    {"clue_id": 2, "title": "Self-generated", "url": "https://research.example.org/two",
                     "summary": "This content comes from a previous agent's generated research.",
                     "published_at": DATE, "seen_at": DATE, "source_kind": "agent_research",
                     "source_id": "agent_research"},
                ]
            return []
    out = load_recent_clues(datetime.fromisoformat(TIME), 7, [], store=Store())
    assert [x.id for x in out.evidence] == ["clue:1"]

def test_bad_ticker_or_price_snapshot_timestamp_rejected():
    p = pack()
    p["companies"][0]["as_of"] = "2026-11-13T12:00:00+00:00"
    with pytest.raises(ValidationError):
        InputPack.model_validate(p)
