"""Deterministic F1 monitoring-task registration. Scheduling comes in F6."""
from __future__ import annotations
from typing import Any
from wsj.frontier.contracts import Thesis, ResearchResult

def create_monitoring_plan(theses: list[Thesis], triage: list[dict[str, Any]],
                           research: list[ResearchResult], views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_research = {x.thesis_id: x for x in research}
    plans = []
    for thesis in theses:
        verdicts = [v for v in views if v["thesis_id"] == thesis.thesis_id]
        r = by_research.get(thesis.thesis_id)
        if any(v["stance"] == "candidate" for v in verdicts):
            status = "candidate"
        elif (r and r.conclusion == "rejected") or any(v["stance"] == "reject" for v in verdicts):
            status = "rejected"
        else:
            status = "watch"
        triggers = []
        for issue in thesis.critical_assumptions:
            triggers.append({"type": "assumption", "question": issue})
        for view in verdicts:
            triggers.extend({"type": "catalyst", "question": x} for x in view["catalysts"])
            triggers.extend({"type": "invalidation", "question": x} for x in view["invalidation"])
        if r:
            triggers.extend({"type": "research_gap", "question": x} for x in r.open_questions)
        unique = list({(t["type"], t["question"]): t for t in triggers}.values())
        plans.append({"thesis_id": thesis.thesis_id, "status": status,
                      "company_tickers": sorted({e.ticker for e in thesis.economics}),
                      "triggers": unique, "schedule": None,
                      "note": "Recorded for follow-up. No autonomous monitoring is scheduled in F1."})
    return plans
