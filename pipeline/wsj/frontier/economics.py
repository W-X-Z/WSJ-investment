"""Reproducible economic bridge. A missing parameter is UNKNOWN, not zero."""

from __future__ import annotations

from typing import Any

from wsj.frontier.contracts import Company, EconomicHypothesis


def estimate(hypothesis: EconomicHypothesis, company: Company) -> dict[str, Any]:
    """Translate explicitly labelled assumptions into attributable equity sensitivity.

    The share of a future profit stream is NOT a buy/target price: existing business,
    customer contracts, dilution, investment needs and price-implied expectations
    still require independent review.
    """
    fields = (
        "annual_affected_units",
        "usd_per_unit",
        "company_capture_share",
        "incremental_operating_margin",
        "earnings_multiple",
        "years_to_earnings",
    )
    missing = [field for field in fields if getattr(hypothesis, field) is None]
    base: dict[str, Any] = {
        "ticker": hypothesis.ticker,
        "evidence_ids": hypothesis.evidence_ids,
        "assumption_rationale": hypothesis.assumption_rationale,
        "status": "incomplete" if missing else "hypothetical",
        "missing": missing,
        "company_market_cap_usd": company.market_cap_usd,
    }
    if missing:
        return base
    units = hypothesis.annual_affected_units
    price = hypothesis.usd_per_unit
    share = hypothesis.company_capture_share
    margin = hypothesis.incremental_operating_margin
    multiple = hypothesis.earnings_multiple
    years = hypothesis.years_to_earnings
    assert all(v is not None for v in (units, price, share, margin, multiple, years))
    value_pool = units * price
    revenue = value_pool * share
    operating_profit = revenue * margin
    after_tax = operating_profit * (1 - hypothesis.tax_rate) if operating_profit > 0 else operating_profit
    undiscounted = after_tax * multiple
    present_value = undiscounted / (1 + hypothesis.discount_rate) ** years
    base.update({
        "annual_value_pool_usd": value_pool,
        "annual_company_revenue_usd": revenue,
        "incremental_operating_profit_usd": operating_profit,
        "incremental_after_tax_profit_usd": after_tax,
        "discounted_incremental_equity_value_usd": present_value,
        "delta_value_to_market_cap_pct": present_value / company.market_cap_usd * 100,
        "warning": "Illustrative sensitivity only; no probability, dilution or baseline valuation incorporated.",
    })
    return base


def screen(thesis: Any, registry: dict[str, Company], min_impact_pct: float = 10) -> dict[str, Any]:
    rows = []
    for assumption in thesis.economics:
        company = registry.get(assumption.ticker.upper())
        if company is None:
            rows.append({"ticker": assumption.ticker, "status": "unverified_listing", "missing": ["verified_company"]})
        else:
            rows.append(estimate(assumption, company))
    plausible = any(
        r.get("status") == "hypothetical" and abs(r["delta_value_to_market_cap_pct"]) >= min_impact_pct
        for r in rows
    )
    status = "research" if plausible else "watch"
    return {"thesis_id": thesis.thesis_id, "status": status, "company_impacts": rows,
            "reason": "hypothetical enterprise-value sensitivity, not an investment decision"}
