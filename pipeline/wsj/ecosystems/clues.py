"""단서 수집 (ADR-0028 2단계) — 출처 우선: 출처 목록의 새 글을 모두 받아 시세 기사를 버리고, AI 공급망과 관련 있는 글을 단서로 쌓는다.

    python -m wsj.ecosystems.clues run [--days 2] [--no-llm] [--model haiku] [--out data/clues/latest.json] [--dry-run]
    python -m wsj.ecosystems.clues backfill --days 90      # 로컬에서 (RSS 는 최근 글만 준다 — arXiv·릴리스·DB 의 지난 소식이 주로 채운다)
    python -m wsj.ecosystems.clues sources                 # 출처 목록 점검 (형식·중복·사용 여부)

키워드 검색이 아니라 **출처 목록**(`research/sources/registry.json`)이 입력이다 — 키워드로는 모르는 것을 찾을 수 없다.
그래프 어휘(노드·기업)는 태깅에만 쓰고 거르는 데 쓰지 않는다. 걸러내는 것은 두 가지뿐:
  1) 시세·특징주·지분 변동·투자 권유 기사, 시세 집계 사이트 (규칙)
  2) 주제 밖 글 — AI 데이터센터 공급망(반도체·메모리·패키징·기판·광·전력·냉각)과 그 수요 변화가 아닌 것 (LLM, 없으면 전문 출처는 통과·종합 출처는 어휘에 걸린 것만)
점수·등급은 붙이지 않는다. 기업 소식(ideas.company_events)과 공급망 이슈도 같은 단서 줄기에 넣어 해석 작업이 한 곳만 읽게 한다.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from wsj.ecosystems.ontology import GRAPH_PATH, load_graph

log = logging.getLogger("wsj.ecosystems.clues")
REGISTRY_PATH = GRAPH_PATH.parents[1] / "sources" / "registry.json"
SUPPORTED = {"rss", "atom"}

PRICE_EXTRA = re.compile(
    r"\bstocks? to (?:buy|watch|sell)\b|\bwhy .{0,60} stock\b|\bis .{0,40} (?:a buy|a sell|undervalued|overvalued)\b|\btop \d+ .{0,40}stocks?\b|"
    r"\b(?:buy|sell|hold) rating\b|\bdividend\b|\bearnings call transcript\b|\bstock (?:is|was) (?:up|down)\b|\btechnical analysis\b|"
    r"관련주|테마주|수혜주 \d|증시 브리핑|마감 시황|장중 시황|코스피 지수|코스닥 지수|외국인 순매수|기관 순매수",
    re.I)


@dataclass
class Source:
    id: str
    name: str
    type: str
    url: str
    lang: str = "en"
    region: str = "global"
    kinds: list[str] = field(default_factory=list)
    ecosystems: list[str] = field(default_factory=list)
    broad: bool = False          # 종합 매체 — 주제 밖 글이 많다 (LLM 이 없으면 어휘에 걸린 것만)
    enabled: bool = True
    title_filter: str | None = None

    @property
    def kind(self) -> str:
        return self.kinds[0] if self.kinds else "trade_press"


@dataclass
class Clue:
    url: str
    title: str
    summary: str
    published_at: datetime | None
    source_id: str
    source_name: str
    source_kind: str
    lang: str | None = None
    region: str | None = None
    companies: list[dict[str, Any]] = field(default_factory=list)
    nodes: set[str] = field(default_factory=set)
    relevant: bool = True
    note: str | None = None
    broad: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        return {"url": self.url, "title": self.title[:400], "summary": (self.summary or "")[:500] or None,
                "published_at": self.published_at.isoformat() if self.published_at else None,
                "source_id": self.source_id, "source_name": self.source_name, "source_kind": self.source_kind, "lang": self.lang, "region": self.region,
                "companies": self.companies, "nodes": sorted(self.nodes), "relevant": self.relevant, "note": self.note, "extra": self.extra or None}


# ---------------------------------------------------------------- 출처 목록
def load_registry(path: Path = REGISTRY_PATH) -> list[Source]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw["sources"] if isinstance(raw, dict) else raw
    out = []
    for r in rows:
        out.append(Source(id=r["id"], name=r.get("name") or r["id"], type=r.get("type", "rss"), url=r["url"], lang=r.get("lang", "en"),
                          region=r.get("region", "global"), kinds=list(r.get("kinds") or []), ecosystems=list(r.get("ecosystems") or []),
                          broad=bool(r.get("broad")), enabled=r.get("enabled", True) is not False, title_filter=r.get("title_filter")))
    return out


def check_registry(sources: list[Source]) -> list[str]:
    """형식 점검 — CI·`sources` 명령이 쓴다."""
    errs = []
    seen_id, seen_url = set(), set()
    for s in sources:
        if not re.fullmatch(r"[a-z0-9_]{2,40}", s.id):
            errs.append(f"{s.id}: id 는 영문 소문자·숫자·_")
        if s.id in seen_id:
            errs.append(f"{s.id}: id 중복")
        if s.url in seen_url:
            errs.append(f"{s.id}: url 중복")
        if not s.url.startswith("https://") and not s.url.startswith("http://"):
            errs.append(f"{s.id}: url")
        if s.type not in SUPPORTED | {"html_list", "json_api"}:
            errs.append(f"{s.id}: type {s.type}")
        seen_id.add(s.id)
        seen_url.add(s.url)
    return errs


# ---------------------------------------------------------------- 거르기
def is_noise(title: str, publisher: str | None = None) -> bool:
    from wsj.ecosystems.company_feed import HOLDINGS_NOISE, NEWS_UP, NOISE_PUBLISHERS, PRICE_CHATTER

    if (publisher or "").strip().lower() in NOISE_PUBLISHERS:
        return True
    if HOLDINGS_NOISE.search(title) or PRICE_EXTRA.search(title):
        return True
    return bool(PRICE_CHATTER.search(title)) and not NEWS_UP.search(title)


def norm_url(u: str) -> str:
    u = u.strip()
    u = re.sub(r"[?&](utm_[a-z]+|cmpid|ref|src|fbclid|gclid)=[^&#]*", "", u)
    return u.rstrip("?&#")


# ---------------------------------------------------------------- 수집
def fetch_source(http: Any, s: Source, since: datetime) -> list[Clue]:
    from wsj.ecosystems.sources import BROWSER_UA, parse_feed

    if s.type not in SUPPORTED or not s.enabled:
        return []
    entries = parse_feed(http.get_text(s.url, headers=BROWSER_UA))
    out = []
    for link, title, d, summary in entries:
        if not link or not title:
            continue
        if d and d < since:
            continue
        if s.title_filter and not re.search(s.title_filter, f"{title} {summary}", re.I):
            continue
        out.append(Clue(norm_url(link), title, summary, d, s.id, s.name, s.kind, s.lang, s.region, broad=s.broad))
    return out


def db_clues(store: Any, since: datetime, graph: dict[str, Any]) -> list[Clue]:
    """기업 소식·공급망 이슈를 같은 단서 줄기에 넣는다 (이미 걸러진 것들 — 시세 기사만 다시 버린다)."""
    labels = {n["id"]: n["label"] for n in graph["nodes"]}
    out: list[Clue] = []
    try:
        for r in store.select("ideas.company_events", ["company_id", "kind", "published_at", "title", "url", "publisher", "lang", "importance"],
                              {"published_at": ("gte", since.isoformat())}):
            if not r.get("url") or not r.get("title"):
                continue
            c = Clue(norm_url(r["url"]), r["title"], "", _parse(r.get("published_at")), "company_feed", r.get("publisher") or "기업 소식",
                     "disclosure" if r.get("kind") in ("disclosure", "filing") else "company_feed", r.get("lang"), None,
                     [{"company": r["company_id"], "name": labels.get(r["company_id"], r["company_id"])}])
            c.extra = {"publisher": r.get("publisher"), "kind": r.get("kind")}
            out.append(c)
    except Exception as exc:  # noqa: BLE001
        log.warning("company_events 를 읽지 못함: %s", exc)
    try:
        for r in store.select("ideas.supply_chain_issues", ["issue_key", "title", "summary", "nodes", "companies", "sources", "first_seen"],
                              {"first_seen": ("gte", since.isoformat()), "status": "active"}):
            src = (r.get("sources") or [{}])[0]
            if not src.get("url"):
                continue
            c = Clue(norm_url(src["url"]), r["title"], r.get("summary") or "", _parse(src.get("published_at") or r.get("first_seen")), "issues",
                     src.get("publisher") or "공급망 이슈", "issue", None, None,
                     [{"company": x.get("company_id"), "name": x.get("label") or x.get("company_id")} for x in r.get("companies") or [] if isinstance(x, dict)],
                     set(r.get("nodes") or []))
            c.extra = {"issue_key": r["issue_key"]}
            out.append(c)
    except Exception as exc:  # noqa: BLE001
        log.warning("supply_chain_issues 를 읽지 못함: %s", exc)
    return out


def _parse(s: Any) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


# ---------------------------------------------------------------- 태깅 (거르지 않는다)
def tag(clues: list[Clue], graph: dict[str, Any]) -> None:
    from wsj.ecosystems.issues import build_lexicon

    node_pats, comp_pats = build_lexicon(graph)
    labels = {n["id"]: n for n in graph["nodes"]}
    for c in clues:
        text = f"{c.title} {c.summary}"
        for pat, nid in node_pats:
            if pat.search(text):
                c.nodes.add(nid)
        have = {x.get("company") for x in c.companies}
        for pat, cid in comp_pats:
            if cid not in have and pat.search(text):
                n = labels.get(cid) or {}
                lst = n.get("listing") or {}
                c.companies.append({"company": cid, "name": n.get("label", cid), "ticker": lst.get("ticker"), "exchange": lst.get("exchange")})
                have.add(cid)


LLM_SYSTEM = """너는 AI 데이터센터 공급망 리서치의 단서 분류기다. 입력은 여러 출처의 새 글 목록(i, 제목, 요약, 출처)이다.
각 글에 대해 판단한다:
- keep: AI 데이터센터 공급망(반도체·메모리·HBM·패키징·기판·PCB·테스트·장비·소재·광통신·레이저·전력·변압기·배터리·커패시터·냉각·현장 발전·전력망 접속)이나
  그 수요(모델·추론·클라우드 증설·하이퍼스케일러 투자)를 바꿀 수 있는 사실·계획·기술·정책이면 true.
  주가·시세 해설, 투자 권유, 실적 일정 안내, 일반 거시·정치, 소비자 제품 리뷰, 광고·이벤트 홍보는 false.
- companies: 글에 이름이 나온 상장 기업 (아는 경우 ticker, exchange: KRX|KOSDAQ|NYSE|Nasdaq|TWSE|TSE 등). 비상장·정부기관은 빼라. 모르면 빈 배열.
- note: 무엇에 관한 글인지 한국어 한 줄(60자 안). 판단·전망은 쓰지 마라.
- keep 이 false 인 글은 {"i": n, "keep": false} 만 쓴다 (companies·note 없이). 모든 i 를 빠짐없이 쓴다.
출력은 JSON 하나: {"items": [{"i": 0, "keep": true, "companies": [{"name": "…", "ticker": "…", "exchange": "…"}], "note": "…"}, {"i": 1, "keep": false}]}"""


def llm_screen(clues: list[Clue], api_key: str, model: str = "haiku", batch: int = 50, workers: int = 4) -> dict[str, Any]:
    """Haiku 로 주제 밖 글을 거른다. 묶음(batch)마다 한 번 부르고, 묶음들은 workers 개씩 동시에 보낸다."""
    from concurrent.futures import ThreadPoolExecutor

    from wsj.briefs.llm import LLM, resolve_model, sum_usage

    llm = LLM(api_key)
    mdl = resolve_model(model)
    parts = [clues[start:start + batch] for start in range(0, len(clues), batch)]

    def screen(part: list[Clue]) -> tuple[list[Clue], dict[str, Any] | None, list[Any]]:
        payload = [{"i": i, "title": c.title, "summary": (c.summary or "")[:280], "source": c.source_name} for i, c in enumerate(part)]
        try:
            out, comps = llm.complete_json(LLM_SYSTEM, json.dumps(payload, ensure_ascii=False), mdl,
                                           "직전 응답을 유효한 JSON 하나로 다시 출력하라. 오류: {error}", max_tokens=8000)
        except Exception as exc:  # noqa: BLE001 - 분류가 실패하면 규칙으로 (아래)
            log.warning("llm screen batch failed (%d items): %s", len(part), exc)
            return part, None, []
        return part, out, comps

    comps_all: list[Any] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(screen, parts))
    for part, out, comps in results:
        comps_all += comps
        apply_screen(part, out)
    return sum_usage(comps_all) if comps_all else {}


def apply_screen(part: list[Clue], out: dict[str, Any] | None) -> None:
    """LLM 응답을 단서에 옮긴다. 응답이 없거나 빠진 글은 규칙(rule_keep)으로."""
    by_i = {int(x.get("i", -1)): x for x in (out or {}).get("items") or [] if isinstance(x, dict)}
    for i, c in enumerate(part):
        x = by_i.get(i)
        if x is None:
            c.relevant = rule_keep(c)
            continue
        c.relevant = bool(x.get("keep"))
        if not c.relevant:
            continue
        c.note = (x.get("note") or "")[:120] or None
        have = {(y.get("name") or "").lower() for y in c.companies}
        for y in x.get("companies") or []:
            if isinstance(y, dict) and y.get("name") and y["name"].lower() not in have:
                c.companies.append({"company": None, "name": y["name"], "ticker": y.get("ticker"), "exchange": y.get("exchange")})
                have.add(y["name"].lower())


def rule_keep(c: Clue) -> bool:
    """LLM 이 없을 때: 전문 출처·기업 소식·이슈는 통과, 종합 매체는 그래프 어휘에 걸린 것만."""
    return not c.broad or bool(c.nodes) or any(x.get("company") for x in c.companies)


# ---------------------------------------------------------------- 실행
def collect(http: Any, store: Any | None, sources: list[Source], since: datetime, graph: dict[str, Any]) -> tuple[list[Clue], dict[str, Any]]:
    stats: dict[str, Any] = {"sources": {}, "failed": []}
    found: dict[str, Clue] = {}
    for s in sources:
        if not s.enabled or s.type not in SUPPORTED:
            continue
        try:
            got = fetch_source(http, s, since)
        except Exception as exc:  # noqa: BLE001 - 출처 하나가 죽어도 나머지는 계속
            stats["failed"].append({"id": s.id, "error": str(exc)[:160]})
            log.warning("source %s failed: %s", s.id, exc)
            continue
        stats["sources"][s.id] = len(got)
        for c in got:
            found.setdefault(c.url, c)
    if store is not None:
        for c in db_clues(store, since, graph):
            found.setdefault(c.url, c)
    clues = list(found.values())
    noise = 0
    for c in clues:
        if is_noise(c.title, (c.extra or {}).get("publisher") or c.source_name):
            c.relevant = False
            c.note = "시세·지분 기사"
            noise += 1
    stats.update({"fetched": len(clues), "noise": noise})
    return clues, stats


def title_key(title: str) -> str:
    """같은 글인지 보는 제목 열쇠: 끝의 ' - 매체명' 을 떼고, 글자·숫자만 소문자로."""
    t = re.sub(r"\s+[-–—|]\s+[^-–—|]{1,40}$", "", title.strip())
    return re.sub(r"[\W_]+", "", t.lower())


def mark_duplicates(clues: list[Clue], seen: set[str] | frozenset[str] = frozenset()) -> int:
    """제목이 같은 글은 하나만 남긴다 (구글 뉴스가 같은 기사를 주소만 바꿔 다시 내는 경우, 연재물 등).
    남기는 쪽: 이미 저장한 것(seen) → 시세 기사로 버리지 않은 것 → 원문 주소(news.google.com 이 아닌 것) → 먼저 본 것.
    나머지 새 글은 relevant=false 로 저장만 해서 다음 날 다시 보지 않게 한다. 돌려주는 값은 그렇게 표시한 수."""
    groups: dict[str, list[Clue]] = {}
    for c in clues:
        k = title_key(c.title)
        if len(k) >= 8:
            groups.setdefault(k, []).append(c)
    n = 0
    for same in groups.values():
        if len(same) < 2:
            continue
        keep = min(same, key=lambda c: (c.url not in seen, not c.relevant, "news.google.com" in c.url))
        for c in same:
            if c is not keep and c.relevant and c.url not in seen:
                c.relevant = False
                c.note = "같은 제목 중복"
                n += 1
    return n


def tech_signals_due(now: datetime | None = None) -> bool:
    """기술 흐름 단서는 주 1회 (월요일 KST) — 특허·논문 자료는 분기에 한 번 바뀌므로 한꺼번에 쏟지 않고 매주 몇 개씩."""
    now = now or datetime.now(UTC)
    return (now + timedelta(hours=9)).weekday() == 0


def tech_signal_clues(store: Any, graph: dict[str, Any], cap: int = 6, seen: set[str] | None = None) -> list[Clue]:
    """techdocs 의 노드별 시계열·기관·대표 문서 → '빠르게 늘어나는 기술 × 새로 들어온 미국·한국 기관' 단서 (이미 본 것은 빼고 cap 개)."""
    from wsj.ecosystems.techdocs import signal_text, signals

    try:
        series = store.select("ideas.tech_series", ["node", "source", "period", "n"])
        orgs = store.select("ideas.tech_orgs", ["node", "source", "span", "org", "company", "n", "first_year"])
        docs = store.select("ideas.tech_docs", ["source", "title", "published_on", "orgs", "nodes", "url"], {"published_on": ("gte", "2023-01-01")})
    except Exception as exc:  # noqa: BLE001 - 0033 전이거나 백필 전
        log.warning("techdocs 를 읽지 못함: %s", exc)
        return []
    out: list[Clue] = []
    now = datetime.now(UTC)
    labels = {n["id"]: n for n in graph["nodes"]}
    for sgl in signals(series, orgs, docs, graph):
        if sgl["url"] in (seen or set()) or any(c.url == sgl["url"] for c in out):
            continue
        title, summary = signal_text(sgl)
        short = re.sub(r"\s+\(.*$", "", sgl["label"])
        comp = labels.get(sgl["company"] or "") or {}
        lst = comp.get("listing") or {}
        companies = [{"company": sgl["company"], "name": comp.get("label", sgl["org"]) if comp else sgl["org"],
                      "ticker": lst.get("ticker"), "exchange": lst.get("exchange")}]
        out.append(Clue(sgl["url"], title, summary, now, "techdocs", "특허·논문 흐름", "tech_signal", lang="ko", region=sgl["country"] or None,
                        companies=companies, nodes={sgl["node"]}, relevant=True,
                        note=f"기술 흐름 신호 — {short}",
                        extra={"n_2024": sgl["n24"], "n_2022_23": sgl["n22"], "first_year": sgl["first_year"], "ratio": sgl["ratio"]}))
        if len(out) >= cap:
            break
    return out


def already_seen(store: Any, urls: list[str]) -> set[str]:
    try:
        return {r["url"] for r in store.select("ideas.clues", ["url"], {"url": urls})}
    except Exception as exc:  # noqa: BLE001 - 0032 전
        log.warning("ideas.clues 를 읽지 못함 (0032 적용 전?): %s", exc)
        return set()


def run(http: Any, store: Any | None, days: int, use_llm: bool, model: str, api_key: str | None, registry: Path = REGISTRY_PATH,
        tech_signals: bool | None = None) -> dict[str, Any]:
    graph = load_graph()
    sources = load_registry(registry)
    since = datetime.now(UTC) - timedelta(days=days)
    clues, stats = collect(http, store, sources, since, graph)
    seen = already_seen(store, [c.url for c in clues]) if store is not None else set()
    stats["duplicate"] = mark_duplicates(clues, seen)
    new = [c for c in clues if c.url not in seen]
    tag(new, graph)
    todo = [c for c in new if c.relevant]
    if use_llm and api_key and todo:
        stats["llm_usage"] = llm_screen(todo, api_key, model)
    else:
        for c in todo:
            c.relevant = rule_keep(c)
    if store is not None and (tech_signals if tech_signals is not None else tech_signals_due()):
        sig = tech_signal_clues(store, graph)
        sig = [c for c in sig if c.url not in already_seen(store, [c.url for c in sig])]
        new += sig
        stats["tech_signals"] = len(sig)
    stats.update({"new": len(new), "kept": sum(1 for c in new if c.relevant), "dropped": sum(1 for c in new if not c.relevant)})
    if store is not None and new:
        try:
            stats["saved"] = store.upsert("ideas.clues", [c.row() for c in new], ["url"])
        except Exception as exc:  # noqa: BLE001
            log.warning("ideas.clues 에 쓸 수 없음 (0032 적용 전?): %s", exc)
            stats["saved"] = 0
    stats["clues"] = new
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "backfill"):
        p = sub.add_parser(name)
        p.add_argument("--days", type=int, default=2 if name == "run" else 90)
        p.add_argument("--no-llm", action="store_true")
        p.add_argument("--model", default="haiku")
        p.add_argument("--out", type=Path)
        p.add_argument("--dry-run", action="store_true", help="저장하지 않는다 (DB 도 읽지 않는다)")
        p.add_argument("--registry", type=Path, default=REGISTRY_PATH)
        p.add_argument("--tech-signals", action="store_true", default=None, help="기술 흐름 단서를 오늘 넣는다 (기본: 월요일 KST 만)")
    s = sub.add_parser("sources")
    s.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if args.cmd == "sources":
        srcs = load_registry(args.registry)
        errs = check_registry(srcs)
        by: dict[str, int] = {}
        for x in srcs:
            by[f"{x.region}/{x.type}"] = by.get(f"{x.region}/{x.type}", 0) + 1
        print(json.dumps({"sources": len(srcs), "enabled_feeds": sum(1 for x in srcs if x.enabled and x.type in SUPPORTED), "by": by, "errors": errs},
                         ensure_ascii=False, indent=1))
        return 1 if errs else 0
    from wsj.config import load_settings
    from wsj.http import HttpClient

    settings = load_settings()
    store = None
    if not args.dry_run:
        from wsj.db import make_store

        store = make_store(settings)
    http = HttpClient(settings.sec_user_agent, timeout=25, max_retries=1)
    run_id = None
    try:
        if store is not None:
            run_id = store.run_started("clues", {"days": args.days, "llm": not args.no_llm})
        stats = run(http, store, args.days, not args.no_llm, args.model, settings.anthropic_api_key or None, args.registry,
                    tech_signals=getattr(args, "tech_signals", None))
        if store is not None and run_id is not None:
            store.run_finished(run_id, "succeeded", int(stats.get("saved") or 0), json.loads(json.dumps({k: v for k, v in stats.items() if k != "clues"}, default=str)), None)
    except Exception as exc:
        if store is not None and run_id is not None:
            store.run_finished(run_id, "failed", 0, {}, str(exc)[:500])
        raise
    finally:
        http.close()
    clues = stats.pop("clues")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"stats": stats, "clues": [c.row() for c in clues]}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    summary = {k: v for k, v in stats.items() if k != "sources"} | {"sources_ok": len(stats.get("sources", {}))}
    if args.dry_run:  # 점검 실행: 출처별 건수와 실패를 모두 보인다 (clues-probe 워크플로)
        summary["by_source"] = stats.get("sources", {})
        summary["silent"] = sorted(s.id for s in load_registry(args.registry) if s.enabled and s.type in SUPPORTED and not stats.get("sources", {}).get(s.id))
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=1 if args.dry_run else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
