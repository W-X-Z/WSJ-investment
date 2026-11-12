"""Versioned, validated handoff contracts. LLM estimates never become reported facts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = {"extra": "forbid"}


class Evidence(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    text: str = Field(min_length=20)
    published_at: datetime
    observed_at: datetime
    source_kind: str = "research"

    @field_validator("published_at", "observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence timestamps require explicit timezone")
        return value


class Company(StrictModel):
    ticker: str = Field(min_length=1)
    name: str = Field(min_length=1)
    exchange: Literal["NASDAQ", "NYSE", "AMEX", "KOSPI", "KOSDAQ"]
    market_cap_usd: float = Field(gt=0, allow_inf_nan=False)
    price_usd: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("company data requires explicit timezone")
        return value


class InputPack(StrictModel):
    as_of: datetime
    evidence: list[Evidence] = Field(min_length=1)
    companies: list[Company] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_pack(self) -> "InputPack":
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of requires explicit timezone")
        if len({e.id for e in self.evidence}) != len(self.evidence):
            raise ValueError("duplicate evidence ids")
        if len({(c.exchange, c.ticker.upper()) for c in self.companies}) != len(self.companies):
            raise ValueError("duplicate listed company")
        if any(e.published_at > self.as_of or e.observed_at > self.as_of for e in self.evidence):
            raise ValueError("future evidence or future observation would cause look-ahead bias")
        if any(c.as_of > self.as_of for c in self.companies):
            raise ValueError("future market-cap snapshot would cause look-ahead bias")
        return self


class Signal(StrictModel):
    signal_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    change: str = Field(min_length=10)
    novelty: Literal["new", "update", "rediscovered"]
    evidence_ids: list[str] = Field(min_length=1)


class SignalBatch(StrictModel):
    signals: list[Signal] = Field(max_length=8)


class EconomicHypothesis(StrictModel):
    """Explicitly hypothetical revenue bridge; these are NOT independently verified."""
    ticker: str = Field(min_length=1)
    annual_affected_units: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    usd_per_unit: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    company_capture_share: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    incremental_operating_margin: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)
    tax_rate: float = Field(default=0.25, ge=0, lt=1, allow_inf_nan=False)
    earnings_multiple: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    years_to_earnings: float | None = Field(default=None, ge=0, le=30, allow_inf_nan=False)
    discount_rate: float = Field(default=0.12, ge=0, lt=1, allow_inf_nan=False)
    assumption_rationale: str = Field(min_length=10)
    evidence_ids: list[str] = Field(default_factory=list)


class Thesis(StrictModel):
    thesis_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    mechanism: str = Field(min_length=20)
    value_transfer: str = Field(min_length=10)
    horizon: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    critical_assumptions: list[str] = Field(min_length=1)
    economics: list[EconomicHypothesis] = Field(default_factory=list)


class ThesisBatch(StrictModel):
    theses: list[Thesis] = Field(max_length=5)


class Finding(StrictModel):
    statement: str = Field(min_length=10)
    status: Literal["supported", "contradicted", "unverified"]
    evidence_ids: list[str] = Field(default_factory=list)


class ResearchResult(StrictModel):
    thesis_id: str = Field(min_length=1)
    findings: list[Finding] = Field(default_factory=list)
    objections: list[str] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)
    conclusion: Literal["supported", "uncertain", "rejected"]


class InvestmentView(StrictModel):
    thesis_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    stance: Literal["candidate", "watch", "reject"]
    rationale: str = Field(min_length=10)
    catalysts: list[str] = Field(default_factory=list)
    invalidation: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class InvestmentBatch(StrictModel):
    views: list[InvestmentView] = Field(default_factory=list)
