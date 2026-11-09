"""① 원천 → 상상 단계 입력. ideas.clues 의 최근 며칠을 출처 종류별로 묶고, 중복 제목을 지운 뒤 번호(c<clue_id>)를 붙인다.

- 관련 표시(relevant)된 항목은 요약까지, 논문·정책·표준은 관련 표시가 없어도 제목만 넣는다(어휘 필터가 새 주제를 놓치지 않게).
- 회사 뉴스 피드(company_feed)는 관련 표시분 제목만, 상한을 둔다. 에이전트가 직접 연 출처(agent_research)·시장 데이터는 뺀다.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

ORDER = ("policy", "regulation", "standards", "research", "release_notes", "company_newsroom", "disclosure",
         "trade_press", "company_feed")
KIND_KO = {"policy": "정책", "regulation": "규제", "standards": "표준", "research": "논문", "release_notes": "릴리스 노트",
           "company_newsroom": "회사 보도자료", "disclosure": "공시", "trade_press": "업계지", "company_feed": "회사 뉴스"}
SKIP = {"agent_research", "market_data"}
TITLE_ONLY_OK = {"policy", "regulation", "standards", "research"}
CAPS = {"company_feed": 120, "trade_press": 450, "research": 260}
COLUMNS = ["clue_id", "title", "summary", "published_at", "seen_at", "source_name", "source_kind", "relevant", "url"]


def fetch(store: Any, days: int = 3, as_of: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
    since = (date.fromisoformat(as_of) if as_of else date.today()) - timedelta(days=days)
    return store.select("ideas.clues", COLUMNS, {"seen_at": ("gte", since.isoformat())}, limit=limit, order="seen_at.desc")


def _key(title: str) -> str:
    return re.sub(r"[\W_]+", "", (title or "").lower())[:48]


def _clip(text: str | None, n: int) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def select(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for r in sorted(rows, key=lambda r: (not r.get("relevant"), str(r.get("published_at") or r.get("seen_at") or "")),
                    reverse=False):
        kind = r.get("source_kind") or "other"
        if kind in SKIP or not r.get("title"):
            continue
        if not r.get("relevant") and kind not in TITLE_ONLY_OK:
            continue
        k = _key(r["title"])
        if not k or k in seen:
            continue
        seen.add(k)
        groups[kind].append(r)
    for kind, cap in CAPS.items():
        if kind in groups:
            groups[kind] = groups[kind][:cap]
    return groups


def render(rows: list[dict[str, Any]], days: int, as_of: str, summary_len: int = 180) -> str:
    groups = select(rows)
    total = sum(len(v) for v in groups.values())
    out = [f"# 원천 다이제스트 {as_of} (최근 {days}일, {total}건 · 번호 = ideas.clues id)", ""]
    for kind in list(ORDER) + sorted(k for k in groups if k not in ORDER):
        items = groups.get(kind)
        if not items:
            continue
        out.append(f"## {KIND_KO.get(kind, kind)} ({len(items)})")
        for r in items:
            day = str(r.get("published_at") or r.get("seen_at") or "")[:10]
            line = f"- [c{r['clue_id']}] ({_clip(r.get('source_name'), 28)}, {day}) {_clip(r['title'], 160)}"
            if r.get("relevant") and kind != "company_feed" and r.get("summary"):
                line += f" — {_clip(r['summary'], summary_len)}"
            out.append(line)
        out.append("")
    return "\n".join(out)
