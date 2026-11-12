"""Evidence-grounded F1 vertical slice with recoverable, typed agent handoffs."""
from __future__ import annotations
import hashlib
import json
from datetime import timedelta
from typing import Any, Callable, TypeVar
from pydantic import BaseModel
from wsj.frontier.agents import DISCOVERY, OPPORTUNITY, RESEARCH, INVESTMENT, StructuredLLM
from wsj.frontier.contracts import (
    InputPack, SignalBatch, ThesisBatch, ResearchResult, InvestmentBatch,
)
from wsj.frontier.economics import screen
from wsj.frontier.storage import SQLiteRunStore

T = TypeVar("T", bound=BaseModel)
VERSION = "f1-2026-11-v1"

class EvidenceError(ValueError):
    """An agent invented or misattributed a referenced fact."""

def check_ids(ids: list[str], allowed: set[str], location: str) -> None:
    unknown = set(ids) - allowed
    if unknown:
        raise EvidenceError(f"{location}: unknown source IDs {sorted(unknown)}")

class FrontierPipeline:
    def __init__(self, llm: StructuredLLM, store: SQLiteRunStore, *,
                 max_research: int = 3, min_impact_pct: float = 10.0):
        self.llm, self.store = llm, store
        self.max_research, self.min_impact_pct = max_research, min_impact_pct

    def agent(self, run_id: str, key: str, response_type: type[T], prompt: str,
              payload: dict[str, Any], check: Callable[[T], None]) -> T:
        cached = self.store.get_stage(run_id, key)
        if cached is not None:
            result = response_type.model_validate(cached)
            check(result)
            return result
        result = response_type.model_validate(self.llm.generate(key, prompt, payload))
        check(result)   # never persist ungrounded LLM output
        self.store.save_stage(run_id, key, result.model_dump(mode="json"))
        return result

    def run(self, pack: InputPack) -> dict[str, Any]:
        data = pack.model_dump(mode="json")
        spec = {"version": VERSION, "input": data, "model": getattr(self.llm, "model", "test"),
                "max_research": self.max_research, "min_impact_pct": self.min_impact_pct}
        fingerprint = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        run_id = "frontier:" + fingerprint[:24]
        self.store.begin(run_id, pack.as_of.isoformat(), fingerprint)
        evidence = {e.id: e for e in pack.evidence}
        tickers = {c.ticker.upper(): c for c in pack.companies}
        ids = set(evidence)
        try:
            cached = self.store.get_stage(run_id, "final")
            if cached is not None:
                self.store.finish(run_id, "completed")
                return cached

            def validate_signals(batch: SignalBatch) -> None:
                if len({s.signal_id for s in batch.signals}) != len(batch.signals):
                    raise EvidenceError("duplicate signal ids")
                for s in batch.signals:
                    check_ids(s.evidence_ids, ids, s.signal_id)

            signals = self.agent(run_id, "discovery", SignalBatch, DISCOVERY,
                                 {"as_of": data["as_of"], "evidence": data["evidence"]},
                                 validate_signals)

            def validate_theses(batch: ThesisBatch) -> None:
                if len({t.thesis_id for t in batch.theses}) != len(batch.theses):
                    raise EvidenceError("duplicate thesis ids")
                for t in batch.theses:
                    check_ids(t.evidence_ids, ids, t.thesis_id)
                    for econ in t.economics:
                        check_ids(econ.evidence_ids, ids, t.thesis_id + ":economics")

            if signals.signals:
                theses = self.agent(run_id, "opportunity", ThesisBatch, OPPORTUNITY,
                                    {"as_of": data["as_of"], "signals": signals.model_dump(mode="json"),
                                     "evidence": data["evidence"], "companies": data["companies"]},
                                    validate_theses)
            else:
                theses = ThesisBatch(theses=[])

            triage = [screen(t, tickers, self.min_impact_pct) for t in theses.theses]
            self.store.save_stage(run_id, "triage", triage)
            shortlisted = [t for t, x in zip(theses.theses, triage, strict=True)
                           if x["status"] == "research"][:self.max_research]
            research: list[ResearchResult] = []
            for thesis in shortlisted:
                def validate_research(r: ResearchResult) -> None:
                    if r.thesis_id != thesis.thesis_id:
                        raise EvidenceError("research references wrong thesis")
                    for finding in r.findings:
                        check_ids(finding.evidence_ids, ids, "finding")
                        if finding.status != "unverified" and not finding.evidence_ids:
                            raise EvidenceError("verified research claim missing citation")

                result = self.agent(run_id, "research:" + thesis.thesis_id,
                                    ResearchResult, RESEARCH,
                                    {"thesis": thesis.model_dump(mode="json"),
                                     "triage": next(x for x in triage if x["thesis_id"] == thesis.thesis_id),
                                     "evidence": data["evidence"]},
                                    validate_research)
                research.append(result)

            views = InvestmentBatch(views=[])
            if research:
                short_ids = {t.thesis_id for t in shortlisted}

                def validate_views(batch: InvestmentBatch) -> None:
                    for view in batch.views:
                        if view.thesis_id not in short_ids or view.ticker.upper() not in tickers:
                            raise EvidenceError("investment result refers to unverified thesis/ticker")
                        check_ids(view.evidence_ids, ids, "investment view")

                views = self.agent(run_id, "investment", InvestmentBatch, INVESTMENT,
                                   {"theses": [t.model_dump(mode="json") for t in shortlisted],
                                    "triage": [x for x in triage if x["status"] == "research"],
                                    "research": [x.model_dump(mode="json") for x in research],
                                    "companies": data["companies"]}, validate_views)

            by_id = {r.thesis_id: r for r in research}
            triage_by_id = {t["thesis_id"]: t for t in triage}
            final_views = []
            for view in views.views:
                item = view.model_dump(mode="json")
                company = tickers[view.ticker.upper()]
                impact = next((x for x in triage_by_id[view.thesis_id]["company_impacts"]
                               if x["ticker"].upper() == view.ticker.upper()), {})
                distinct_hosts = {evidence[i].url.host for i in view.evidence_ids}
                age = pack.as_of - company.as_of
                eligible = (impact.get("status") == "hypothetical"
                            and abs(impact["delta_value_to_market_cap_pct"]) >= self.min_impact_pct
                            and len(distinct_hosts) >= 2
                            and by_id[view.thesis_id].conclusion == "supported"
                            and timedelta(0) <= age <= timedelta(days=30))
                if item["stance"] == "candidate" and not eligible:
                    item["stance"] = "watch"
                    item["rationale"] += " [Gate: independent corroboration / current market data / research not sufficient]"
                final_views.append(item)

            output = {
                "version": VERSION, "run_id": run_id, "as_of": data["as_of"],
                "signals": signals.model_dump(mode="json")["signals"],
                "theses": theses.model_dump(mode="json")["theses"],
                "triage": triage, "research": [r.model_dump(mode="json") for r in research],
                "investment": final_views,
                "limitations": [
                    "No autonomous external research in F1; only supplied evidence is examined.",
                    "Economic estimates are hypothetical sensitivities, NOT investment forecasts.",
                    "No buy/sell signals or automatic trade execution.",
                ],
            }
            self.store.save_stage(run_id, "final", output)
            self.store.finish(run_id, "completed")
            return output
        except Exception:
            self.store.finish(run_id, "failed")
            raise
