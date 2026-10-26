"""Claude API 래퍼 — 단계별 호출, 웹 검색 서버 도구, JSON 추출·복구, 토큰·비용 집계.

검증 (2026-10-26, anthropic SDK 2.3.0): 모델 ID claude-sonnet-5-5 / claude-opus-5-5 / claude-fable-5-1,
웹 검색 도구 {"type": "web_search_20250305", "name": "web_search", "max_uses": N} ($10 / 1,000회),
인용은 text 블록의 citations[].type == "web_search_result_location". 검색이 길어지면 stop_reason == "pause_turn"
이 올 수 있어 assistant 턴을 되돌려 이어 보낸다.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("wsj.briefs.llm")

MODELS = {
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
    "fable": "claude-fable-5-1",
    "haiku": "claude-haiku-5-5",
}
# USD per 1M tokens (input, output). 모르는 모델은 None → 비용 미산출.
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-fable-5-1": (10.0, 50.0),
}
WEB_SEARCH_USD = 0.01
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}


def resolve_model(name: str) -> str:
    return MODELS.get(name, name)


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    web_searches: int = 0
    stop_reason: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0
    raw_content: list[Any] = field(default_factory=list)

    @property
    def cost_usd(self) -> float | None:
        p = PRICES.get(self.model)
        if not p:
            return None
        base_in = self.input_tokens - self.cache_read_tokens - self.cache_write_tokens
        cost = (
            max(base_in, 0) * p[0]
            + self.cache_read_tokens * p[0] * 0.1
            + self.cache_write_tokens * p[0] * 1.25
            + self.output_tokens * p[1]
        ) / 1_000_000
        return cost + self.web_searches * WEB_SEARCH_USD

    def usage(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "web_searches": self.web_searches,
            "stop_reason": self.stop_reason,
            "elapsed_s": round(self.elapsed_s, 1),
            "cost_usd": round(self.cost_usd, 4) if self.cost_usd is not None else None,
        }


class LLM:
    def __init__(self, api_key: str, max_retries: int = 3) -> None:
        import anthropic  # 지연 임포트: 키 없는 --dry-run 에서는 SDK 가 없어도 된다

        self._client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries, timeout=600.0)

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        max_tokens: int = 8000,
        web_search_max_uses: int | None = None,
        temperature: float | None = None,
        prior: list[dict[str, Any]] | None = None,
        thinking_budget: int | None = None,
    ) -> Completion:
        """단일 턴 호출. prior 를 주면 그 뒤에 user 를 붙인다 (복구 재시도용). pause_turn 은 자동으로 이어 간다.
        thinking_budget 을 주면 확장 사고를 켠다 (출력 토큰으로 과금, temperature 와 동시 사용 불가)."""
        messages: list[dict[str, Any]] = list(prior or []) + [{"role": "user", "content": user}]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": messages,
        }
        if thinking_budget:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            kwargs["max_tokens"] = max(max_tokens, thinking_budget + 4000)
        elif temperature is not None:
            kwargs["temperature"] = temperature
        if web_search_max_uses:
            kwargs["tools"] = [{**WEB_SEARCH_TOOL, "max_uses": web_search_max_uses}]

        comp = Completion(text="", model=model)
        t0 = time.monotonic()
        for _turn in range(4):
            try:
                resp = self._client.messages.create(**kwargs)
            except Exception as exc:  # noqa: BLE001
                # 모델이 이 형태의 thinking 파라미터를 거부하면 끄고 한 번 더
                if "thinking" in kwargs and "thinking" in str(exc).lower():
                    log.warning("thinking rejected by API (%s) — retrying without", str(exc)[:120])
                    kwargs.pop("thinking")
                    resp = self._client.messages.create(**kwargs)
                else:
                    raise
            u = resp.usage
            comp.input_tokens += u.input_tokens or 0
            comp.output_tokens += u.output_tokens or 0
            comp.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
            comp.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0
            stu = getattr(u, "server_tool_use", None)
            if stu is not None:
                comp.web_searches += getattr(stu, "web_search_requests", 0) or 0
            comp.stop_reason = resp.stop_reason
            comp.raw_content.extend(resp.content)
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    comp.text += block.text
                    for c in getattr(block, "citations", None) or []:
                        if getattr(c, "type", "") == "web_search_result_location":
                            comp.citations.append(
                                {
                                    "url": c.url,
                                    "title": getattr(c, "title", None),
                                    "cited_text": (getattr(c, "cited_text", "") or "")[:200],
                                }
                            )
            if resp.stop_reason != "pause_turn":
                break
            # 서버 도구가 턴을 멈춤 — assistant 내용을 되돌려 이어 간다
            kwargs["messages"] = kwargs["messages"] + [{"role": "assistant", "content": resp.content}]
        comp.elapsed_s = time.monotonic() - t0
        log.info(
            "%s in=%d out=%d cache_r=%d searches=%d stop=%s %.1fs cost=%s",
            model,
            comp.input_tokens,
            comp.output_tokens,
            comp.cache_read_tokens,
            comp.web_searches,
            comp.stop_reason,
            comp.elapsed_s,
            comp.usage()["cost_usd"],
        )
        return comp

    def complete_json(
        self, system: str, user: str, model: str, repair_user: str, **kw: Any
    ) -> tuple[dict[str, Any], list[Completion]]:
        comps: list[Completion] = []
        comp = self.complete(system, user, model, **kw)
        comps.append(comp)
        try:
            return extract_json(comp.text), comps
        except ValueError as exc:
            log.warning("JSON parse failed (%s); asking for repair", exc)
            prior = [
                {"role": "user", "content": user},
                {"role": "assistant", "content": comp.text or "(empty)"},
            ]
            kw2 = {k: v for k, v in kw.items() if k != "web_search_max_uses"}
            comp2 = self.complete(system, repair_user.format(error=str(exc)[:200]), model, prior=prior, **kw2)
            comps.append(comp2)
            return extract_json(comp2.text), comps


_RE_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def extract_json(text: str) -> dict[str, Any]:
    """마지막 ```json 블록 → 없으면 가장 바깥 {} → 실패 시 ValueError."""
    if not text or not text.strip():
        raise ValueError("empty response")
    blocks = _RE_FENCE.findall(text)
    candidates = list(reversed(blocks))
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last > first:
        candidates.append(text[first : last + 1])
    last_err: Exception | None = None
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as exc:
            last_err = exc
            # 흔한 오류: 문자열 안의 제어문자
            try:
                obj = json.loads(cand, strict=False)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass
    raise ValueError(f"no parseable JSON object ({last_err})")


def sum_usage(comps: list[Completion]) -> dict[str, Any]:
    tot = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "web_searches": 0,
        "cost_usd": 0.0,
        "elapsed_s": 0.0,
    }
    for c in comps:
        tot["input_tokens"] += c.input_tokens
        tot["output_tokens"] += c.output_tokens
        tot["cache_read_tokens"] += c.cache_read_tokens
        tot["web_searches"] += c.web_searches
        tot["elapsed_s"] += c.elapsed_s
        if c.cost_usd is not None:
            tot["cost_usd"] += c.cost_usd
    tot["cost_usd"] = round(tot["cost_usd"], 4)
    tot["elapsed_s"] = round(tot["elapsed_s"], 1)
    return tot
