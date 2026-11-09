"""N13 카드 변화 비교 → 종목 프로필.

연도별 카드를 칸별로 나란히 놓고 코드로 비교한다(모델 호출 없음). 뜻 풀이는 3단계 에이전트가 한다.
  added    새 해에만 있는 항목(라벨 기준)
  removed  이전 해에만 있던 항목
  changed  같은 라벨인데 값(value)이 바뀐 항목
  filled / emptied  칸 자체가 생기거나 비워짐
고객 칸은 상위 2사 비중 변화, 확인 관계는 이름 기준 추가·삭제도 본다.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from wsj.deep.cards import SLOT_KO, SLOTS

SIMILAR = 0.6   # 라벨이 이 이상 비슷하면 같은 항목으로 본다 ('수직 계열화' ≈ '수직계열화 제조')


def _norm(label: str) -> str:
    return re.sub(r"[\s·・()/,.-]+", "", label or "").lower()


def _by_label(slot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {i["label"]: i for i in slot.get("items") or [] if i.get("label")}


def align(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """b(이전 해)의 라벨을 a(새 해) 라벨에 맞춘다: 정규화 일치 → 가장 비슷한 것(≥ SIMILAR). 반환: 새 라벨로 바꾼 b."""
    out, used = {}, set()
    na = {_norm(k): k for k in a}
    rest = []
    for k, v in b.items():
        if _norm(k) in na and na[_norm(k)] not in used:
            out[na[_norm(k)]] = v
            used.add(na[_norm(k)])
        else:
            rest.append((k, v))
    for k, v in rest:
        best = max(((SequenceMatcher(None, _norm(k), _norm(x)).ratio(), x) for x in a if x not in used), default=(0, None))
        if best[1] is not None and best[0] >= SIMILAR:
            out[best[1]] = v
            used.add(best[1])
        else:
            out[k] = v
    return out


def slot_diff(new: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    a = _by_label(new)
    b = align(a, _by_label(old))
    out: dict[str, Any] = {
        "added": [{"label": k, "value": v.get("value"), "detail": v.get("detail")} for k, v in a.items() if k not in b],
        "removed": [{"label": k, "value": v.get("value"), "detail": v.get("detail")} for k, v in b.items() if k not in a],
        "changed": [{"label": k, "from": b[k].get("value"), "to": v.get("value"), "detail": v.get("detail")}
                    for k, v in a.items() if k in b and (v.get("value") or "") != (b[k].get("value") or "")
                    and (v.get("value") or b[k].get("value"))],
    }
    if old.get("empty") and not new.get("empty"):
        out["filled"] = True
    if new.get("empty") and not old.get("empty"):
        out["emptied"] = True
    if "top2_pct" in new or "top2_pct" in old:
        if new.get("top2_pct") != old.get("top2_pct"):
            out["top2_pct"] = {"from": old.get("top2_pct"), "to": new.get("top2_pct")}
    return {k: v for k, v in out.items() if v}


def relations_diff(new: list[dict[str, Any]], old: list[dict[str, Any]]) -> dict[str, Any]:
    a = {(r.get("type"), r.get("name")): r for r in new or []}
    b = {(r.get("type"), r.get("name")): r for r in old or []}
    return {k: v for k, v in {
        "added": [{"type": t, "name": n, "detail": r.get("detail")} for (t, n), r in a.items() if (t, n) not in b],
        "removed": [{"type": t, "name": n} for (t, n) in b if (t, n) not in a],
    }.items() if v}


def compare(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """cards: 최신 → 과거 순 [{doc:{key}, card:{…}}]. 인접한 두 해씩 비교."""
    out = []
    for i in range(len(cards) - 1):
        new, old = cards[i], cards[i + 1]
        slots = {}
        for s in SLOTS:
            d = slot_diff(new["card"].get(s) or {}, old["card"].get(s) or {})
            if d:
                slots[s] = d
        rel = relations_diff(new["card"].get("relations") or [], old["card"].get("relations") or [])
        out.append({"from": old["doc"]["key"], "to": new["doc"]["key"], "slots": slots, **({"relations": rel} if rel else {})})
    return out


def profile(cards: list[dict[str, Any]], target: dict[str, Any] | None = None,
            recent: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """종목 프로필 절의 재료: 최신 카드 + 연도별 변화 + 빈 칸 + (있으면) 시세·최근 공시."""
    if not cards:
        return {"error": "카드가 없다"}
    latest = cards[0]
    empty = [SLOT_KO[s] for s in SLOTS if (latest["card"].get(s) or {}).get("empty", True)]
    out: dict[str, Any] = {
        "latest": {"doc": latest["doc"], "card": latest["card"]},
        "changes": compare(cards),
        "empty_slots": empty,
        "years": [c["doc"]["key"] for c in cards],
    }
    if target:
        out["target"] = {k: target.get(k) for k in ("symbol", "market", "name", "exchange", "sector", "industry", "price",
                                                    "market_cap", "changes", "range_52w", "cik", "corp_code",
                                                    "sic_description") if target.get(k) is not None}
    if recent:
        out["recent_filings"] = recent
    return out
