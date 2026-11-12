"""Replaceable LLM agent adapter; orchestrator validates every structured result."""
from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any, Protocol

class StructuredLLM(Protocol):
    def generate(self, stage: str, instructions: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...

class AnthropicJSONLLM:
    def __init__(self, model: str, max_tokens: int = 4000):
        if not model:
            raise ValueError("Explicit model required")
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, stage: str, instructions: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        msg = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, temperature=0,
            system=("Ground claims in supplied evidence IDs only. Never fabricate tickers, "
                    "financial values, contracts, or citations. Unknown data must be null; "
                    "hypothetical numeric assumptions must be explicitly labelled. "
                    "Return one JSON object, not Markdown. No automatic buy orders.\n" + instructions),
            messages=[{"role": "user", "content": json.dumps(
                {"stage": stage, "data": payload}, ensure_ascii=False)}],
        )
        raw = "\n".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        if raw.startswith(chr(96) * 3):
            raw = raw.split("\n", 1)[1].rsplit("\n", 1)[0]
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object")
        return parsed

DISCOVERY = """
Detect new changes in technology (physics, engineering, processes), customer demand,
bottlenecks and gaps between expectations and evidence. Compare original publication
vs reporting dates. Re-publication is not a fresh breakthrough.
Return JSON {"signals":[{"signal_id":str,"title":str,"change":str,
"novelty":"new|update|rediscovered","evidence_ids":[str]}]}; max eight.
"""

OPPORTUNITY = """
Generate up to five distinct, falsifiable economic opportunity theses. For each change,
consider direct benefit, hidden suppliers, displacement and countervailing outcomes.
Analyze economic magnitude, time-to-profit and US/Korean listed company leverage early.
Return {"theses":[{"thesis_id":str,"title":str,"mechanism":str,
"value_transfer":str,"horizon":str,"evidence_ids":[str],
"critical_assumptions":[str],"economics":[{"ticker":str,
"annual_affected_units":number|null,"usd_per_unit":number|null,
"company_capture_share":number|null,"incremental_operating_margin":number|null,
"tax_rate":number,"earnings_multiple":number|null,
"years_to_earnings":number|null,"discount_rate":number,
"assumption_rationale":str,"evidence_ids":[str]}]}]}.
Only use supplied tickers. Quantitative parameters are HYPOTHESES, not evidence.
Use null for any unsupported number. Do not assume industry TAM equals equity value.
"""

RESEARCH = """
Independently challenge the thesis using only evidence supplied in this run.
Test technical feasibility, alternative technologies, unit economics, manufacturing,
customers, contractual economics, competitors, dilution and falsifiers.
No external search is available in F1; missing information becomes open_questions.
Return {"thesis_id":str,"findings":[{"statement":str,
"status":"supported|contradicted|unverified","evidence_ids":[str]}],
"objections":[str],"open_questions":[str],
"conclusion":"supported|uncertain|rejected"}.
"""

INVESTMENT = """
Synthesize valuation sensitivity and contradictory evidence into equity RESEARCH
disposition, never a buy/sell instruction. A delta-value sensitivity is not a target
price and excludes baseline business valuation; mention this limitation.
Return {"views":[{"thesis_id":str,"ticker":str,
"stance":"candidate|watch|reject","rationale":str,
"catalysts":[str],"invalidation":[str],"evidence_ids":[str]}]}.
'candidate' only means further human underwriting is warranted.
"""
