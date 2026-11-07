"""선별 에이전트 (2단계) — 지난 창의 관련 단서를 '변화 사건'으로 묶고, 아이디어 작업을 받을 사건을 고른다. 하루 보고서 한 건.

    python -m wsj screen --hours 24 [--dry-run] [--plan] [--model sonnet] [--out data/screen/report.json]

1단계(ecosystems/clues.py, Haiku)가 relevant·테마를 붙여 둔 단서를 받는다.
  읽기  ideas.clues (relevant, seen_at ≥ 창 시작) + ideas.clue_texts (본문 앞 SCREEN_BODY_CHARS 자)
        + 기존 아이디어·기각 기록: public.v_reports(kind=idea) → 없거나 비면 ideas.opportunities
        + 최근 선별 보고서: public.v_reports(kind=screen, 지난 3일, 오늘 것 제외) — 이미 고른 사건을 다시 고르지 않게
  묶음  원본(공시·규칙·표준·논문)부터, 같은 기업·노드 단서끼리 가까이 — 묶음마다 한 번 부른다.
        시스템 프롬프트 + 기존 아이디어 목록은 모든 호출에서 같다 → 프롬프트 캐시 (첫 호출만 쓰기 값).
  병합  묶음이 둘 이상이면 마지막에 한 번 더 불러 묶음 사이의 같은 사건을 합친다 (출력은 출처 사건 id 만 — 단서 id 는 코드가 합친다).
  규칙  dup → 진행 안 함 · 기존 아이디어(기각 포함)와 겹치는데 update 가 아니면 진행 안 함 · 그래프 id 로 겹치는 기존 아이디어를 overlaps 에 더한다.
  저장  research.put_reports (SCREEN_REPORT_RPC; 404/406 이면 ideas → public 순) — report_id 'screen:YYYY-MM-DD'(KST).
        실행 기록 ops.put_agent_run(task=screen) — 없으면 건너뛴다.
예산  실행당 SCREEN_MAX_INPUT_TOKENS(기본 40만, 캐시 포함 입력 전부)·SCREEN_MAX_USD(기본 $2).
      다음 묶음(+병합 몫)이 상한을 넘을 것 같으면 더 보내지 않고 처리한 만큼 보고서를 쓴다 (stats.truncated).
출력은 proceed·reason 까지다 — 매수·매도·목표가 같은 투자 권유는 쓰지 않는다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from wsj.util import chunked

log = logging.getLogger("wsj.agents.screen")

TASK = "screen"
CREATED_BY = "screen-agent"
RPC_SCHEMAS = ("research", "ideas", "public")
NOVELTY = ("new", "update", "dup")
REJECTED = {"dropped", "rejected", "reject", "rejection", "no", "pass", "skip", "skipped"}
ENTITY_RE = re.compile(r"^[a-z][a-z_]*:[A-Za-z0-9_.\-]+$")
KST = timedelta(hours=9)

BATCH_MAX_TOKENS = 24_000            # 묶음 호출 max_tokens (실제로 나온 만큼만 과금 — 예산 어림은 아래 *_output_estimate)
MERGE_MAX_TOKENS = 24_000
STRONG_OVERLAP = 3                   # 그래프 id 로 본 겹침 점수가 이 이상이면 '기각 아이디어' 규칙에 쓴다 (기업 2점·그 밖 노드 1점)
RULE_OVERLAP = 2                     # 이 이상이면 overlaps 에 더한다 (기업 하나 공유)

# 층 순서 — 원본이 먼저 (예산이 모자라 잘리면 뒤쪽이 잘린다)
LAYER_RANK = {"raw": 0, "disclosure": 0, "newsroom": 1, "issue": 1, "market": 1, "press": 2, "company": 3}
KIND_LAYER = {"company_feed": "company", "disclosure": "disclosure", "issue": "issue", "company_newsroom": "newsroom",
              "standards": "raw", "conference": "raw", "research": "raw", "policy": "raw", "release_notes": "raw",
              "tech_signal": "raw", "regulation": "raw", "code": "raw", "jobs": "raw", "market_move": "market"}


# ---------------------------------------------------------------- 가격·토큰
@dataclass(frozen=True)
class Price:
    """USD / 1M 토큰."""

    input: float
    output: float
    cache_read: float
    cache_write: float

    def cost(self, input_tokens: float = 0, output_tokens: float = 0, cache_read: float = 0, cache_write: float = 0) -> float:
        return (input_tokens * self.input + output_tokens * self.output + cache_read * self.cache_read
                + cache_write * self.cache_write) / 1_000_000


PRICES: dict[str, Price] = {
    "claude-sonnet-5-5": Price(2.0, 10.0, 0.10, 2.50),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.01, 0.125),
    "claude-opus-5-5": Price(4.0, 20.0, 0.20, 5.0),
}


def price_for(model: str) -> Price:
    """모르는 모델은 표에서 가장 비싼 값으로 어림한다 (예산 상한이 느슨해지지 않게)."""
    if model in PRICES:
        return PRICES[model]
    log.warning("가격표에 없는 모델 %s — 가장 비싼 값으로 어림한다", model)
    return max(PRICES.values(), key=lambda p: p.output)


def estimate_tokens(text: str) -> int:
    """보수적 어림: ASCII 3.5자당 1토큰, 그 밖(한글·한자)은 1자당 1토큰."""
    n_ascii = sum(1 for ch in text if ord(ch) < 128)
    return int(n_ascii / 3.5 + (len(text) - n_ascii)) + 1


def kst_date(now: datetime) -> str:
    return (now.astimezone(UTC) + KST).date().isoformat()


# ---------------------------------------------------------------- 설정
@dataclass
class ScreenConfig:
    hours: int = 24
    model: str = "claude-sonnet-5-5"
    max_input_tokens: int = 400_000
    max_usd: float = 2.0
    body_chars: int = 4000
    batch_tokens: int = 60_000
    batch_max_items: int = 160
    effort: str | None = "medium"
    report_rpc: str = "put_reports"
    recent_days: int = 3
    max_ideas: int = 200

    @classmethod
    def from_settings(cls, settings: Any, **override: Any) -> ScreenConfig:
        from wsj.briefs.llm import resolve_model

        cfg = cls(model=resolve_model(settings.screen_model), max_input_tokens=int(settings.screen_max_input_tokens),
                  max_usd=float(settings.screen_max_usd), body_chars=int(settings.screen_body_chars),
                  batch_tokens=int(settings.screen_batch_tokens), effort=(settings.screen_effort or None),
                  report_rpc=settings.screen_report_rpc or "put_reports")
        for k, v in override.items():
            if v is not None:
                setattr(cfg, k, resolve_model(v) if k == "model" else v)
        return cfg


# ---------------------------------------------------------------- 사용량·예산
@dataclass
class Usage:
    """input_tokens 는 API 의미 그대로 '캐시 밖 입력'이다. 캐시 읽기·쓰기는 따로 센다."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    calls: int = 0

    def add(self, comp: Any) -> None:
        self.input_tokens += int(getattr(comp, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(comp, "output_tokens", 0) or 0)
        self.cache_read_tokens += int(getattr(comp, "cache_read_tokens", 0) or 0)
        self.cache_write_tokens += int(getattr(comp, "cache_write_tokens", 0) or 0)
        self.calls += 1

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    def est_usd(self, price: Price) -> float:
        return price.cost(self.input_tokens, self.output_tokens, self.cache_read_tokens, self.cache_write_tokens)

    def as_dict(self, price: Price) -> dict[str, Any]:
        return {"model": self.model, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "cache_read_tokens": self.cache_read_tokens, "cache_write_tokens": self.cache_write_tokens,
                "est_usd": round(self.est_usd(price), 4), "calls": self.calls}


@dataclass
class PlannedCall:
    system_tokens: int
    user_tokens: int
    output_tokens: int


@dataclass
class Budget:
    max_input_tokens: int
    max_usd: float
    price: Price

    def project(self, calls: list[PlannedCall], cache_warm: bool) -> tuple[int, float]:
        """앞으로 부를 호출들의 (입력 토큰, 비용) 어림. 시스템 블록은 첫 호출만 캐시 쓰기, 나머지는 캐시 읽기."""
        tokens, usd, warm = 0, 0.0, cache_warm
        for c in calls:
            tokens += c.system_tokens + c.user_tokens
            usd += self.price.cost(c.user_tokens, c.output_tokens,
                                   cache_read=c.system_tokens if warm else 0, cache_write=0 if warm else c.system_tokens)
            warm = True
        return tokens, usd

    def exceeded(self, usage: Usage, calls: list[PlannedCall], cache_warm: bool) -> str | None:
        """상한을 넘을 것 같으면 그 이유('max_input_tokens' | 'max_usd'), 아니면 None."""
        tokens, usd = self.project(calls, cache_warm)
        if usage.total_input + tokens > self.max_input_tokens:
            return "max_input_tokens"
        if usage.est_usd(self.price) + usd > self.max_usd:
            return "max_usd"
        return None


def batch_output_estimate(n_items: int) -> int:
    """사건 최대 25개 × 한국어 요약·사유 ≈ 단서 160개 묶음에 1만 토큰."""
    return min(BATCH_MAX_TOKENS, 2000 + 50 * n_items)


def merge_output_estimate(user_tokens: int) -> int:
    """병합은 합친·바뀐 사건만 낸다 — 입력의 절반 안쪽."""
    return min(MERGE_MAX_TOKENS, 1000 + int(0.5 * user_tokens))


# ---------------------------------------------------------------- 입력: 단서
def clue_layer(row: dict[str, Any]) -> str:
    if row.get("source_kind") == "market_move":
        return "market"
    ex = row.get("extra") if isinstance(row.get("extra"), dict) else {}
    if ex.get("layer") in LAYER_RANK:
        return ex["layer"]
    return KIND_LAYER.get(row.get("source_kind") or "", "press")


def clue_tags(row: dict[str, Any]) -> list[str]:
    """단서에 붙은 그래프 id (기업 id + 노드)."""
    out: list[str] = []
    for c in row.get("companies") or []:
        cid = c.get("company") if isinstance(c, dict) else None
        if cid and cid not in out:
            out.append(cid)
    for n in row.get("nodes") or []:
        if n and n not in out:
            out.append(n)
    return out


def clue_item(row: dict[str, Any], body: str | None, body_chars: int) -> dict[str, Any]:
    """프롬프트에 넣는 단서 한 줄 (짧은 키 — 프롬프트에 뜻을 적어 둔다)."""
    ex = row.get("extra") if isinstance(row.get("extra"), dict) else {}
    co: list[str] = []
    for c in row.get("companies") or []:
        if isinstance(c, dict):
            v = c.get("company") or (c.get("name") or "").strip()
            if v and v not in co:
                co.append(v)
    nodes = [n for n in row.get("nodes") or [] if n and n not in co]
    when = str(row.get("published_at") or row.get("seen_at") or "")[:10]
    item: dict[str, Any] = {"id": int(row["clue_id"]), "t": (row.get("title") or "").strip()[:400],
                            "s": (row.get("summary") or "").strip()[:500] or None, "src": row.get("source_name") or row.get("source_id"),
                            "layer": clue_layer(row), "date": when or None, "co": co[:8] or None, "nodes": nodes[:8] or None,
                            "note": row.get("note") or None, "themes": ex.get("themes") or None}
    if body:
        item["body"] = body.strip()[:body_chars]
    return {k: v for k, v in item.items() if v is not None}


CLUE_COLUMNS = ["clue_id", "url", "title", "summary", "published_at", "seen_at", "source_id", "source_name", "source_kind",
                "companies", "nodes", "note", "extra"]


def load_clues(store: Any, since: datetime) -> tuple[int, list[dict[str, Any]]]:
    """(창 안의 단서 수 전체, 그중 relevant 행)."""
    iso = since.astimezone(UTC).isoformat()
    try:
        n_all = len(store.select("ideas.clues", ["clue_id"], {"seen_at": ("gte", iso)}))
    except Exception as exc:  # noqa: BLE001 - 세기만 하는 것이라 실패해도 계속
        log.warning("단서 수를 세지 못함: %s", exc)
        n_all = -1
    rows = store.select("ideas.clues", CLUE_COLUMNS, {"relevant": True, "seen_at": ("gte", iso)})
    return (n_all if n_all >= 0 else len(rows)), rows


def load_bodies(store: Any, urls: list[str], chunk: int = 40) -> dict[str, str]:
    """본문이 있는(status=ok) 단서만. 주소가 길어 40개씩 묻는다."""
    out: dict[str, str] = {}
    for part in chunked(urls, chunk):
        try:
            for r in store.select("ideas.clue_texts", ["url", "body"], {"url": part, "status": "ok"}):
                if r.get("body"):
                    out[r["url"]] = r["body"]
        except Exception as exc:  # noqa: BLE001 - 본문 없이도 제목·요약으로 선별한다
            log.warning("본문을 읽지 못함 (%d건): %s", len(part), str(exc)[:200])
    return out


# ---------------------------------------------------------------- 입력: 기존 아이디어·최근 선별
@dataclass
class Idea:
    report_id: str
    title: str
    subjects: list[str] = field(default_factory=list)
    verdict: str | None = None
    stars: int | None = None
    reason: str | None = None

    @property
    def rejected(self) -> bool:
        return (self.verdict or "").strip().lower() in REJECTED

    def prompt_row(self) -> dict[str, Any]:
        row = {"id": self.report_id, "v": self.verdict, "stars": self.stars, "t": self.title[:120], "subj": self.subjects[:8] or None,
               "why": (self.reason or "")[:240] or None}
        return {k: v for k, v in row.items() if v is not None}


def _as_obj(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            o = json.loads(v)
            return o if isinstance(o, dict) else {}
        except ValueError:
            return {}
    return {}


def idea_from_report(r: dict[str, Any]) -> Idea | None:
    rid = r.get("report_id") or r.get("id")
    if not rid or not r.get("title"):
        return None
    body = _as_obj(r.get("body"))
    reason = r.get("rejection_reason") or body.get("rejection_reason")
    subjects = [s for s in (r.get("subjects") or []) if isinstance(s, str)]
    stars = r.get("stars")
    return Idea(str(rid), str(r["title"]), subjects, r.get("verdict") or r.get("status"),
                int(stars) if isinstance(stars, (int, float)) else None, str(reason) if reason else None)


def idea_from_opportunity(r: dict[str, Any]) -> Idea | None:
    key = r.get("opportunity_key")
    if not key or not r.get("title"):
        return None
    subjects = [n for n in r.get("nodes") or [] if isinstance(n, str)]
    for c in r.get("companies") or []:
        cid = c.get("company") if isinstance(c, dict) else None
        if cid and cid not in subjects:
            subjects.insert(0, cid)
    stars = r.get("stars")
    return Idea(f"opportunity:{key}", str(r["title"]), subjects, r.get("status"),
                int(stars) if isinstance(stars, (int, float)) else None, r.get("status_note") or None)


def _sort_recent(rows: list[dict[str, Any]], *keys: str) -> list[dict[str, Any]]:
    def k(r: dict[str, Any]) -> str:
        return max((str(r.get(x) or "") for x in keys), default="")

    return sorted(rows, key=k, reverse=True)


def load_memory(store: Any, as_of: str, recent_days: int = 3, max_ideas: int = 200) -> tuple[list[Idea], list[dict[str, Any]], str]:
    """(기존 아이디어, 최근 선별 사건, 어디서 읽었나). public.v_reports 가 있으면 그것, 없거나 아이디어가 없으면 ideas.opportunities."""
    ideas: list[Idea] = []
    source = "none"
    try:
        rows = store.select("public.v_reports", ["*"], {"kind": ["idea"]}, limit=max_ideas * 2)
        ideas = [i for i in (idea_from_report(r) for r in _sort_recent(rows, "updated_at", "as_of", "created_at")) if i]
        source = "v_reports" if ideas else source
    except Exception as exc:  # noqa: BLE001 - 0040 전
        log.info("public.v_reports 를 읽지 못함 (0040 전?) — ideas.opportunities 로: %s", str(exc)[:160])
    if not ideas:
        try:
            rows = store.select("ideas.opportunities", ["opportunity_key", "title", "status", "status_note", "stars", "nodes", "companies",
                                                         "updated_at"])
            ideas = [i for i in (idea_from_opportunity(r) for r in _sort_recent(rows, "updated_at")) if i]
            source = "opportunities" if ideas else source
        except Exception as exc:  # noqa: BLE001
            log.warning("ideas.opportunities 도 읽지 못함 — 기존 아이디어 없이 선별한다: %s", str(exc)[:160])
    recent: list[dict[str, Any]] = []
    try:
        start = (date.fromisoformat(as_of) - timedelta(days=recent_days)).isoformat()
        rows = store.select("public.v_reports", ["report_id", "as_of", "body"], {"kind": "screen", "as_of": ("gte", start)}, limit=20)
        for r in _sort_recent(rows, "as_of"):
            if r.get("report_id") == f"screen:{as_of}":
                continue                                   # 같은 날 다시 돌린 경우 — 자기 자신과 겹친다고 하지 않게
            for e in _as_obj(r.get("body")).get("events") or []:
                if isinstance(e, dict) and e.get("title"):
                    recent.append({"report": r["report_id"], "t": str(e["title"])[:120], "novelty": e.get("novelty"),
                                   "proceed": bool(e.get("proceed")), "ent": [x for x in e.get("entities") or [] if isinstance(x, str)][:5]})
    except Exception as exc:  # noqa: BLE001 - 0040 전이거나 아직 보고서가 없다
        log.info("최근 선별 보고서를 읽지 못함: %s", str(exc)[:160])
    return ideas[:max_ideas], recent[:80], source


def graph_node_ids() -> set[str]:
    try:
        from wsj.ecosystems.ontology import load_graph

        return {n["id"] for n in load_graph()["nodes"] if n.get("id")}
    except Exception as exc:  # noqa: BLE001 - 그래프가 없으면 단서의 태그만 믿는다
        log.warning("그래프를 읽지 못함: %s", exc)
        return set()


# ---------------------------------------------------------------- 묶음
def order_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """원본·본문 있는 단서가 앞으로, 같은 주인공(첫 그래프 기업 → 첫 노드 → 층) 단서끼리 붙여 둔다.
    예산이 모자라 뒤 묶음을 못 보내면 덜 중요한 쪽이 잘리고, 같은 사건의 단서는 되도록 한 묶음에 들어간다."""

    def key(it: dict[str, Any]) -> tuple[int, int, str]:
        recent_first = "".join(chr(255 - ord(ch)) for ch in it["date"]) if it.get("date") else "￿"   # 최근 날짜가 먼저, 날짜 없으면 끝
        return (LAYER_RANK.get(it.get("layer", "press"), 2), 0 if it.get("body") else 1, recent_first)

    def cluster(it: dict[str, Any]) -> str:
        ids = [c for c in it.get("co") or [] if ENTITY_RE.match(c)]
        if ids:
            return ids[0]
        if it.get("nodes"):
            return it["nodes"][0]
        return f"layer:{it.get('layer')}"

    groups: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        groups.setdefault(cluster(it), []).append(it)
    for g in groups.values():
        g.sort(key=key)
    ordered = sorted(groups.values(), key=lambda g: (key(g[0])[:2], -len(g), key(g[0])[2]))
    return [it for g in ordered for it in g]


@dataclass
class Batch:
    items: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0

    @property
    def clue_ids(self) -> list[int]:
        return [it["id"] for it in self.items]

    @property
    def bodies(self) -> int:
        return sum(1 for it in self.items if it.get("body"))


def make_batches(items: list[dict[str, Any]], batch_tokens: int, max_items: int) -> list[Batch]:
    out: list[Batch] = []
    cur = Batch()
    for it in items:
        t = estimate_tokens(json.dumps(it, ensure_ascii=False)) + 2
        if cur.items and (cur.tokens + t > batch_tokens or len(cur.items) >= max_items):
            out.append(cur)
            cur = Batch()
        cur.items.append(it)
        cur.tokens += t
    if cur.items:
        out.append(cur)
    return out


# ---------------------------------------------------------------- 프롬프트
SYSTEM = """너는 개인 투자 리서치 파이프라인의 '선별 에이전트'다. 입력은 지난 창(보통 24시간)에 새로 들어온 공급망 단서다 — 1단계 분류기가
주제 안(AI 데이터센터 공급망과 그 수요·정책, 일부 다른 산업의 부품·소재·공정)이라고 남긴 글들이다.
할 일: 단서를 '변화 사건'으로 묶고, 어느 사건이 아이디어 작업(사람 대신 깊이 조사하는 다음 단계)을 받을 만한지 고른다.

원칙
1. '무엇이 달라졌나'를 먼저 본다. 이전에 알던 것과 비교해 새로 생긴 사실 — 수치·일정·사양·고객·규칙·용량·가격·점유 — 이 무엇인가.
   같은 사실을 여러 매체가 다시 쓴 것은 한 사건이다. 새 사실이 없는 소개·해설·전망·재탕은 사건으로 만들지 않거나 dup 으로 둔다.
2. 원본을 우선한다. 공시·규칙·표준·논문·릴리스 노트(layer raw·disclosure)가 뉴스(press·company)보다 앞선다. 같은 사건에 원본 단서가
   있으면 clue_ids 맨 앞에 둔다. 뉴스만 있는 사건은 summary 에 '보도 기준'이라고 밝힌다.
3. proceed=true 는 두 조건을 모두 만족할 때만이다.
   (a) 1년 안에 특정 상장사의 매출·이익(물량·판가·제품 비중·원가)을 바꿀 수 있다 — 소유자는 약 1년 보유 후 매도하는 관점이다.
       먼 미래의 기술 가능성, 회사 이름이 없는 거시 이야기, 가격 움직임만 있는 단서는 여기서 탈락한다.
   (b) 기존 아이디어·기각 기록(아래 '기존 아이디어')이 이미 다룬 것이 아니다. 같은 기업의 같은 부품·제품을 다루면 겹치는 것으로 보고
       overlaps 에 그 id 를 쓴다. 겹치면 이 사건이 그 판단의 근거(기각 사유 포함)를 바꿀 때만 proceed 하고, 그때 novelty 는 update,
       reason 에 무엇이 바뀌었는지 쓴다. 바뀐 게 없으면 proceed=false. (코드가 이 규칙을 다시 확인한다 — 겹치는데 update 가 아니면 진행하지 않는다.)
4. 투자 권유를 쓰지 않는다. 매수·매도·목표가·비중·시점·주가 전망을 쓰지 않는다. 판단은 proceed 와 reason 으로만 한다.
5. 단서에 없는 사실·숫자를 만들지 않는다. 확인되지 않은 것은 '보도 기준', '계획'처럼 밝힌다.
6. layer=market(업종 동반 급변) 단서는 가격 사실이다 — 같은 날의 원인 단서와 한 사건으로 묶고, 원인이 실적을 바꿀 때만 proceed 한다.

필드
- title: 무엇이 달라졌나, 한국어 한 줄(60자 안). 명사형.
- summary: 2~3문장. 무엇이 새로 나왔고 이전과 무엇이 다른가, 어느 회사의 무엇에 닿는가.
- clue_ids: 이 사건의 근거 단서 id. 원본 먼저. 한 단서는 한 사건에만.
- entities: 사건의 주인공 — 단서의 co·nodes 에 있는 그래프 id('company:…', 'component:…' 같은 값)만. 이름뿐인 기업은 넣지 말고 summary 에 이름으로 쓴다.
- novelty: new(처음 보는 변화) | update(이미 알던 주제·아이디어에 새 사실이 더해짐) | dup(이미 본 사건의 재보도 — '최근 선별 사건'이나 기존 아이디어와 같은 사실). dup 이면 proceed=false.
- overlaps: 겹치는 기존 아이디어 id 나 최근 선별 보고서 id (아래 목록에 있는 id 만). 없으면 [].
- proceed: true | false.
- reason: 한국어 한두 문장. proceed 의 근거 — 누구의 실적에 1년 안에 어떻게 닿는지, 또는 왜 아닌지(이미 다룸·먼 이야기·근거 부족).
- hypothesis_seed: proceed=true 일 때 조사할 가설 한국어 한 줄 ('A 가 바뀌면 B 회사의 C 가 늘어난다'). 아니면 null.

작업 A — 묶음 선별
입력: {"task":"A","window":{...},"clues":[{"id":단서 id,"t":제목,"s":요약,"src":출처,"layer":층,"date":날짜,"co":[그래프 기업 id 또는 이름],
       "nodes":[그래프 노드 id],"note":분류기 한 줄,"themes":[정책 테마],"body":본문 앞부분(있을 때)}]}
출력: {"events":[{"title":"…","summary":"…","clue_ids":[…],"entities":[…],"novelty":"new","overlaps":[],"proceed":false,"reason":"…","hypothesis_seed":null}]}
- 변화가 없는 단서는 어떤 사건에도 넣지 않아도 된다. 사건은 중요한 것부터 최대 25개.

작업 B — 병합 (묶음이 여럿일 때)
입력: {"task":"B","events":[{"id":"b1e1","title":…,"summary":…,"entities":…,"novelty":…,"overlaps":…,"proceed":…,"reason":…,"hypothesis_seed":…,"n_clues":N,"primary":원본 단서 유무}]}
출력: {"events":[{"from":["b1e1","b2e3"],"title":"…","summary":"…","novelty":"update","overlaps":[],"proceed":true,"reason":"…","hypothesis_seed":"…"}]}
- 같은 변화를 다룬 사건을 하나로 합치고, 합친 뒤 proceed 를 원칙 3 으로 다시 판단한다.
- 출력은 합친 사건과 판단(novelty·overlaps·proceed)이 바뀐 사건만이다. 출력하지 않은 입력 사건은 그대로 남는다.
- 한 입력 사건 id 는 from 에 한 번만 쓴다.

출력은 JSON 객체 하나뿐이다. 설명·머리말·코드 블록 없이."""

REPAIR = ("직전 응답이 형식에 맞지 않는다: {error}\n같은 판단을 형식에 맞는 JSON 객체 하나로 다시 출력하라. "
          "길어서 잘렸다면 덜 중요한 사건을 빼고 summary 를 줄여라.")


def build_system(ideas: list[Idea], recent: list[dict[str, Any]]) -> str:
    """시스템 블록 = 고정 프롬프트 + 기존 아이디어 + 최근 선별 사건. 한 실행 안의 모든 호출에서 같아 캐시된다."""
    lines = [SYSTEM, "", "--- 기존 아이디어 (id·v=상태/판정·stars·t=제목·subj=그래프 id·why=기각/상태 사유) ---"]
    lines += [json.dumps(i.prompt_row(), ensure_ascii=False) for i in ideas] or ["(없음)"]
    lines += ["", "--- 최근 선별 사건 (report=보고서 id, 지난 며칠) ---"]
    lines += [json.dumps(e, ensure_ascii=False) for e in recent] or ["(없음)"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 검증
class ScreenFormatError(ValueError):
    """LLM 응답이 형식에 맞지 않는다 (구조 오류 — 다시 묻는다)."""


class ScreenError(RuntimeError):
    """실행 실패 (보고서를 쓰지 않는다)."""


class ReportRpcMissing(RuntimeError):
    """보고서 저장 RPC 를 어느 스키마에서도 찾지 못했다."""


def _str(x: Any) -> str:
    return x.strip() if isinstance(x, str) else ""


def _check_common(e: dict[str, Any], where: str, errs: list[str]) -> None:
    if not _str(e.get("title")):
        errs.append(f"{where}.title 비어 있음")
    if not _str(e.get("summary")):
        errs.append(f"{where}.summary 비어 있음")
    if e.get("novelty") not in NOVELTY:
        errs.append(f"{where}.novelty 는 new|update|dup")
    if not isinstance(e.get("proceed"), bool):
        errs.append(f"{where}.proceed 는 true|false")
    if not _str(e.get("reason")):
        errs.append(f"{where}.reason 비어 있음")
    if e.get("proceed") is True and not _str(e.get("hypothesis_seed")):
        errs.append(f"{where}.hypothesis_seed 는 proceed=true 일 때 필수")
    for k in ("overlaps",) + (("entities",) if "entities" in e else ()):
        if k in e and e[k] is not None and not isinstance(e[k], list):
            errs.append(f"{where}.{k} 는 배열")


def _clean_common(e: dict[str, Any], known_reports: set[str]) -> dict[str, Any]:
    return {"title": _str(e["title"])[:120], "summary": _str(e["summary"])[:800], "novelty": e["novelty"],
            "overlaps": list(dict.fromkeys(x for x in e.get("overlaps") or [] if isinstance(x, str) and x in known_reports)),
            "proceed": bool(e["proceed"]), "reason": _str(e["reason"])[:600],
            "hypothesis_seed": _str(e.get("hypothesis_seed"))[:300] or None}


def _ids(xs: Any) -> list[int] | None:
    if not isinstance(xs, list):
        return None
    out = []
    for x in xs:
        if isinstance(x, bool):
            return None
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, str) and x.strip().isdigit():
            out.append(int(x.strip()))
        else:
            return None
    return out


def validate_batch(obj: Any, allowed_ids: set[int], known_reports: set[str], allowed_entities: set[str],
                   warnings: list[str] | None = None) -> list[dict[str, Any]]:
    """작업 A 응답 → 사건 목록. 구조가 틀리면 ScreenFormatError, 모르는 id·중복 단서·모르는 엔티티는 지우고 warnings 에 남긴다."""
    warnings = warnings if warnings is not None else []
    if not isinstance(obj, dict) or not isinstance(obj.get("events"), list):
        raise ScreenFormatError('최상위는 {"events": [...]} 객체여야 한다')
    errs: list[str] = []
    for i, e in enumerate(obj["events"]):
        if not isinstance(e, dict):
            errs.append(f"events[{i}] 는 객체")
            continue
        _check_common(e, f"events[{i}]", errs)
        if _ids(e.get("clue_ids")) is None:
            errs.append(f"events[{i}].clue_ids 는 정수 배열")
    if errs:
        raise ScreenFormatError("; ".join(errs[:12]))
    used: set[int] = set()
    out: list[dict[str, Any]] = []
    for i, e in enumerate(obj["events"]):
        ids = []
        for cid in _ids(e["clue_ids"]) or []:
            if cid not in allowed_ids:
                warnings.append(f"events[{i}]: 모르는 단서 id {cid}")
            elif cid in used:
                warnings.append(f"events[{i}]: 단서 {cid} 가 앞 사건에 이미 있음")
            elif cid not in ids:
                ids.append(cid)
        if not ids:
            warnings.append(f"events[{i}]: 남는 단서가 없어 뺌 ({_str(e.get('title'))[:40]})")
            continue
        used.update(ids)
        ents = []
        for x in e.get("entities") or []:
            if isinstance(x, str) and ENTITY_RE.match(x) and (not allowed_entities or x in allowed_entities):
                if x not in ents:
                    ents.append(x)
            else:
                warnings.append(f"events[{i}]: 엔티티 {str(x)[:40]} 뺌")
        out.append({**_clean_common(e, known_reports), "clue_ids": ids, "entities": ents})
    return out


def validate_merge(obj: Any, sources: dict[str, dict[str, Any]], known_reports: set[str],
                   warnings: list[str] | None = None) -> list[dict[str, Any]]:
    """작업 B 응답 → 합친 사건 목록 (clue_ids·entities 는 출처 사건에서 코드가 합친다).
    응답에 없는 출처 사건은 그대로 붙인다 — 병합은 합친·판단이 바뀐 사건만 내도록 해 출력을 줄인다."""
    warnings = warnings if warnings is not None else []
    if not isinstance(obj, dict) or not isinstance(obj.get("events"), list):
        raise ScreenFormatError('최상위는 {"events": [...]} 객체여야 한다')
    errs: list[str] = []
    for i, e in enumerate(obj["events"]):
        if not isinstance(e, dict):
            errs.append(f"events[{i}] 는 객체")
            continue
        _check_common(e, f"events[{i}]", errs)
        if not isinstance(e.get("from"), list) or not e["from"] or not all(isinstance(x, str) for x in e["from"]):
            errs.append(f"events[{i}].from 은 사건 id 문자열 배열")
    if errs:
        raise ScreenFormatError("; ".join(errs[:12]))
    used: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, e in enumerate(obj["events"]):
        src = []
        for sid in e["from"]:
            if sid not in sources:
                warnings.append(f"merge[{i}]: 모르는 사건 id {sid}")
            elif sid in used:
                warnings.append(f"merge[{i}]: 사건 {sid} 가 앞에서 이미 합쳐짐")
            else:
                src.append(sid)
        if not src:
            continue
        used.update(src)
        ids = list(dict.fromkeys(c for sid in src for c in sources[sid]["clue_ids"]))
        ents = list(dict.fromkeys(x for sid in src for x in sources[sid]["entities"]))
        out.append({**_clean_common(e, known_reports), "clue_ids": ids, "entities": ents})
    out += [dict(ev) for sid, ev in sources.items() if sid not in used]
    return out


def local_merge(batch_events: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """병합 호출을 못 했을 때: 이어 붙이고, 제목이 같은 사건만 합친다."""
    out: list[dict[str, Any]] = []
    by_title: dict[str, dict[str, Any]] = {}
    for evs in batch_events:
        for e in evs:
            k = re.sub(r"[\W_]+", "", e["title"].lower())
            if k and k in by_title:
                t = by_title[k]
                t["clue_ids"] = list(dict.fromkeys(t["clue_ids"] + e["clue_ids"]))
                t["entities"] = list(dict.fromkeys(t["entities"] + e["entities"]))
                t["overlaps"] = list(dict.fromkeys(t["overlaps"] + e["overlaps"]))
                if e["proceed"] and not t["proceed"]:
                    t.update(proceed=True, reason=e["reason"], hypothesis_seed=e["hypothesis_seed"], novelty=e["novelty"])
                continue
            c = dict(e)
            out.append(c)
            if k:
                by_title[k] = c
    return out


# ---------------------------------------------------------------- 규칙 (겹침·중복)
def rule_overlaps(entities: list[str], ideas: list[Idea], limit: int = 3) -> list[tuple[str, int]]:
    """그래프 id 가 겹치는 기존 아이디어 (id, 점수) — 기업 2점, 그 밖 노드 1점. RULE_OVERLAP 이상만, 점수순."""
    ents = set(entities)
    scored = []
    for idea in ideas:
        shared = ents & set(idea.subjects)
        score = sum(2 if s.startswith("company:") else 1 for s in shared)
        if score >= RULE_OVERLAP:
            scored.append((idea.report_id, score))
    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def apply_rules(events: list[dict[str, Any]], ideas: list[Idea]) -> list[dict[str, Any]]:
    """LLM 판단 뒤에 거는 결정 규칙. 순서대로:
    1) overlaps += 그래프 id 로 겹치는 기존 아이디어 (기업 하나 이상 공유).
    2) dup 은 진행하지 않는다.
    3) 이미 다룬 것과 겹치면(LLM 이 적은 겹침, 또는 그래프 겹침 점수 STRONG_OVERLAP 이상) LLM 이 update 라고 한 경우만 진행한다 —
       '기존 판단(기각 사유 포함)을 바꾸는 새 사실'이라고 스스로 밝힌 것만 통과. 기각된 아이디어면 사유에 그렇게 적는다.
    4) LLM 이 겹침을 적고도 new 라 했으면 표시는 update 로 고친다 (3 은 원래 표시로 본다).
    5) 진행하지 않는 사건은 hypothesis_seed 를 비운다."""
    by_id = {i.report_id: i for i in ideas}
    for e in events:
        orig = e["novelty"]
        llm_ov = list(e.get("overlaps") or [])
        rule = rule_overlaps(e.get("entities") or [], ideas)
        e["overlaps"] = list(dict.fromkeys(llm_ov + [rid for rid, _ in rule]))
        if orig == "dup" and e["proceed"]:
            e["proceed"] = False
            e["reason"] = f"{e['reason']} (재보도로 판단해 진행하지 않음)"
        strong = list(dict.fromkeys(llm_ov + [rid for rid, s in rule if s >= STRONG_OVERLAP]))
        if e["proceed"] and orig != "update" and strong:
            rej = next((rid for rid in strong if by_id.get(rid) and by_id[rid].rejected), None)
            what = f"기각된 {rej}" if rej else f"기존 {strong[0]}"
            e["proceed"] = False
            e["reason"] = f"{e['reason']} ({what} 와 겹치는데 그 판단을 바꾸는 새 사실이라는 근거가 없어 진행하지 않음)"
        if orig == "new" and llm_ov:
            e["novelty"] = "update"
        if not e["proceed"]:
            e["hypothesis_seed"] = None
    return events


def finalize(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """진행 → new → update → dup, 단서 많은 순으로 정렬하고 e1.. 번호를 붙인다."""
    rank = {"new": 0, "update": 1, "dup": 2}
    events = sorted(events, key=lambda e: (not e["proceed"], rank.get(e["novelty"], 3), -len(e["clue_ids"])))
    return [{"event_id": f"e{i}", "title": e["title"], "summary": e["summary"], "clue_ids": e["clue_ids"], "entities": e["entities"],
             "novelty": e["novelty"], "overlaps": e["overlaps"], "proceed": e["proceed"], "reason": e["reason"],
             "hypothesis_seed": e["hypothesis_seed"] if e["proceed"] else None}
            for i, e in enumerate(events, 1)]


# ---------------------------------------------------------------- LLM 호출
def ask_json(llm: Any, system: str, user: str, model: str, validate: Callable[[Any], list[dict[str, Any]]], usage: Usage, *,
             max_tokens: int, effort: str | None, may_retry: Callable[[int], bool] = lambda _n: True) -> list[dict[str, Any]]:
    """한 번 부르고, JSON 이 깨졌거나 구조가 틀리면 오류를 알려 한 번만 다시 묻는다. 두 번째도 틀리면 ScreenFormatError.
    may_retry(앞 응답 출력 토큰) 가 False 면 다시 묻지 않는다 (예산)."""
    from wsj.briefs.llm import extract_json

    kw: dict[str, Any] = {"max_tokens": max_tokens}
    if effort:
        kw["effort"] = effort
    comp = llm.complete(system, user, model, **kw)
    usage.add(comp)
    try:
        return validate(extract_json(comp.text))
    except ValueError as exc:
        err = exc
        log.warning("응답 형식 오류 (stop=%s): %s", getattr(comp, "stop_reason", None), str(exc)[:200])
    if not may_retry(int(getattr(comp, "output_tokens", 0) or 0)):
        raise ScreenFormatError(f"형식 오류, 예산 때문에 다시 묻지 않음: {err}")
    prior = [{"role": "user", "content": user}, {"role": "assistant", "content": comp.text or "(empty)"}]
    comp2 = llm.complete(system, REPAIR.format(error=str(err)[:600]), model, prior=prior, **kw)
    usage.add(comp2)
    try:
        return validate(extract_json(comp2.text))
    except ValueError as exc:
        raise ScreenFormatError(f"다시 물어도 형식 오류: {exc}") from exc


def merge_payload(batch_events: list[list[dict[str, Any]]], items_by_id: dict[int, dict[str, Any]]) -> tuple[str, dict[str, dict[str, Any]]]:
    sources: dict[str, dict[str, Any]] = {}
    rows = []
    for b, evs in enumerate(batch_events, 1):
        for j, e in enumerate(evs, 1):
            sid = f"b{b}e{j}"
            sources[sid] = e
            primary = any(items_by_id.get(c, {}).get("layer") in ("raw", "disclosure") for c in e["clue_ids"])
            rows.append({"id": sid, "title": e["title"], "summary": e["summary"], "entities": e["entities"], "novelty": e["novelty"],
                         "overlaps": e["overlaps"], "proceed": e["proceed"], "reason": e["reason"], "hypothesis_seed": e["hypothesis_seed"],
                         "n_clues": len(e["clue_ids"]), "primary": primary})
    return json.dumps({"task": "B", "events": rows}, ensure_ascii=False), sources


# ---------------------------------------------------------------- 실행
@dataclass
class Prepared:
    now: datetime
    since: datetime
    as_of: str
    clues_in: int
    relevant: int
    items: list[dict[str, Any]]
    batches: list[Batch]
    ideas: list[Idea]
    recent: list[dict[str, Any]]
    memory_source: str
    system: str
    allowed_entities: set[str]
    graph_ids: set[str]

    @property
    def window(self) -> dict[str, str]:
        return {"from": self.since.astimezone(UTC).isoformat(), "to": self.now.astimezone(UTC).isoformat()}

    @property
    def known_reports(self) -> set[str]:
        return {i.report_id for i in self.ideas} | {e["report"] for e in self.recent}


def prepare(store: Any, cfg: ScreenConfig, now: datetime | None = None, graph_ids: set[str] | None = None) -> Prepared:
    now = now or datetime.now(UTC)
    since = now - timedelta(hours=cfg.hours)
    as_of = kst_date(now)
    clues_in, rows = load_clues(store, since)
    bodies = load_bodies(store, [r["url"] for r in rows if r.get("url")]) if rows else {}
    ideas, recent, mem = load_memory(store, as_of, cfg.recent_days, cfg.max_ideas)
    items = [clue_item(r, bodies.get(r.get("url") or ""), cfg.body_chars) for r in rows if r.get("clue_id") is not None]
    ordered = order_items(items)
    batches = make_batches(ordered, cfg.batch_tokens, cfg.batch_max_items)
    gids = graph_node_ids() if graph_ids is None else graph_ids
    allowed = set(gids)
    for r in rows:
        allowed.update(t for t in clue_tags(r) if ENTITY_RE.match(t))
    return Prepared(now, since, as_of, clues_in, len(rows), ordered, batches, ideas, recent, mem, build_system(ideas, recent), allowed, gids)


def batch_user(p: Prepared, b: Batch) -> str:
    return json.dumps({"task": "A", "window": p.window, "clues": b.items}, ensure_ascii=False)


def plan(p: Prepared, cfg: ScreenConfig) -> dict[str, Any]:
    """LLM 을 부르지 않고 묶음과 어림 비용만."""
    price = price_for(cfg.model)
    sys_t = estimate_tokens(p.system)
    calls = [PlannedCall(sys_t, estimate_tokens(batch_user(p, b)), batch_output_estimate(len(b.items))) for b in p.batches]
    if len(calls) > 1:
        mu = sum(c.output_tokens for c in calls)
        calls.append(PlannedCall(sys_t, mu, merge_output_estimate(mu)))
    tokens, usd = Budget(cfg.max_input_tokens, cfg.max_usd, price).project(calls, cache_warm=False)
    return {"as_of": p.as_of, "window": p.window, "model": cfg.model, "clues_in": p.clues_in, "relevant": p.relevant,
            "bodies": sum(b.bodies for b in p.batches), "ideas": len(p.ideas), "memory_source": p.memory_source, "recent_events": len(p.recent),
            "system_tokens_est": sys_t, "batches": [{"items": len(b.items), "bodies": b.bodies, "tokens_est": b.tokens} for b in p.batches],
            "merge_call": len(p.batches) > 1, "est_input_tokens": tokens, "est_output_tokens": sum(c.output_tokens for c in calls),
            "est_usd": round(usd, 3), "caps": {"max_input_tokens": cfg.max_input_tokens, "max_usd": cfg.max_usd}}


def screen(p: Prepared, llm: Any, cfg: ScreenConfig) -> dict[str, Any]:
    """묶음 선별 → (병합) → 규칙 → 보고서 행. 묶음이 하나도 성공하지 못하면 ScreenError."""
    price = price_for(cfg.model)
    budget = Budget(cfg.max_input_tokens, cfg.max_usd, price)
    usage = Usage(cfg.model)
    sys_t = estimate_tokens(p.system)
    warnings: list[str] = []
    batch_events: list[list[dict[str, Any]]] = []
    processed: list[Batch] = []
    failed: list[dict[str, Any]] = []
    truncation: str | None = None
    warm = False
    for bi, b in enumerate(p.batches):
        user = batch_user(p, b)
        call = PlannedCall(sys_t, estimate_tokens(user), batch_output_estimate(len(b.items)))
        planned = [call]
        if batch_events:                               # 이 묶음까지 성공하면 병합이 필요하다 — 병합 몫을 남겨 둔다
            mu = usage.output_tokens + call.output_tokens
            planned.append(PlannedCall(sys_t, mu, merge_output_estimate(mu)))
        why = budget.exceeded(usage, planned, warm)
        if why:
            truncation = why
            log.warning("예산 상한(%s) — 묶음 %d/%d 부터 보내지 않는다", why, bi + 1, len(p.batches))
            break
        allowed_ids = set(b.clue_ids)

        def may_retry(out_tokens: int, _user_t: int = call.user_tokens) -> bool:
            return budget.exceeded(usage, [PlannedCall(sys_t, _user_t + out_tokens + 200, out_tokens)], True) is None

        try:
            evs = ask_json(llm, p.system, user, cfg.model,
                           lambda o, _a=allowed_ids: validate_batch(o, _a, p.known_reports, p.allowed_entities, warnings),
                           usage, max_tokens=BATCH_MAX_TOKENS, effort=cfg.effort, may_retry=may_retry)
        except Exception as exc:  # noqa: BLE001 - 묶음 하나가 실패해도 나머지는 계속
            log.warning("묶음 %d 실패: %s", bi + 1, str(exc)[:300])
            failed.append({"batch": bi + 1, "clues": len(b.items), "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            warm = warm or usage.calls > 0
            continue
        warm = True
        batch_events.append(evs)
        processed.append(b)
    if failed and not processed:                     # 예산 때문에 하나도 못 보낸 경우는 빈 보고서(truncated)를 쓴다
        raise ScreenError(f"묶음이 하나도 성공하지 못함 ({len(failed)}개 실패, 예산 {truncation or '여유'}): "
                          + "; ".join(f["error"] for f in failed[:3]))
    merge_mode = "none"
    events: list[dict[str, Any]] = batch_events[0] if len(batch_events) == 1 else []
    if len(batch_events) > 1:
        items_by_id = {it["id"]: it for it in p.items}
        user, sources = merge_payload(batch_events, items_by_id)
        ut = estimate_tokens(user)
        why = budget.exceeded(usage, [PlannedCall(sys_t, ut, merge_output_estimate(ut))], warm)
        if why:
            log.warning("병합 호출이 예산(%s)을 넘어 코드로 합친다", why)
            events, merge_mode = local_merge(batch_events), "local"
            truncation = truncation or why
        else:
            try:
                events = ask_json(llm, p.system, user, cfg.model,
                                  lambda o: validate_merge(o, sources, p.known_reports, warnings),
                                  usage, max_tokens=MERGE_MAX_TOKENS, effort=cfg.effort,
                                  may_retry=lambda out: budget.exceeded(usage, [PlannedCall(sys_t, ut + out, out)], True) is None)
                merge_mode = "llm"
            except Exception as exc:  # noqa: BLE001 - 병합이 실패해도 묶음 결과는 쓴다
                log.warning("병합 실패 — 코드로 합친다: %s", str(exc)[:300])
                events, merge_mode = local_merge(batch_events), "local"
    events = finalize(apply_rules(events, p.ideas))
    skipped = p.batches[len(processed) + len(failed):]
    stats = {"clues_in": p.clues_in, "relevant": p.relevant, "bodies_read": sum(b.bodies for b in processed),
             "clues_screened": sum(len(b.items) for b in processed), "clues_in_events": len({c for e in events for c in e["clue_ids"]}),
             "batches": len(p.batches), "batches_done": len(processed), "merge": merge_mode,
             "proceed": sum(1 for e in events if e["proceed"]), "ideas_context": len(p.ideas), "memory_source": p.memory_source,
             "truncated": bool(truncation or failed),
             "skipped_clues": sum(len(b.items) for b in skipped) + sum(f["clues"] for f in failed)}
    if truncation:
        stats["truncation_reason"] = truncation
    if failed:
        stats["failed_batches"] = failed
    if warnings:
        stats["warnings"] = warnings[:30]
    body = {"window": p.window, "events": events, "stats": stats, "usage": usage.as_dict(price)}
    return report_row(p, body)


def report_row(p: Prepared, body: dict[str, Any]) -> dict[str, Any]:
    events = body["events"]
    n_go = sum(1 for e in events if e["proceed"])
    title = f"{p.as_of} 선별: 사건 {len(events)}건 · 진행 {n_go}건" + (" (일부만 처리)" if body["stats"].get("truncated") else "")
    subjects: list[str] = []
    for e in sorted(events, key=lambda e: not e["proceed"]):
        for x in e["entities"]:
            if x not in subjects and (not p.graph_ids or x in p.graph_ids):
                subjects.append(x)
    cites = sorted({c for e in events for c in e["clue_ids"]})
    return {"report_id": f"screen:{p.as_of}", "kind": "screen", "title": title, "subjects": subjects[:40], "as_of": p.as_of,
            "body": body, "cites": cites, "created_by": CREATED_BY}


def empty_report(p: Prepared, cfg: ScreenConfig) -> dict[str, Any]:
    stats = {"clues_in": p.clues_in, "relevant": p.relevant, "bodies_read": 0, "clues_screened": 0, "clues_in_events": 0,
             "batches": 0, "batches_done": 0, "merge": "none", "proceed": 0, "ideas_context": len(p.ideas),
             "memory_source": p.memory_source, "truncated": False, "skipped_clues": 0}
    return report_row(p, {"window": p.window, "events": [], "stats": stats, "usage": Usage(cfg.model).as_dict(price_for(cfg.model))})


# ---------------------------------------------------------------- 저장
def _status(exc: Exception) -> int | None:
    st = getattr(exc, "status", None)
    if isinstance(st, int):
        return st
    m = re.search(r"-> (\d{3})", str(exc))
    return int(m.group(1)) if m else None


def rpc_targets(spec: str) -> list[tuple[str, str]]:
    """'put_reports' → research, ideas, public 순. 'ideas.put_reports' → ideas 먼저, 그다음 나머지."""
    spec = (spec or "put_reports").strip()
    schema, fn = spec.split(".", 1) if "." in spec else (None, spec)
    order = ([schema] if schema else []) + [s for s in RPC_SCHEMAS if s != schema]
    return [(s, fn) for s in order]


def save_report(store: Any, row: dict[str, Any], rpc: str = "put_reports") -> dict[str, Any]:
    """research.put_reports(rows) 로 보고서 한 행. 404(함수 없음)·406(스키마 미노출)이면 다음 스키마.
    어디에도 없으면 ReportRpcMissing, 함수가 행을 거부하면 RuntimeError."""
    if not hasattr(store, "rpc"):
        raise ReportRpcMissing(f"이 저장소({type(store).__name__})는 RPC 를 부를 수 없다 — WSJ_STORE=postgrest 로 실행")
    tried = []
    for schema, fn in rpc_targets(rpc):
        try:
            res = store.rpc(fn, {"rows": [row]}, schema=schema)
        except Exception as exc:  # noqa: BLE001
            st = _status(exc)
            if st in (404, 406):
                tried.append(f"{schema}.{fn} ({st})")
                continue
            raise
        rejected = (res or {}).get("rejected") if isinstance(res, dict) else None
        if rejected:
            raise RuntimeError(f"{schema}.{fn} 가 보고서를 거부: {json.dumps(rejected, ensure_ascii=False)[:400]}")
        return {"rpc": f"{schema}.{fn}", "result": res}
    raise ReportRpcMissing("보고서 저장 함수를 찾지 못했다: " + ", ".join(tried)
                           + " — 마이그레이션 0040(research.put_reports) 적용 전이거나 이름이 다르다 (SCREEN_REPORT_RPC 로 바꿀 수 있다)")


class AgentRunLog:
    """ops.put_agent_run(row_in) — 없으면(404/406) 조용히 끈다. 기록 실패가 본 작업을 막지 않는다."""

    def __init__(self, store: Any | None) -> None:
        self.store = store if store is not None and hasattr(store, "rpc") else None

    def put(self, status: str, rows: int | None = None, counts: dict[str, Any] | None = None, note: str | None = None) -> None:
        if self.store is None:
            return
        payload: dict[str, Any] = {"task": TASK, "status": status}
        if rows is not None:
            payload["rows"] = rows
        if counts is not None:
            payload["counts"] = counts
        if note:
            payload["note"] = note[:600]
        try:
            self.store.rpc("put_agent_run", {"row_in": payload}, schema="ops")
        except Exception as exc:  # noqa: BLE001
            if _status(exc) in (404, 406):
                log.info("ops.put_agent_run 없음 — 실행 기록을 건너뛴다")
                self.store = None
            else:
                log.warning("실행 기록 실패: %s", str(exc)[:200])


def run_counts(row: dict[str, Any]) -> dict[str, Any]:
    st = row["body"]["stats"]
    keep = ("clues_in", "relevant", "bodies_read", "clues_screened", "batches", "batches_done", "proceed", "truncated", "skipped_clues", "merge")
    return {k: st.get(k) for k in keep} | {"events": len(row["body"]["events"]), "est_usd": row["body"]["usage"]["est_usd"],
                                          "model": row["body"]["usage"]["model"]}


def step_summary(row: dict[str, Any], stored: str) -> str:
    b = row["body"]
    st, u = b["stats"], b["usage"]
    lines = [f"### {row['title']}", "",
             f"- 창: {b['window']['from'][:16]} → {b['window']['to'][:16]} (UTC) · 단서 {st['clues_in']} · 관련 {st['relevant']} · "
             f"본문 {st['bodies_read']} · 묶음 {st['batches_done']}/{st['batches']} · 병합 {st['merge']}",
             f"- 비용: {u['model']} 입력 {u['input_tokens']:,} · 캐시 읽기 {u['cache_read_tokens']:,} · 캐시 쓰기 {u['cache_write_tokens']:,} · "
             f"출력 {u['output_tokens']:,} → ≈ ${u['est_usd']}",
             f"- 저장: {stored}"]
    if st.get("truncated"):
        lines.append(f"- 일부만 처리: {st.get('truncation_reason') or '묶음 실패'} · 못 본 단서 {st.get('skipped_clues')}")
    if b["events"]:
        lines += ["", "| # | 진행 | 새로움 | 사건 | 단서 |", "|---|---|---|---|---|"]
        for e in b["events"]:
            lines.append(f"| {e['event_id']} | {'✅' if e['proceed'] else '—'} | {e['novelty']} | {e['title'].replace('|', '/')} | {len(e['clue_ids'])} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- CLI
def cli(args: Any) -> int:
    """python -m wsj screen … — 0 저장됨(또는 dry-run/plan) · 1 실패 · 3 저장 함수 없음(보고서는 파일로 남김)."""
    from wsj.config import load_settings
    from wsj.db import make_store

    settings = load_settings()
    if getattr(args, "store", None):
        settings.wsj_store = args.store
    cfg = ScreenConfig.from_settings(settings, hours=args.hours, model=args.model)
    store = make_store(settings)
    writes = not (args.dry_run or args.plan)
    runlog = AgentRunLog(store if writes else None)
    out_path = Path(args.out) if args.out else None
    try:
        p = prepare(store, cfg)
        if args.plan:
            print(json.dumps(plan(p, cfg), ensure_ascii=False, indent=1))
            return 0
        runlog.put("running")
        if not p.items:
            row = empty_report(p, cfg)
        else:
            if not settings.anthropic_api_key:
                raise ScreenError("ANTHROPIC_API_KEY 가 없다")
            from wsj.briefs.llm import LLM

            row = screen(p, LLM(settings.anthropic_api_key), cfg)
        stored = "dry-run (쓰지 않음)"
        code = 0
        if writes:
            try:
                res = save_report(store, row, cfg.report_rpc)
                stored = f"{res['rpc']} → {json.dumps(res['result'], ensure_ascii=False)[:120]}"
            except ReportRpcMissing as exc:
                out_path = out_path or settings.wsj_data_dir / "screen" / f"screen-{p.as_of}.json"
                stored = f"저장 못 함 — {exc}. 보고서는 {out_path} 에 남겼다"
                log.error("%s", stored)
                code = 3
            except Exception as exc:  # noqa: BLE001 - 함수가 행을 거부했거나 DB 오류: 보고서는 파일로 남기고 실패로 끝낸다
                out_path = out_path or settings.wsj_data_dir / "screen" / f"screen-{p.as_of}.json"
                stored = f"저장 실패 — {type(exc).__name__}: {str(exc)[:300]}. 보고서는 {out_path} 에 남겼다"
                log.error("%s", stored)
                code = 1
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(row, ensure_ascii=False, indent=1), encoding="utf-8")
        counts = run_counts(row)
        runlog.put("succeeded" if code == 0 else "failed", rows=len(row["body"]["events"]), counts=counts,
                   note=row["title"] if code == 0 else stored)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write(step_summary(row, stored))
        print(json.dumps(row, ensure_ascii=False, indent=1 if args.dry_run else None))
        print(f"[screen] {row['title']} · ≈ ${row['body']['usage']['est_usd']} · {stored}", file=sys.stderr)
        return code
    except ScreenError as exc:
        log.error("선별 실패: %s", exc)
        runlog.put("failed", note=str(exc))
        return 1
    except Exception as exc:
        runlog.put("failed", note=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        store.close()
