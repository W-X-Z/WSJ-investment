"""가설 검증 기록 (ADR-0022) — 예측(watch)의 채점이 ★ 를 움직인다.

★ 는 확신이 아니라 검증 단계다 (ADR-0020): ★1 가설 · ★2 부분 확인(예측 1개 적중 또는 기업 직접 근거) · ★3 확인(적중 2개 이상, 또는 기업 공식 숫자).
이 모듈은 매 실행 끝에 모든 활성 아이디어의 watch 를 읽어
  - 적중(strengthen 예측의 hit)이 쌓이면 ★ 를 올리고 (★3 은 기존 문턱 — 30일 안 기업 직접 근거·근거 점수 7+ — 을 그대로 요구),
  - 반증 조건(direction=weaken)이 성립(hit)하면 가설을 버리고(close),
  - strengthen 예측이 2개 이상 빗나가면 ★1 로 내린다.
채점의 뜻: hit = 적힌 조건이 실제로 일어났다(그대로). strengthen 의 hit 는 적중, weaken 의 hit 는 반증 성립. miss = 그 날짜까지 일어나지 않았다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from wsj.ecosystems.assess import STAR3_MIN_SCORE

MISSES_TO_DEMOTE = 2


def summarize(watch: list[Any] | None) -> dict[str, Any]:
    """watch 목록 → 검증 기록 {predictions, hits, misses, pending, falsified, stage, hit_items, miss_items}."""
    hits, misses, pending, falsified = [], [], 0, []
    n = 0
    for w in watch or []:
        if not isinstance(w, dict):
            continue
        n += 1
        status, direction = w.get("status", "pending"), w.get("direction") or "strengthen"
        if status == "pending":
            pending += 1
        elif status == "hit" and direction == "weaken":
            falsified.append(w)
        elif status == "hit":
            hits.append(w)
        elif status == "miss" and direction == "strengthen":
            misses.append(w)
    stage = 3 if len(hits) >= 2 else 2 if len(hits) >= 1 else 1
    return {"predictions": n, "hits": len(hits), "misses": len(misses), "pending": pending, "falsified": len(falsified), "stage": stage,
            "hit_items": [str(w.get("what") or "")[:80] for w in hits][:3],
            "falsifier": (str(falsified[0].get("what") or "")[:120] + (f" — {falsified[0]['grade_note']}" if falsified[0].get("grade_note") else "")) if falsified else None}


def decide(stars: int, s: dict[str, Any], score: int | None, direct_recent: bool) -> tuple[str, int, str]:
    """(판정, 새 ★, 설명). 판정: close | promote | demote | keep."""
    if s["falsified"]:
        return "close", stars, f"반증 조건 성립 — {s['falsifier']}"
    if s["stage"] > stars:
        new = s["stage"]
        note = f"예측 {s['hits']}건 적중"
        if new == 3 and not (direct_recent and (score or 0) >= STAR3_MIN_SCORE):
            new = 2
            note += f" (★3 은 30일 안 기업 직접 근거·근거 점수 {STAR3_MIN_SCORE}+ 필요)"
        if new > stars:
            return "promote", new, f"{note} → ★{new}"
        return "keep", stars, ""
    if s["misses"] >= MISSES_TO_DEMOTE and stars > 1:
        return "demote", 1, f"예측 {s['misses']}건 빗나감 → ★1"
    return "keep", stars, ""


def _direct_recent(idea: dict[str, Any], now: datetime, days: int = 30) -> bool:
    from wsj.ecosystems.ideas import company_signal_date

    at = company_signal_date(idea)
    return bool(at and at >= (now - timedelta(days=days)).date().isoformat())


def audit(existing: dict[str, dict[str, Any]], rows: list[dict[str, Any]], refresh: list[dict[str, Any]], now: datetime,
          model: str, method: str, keep: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[str]]:
    """실행 끝에 한 번: 고쳐 쓴 행(rows)과 손대지 않은 아이디어(refresh)의 watch 로 검증 기록을 assessment.verification 에 적고 ★ 규칙을 적용한다.
    손대지 않은 아이디어의 ★·상태가 바뀌면 put_ideas 행을 새로 만든다 (keep = 복사할 필드). 반환: (추가 행, 로그)."""
    extra, notes = [], []
    by_key = {r["idea_key"]: r for r in rows}
    for r in rows:
        if r.get("status") != "active" or not isinstance(r.get("assessment"), dict):
            continue
        s = summarize(r.get("watch"))
        r["assessment"]["verification"] = s
        kind, new, note = decide(int(r.get("stars") or 1), s, r["assessment"].get("score"), _direct_recent(r, now))
        if kind == "close":  # LLM 이 같은 실행에서 고쳐 쓴 아이디어는 버리지 않고 ★1 로 — 다시 판단한 쪽을 믿되 반증을 기록한다
            r["stars"], r["trend"] = 1, "weakened"
            r["what_changed"] = f"{r.get('what_changed') or ''} · {note} (고쳐 쓴 가설이라 ★1 로 유지)".strip(" ·")[:300]
            notes.append(f"{r['idea_key']}: {note} — 고쳐 쓴 행이라 ★1")
        elif kind in ("promote", "demote"):
            r["stars"], r["stars_reason"] = new, ((r.get("stars_reason") or "") + f" ({note})")[:300]
            r["trend"] = "strengthened" if kind == "promote" else "weakened"
            r["what_changed"] = f"{r.get('what_changed') or ''} · {note}".strip(" ·")[:300]
            notes.append(f"{r['idea_key']}: {note}")
    for f in refresh:
        key = f["idea_key"]
        x = existing.get(key) or {}
        if key in by_key or (x.get("status") or "active") != "active" or not isinstance(f.get("assessment"), dict):
            continue
        s = summarize(f.get("watch"))
        f["assessment"]["verification"] = s
        kind, new, note = decide(int(x.get("stars") or 1), s, f["assessment"].get("score"), _direct_recent(x, now))
        if kind == "keep":
            continue
        notes.append(f"{key}: {note}")
        if kind == "close":
            extra.append({"idea_key": key, "status": "closed", "trend": "weakened", "close_reason": note[:300], "updated_at": now.isoformat()})
            continue
        extra.append({"idea_key": key, "status": "active", "trend": "strengthened" if kind == "promote" else "weakened",
                      **{k: x.get(k) for k in keep}, "watch": f.get("watch") or x.get("watch") or [], "stars": new,
                      "stars_reason": ((x.get("stars_reason") or "") + f" ({note})")[:300], "what_changed": note[:300],
                      "last_signal_at": str(x.get("last_signal_at"))[:10] if x.get("last_signal_at") else None,
                      "updated_at": now.isoformat(), "model": model, "method": method})
    return extra, notes
