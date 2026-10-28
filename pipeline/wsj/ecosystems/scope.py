"""시장 범위 (ADR-0021) — 아이디어의 주 기업(primary)은 사용자가 바로 거래할 수 있는 미국·한국 상장사만.

대만·일본·유럽·중국 상장사는 그래프에서 빼지 않는다: 공급망의 변화는 그들에게서 자주 시작되고(TSMC·Unimicron·力成…),
그 소식·월매출·가동률은 신호와 근거로 계속 쓴다. 다만 아이디어의 끝(투자 대상)은 범위 안의 기업이어야 하고,
범위 밖 기업은 companies 에 고객·경쟁·동종(peer) 역할로만 들어간다.
"""
from __future__ import annotations

from typing import Any

# 미국 거래소에 상장된 ADR(TSM·ASX 등)도 거래소가 NYSE·Nasdaq 이므로 범위 안이다. OTC·핑크시트는 밖.
IDEA_EXCHANGES: frozenset[str] = frozenset({"NYSE", "Nasdaq", "NYSE American", "KRX", "KOSDAQ"})
SCOPE_LABEL = "미국(NYSE·Nasdaq)·한국(KRX·KOSDAQ) 상장사"
OUT_OF_SCOPE_REASON = f"시장 범위 밖 — 주 기업은 {SCOPE_LABEL}만 (ADR-0021)"


def exchange_of(node: dict[str, Any] | None) -> str | None:
    return ((node or {}).get("listing") or {}).get("exchange") or None


def in_scope(node: dict[str, Any] | None) -> bool:
    """이 기업 노드가 아이디어의 주 기업이 될 수 있는가."""
    return exchange_of(node) in IDEA_EXCHANGES


def scope_note(node: dict[str, Any] | None) -> str | None:
    """범위 밖 기업을 입력에 표시할 때 쓰는 짧은 꼬리표 (None 이면 범위 안)."""
    ex = exchange_of(node)
    return None if ex in IDEA_EXCHANGES else f"범위 밖({ex or '비상장'})"
