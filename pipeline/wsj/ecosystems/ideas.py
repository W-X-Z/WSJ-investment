"""투자 아이디어 엔진 — 최근 변화에서 출발해 그래프로 추론하고, AI 가 직관적인 아이디어와 근거 사슬을 쓴다. ADR-0016.

    python -m wsj.ecosystems.ideas                         # 매일: 신호 → 후보 사슬 → LLM → 검증 → ideas.investment_ideas
    python -m wsj.ecosystems.ideas --dry-run --out x.json  # DB 에 쓰지 않음
    python -m wsj.ecosystems.ideas --snapshot DIR --emit-prompt p.json      # 오프라인: DIR/issues.json·indicators.json 으로 LLM 입력만
    python -m wsj.ecosystems.ideas --snapshot DIR --from-llm-json raw.json --out ideas.json  # 외부에서 쓴 LLM 출력 검증
    python -m wsj.ecosystems.ideas --load ideas.json       # 검증된 아이디어를 DB 에 적재

흐름
1. 신호(signal): 최근 이슈(★2 이상), 눈에 띄는 지표(대만 공급사 월매출 YoY, 미국 PPI), 그리고 기업별 최신 소식
   (company_feed: SEC·대만·일본·중국·한국 공시, 월매출, 기업명 뉴스 — 최근 14일). 이슈 문장은 지금 그래프의 어휘로
   다시 태깅한다 — 그래프가 커지면 예전 이슈도 새 노드에 닿는다. 모든 신호는 나이만큼 가중이 줄어든다(반감기 7일).
2. 후보 사슬(candidate): 신호 노드에서 impact.influence_paths 로 기업까지의 경로를 계산하고 점수를 매긴다.
   점수 = Σ(신호 ★ 가중 × 경로 신뢰도) × 규모 가중(소형 우대) × 공급 집중(공급사가 적을수록 큼).
   동종 공급사·기술 전환 관계(displaces·substitutes_for·develops·holds_ip)를 곁들인다.
3. 근거 목록(evidence): 신호의 출처(S…)와 경로 관계의 출처(G…)에 id 를 붙인다. AI 는 이 id 만 인용할 수 있다.
4. LLM: 직관적인 제목 + 두 문장 + ★1~3 + 기업 + 근거 사슬 + 리스크 + 다음 확인 신호. 기존 아이디어는 같은 key 로 갱신·약화·종료.
5. 검증: 없는 id·기업, 근거 없는 단계, 14일 안의 최신 근거(S)가 없는 새 아이디어·갱신은 버린다. 사람이 읽는 화면은 이 결과만 본다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from wsj.ecosystems.ontology import load_graph, load_ontology

log = logging.getLogger("wsj.ecosystems.ideas")

IDEA_TYPES = {"bottleneck": "병목 수혜", "transition": "기술 전환", "confirmation": "실적·가격 확인", "risk": "리스크"}
SIZE_WEIGHT = {"micro": 1.6, "small": 1.45, "mid": 1.0, "large": 0.55, "mega": 0.3, "private": 0.0, "unknown": 0.8}
STAR_WEIGHT = {3: 4.0, 2: 2.0, 1: 1.0}
FRESH_DAYS = 14          # 새 아이디어·갱신에 필요한 최신 근거의 나이
HALF_LIFE_DAYS = 7.0     # 신호 가중 반감기
COMPANY_NODE_DAMP = 0.35  # 기업 소식이 태깅한 노드로 퍼지는 힘 (소식의 주어는 그 기업이다)
SUPPLY_RELS = ("offered_by", "develops", "holds_ip")
TRANSITION_RELS = ("displaces", "substitutes_for", "develops", "holds_ip", "defers", "adopts")
TIER_KO = {
    "independent_measurement": "독립 실측", "standard_body": "표준 문서", "official_issuer": "당사자 공시", "customer_statement": "고객 진술",
    "third_party_report": "보도·리서치", "vendor_claim": "공급사 주장", "technical_inference": "기술 추론", "hypothesis": "가설",
}
SOURCE_TIER = {"sec": "official_issuer", "newsroom": "official_issuer", "policy": "standard_body", "data": "official_issuer",
               "analyst": "third_party_report", "trade": "third_party_report", "news": "third_party_report", "research": "independent_measurement"}


def age_days(d: str | None, now: datetime) -> int | None:
    if not d:
        return None
    try:
        dt = datetime.fromisoformat(str(d)[:10]).replace(tzinfo=UTC)
    except ValueError:
        return None
    return max(0, (now - dt).days)


def recency(d: str | None, now: datetime) -> float:
    """최근일수록 1 에 가깝다. 날짜 없는 근거는 0.3."""
    a = age_days(d, now)
    return 0.3 if a is None else max(0.15, 0.5 ** (a / HALF_LIFE_DAYS))


def stars_of(importance: int | None) -> int:
    i = int(importance or 0)
    return 3 if i >= 8 else 2 if i >= 5 else 1


# ---------------------------------------------------------------- evidence registry
@dataclass
class Evidence:
    eid: str
    url: str
    title: str
    publisher: str | None = None
    date: str | None = None
    tier: str | None = None
    excerpt: str | None = None

    def public(self) -> dict[str, Any]:
        d = {"id": self.eid, "url": self.url, "title": self.title, "publisher": self.publisher, "date": self.date,
             "tier": self.tier, "tier_ko": TIER_KO.get(self.tier or "", None)}
        if self.excerpt and self.eid.startswith("S"):  # 확인된 사실(원문 확인 소식의 요약)·공시 본문 발췌 — 화면의 '확인된 사실'
            d["note"] = self.excerpt[:280]
        return d


@dataclass
class Registry:
    items: dict[str, Evidence] = field(default_factory=dict)
    by_key: dict[tuple[str, str], str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, prefix: str, url: str, title: str, **kw: Any) -> str | None:
        if not url or not str(url).startswith("https://"):
            return None
        key = (url, title[:80])
        if key in self.by_key:
            return self.by_key[key]
        self.counters[prefix] += 1
        eid = f"{prefix}{self.counters[prefix]}"
        self.items[eid] = Evidence(eid, url, title, **kw)
        self.by_key[key] = eid
        return eid


# ---------------------------------------------------------------- signals
def load_signals(issues: list[dict[str, Any]], indicators: list[dict[str, Any]], graph: dict[str, Any], reg: Registry,
                 now: datetime, days: int = 21, min_stars: int = 2) -> list[dict[str, Any]]:
    from wsj.ecosystems.indicators import TW_ENTITIES
    from wsj.ecosystems.issues import build_lexicon

    node_pats, comp_pats = build_lexicon(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    since = now - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for r in issues:
        if r.get("status", "active") != "active":
            continue
        latest = r.get("latest_published_at") or r.get("first_seen")
        if latest and datetime.fromisoformat(str(latest).replace("Z", "+00:00")) < since:
            continue
        st = stars_of(r.get("importance"))
        if st < min_stars:
            continue
        # 이슈 요약은 한국어라 영어 어휘에 잘 안 걸린다 → 출처 제목(대개 영어)도 함께 태깅
        text = " ".join(str(r.get(k) or "") for k in ("title", "summary", "why_it_matters")) + " " + " ".join(
            str(s.get("title") or "") for s in (r.get("sources") or [])[:6])
        tagged_nodes = {nid for pat, nid in node_pats if pat.search(text)}
        tagged_cos = {cid for pat, cid in comp_pats if pat.search(text)}
        node_ids = [n for n in dict.fromkeys([*(r.get("nodes") or []), *sorted(tagged_nodes)]) if n in nodes and nodes[n]["kind"] != "company"]
        cos = [c.get("company_id") for c in (r.get("companies") or [])] + sorted(tagged_cos)
        cos = [c for c in dict.fromkeys(cos) if c in nodes and nodes[c]["kind"] == "company"]
        eids = []
        for s in (r.get("sources") or [])[:4]:
            e = reg.add("S", s.get("url", ""), s.get("title") or r["title"], publisher=s.get("publisher"),
                        date=str(s.get("published_at") or "")[:10] or None, tier=SOURCE_TIER.get(s.get("source_type", ""), "third_party_report"))
            if e:
                eids.append(e)
        if not eids:
            continue
        out.append({"sid": f"I{len(out) + 1}", "kind": "issue", "ref": r["issue_key"], "title": r["title"], "stars": st,
                    "date": str(latest)[:10], "what": r.get("summary"), "why": r.get("why_it_matters"),
                    "nodes": node_ids[:8], "companies": cos[:8], "evidence": eids, "ecosystem": r.get("ecosystem")})
    by_code = {str(e["local_code"]): eid for eid, e in TW_ENTITIES.items()}
    for m in indicators:
        yoy = m.get("yoy_pct")
        yoy = float(yoy) if yoy is not None else None
        cat = m.get("category")
        notable = (cat == "tw_revenue" and yoy is not None and (yoy >= 40 or yoy <= -20)) or (cat == "ppi" and yoy is not None and abs(yoy) >= 10)
        if not notable:
            continue
        cos = list(m.get("companies") or [])
        if cat == "tw_revenue":
            code = str(m["indicator_id"]).split(":")[-1]
            if code in by_code:
                cos.append(by_code[code])
        cos = [c for c in dict.fromkeys(cos) if c in nodes]
        month = str(m.get("as_of"))[:7]
        title = f"{m['label']} {month} 전년 대비 {yoy:+.0f}%"
        # 월간 지표는 다음 달 10일~중순에 나온다 — 신호 날짜는 대략의 발표일 (issues.py 와 같은 +40일)
        released = (datetime.fromisoformat(str(m.get("as_of"))[:10]) + timedelta(days=40)).date().isoformat()
        e = reg.add("S", m.get("source_url") or "", title, publisher="TWSE·TPEx 공시" if cat == "tw_revenue" else "US BLS",
                    date=min(released, now.date().isoformat()), tier="official_issuer")
        if not e:
            continue
        out.append({"sid": f"M{sum(1 for s in out if s['kind'] == 'indicator') + 1}", "kind": "indicator", "ref": m["indicator_id"], "title": title,
                    "stars": 3 if (cat == "tw_revenue" and yoy >= 80) or (cat == "ppi" and yoy >= 30) else 2,
                    "date": min(released, now.date().isoformat()), "what": title, "why": None, "nodes": [n for n in (m.get("nodes") or []) if n in nodes],
                    "companies": cos, "evidence": [e], "ecosystem": m.get("ecosystem")})
    return out


def company_signals(events: list[Any], graph: dict[str, Any], reg: Registry, now: datetime, focus: set[str] | None = None,
                    days: int = FRESH_DAYS, max_signals: int = 60, per_company: int = 4) -> list[dict[str, Any]]:
    """기업별 최신 소식(company_feed.CompanyEvent) → 기업 단위 신호 E1…. 사건성(★2+)·노드 태깅·기존 아이디어 기업만."""
    from wsj.ecosystems.company_feed import native_names, node_terms
    from wsj.ecosystems.issues import build_lexicon

    focus = focus or set()
    node_pats, comp_pats = build_lexicon(graph)
    cjk = node_terms()
    natives = [(nm, cid) for cid, nm in native_names().items() if len(nm) >= 3]  # 'SK하이닉스' 같은 현지어 기업명
    nodes = {n["id"]: n for n in graph["nodes"]}
    since = now - timedelta(days=days)
    by_co: dict[str, list[Any]] = defaultdict(list)
    for e in events:
        if e.published_at >= since and e.company_id in nodes:
            by_co[e.company_id].append(e)
    scored = []
    for cid, evs in by_co.items():
        n = nodes[cid]
        size = n.get("size_band") or "unknown"
        if size == "private":
            continue
        tagged_nodes: set[str] = set()
        tagged_cos: set[str] = set()
        keep = []
        for e in evs:
            text = f"{e.title} {(e.text or '')[:300]}"
            en = {nid for pat, nid in node_pats if pat.search(text)} | {nid for t, nid in cjk if t in text}
            en = {x for x in en if x in nodes and nodes[x]["kind"] != "company"}
            # 사건어도 노드도 없는 일반 기사(★1 뉴스)는 버린다 — 회사 소개·시세·행사 기사
            if e.kind == "news" and e.importance < 2 and not en:
                continue
            keep.append(e)
            tagged_nodes |= en
            tagged_cos |= {c for pat, c in comp_pats if pat.search(text)} | {c for nm, c in natives if nm in text}
        if not keep:
            continue
        evs = sorted(keep, key=lambda e: (-e.importance, -e.published_at.timestamp()))
        top = evs[0].importance
        if top < 2 and not tagged_nodes and cid not in focus:
            continue
        newest = max(e.published_at for e in evs).date().isoformat()
        official = any(e.tier == "official_issuer" and e.importance >= 2 for e in evs)
        score = ((top ** 2 + sum(1 for e in evs if e.importance >= 2)) * recency(newest, now) * (1.5 if cid in focus else 1.0)
                 * (1.3 if official else 1.0) * (1 + 0.2 * min(len(tagged_nodes), 3)) * (1.2 if size in ("micro", "small", "mid") else 0.8))
        scored.append((score, cid, evs, tagged_nodes, tagged_cos, newest))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _score, cid, evs, tagged_nodes, tagged_cos, newest in scored[:max_signals]:
        picked = sorted(evs[:per_company], key=lambda e: e.published_at, reverse=True)
        items, eids, used_events = [], [], []
        for e in picked:
            d = e.published_at.date().isoformat()
            eid = reg.add("S", e.url, e.title, publisher=e.publisher, date=d, tier=e.tier, excerpt=(e.text or None))
            if eid:
                eids.append(eid)
                it = {"date": d, "kind": e.kind, "importance": e.importance, "title": e.title[:180], "ev": eid}
                if (e.extra or {}).get("verified_by"):
                    it["verified"] = True  # 원문을 열어 숫자·날짜를 확인한 소식 (excerpt 에 확인 내용)
                items.append(it)
                used_events.append(e)
        if not eids:
            continue
        label = re.split(r"\s+\(", nodes[cid]["label"])[0]
        supplies = [nodes[e["from"]]["label"] for e in graph["edges"] if e["relation"] == "offered_by" and e["to"] == cid][:3]
        out.append({"sid": f"E{len(out) + 1}", "kind": "company", "ref": f"events:{cid}", "subject": cid, "title": f"{label} 최근 소식 {len(items)}건",
                    "supplies": supplies,
                    "stars": max(1, min(3, evs[0].importance)), "date": newest, "what": None, "why": None,
                    "nodes": sorted(tagged_nodes)[:8], "companies": [cid, *sorted(tagged_cos - {cid})[:4]], "evidence": eids,
                    "ecosystem": nodes[cid].get("ecosystem"), "items": items, "_events": used_events})
    return out


# ---------------------------------------------------------------- candidate chains
def _suppliers(graph: dict[str, Any]) -> dict[str, list[str]]:
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    sup: dict[str, list[str]] = defaultdict(list)
    for e in graph["edges"]:
        if e["relation"] == "offered_by" and kinds.get(e["to"]) == "company":
            sup[e["from"]].append(e["to"])
    return sup


def _concentration(n_suppliers: int) -> float:
    if n_suppliers <= 0:
        return 1.0
    return 1.5 if n_suppliers == 1 else 1.3 if n_suppliers <= 3 else 1.0 if n_suppliers <= 6 else 0.8


def _edge_evidence(edge: dict[str, Any], reg: Registry, nodes: dict[str, dict[str, Any]]) -> str | None:
    for ev in edge.get("evidence") or []:
        title = f"{nodes[edge['from']]['label']} → {nodes[edge['to']]['label']} ({edge['relation']})"
        e = reg.add("G", ev.get("url", ""), title, tier=edge.get("evidence_tier"), date=(ev.get("published_at") or None),
                    excerpt=(ev.get("excerpt") or edge.get("note") or None))
        if e:
            return e
    return None


def build_candidates(graph: dict[str, Any], signals: list[dict[str, Any]], reg: Registry, top: int = 24, max_depth: int = 5,
                     now: datetime | None = None) -> list[dict[str, Any]]:
    from wsj.ecosystems.impact import influence_paths

    onto = load_ontology()
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    sup = _suppliers(graph)
    cache: dict[str, list[dict[str, Any]]] = {}
    acc: dict[str, dict[str, Any]] = {}

    def slot(cid: str) -> dict[str, Any]:
        return acc.setdefault(cid, {"raw": 0.0, "signals": set(), "paths": [], "direct": set(), "fresh": 0.0})

    now = now or datetime.now(UTC)
    for s in signals:
        w = STAR_WEIGHT.get(s["stars"], 1.0) * recency(s.get("date"), now)
        is_co = s["kind"] == "company"
        for nid in s["nodes"]:
            if nid not in cache:
                cache[nid] = influence_paths(graph, nid, max_depth=max_depth, onto=onto)
            # 특이도: 많은 기업에 닿는 범용 노드(세대·요구)일수록 약하게 — 1/√(도달 기업 수)
            reach = len({p["company_id"] for p in cache[nid]}) or 1
            spec = 3.0 / math.sqrt(reach)
            best: dict[str, dict[str, Any]] = {}
            for p in cache[nid]:
                cur = best.get(p["company_id"])
                if cur is None or p["confidence"] > cur["confidence"]:
                    best[p["company_id"]] = p
            for cid, p in best.items():
                c = slot(cid)
                c["raw"] += w * spec * p["confidence"] * (1 if p["sign"] >= 0 else -1) * (COMPANY_NODE_DAMP if is_co else 1.0)
                c["signals"].add(s["sid"])
                c["paths"].append({**p, "_sid": s["sid"]})
        for cid in s["companies"]:
            c = slot(cid)
            # 기업 소식의 주어는 그 기업 자신 (강하게), 함께 언급된 고객·경쟁사는 약하게
            c["raw"] += w * (1.0 if cid == s.get("subject") else 0.3 if is_co else 0.7)
            c["signals"].add(s["sid"])
            c["direct"].add(s["sid"])
            if is_co and cid == s.get("subject") and s["stars"] >= 2:
                c["fresh"] += w * (1.5 if s["nodes"] else 1.0)  # 소식이 공급망 노드(병목·부품)를 직접 말하면 더

    # 기업이 직접 공급·개발하는 노드 (경로가 없을 때 공급 노드·맥락으로 쓴다)
    offers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in graph["edges"]:
        if e["relation"] == "offered_by" and nodes.get(e["to"], {}).get("kind") == "company":
            offers[e["to"]].append(e)
        elif e["relation"] in ("develops", "holds_ip") and nodes.get(e["from"], {}).get("kind") == "company":
            offers[e["from"]].append(e)

    out = []
    for cid, c in acc.items():
        n = nodes[cid]
        size = n.get("size_band") or "unknown"
        if size == "private" or (n.get("listing") or {}).get("filer_type") == "private":
            continue
        paths = sorted(c["paths"], key=lambda p: -p["confidence"])
        supply_node = None
        for p in paths:
            if p["relations"] and p["relations"][-1] in SUPPLY_RELS and len(p["path"]) >= 2:
                supply_node = p["path"][-2]["node_id"]
                break
        if supply_node is None:  # 경로 없이 기업 소식만 있는 기업 → 직접 공급하는 노드 중 공급사가 가장 적은 것
            own = [e["from"] for e in offers.get(cid, []) if e["relation"] == "offered_by"]
            supply_node = min(own, key=lambda x: len(sup.get(x, [])), default=None)
        n_sup = len(sup.get(supply_node, [])) if supply_node else 0
        size_w, conc = SIZE_WEIGHT.get(size, 0.8), _concentration(n_sup)
        score = abs(c["raw"]) * size_w * conc * (1 + 0.15 * (len(c["signals"]) - 1))
        out.append({"company_id": cid, "score": round(score, 3), "sign": 1 if c["raw"] >= 0 else -1, "_paths": paths, "_supply": supply_node,
                    "_n_sup": n_sup, "_signals": sorted(c["signals"]), "_direct": sorted(c["direct"]), "_fresh": c["fresh"] * size_w * conc})
    out.sort(key=lambda x: -x["score"])
    # 최신 몫: 자기 공시·실적·수주(E ★2+)가 있는 기업은 경로 점수와 별개로 top/2 까지 먼저 넣는다 —
    # 업계 이슈가 많이 쌓인 범용 노드의 기업이 후보를 독식해 '지금 기업에 일어난 일'이 묻히지 않게
    picked: list[dict[str, Any]] = []
    by_supply: dict[str, int] = defaultdict(int)
    for c in sorted((x for x in out if x["_fresh"] > 0), key=lambda x: -x["_fresh"]):
        if len(picked) >= top // 2:
            break
        if by_supply[c["_supply"] or c["company_id"]] < 3:
            picked.append(c)
            by_supply[c["_supply"] or c["company_id"]] += 1
    # 다양성: 같은 부품·공정의 공급사는 3곳까지, 생태계마다 최소 몫을 남긴다 (한 테마가 후보를 독식하지 않게)
    per_eco = max(3, top // 5)
    eco_of = lambda c: nodes[c["company_id"]].get("ecosystem")  # noqa: E731
    for want_eco in ("hbm", "optics", "power"):
        for c in out:
            if sum(1 for x in picked if eco_of(x) == want_eco) >= per_eco:
                break
            if eco_of(c) == want_eco and c not in picked and by_supply[c["_supply"] or c["company_id"]] < 3:
                picked.append(c)
                by_supply[c["_supply"] or c["company_id"]] += 1
    for c in out:
        if len(picked) >= top:
            break
        if c not in picked and by_supply[c["_supply"] or c["company_id"]] < 3:
            picked.append(c)
            by_supply[c["_supply"] or c["company_id"]] += 1
    out = sorted(picked, key=lambda x: -x["score"])

    # 사람이 아니라 AI 가 읽을 압축 표현: 경로는 라벨·관계·근거 id, 동종 공급사, 기술 전환 관계
    result = []
    for k, c in enumerate(out, 1):
        n = nodes[c["company_id"]]
        lst = n.get("listing") or {}
        chains = []
        seen_paths = set()
        for p in c["_paths"]:
            key = tuple(x["node_id"] for x in p["path"])
            if key in seen_paths:
                continue
            seen_paths.add(key)
            steps = []
            for eid_ in p["edge_ids"]:
                e = edges.get(eid_)
                if not e:
                    continue
                steps.append({"from": nodes[e["from"]]["label"], "rel": e["relation"], "to": nodes[e["to"]]["label"],
                              "tier": e.get("evidence_tier"), "ev": _edge_evidence(e, reg, nodes)})
            chains.append({"signal": p["_sid"], "confidence": p["confidence"], "path_ids": [x["node_id"] for x in p["path"]], "steps": steps})
            if len(chains) >= 3:
                break
        peers = []
        if c["_supply"]:
            for pid in sup.get(c["_supply"], []):
                if pid != c["company_id"]:
                    pn = nodes[pid]
                    peers.append(f"{pn['label']} [{pn.get('size_band')}]")
        trans = []
        path_nodes = {x["node_id"] for p in c["_paths"][:6] for x in p["path"]} | {c["company_id"]}
        for e in graph["edges"]:
            if e["relation"] in TRANSITION_RELS and (e["from"] in path_nodes or e["to"] in path_nodes):
                mat = nodes[e["to"]].get("maturity") or nodes[e["from"]].get("maturity") or {}
                trans.append({"from": nodes[e["from"]]["label"], "rel": e["relation"], "to": nodes[e["to"]]["label"],
                              "polarity": e.get("polarity"), "stage": mat.get("stage"), "ev": _edge_evidence(e, reg, nodes)})
        result.append({
            "cid": f"C{k}", "company_id": c["company_id"], "company": n["label"], "ticker": lst.get("ticker"), "exchange": lst.get("exchange"),
            "size_band": n.get("size_band"), "ecosystem": n.get("ecosystem"), "also_in": n.get("also_in") or [], "score": c["score"],
            "net_sign": "+" if c["sign"] > 0 else "-", "signals": c["_signals"], "directly_named_in": c["_direct"],
            "supply_node": nodes[c["_supply"]]["label"] if c["_supply"] else None, "suppliers_of_that_node": c["_n_sup"],
            "peers": peers[:6], "chains": chains, "transitions": trans[:6],
            "offers": [{"node": nodes[e["from"] if e["relation"] == "offered_by" else e["to"]]["label"], "rel": e["relation"],
                        "ev": _edge_evidence(e, reg, nodes)} for e in offers.get(c["company_id"], [])[:5]],
        })
    return result


# ---------------------------------------------------------------- LLM
LLM_SYSTEM = """너는 AI 공급망(HBM·첨단 패키징 / 800G·1.6T 광통신 / AI 데이터센터 800VDC 전력·냉각) 전문 투자 리서치 애널리스트다.
목표: '지금' 투자 기회가 큰 상장 기업을 찾아, 바쁜 투자자가 한눈에 이해하는 '투자 아이디어'로 쓴다. 사람은 데이터를 보지 않고 아이디어와 근거만 본다.
오늘 날짜: {today}

입력
- signals: 최근 변화. I=업계 이슈, M=가격·실적 지표, E=기업별 최신 소식(공시·월매출·실적 발표·수주·기업명 뉴스; items 에 날짜·종류·중요도,
  supplies 는 그 기업이 그래프에서 공급하는 부품·소재). E 의 기업이 candidates 에 없어도 E 근거만으로 아이디어를 만들 수 있다.
  verified=true 인 항목은 원문을 열어 확인한 소식이고, 확인한 숫자·날짜는 evidence 의 excerpt 에 있다 — 숫자는 여기서 가져온다.
  각 신호와 항목에 근거 id. date 가 최근일수록 중요하다.
- candidates: 그래프가 계산한 '변화 → 병목·기술 → 공급 → 기업' 경로 후보. score 는 신호 강도×최근성×소형 가중×공급 집중.
  chains.steps 는 관계 사슬(근거 id 'ev'), chains.path_ids 는 그 사슬의 노드 id (선행 추론의 path 에 그대로 쓴다),
  peers 는 같은 부품·공정의 다른 공급사, transitions 는 대체·개발·IP 관계(성숙도 stage),
  offers 는 그 기업이 직접 공급·개발하는 부품·기술(그래프 근거). 기업 소식(E)으로 들어온 후보는 offers 로 '왜 AI 공급망인가'를 잇는다.
- evidence: 인용 가능한 근거 목록. S=최근 신호 출처(age_d = 며칠 전), G=그래프 관계 출처(배경 구조, 날짜가 오래됐을 수 있음). 이 목록의 id 만 인용한다.
- existing: 이미 피드에 있는 아이디어 (last_signal_at = 마지막 최신 근거 날짜). 같은 논리면 같은 idea_key 로 갱신한다.

최신성 규칙 (가장 중요)
- 아이디어는 최근 {fresh}일 안의 사실(S 근거, age_d ≤ {fresh})에서 출발한다. 그런 근거가 없으면 새 아이디어를 만들지 않는다.
- chain 첫 단계 claim 은 최근 사실 그 자체다 — 무엇이 언제 일어났나 (예: "10/21 유니테스트가 SK hynix와 162억원 검사장비 공급계약을 공시했다").
- G 근거는 '왜 그 변화가 이 기업에 닿는가'의 구조 설명에만 쓴다. 현재 상황(수요·부족·점유율)을 G 근거만으로 주장하지 않는다.
- E 신호(기업 자체의 공시·월매출·실적)는 노출을 직접 확인해 준다. 업계 이슈(I)와 기업 소식(E)이 같은 방향이면 강한 아이디어다.
- 시세 기사(주가 등락)는 근거로 쓰지 않는다.
- 근거는 세 층이다. 기업 직접 = primary 기업 자신의 공시·실적·수주·제품·월매출 (E 의 주어가 그 기업, 또는 이슈에 그 기업이 이름으로 나옴).
  관련 = 고객·경쟁사·동종 기업의 소식. 업계 = 산업 뉴스·가격·지표. G = 구조 설명.
- 기존 아이디어 update 는 primary 기업의 직접 근거가 새로 나왔을 때만 '강화'다. 업계·관련 소식만 새로 나왔으면 keep 한다.
  꼭 고쳐야 하면(사슬의 사실이 바뀜) update 하되 ★를 올리지 말고 what_changed 를 "업계: …" 로 쓴다 — 검증기도 그렇게 바꾼다.
- 업계 소식만으로 만든 새 아이디어는 thesis 둘째 문장에 "아직 이 기업 자신의 확인(공시·실적)은 없다" 는 사실을 밝힌다.
- existing 의 company_signal_at 은 그 아이디어의 기업 직접 근거 최신 날짜다. 이보다 새 직접 근거가 없으면 '강화'가 아니다.

선행 추론 (이 시스템의 목적 — 가장 중요)
- 수주·계약·실적은 발표 즉시 주가에 반영된다. 우리가 찾는 것은 그 **다음**이다: 기술·산업의 변화(I·M 신호)가 그래프의 영향 관계를 타고
  어느 기업의 숫자를 바꿀지 **시장보다 먼저** 짚는 것. 1차 수혜(변화에 이름이 직접 나온 기업)는 대개 이미 반영됐다고 보고,
  2차·3차(그 기업의 공급사, 병목을 푸는 부품·장비·소재의 공급사, 대체 기술의 보유자)에서 아직 조용한 기업을 찾는다.
- 아이디어마다 anticipation 을 쓴다: trigger = 출발한 변화의 근거 id(S), path = candidates.chains.path_ids 처럼 그래프 노드 id 로 적은
  '변화 → … → 기업' 경로(마지막은 primary 의 id), mechanism = 왜 그 변화가 이 기업의 매출·마진을 바꾸는지 한 문장(기술·공정 이유),
  lead_quarters = 그 변화가 이 기업 숫자(월매출·분기 실적)에 나타나기까지 분기 수, effect = {{pct_of_revenue, basis, evidence}}
  (변화의 규모 ÷ 이 기업 매출 — 입력 근거로 계산할 수 있을 때만, 분모·분자를 basis 에), priced_in = none|partial|full
  (prices 의 1개월 수익률·거래량·저점 대비와 E 신호 유무로 판단; 기업 자신의 소식이 이미 나왔고 주가가 반응했으면 full).
- 좋은 선행 아이디어의 모양: 변화는 확인된 사실(최근 S 근거), 경로는 그래프 간선으로 이어짐(끊기면 0점), 기업은 아직 자기 소식이 없고
  주가가 조용함, 변화의 규모가 그 기업 매출에 비해 큼(작은 회사), 발현까지 1~4분기. 이런 기업은 기업 직접 근거가 없어 ★2 까지만 받는다 —
  그래도 쓴다. ★는 확신이고 선행 점수는 기대값이다. 둘을 섞지 않는다.
- 반대로 자기 소식이 이미 나와 주가가 반응한 기업(priced_in=full)은 '확인' 아이디어로만 쓰고, 같은 논리의 다음 고리가 있으면 그쪽을 primary 로.

아이디어를 만드는 법
- 한 아이디어 = 하나의 논리: "무엇이 바뀌었나(최근 사실) → 그래서 어떤 병목/전환이 조여지나 → 공급이 왜 소수에게 몰리나 → 그래서 이 기업".
  유형: bottleneck(병목 수혜) | transition(기술 전환의 승자·새 병목) | confirmation(실적·수주·가격이 확인해 준 노출) | risk(대체·수요 이탈로 피해).
- 제목: 투자자가 바로 이해하는 짧은 한 문장, 30자 안팎. 무엇이 어디로 움직이는지를 말한다.
  기업명·티커·숫자·괄호·줄표(—)·부제는 넣지 않는다 — 기업은 카드에 따로 나온다. 업계 은어 대신 결과를 말한다.
  예) "전력망 연결을 못 기다리는 데이터센터는 현장 가스엔진으로", "HBM 을 높이 쌓을수록 번인 검사가 길어진다"
- thesis: 2문장. 첫 문장은 최근 변화(날짜 포함), 둘째 문장은 왜 이 기업인가.
- primary 는 상장 소형·중형 공급사를 우선한다. 대형·초대형은 논리가 압도적일 때만 primary, 보통은 수요처·경쟁 맥락으로 companies 에 넣는다.
- chain: 3~5 단계. 각 단계 claim 은 한 문장, evidence 에 근거 id 1개 이상. 기술 추론(technical_inference) 근거만 있는 단계는 claim 끝에 "(추론)".
- stars: 3 = 최근 사실이 병목·전환을 직접 확인하고 + 공급이 소수에 집중되고 + 기업 노출이 최근 공식 근거(공시·실적)로 확인. 2 = 셋 중 둘. 1 = 하나 또는 추론 의존.
  ★3 은 primary 기업의 최근 30일 직접 근거가 있어야 한다 (없으면 검증기가 ★2 로 내린다).
- risks: 1~3개. 반대 근거·대체 경로·이미 알려진 정도(대형 고객 집중, 중국 경쟁, 경쟁사 증설 시점 등). 근거 id 가 있으면 붙이고 없으면 빈 배열.
- watch: 2~3개, 날짜와 측정 기준이 있는 확인 일정. {{"what": "TPEx 10월 월매출 공시", "due": "2026-11-10", "metric": "YoY", "threshold": "≥ +50%",
  "direction": "strengthen"}} — 그 날짜에 무엇을 보면 아이디어가 강해지는지(strengthen) 약해지는지(weaken) 판정할 수 있게 쓴다. 날짜를 모르면 due 를 비운다.
- 노출 순도: primary 기업 항목에 "exposure": {{"share_pct": 49, "segment": "광통신", "basis": "3Q26 부문 매출 23.79억/전체 48.6억 달러", "evidence": "S12"}}.
  그 병목·전환과 관련된 사업이 회사 매출에서 차지하는 비중이다. 입력 근거(공시·실적 발표의 부문 매출)로 계산할 수 있을 때만 쓰고, 모르면 빼라 — 추정 금지.
- 판단 점수: 검증기가 근거 점수(확신, 10점: 기업 직접 근거 4 · 숫자 확인 1 · 병목 구조 3 · 노출 순도 2 · 반대 근거 −2)와 선행 점수(기대값)를 계산하지만
  화면에는 올리지 않는다 — 사람이 보는 결과는 아래 '가치평가'다. ★3 은 근거 점수 7점 이상이어야 하고, 2점 이하는 ★1 로 내려간다.
- states: 병목·부품의 상태 관측치(가격 배수·리드타임·가동률·재고·수주잔고·평균단가 등, 원문에서 확인한 숫자). 병목이 조여지는지 풀리는지의 근거로 쓴다.
- leads: 엔진이 찾은 조사 단서 — 기업 소식은 있는데 아이디어가 없는 기업, 활동이 많은 병목의 미커버 공급사, 설명 안 된 가격 급변. 근거가 되면 아이디어로 만든다.
- prices: 주요 기업의 종가(close, currency)·발행주식수(shares)·시가총액(market_cap_usd)·이미 움직인 폭(1·12개월, 고점·저점 대비)·tenbagger 와
  fundamentals(TTM 매출 revenue·영업이익률 op_margin_pct·순이익률 net_margin_pct·매출 성장률 revenue_yoy_pct·P/S ps·P/E pe, 현지 통화 원 단위). 가치평가의 재료다.
  근거로 인용하지는 않는다. 저점 대비 3배 이상 오른 기업은 risks 에 "이미 알려진 정도"를 적고, 같은 논리에 시총이 작고 덜 오른 공급사가 있으면 그쪽을 primary 로 고려한다.
- 숫자·날짜는 입력에 있는 것만 쓴다. 매수/매도 권유·시점 예측 금지. 주가에 대한 판단은 아래 valuation 의 시나리오로만 말한다.
- 서로 다른 아이디어가 같은 기업·같은 논리를 반복하지 않게 묶는다. 근거가 빈약하면 만들지 않는다 — 개수보다 질.

가치평가 (결과 — 사람은 이것만 본다)
- 아이디어마다 valuation 을 쓴다. 질문은 하나다: 이 변화가 이 기업의 숫자를 바꾸면 이 회사는 {horizon}개월 뒤 얼마짜리 회사인가, 지금 주가와 얼마나 다른가.
- 재료는 prices[primary] 다: close·currency·shares·market_cap_usd·fundamentals. fundamentals 가 없으면 근거(IR·공시·실적 발표)에서 읽은 매출·이익을 쓰되
  assumptions 에 사실(fact)로 근거 id 와 함께 적는다. 종가(close)가 없으면 valuation 을 쓰지 않고 valuation_skipped 에 이유를 적는다.
- **영향 추정은 네 판단이다.** 기술·산업의 변화가 이 기업 매출을 얼마나 바꾸는지는 입력 어디에도 숫자로 없다 — 네가 추정한다:
  변화의 크기(시장·수량·가격이 얼마나 바뀌나) × 이 기업에 닿는 비율(점유율·공급 비중·경로의 확실성) × 시점(몇 분기 뒤 숫자에 나타나나) → 매출 증분,
  그리고 그때의 마진과 시장이 줄 배수. 이 숫자들은 추정이다. 추정은 금지가 아니라 **표시**다: assumptions 에 kind="estimate" 로 적고 basis 에
  "무엇에서 어떻게 그 숫자를 냈나"를 쓴다 (예: "HBM4 12단은 번인 시간 1.8배(G7) × 고객 증설 2배(S12) → 소켓 수요 2.5배, 이 회사 점유율 40%(추정: 상위 2사 과점) → 매출 +60%").
  사실(kind="fact")은 근거 id 가 있어야 하고, 추정(kind="estimate")은 basis 가 있어야 한다. 다른 절의 '추정 금지'(노출 순도·effect)는 사실 칸에만 적용된다.
  최소한 변화의 크기 · 닿는 비율 · 시점 세 추정이 assumptions 에 있어야 한다.
- 시나리오 3개 bear·base·bull (prob 합 = 1). 각각 {horizon}개월 뒤의 매출(revenue, 현지 통화 원 단위) · 마진(margin_pct, 영업이익률 또는 순이익률) ·
  배수(metric: ps|pe, multiple) → 내재 시총 implied_mcap_local = revenue × multiple (ps) 또는 revenue × margin_pct/100 × multiple (pe).
  검증기가 같은 식으로 다시 계산하고 shares 로 나눠 내재 주가를 낸다 — 산수는 검증기가 한다, 추정은 네가 한다. 확률(prob)도 추정이다: 경로의 확실성·
  경쟁·시장 반영 정도를 보고 매긴다.
  - 배수는 지금 배수(fundamentals.ps·pe)와 동종(peers)의 배수에서 출발해, 성장이 확인될 때 시장이 주는 배수로 옮긴다. 배수를 바꾸면 그 이유를 추정으로 적는다.
  - bear = 아이디어 자체가 틀린 경우를 반드시 포함한다: 변화가 이 기업에 닿지 않거나(경로 단절·경쟁사 수주·고객 내재화) 이미 다 반영된 경우 —
    지금 배수 × 지금 매출 또는 그 아래. 기업 자신의 근거가 없는 아이디어는 bear 확률을 낮게 잡을 이유가 없다.
  - story 는 그 시나리오가 일어나는 한 문장, evidence 는 그 시나리오의 숫자를 받치는 근거 id (없으면 빈 배열).
- expected_price = Σ prob × 내재 주가 (서버 계산). confidence: high = 경로가 그래프 간선과 기업 직접 근거로 이어지고 분모가 공식 재무,
  mid = 경로나 분모 중 하나가 추론, low = 둘 다 추론 (기업 자신의 근거가 없으면 high 는 불가).
- verdict: 3~5문장 한 단락 — 어떤 변화가(날짜) → 어떤 경로로 이 기업 숫자를 → 얼마나(매출·마진, 추정이면 "추정"이라 밝힌다) → 그래서 시총·주가는 →
  시장이 지금 반영한 정도. 사실 숫자는 근거에서, 추정 숫자는 네 논리에서 — 둘을 섞어 쓰지 않는다. "목표가"·"매수" 같은 말은 쓰지 않는다 — 모형 산출이지 권유가 아니다.
- assumptions 3~6개: fact(근거 id 1개 이상) 1개 이상 + estimate(basis) — 변화의 크기·닿는 비율·시점·배수. breaks 1~3개(이 평가가 깨지는 조건과 그것을 확인할 데이터·날짜).
- action=keep 인 기존 아이디어도 valuation 을 쓴다: existing.valuation 이 없으면(아직 평가가 없음) **반드시**, 있으면 (a) 그 뒤 주가가 ±15% 넘게 움직였거나
  (b) 새 근거가 매출·마진 가정을 바꿀 때. 둘 다 아니면 생략한다 — 지난 평가가 그대로 쓰이고 상승여력만 오늘 주가로 다시 계산된다.

existing 처리
- existing 은 지난 실행의 판단이지 사실이 아니다. 믿고 이어 쓰지 말고 오늘의 근거로 다시 판단한다 — 특히 기업 자신의 근거(company_signal_at)가 없는 아이디어는
  구조 추론일 뿐이므로 가치평가에서 bear 확률과 confidence 로 그 사실을 드러낸다. 같은 기업·같은 논리로 더 나은 다음 고리가 보이면 기존 것을 close 하고 새로 쓴다.
- 같은 논리에 최근 {fresh}일 안의 새 근거가 있으면 action=update (idea_key 그대로, chain 을 새 근거로 다시 쓰고, what_changed 에 "날짜 + 새 사실" 한 줄).
- 새 근거가 반대 방향이면 action=weaken, 반증·소멸되면 action=close (reason). 새 근거가 없으면 action=keep (idea_key 만).
- last_signal_at 이 {stale}일 넘게 지났고 이번 입력에도 새 근거가 없으면 action=weaken (reason: 최신 근거 없음).

확인 일정 채점 (grades)
- existing 의 watch 중 status=pending 이고 due 가 지났거나 이번 입력에 결과가 나온 항목을 채점한다.
  hit = 적힌 기준대로 나왔다(아이디어 방향과 같음), miss = 반대로 나왔다, void = 더는 의미가 없다. hit·miss 는 근거 id 가 필요하다.
- 결과가 아직 없으면 채점하지 않는다. 채점은 아이디어를 고치지 않아도(keep) 할 수 있다.

출력: JSON 하나만.
{{"ideas": [{{"action": "new|update|weaken|keep|close", "idea_key": "기존 key 또는 null", "type": "bottleneck|transition|confirmation|risk",
  "title": "...", "thesis": "...", "stars": 1, "stars_reason": "한 줄",
  "companies": [{{"id": "company:...", "role": "primary|peer|customer|competitor|displaced", "why": "한 줄", "exposure": {{"share_pct": 0, "segment": "...", "basis": "...", "evidence": "S1"}}}}],
  "chain": [{{"claim": "...", "evidence": ["S1", "G3"]}}],
  "risks": [{{"claim": "...", "evidence": []}}], "watch": [{{"what": "...", "due": "YYYY-MM-DD", "metric": "...", "threshold": "...", "direction": "strengthen"}}],
  "anticipation": {{"trigger": "S12", "path": ["bottleneck:…", "equipment:…", "company:…"], "mechanism": "한 문장", "lead_quarters": 2,
                   "effect": {{"pct_of_revenue": 25, "basis": "NT$509억 발주 × 점유율 30% ÷ 연매출 NT$28억", "evidence": "S54"}}, "priced_in": "none"}},
  "valuation": {{"horizon_months": {horizon}, "confidence": "mid",
    "scenarios": [{{"name": "bear", "prob": 0.25, "story": "한 문장", "revenue": 2800000000, "margin_pct": 8, "metric": "ps", "multiple": 1.5, "implied_mcap_local": 4200000000, "evidence": ["S12"]}},
                  {{"name": "base", "prob": 0.5, "story": "…", "revenue": 4500000000, "margin_pct": 14, "metric": "pe", "multiple": 20, "implied_mcap_local": 12600000000, "evidence": ["S54", "G3"]}},
                  {{"name": "bull", "prob": 0.25, "story": "…", "revenue": 7000000000, "margin_pct": 18, "metric": "pe", "multiple": 25, "implied_mcap_local": 31500000000, "evidence": ["S54"]}}],
    "verdict": "3~5문장",
    "assumptions": [{{"kind": "fact", "claim": "번인 소켓 매출 비중 60%", "evidence": ["S12"]}},
                    {{"kind": "estimate", "claim": "변화의 크기: 고적층 번인 수요 2.5배", "basis": "번인 시간 1.8배(G7) × 증설 2배(S12)", "evidence": ["G7", "S12"]}},
                    {{"kind": "estimate", "claim": "닿는 비율: 점유율 40%", "basis": "상위 2사 과점, 최근 수주 비중", "evidence": []}},
                    {{"kind": "estimate", "claim": "시점: 2분기 뒤 월매출", "basis": "증설 → 장비 반입 → 양산 리드타임", "evidence": []}}],
    "breaks": [{{"claim": "…", "evidence": ["S3"]}}]}},
  "valuation_skipped": "valuation 을 못 쓸 때만, 이유",
  "what_changed": "update 일 때만", "reason": "weaken/close 일 때"}}],
 "grades": [{{"idea_key": "...", "index": 0, "status": "hit|miss|void", "evidence": "S12", "note": "한 줄"}}]}}"""

VALUATION_HORIZON_MONTHS = 12


def system_prompt(now: datetime) -> str:
    return LLM_SYSTEM.format(today=now.date().isoformat(), fresh=FRESH_DAYS, stale=21, horizon=VALUATION_HORIZON_MONTHS)


def build_payload(signals: list[dict[str, Any]], candidates: list[dict[str, Any]], reg: Registry, existing: list[dict[str, Any]],
                  max_ideas: int, now: datetime | None = None, extras: dict[str, Any] | None = None) -> dict[str, Any]:
    used = set()
    for s in signals:
        used.update(s["evidence"])
    for c in candidates:
        for ch in c["chains"]:
            used.update(st["ev"] for st in ch["steps"] if st["ev"])
        used.update(t["ev"] for t in c["transitions"] if t["ev"])
    now = now or datetime.now(UTC)
    # 기업 소식 항목은 제목·날짜가 signals.items 에 이미 있다 → 근거 목록에는 id·출처·나이만 (입력 토큰 절약)
    in_items = {it["ev"] for s in signals if s["kind"] == "company" for it in s["items"]}
    evidence = []
    for e in reg.items.values():
        if e.eid not in used:
            continue
        row = {"id": e.eid, "publisher": e.publisher, "age_d": age_days(e.date, now), "tier": e.tier}
        if e.eid not in in_items:
            row |= {"title": e.title, "date": e.date}
        if e.excerpt:
            row["excerpt"] = e.excerpt[:220]
        evidence.append(row)
    sigs = []
    for s in signals:
        d = {k: s[k] for k in ("sid", "kind", "title", "stars", "date", "evidence")} | {"age_d": age_days(s.get("date"), now)}
        if s["kind"] == "company":
            d |= {"items": s["items"], "supplies": s.get("supplies") or []}
        else:
            d |= {"what": s.get("what"), "why": s.get("why")}
        sigs.append(d | {"nodes": s["nodes"], "companies": s["companies"]})
    def watch_view(x: dict[str, Any]) -> list[dict[str, Any]]:
        out = []
        for i, w in enumerate(x.get("watch") or []):
            w = w if isinstance(w, dict) else {"what": str(w)}
            out.append({"index": i, "what": w.get("what"), "due": w.get("due"), "threshold": w.get("threshold"), "status": w.get("status", "pending")})
        return out

    extras = extras or {}
    vals = extras.get("valuations") or {}

    def val_view(key: str) -> dict[str, Any] | None:
        v = vals.get(key)
        if not v:
            return None
        return {k: v.get(k) for k in ("as_of", "price", "currency", "expected_price", "expected_upside_pct", "confidence", "horizon_months")}

    return {
        "today": now.date().isoformat(),
        "max_ideas": max_ideas,
        "signals": sigs,
        "candidates": candidates,
        "evidence": evidence,
        "states": extras.get("states") or [],
        "leads": extras.get("leads") or {},
        "prices": extras.get("prices") or {},
        "existing": [{k: x.get(k) for k in ("idea_key", "type", "title", "thesis", "stars", "primary_company", "last_signal_at", "updated_at")}
                     | {"companies": [c.get("id") for c in x.get("companies") or []], "company_signal_at": company_signal_date(x),
                        "score": ((x.get("assessment") or {}).get("score")), "watch": watch_view(x), "valuation": val_view(x["idea_key"])} for x in existing],
    }


# ---------------------------------------------------------------- validation → rows
def clean_title(title: str, comps: list[dict[str, Any]]) -> str:
    """제목 끝의 '— 기업명 …'·'(기업명)' 꼬리를 뗀다 — 기업은 카드에 따로 나온다. 남는 앞부분이 너무 짧으면 그대로 둔다."""
    names: set[str] = set()
    for c in comps:
        for part in str(c.get("name") or "").split(" / "):
            part = part.strip().lower()
            if len(part) >= 3:
                names.add(part)
            if len(part.split(" ")[0]) >= 4:
                names.add(part.split(" ")[0])
        if len(str(c.get("ticker") or "")) >= 3:
            names.add(str(c["ticker"]).lower())
    t = title.strip()
    if " — " in t:
        head, tail = t.rsplit(" — ", 1)
        if len(head) >= 12 and any(n in tail.lower() for n in names):
            t = head.strip()
    m = re.search(r"\s*\(([^)]*)\)\s*$", t)
    if m and any(n in m.group(1).lower() for n in names):
        t = t[: m.start()].strip()
    return t


def make_key(kind: str, primary: str, title: str) -> str:
    slug = re.sub(r"\W+", "", title)[:24]
    return hashlib.sha1(f"{kind}|{primary}|{slug}".encode()).hexdigest()[:12]


REL_KO = {"direct": "기업 직접", "related": "관련 기업", "industry": "업계", "background": "그래프 배경"}
DIRECT_STAR3_DAYS = 30  # ★3 은 primary 기업의 이 기간 안 직접 근거가 있어야 한다


def evidence_rel(eid: str, sig: dict[str, Any] | None, primary: str, idea_cos: set[str]) -> str:
    """근거가 이 아이디어의 주 기업에 대해 무엇인가 — 기업 직접 / 관련 기업 / 업계 / 그래프 배경.
    기업 소식(E)은 주어(subject)가 기준이고, 이슈·지표는 그 안에 이름이 나온 기업이 기준이다."""
    if eid.startswith("G"):
        return "background"
    if not sig:
        return "industry"
    cos = set(sig.get("companies") or [])
    subject = sig.get("subject")
    if subject:
        if subject == primary:
            return "direct"
        return "related" if subject in idea_cos or primary in cos else "industry"
    if primary in cos:
        return "direct"
    return "related" if cos & idea_cos else "industry"


def company_signal_date(idea: dict[str, Any]) -> str | None:
    """기존 아이디어의 '기업 직접 근거' 최신 날짜. rel 이 없던 예전 행은 근거 제목에 주 기업 이름이 있는지로 본다."""
    primary = idea.get("primary_company")
    pc = next((c for c in idea.get("companies") or [] if c.get("id") == primary), None)
    names = [x.lower() for x in [(pc or {}).get("name"), (pc or {}).get("ticker")] if x and len(str(x)) >= 3]
    dates = []
    for st in idea.get("chain") or []:
        for e in st.get("evidence") or []:
            if not str(e.get("id", "")).startswith("S") or not e.get("date"):
                continue
            rel = e.get("rel")
            if rel == "direct" or (rel is None and any(n in str(e.get("title") or "").lower() for n in names)):
                dates.append(str(e["date"])[:10])
    return max(dates) if dates else None


def validate(raw: list[dict[str, Any]], reg: Registry, graph: dict[str, Any], signals: list[dict[str, Any]],
             existing: dict[str, dict[str, Any]], now: datetime, model: str, method: str,
             ctx: dict[str, Any] | None = None, valuations: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """LLM 출력 → ideas.put_ideas 행. valuations 리스트를 주면 아이디어마다 쓴 가치평가(검증·재계산 끝낸 ideas.put_valuations 행)를 거기에 모은다
    (keep 인 아이디어가 다시 쓴 평가도 포함)."""
    from wsj.ecosystems import assess as A

    ctx = ctx or {}
    structure = ctx.get("structure") or A.Structure(graph)
    nodes = {n["id"]: n for n in graph["nodes"]}
    sig_by_ev = {e: s for s in signals for e in s["evidence"]}
    fresh_cut = (now - timedelta(days=FRESH_DAYS)).date().isoformat()
    money = ctx.get("money") or {}
    today = now.date().isoformat()
    rows, rejects = [], []

    def add_valuation(it: dict[str, Any], key: str, primary_id: str, cos: set[str], assessment: dict[str, Any] | None, label: str) -> None:
        if valuations is None or not isinstance(it.get("valuation"), dict):
            return
        ev = lambda ids: [reg.items[e].public() | {"rel": evidence_rel(e, sig_by_ev.get(e), primary_id, cos)} for e in ids if e in reg.items]  # noqa: E731
        v, why = parse_valuation(it["valuation"], money.get(primary_id), ev)
        if not v:
            rejects.append(f"#{label} valuation rejected: {why}")
            return
        ant = (assessment or {}).get("anticipation") or {}
        v |= {"idea_key": key, "as_of": today, "company_id": primary_id, "model": model, "method": method,
              "path": {"labels": ant.get("path_labels") or [], "mechanism": ant.get("mechanism")} if ant else None,
              "calculator": {"evidence_score": (assessment or {}).get("score"), "anticipation_score": ant.get("score"), "priced_in": ant.get("priced_in"),
                             "tenbagger": ((assessment or {}).get("price") or {}).get("tenbagger")} if assessment else None}
        valuations.append(v)

    for i, it in enumerate(raw):
        action = it.get("action") or "new"
        key = it.get("idea_key") if it.get("idea_key") in existing else None
        if action in ("keep", "close", "weaken") and not key:
            rejects.append(f"#{i} {action} without known idea_key")
            continue
        if action == "keep":
            prev = existing[key]
            add_valuation(it, key, prev.get("primary_company"), {c.get("id") for c in prev.get("companies") or []}, prev.get("assessment"), str(i))
            continue
        if action == "close":
            rows.append({"idea_key": key, "status": "closed", "trend": "weakened", "close_reason": (it.get("reason") or "")[:300], "updated_at": now.isoformat()})
            continue
        kind = it.get("type") if it.get("type") in IDEA_TYPES else None
        title, thesis = (it.get("title") or "").strip(), (it.get("thesis") or "").strip()
        try:
            stars = int(it.get("stars"))
        except (TypeError, ValueError):
            stars = 0
        if not kind or not title or not thesis or stars not in (1, 2, 3):
            rejects.append(f"#{i} missing type/title/thesis/stars: {title[:40]}")
            continue
        comps = []
        for c in it.get("companies") or []:
            cid = c.get("id")
            if cid in nodes and nodes[cid]["kind"] == "company":
                n = nodes[cid]
                lst = n.get("listing") or {}
                row_c = {"id": cid, "name": re.split(r"\s+\(", n["label"])[0], "ticker": lst.get("ticker"), "exchange": lst.get("exchange"),
                         "size_band": n.get("size_band"), "role": c.get("role") or "peer", "why": (c.get("why") or "")[:200]}
                ex = c.get("exposure")
                # 노출 비중은 근거 id 가 있어야 받는다 (추정 금지)
                if isinstance(ex, dict) and ex.get("evidence") in reg.items:
                    try:
                        share = float(ex.get("share_pct"))
                    except (TypeError, ValueError):
                        share = -1
                    if 0 <= share <= 100:
                        ev = reg.items[ex["evidence"]]
                        row_c["exposure"] = {"share_pct": round(share, 1), "segment": str(ex.get("segment") or "")[:60],
                                             "basis": str(ex.get("basis") or "")[:160], "url": ev.url, "as_of": ev.date}
                comps.append(row_c)
        primary = next((c for c in comps if c["role"] == "primary"), comps[0] if comps else None)
        if not primary:
            rejects.append(f"#{i} no valid company: {title[:40]}")
            continue
        idea_cos = {c["id"] for c in comps}
        title = clean_title(title, comps)

        def ev_rows(ids: list[str], pid: str = primary["id"], cos: set[str] = idea_cos) -> list[dict[str, Any]]:
            return [reg.items[e].public() | {"rel": evidence_rel(e, sig_by_ev.get(e), pid, cos)} for e in ids if e in reg.items]

        chain = []
        for st in it.get("chain") or []:
            evs = ev_rows(st.get("evidence") or [])
            if st.get("claim") and evs:
                chain.append({"claim": st["claim"].strip(), "evidence": evs})
        has_signal = any(e["id"] in sig_by_ev for st in chain for e in st["evidence"])
        if len(chain) < 2 or (not key and not has_signal):
            rejects.append(f"#{i} weak chain ({len(chain)} steps, signal={has_signal}): {title[:40]}")
            continue
        s_dates = sorted({e["date"] for st in chain for e in st["evidence"] if e["id"].startswith("S") and e.get("date")})
        fresh = [d for d in s_dates if d >= fresh_cut]
        if not fresh and (not key or action == "update"):
            rejects.append(f"#{i} {action} without evidence from the last {FRESH_DAYS} days (newest {s_dates[-1] if s_dates else None}): {title[:40]}")
            continue
        risks = [{"claim": r["claim"].strip(), "evidence": ev_rows(r.get("evidence") or [])}
                 for r in it.get("risks") or [] if isinstance(r, dict) and r.get("claim")]
        sig_refs = sorted({sig_by_ev[e["id"]]["ref"] for st in chain for e in st["evidence"] if e["id"] in sig_by_ev})
        # 마지막 최신 근거 날짜 = 인용한 S 근거 중 가장 최근 (신호 묶음 날짜가 아니라 근거 자체의 날짜)
        last_sig = s_dates[-1] if s_dates else (existing.get(key) or {}).get("last_signal_at") if key else None
        theme = sorted({n for s in signals if s["ref"] in sig_refs for n in s["nodes"]})
        pn = nodes[primary["id"]]
        ecos = sorted({x for x in [pn.get("ecosystem"), *(pn.get("also_in") or [])] if x})
        prev = existing.get(key) if key else None
        direct_dates = sorted({e["date"][:10] for st in chain for e in st["evidence"] if e.get("rel") == "direct" and e.get("date")})
        prev_direct = company_signal_date(prev) if prev else None
        new_direct = bool(direct_dates) and direct_dates[-1] >= fresh_cut and (not prev_direct or direct_dates[-1] > prev_direct)
        stars_note = ""
        # ★3 = 주 기업 자신의 최근 근거가 있어야 한다 (업계 소식만으로는 ★2 까지)
        star3_cut = (now - timedelta(days=DIRECT_STAR3_DAYS)).date().isoformat()
        if stars == 3 and not (direct_dates and direct_dates[-1] >= star3_cut):
            stars, stars_note = 2, f" (기업 직접 근거가 최근 {DIRECT_STAR3_DAYS}일 안에 없어 ★2)"
        what_changed = (it.get("what_changed") or "").strip() or None
        if prev and action != "weaken" and not new_direct:
            # 업계 소식만 새로 나왔다 → '강화' 가 아니다. ★를 올리지 않고, 바뀐 점은 업계 근거로 표시
            if stars > (prev.get("stars") or 0):
                stars, stars_note = int(prev.get("stars") or stars), " (새 기업 직접 근거 없음 → ★ 유지)"
            if what_changed and not what_changed.startswith("업계"):
                what_changed = "업계: " + what_changed
        watch = A.normalize_watch(it.get("watch") or [], now, (prev or {}).get("watch"))
        anticipation = parse_anticipation(it.get("anticipation"), reg, nodes, sig_by_ev)
        draft = {"primary_company": primary["id"], "companies": comps, "chain": chain, "risks": risks, "nodes": theme[:12],
                 "anticipation": anticipation}
        assessment = A.assess(draft, structure, ctx.get("issues") or [], ctx.get("indicators") or [], ctx.get("prices") or {}, now)
        stars, rule_note = A.apply_star_rule(stars, assessment["score"])
        stars_note += rule_note
        trend = "new" if not prev else ("weakened" if action == "weaken" or stars < (prev.get("stars") or 0)
                                        else "strengthened" if new_direct and (stars > (prev.get("stars") or 0) or action == "update")
                                        else "unchanged")
        new_key = key or make_key(kind, primary["id"], title)
        add_valuation(it, new_key, primary["id"], idea_cos, assessment, str(i))
        rows.append({
            "idea_key": new_key, "status": "active", "trend": trend, "type": kind,
            "title": title[:120], "thesis": thesis[:600], "stars": stars, "stars_reason": ((it.get("stars_reason") or "") + stars_note)[:300],
            "primary_company": primary["id"], "companies": comps, "chain": chain, "risks": risks,
            "watch": watch, "what_changed": what_changed, "assessment": assessment, "anticipation": anticipation,
            "nodes": theme[:12], "ecosystems": ecos, "signal_refs": sig_refs,
            "evidence_count": len({e["id"] for st in chain for e in st["evidence"]}),
            "last_signal_at": last_sig, "updated_at": now.isoformat(), "model": model, "method": method,
        })
    rows += star3_audit(existing, {r["idea_key"] for r in rows}, now, model, method)
    return rows, rejects


def parse_anticipation(raw: Any, reg: Registry, nodes: dict[str, dict[str, Any]], sig_by_ev: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """LLM 의 선행 추론 {trigger, path, mechanism, lead_quarters, effect{pct_of_revenue, basis, evidence}, priced_in} 을 검증.
    path 는 그래프 노드 id 만, effect 는 근거 id 가 있어야 받는다 (추정 금지). 점수는 assess.anticipation 이 매긴다."""
    if not isinstance(raw, dict):
        return None
    path = [p for p in (raw.get("path") or []) if isinstance(p, str) and p in nodes][:ANTICIPATION_MAX_PATH]
    trig = raw.get("trigger")
    trig_sig = sig_by_ev.get(trig) if isinstance(trig, str) else None
    out: dict[str, Any] = {"trigger": trig if isinstance(trig, str) else None, "trigger_title": (trig_sig or {}).get("title"),
                           "path": path, "mechanism": str(raw.get("mechanism") or "")[:300],
                           "priced_in": raw.get("priced_in") if raw.get("priced_in") in ("none", "partial", "full") else None}
    try:
        out["lead_quarters"] = int(raw.get("lead_quarters")) if raw.get("lead_quarters") is not None else None
    except (TypeError, ValueError):
        out["lead_quarters"] = None
    eff = raw.get("effect") if isinstance(raw.get("effect"), dict) else None
    if eff and eff.get("evidence") in reg.items:
        try:
            pct = float(eff.get("pct_of_revenue"))
        except (TypeError, ValueError):
            pct = None
        if pct is not None and 0 <= pct <= 1000:
            ev = reg.items[eff["evidence"]]
            out["effect"] = {"pct_of_revenue": round(pct, 1), "basis": str(eff.get("basis") or "")[:160], "evidence": eff["evidence"],
                             "url": ev.url, "as_of": ev.date}
    return out


ANTICIPATION_MAX_PATH = 8
SCENARIO_NAMES = ("bear", "base", "bull")
VALUATION_MIN_VERDICT = 120
VALUATION_MIN_ASSUMPTIONS = 2


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def parse_valuation(raw: Any, money: dict[str, Any] | None, ev_rows: Any, horizon_default: int = VALUATION_HORIZON_MONTHS
                    ) -> tuple[dict[str, Any] | None, str | None]:
    """LLM 의 가치평가 → ideas.put_valuations 행. 산수는 여기서 다시 한다 (ADR-0019):
    내재 시총 = revenue × multiple (ps) 또는 revenue × margin/100 × multiple (pe) → ÷ shares = 내재 주가 → 확률 가중 = expected_price.
    돌려주는 값: (행, None) 또는 (None, 거부 사유). 종가가 없으면 평가하지 않는다."""
    if not isinstance(raw, dict):
        return None, "valuation 없음"
    price = _f((money or {}).get("close"))
    if not money or not price or price <= 0:
        return None, "주가 없음"
    shares = _f(money.get("shares"))
    scen: list[dict[str, Any]] = []
    notes: list[str] = []
    for s in raw.get("scenarios") or []:
        if not isinstance(s, dict) or s.get("name") not in SCENARIO_NAMES or any(x["name"] == s["name"] for x in scen):
            continue
        prob = _f(s.get("prob"))
        if prob is None or not 0 <= prob <= 1:
            continue
        rev, margin, mult = _f(s.get("revenue")), _f(s.get("margin_pct")), _f(s.get("multiple"))
        metric = s.get("metric") if s.get("metric") in ("ps", "pe") else None
        mcap = _f(s.get("implied_mcap_local"))
        calc = None
        if rev is not None and rev >= 0 and mult is not None and mult > 0:
            if metric == "ps":
                calc = rev * mult
            elif metric == "pe" and margin is not None:
                calc = rev * margin / 100 * mult
        if calc is not None and calc > 0:
            if mcap and abs(calc / mcap - 1) > 0.15:
                notes.append(f"{s['name']}: 내재 시총 {mcap:,.0f} → 계산값 {calc:,.0f} 으로 고침")
            mcap = calc
        ip = _f(s.get("implied_price"))
        if mcap and mcap > 0 and shares:
            ip = mcap / shares
        elif ip and ip > 0 and shares:
            mcap = ip * shares
        if not ip or ip <= 0:
            continue
        scen.append({"name": s["name"], "prob": round(prob, 3), "story": str(s.get("story") or "")[:200], "revenue": rev, "margin_pct": margin,
                     "metric": metric, "multiple": mult, "implied_mcap_local": round(mcap) if mcap else None, "implied_price": round(ip, 4),
                     "upside_pct": round(100 * (ip / price - 1), 1), "evidence": ev_rows(s.get("evidence") or [])})
    if len(scen) < 2:
        return None, f"시나리오 {len(scen)}개 (내재 주가를 계산할 수 없음 — revenue·multiple·shares 또는 implied_price 필요)"
    psum = sum(x["prob"] for x in scen)
    if abs(psum - 1) > 0.02:
        return None, f"시나리오 확률 합 {psum:.2f}"
    order = {n: i for i, n in enumerate(SCENARIO_NAMES)}
    scen.sort(key=lambda x: order[x["name"]])
    expected = sum(x["prob"] * x["implied_price"] for x in scen) / psum
    # 가정은 두 종류: 사실(fact, 근거 id 필수)과 추정(estimate, basis 필수 — 변화의 크기·닿는 비율·시점·배수는 LLM 의 판단이다)
    assumptions = []
    for a in raw.get("assumptions") or []:
        if not isinstance(a, dict) or not a.get("claim"):
            continue
        evs = ev_rows(a.get("evidence") or [])
        basis = str(a.get("basis") or "").strip()
        kind = "estimate" if a.get("kind") == "estimate" or (not evs and basis) else "fact"
        if kind == "fact" and not evs:
            continue
        if kind == "estimate" and len(basis) < 6:
            continue
        assumptions.append({"kind": kind, "claim": str(a["claim"]).strip()[:300], "basis": basis[:300] or None, "evidence": evs})
    n_fact = sum(1 for a in assumptions if a["kind"] == "fact")
    if len(assumptions) < VALUATION_MIN_ASSUMPTIONS or n_fact < 1:
        return None, f"가정 {len(assumptions)}개 (사실 {n_fact}) — 사실(근거 id) 1개 이상, 전체 {VALUATION_MIN_ASSUMPTIONS}개 이상 (추정은 basis 필수)"
    breaks = [{"claim": str(b["claim"]).strip()[:300], "evidence": ev_rows(b.get("evidence") or [])}
              for b in raw.get("breaks") or [] if isinstance(b, dict) and b.get("claim")]
    conf = raw.get("confidence") if raw.get("confidence") in ("low", "mid", "high") else None
    if not conf:
        return None, "confidence 는 low|mid|high"
    verdict = str(raw.get("verdict") or "").strip()
    if len(verdict) < VALUATION_MIN_VERDICT:
        return None, f"verdict {len(verdict)}자 (최소 {VALUATION_MIN_VERDICT})"
    try:
        horizon = int(raw.get("horizon_months") or horizon_default)
    except (TypeError, ValueError):
        horizon = horizon_default
    horizon = min(36, max(3, horizon))
    return {"currency": money.get("currency"), "price": price, "price_as_of": money.get("as_of"), "shares": shares,
            "market_cap_usd": _f(money.get("market_cap_usd")), "horizon_months": horizon, "scenarios": scen,
            "expected_price": round(expected, 4), "expected_upside_pct": round(100 * (expected / price - 1), 1), "confidence": conf,
            "verdict": verdict[:2000], "assumptions": assumptions[:8], "breaks": breaks[:4],
            "calc_notes": notes or None}, None


def judged_keys(rows: list[dict[str, Any]]) -> set[str]:
    """이번 실행에서 판단까지 새로 쓴 아이디어 (refresh_rows 가 건너뛸 것). ★3 점검(star3_audit)으로 ★만 내린 행은
    판단이 없으므로 넣지 않는다 — 손대지 않은 아이디어처럼 판단을 다시 계산해야 상세 화면의 점수가 비지 않는다."""
    return {r["idea_key"] for r in rows if r.get("assessment") or r.get("status") != "active"}


_KEEP = ("type", "title", "thesis", "primary_company", "companies", "chain", "risks", "watch", "nodes", "ecosystems", "signal_refs",
         "evidence_count", "last_signal_at")


def star_rule_audit(existing: dict[str, dict[str, Any]], rows: list[dict[str, Any]], refresh: list[dict[str, Any]], now: datetime,
                    model: str, method: str) -> list[dict[str, Any]]:
    """손대지 않은 아이디어도 오늘 다시 계산한 근거 점수와 ★ 가 어긋나면 ★ 를 내린다 (★3 은 7점 이상, 2점 이하는 ★1).
    올리는 일은 하지 않는다 — ★ 를 올리는 판단은 아이디어를 고쳐 쓰는 작업의 몫이다. star3_audit 가 이미 만든 행은 그 행을 고친다."""
    from wsj.ecosystems.assess import apply_star_rule

    by_key = {r["idea_key"]: r for r in rows}
    out = []
    for f in refresh:
        key, score = f["idea_key"], (f.get("assessment") or {}).get("score")
        x = existing.get(key) or {}
        if score is None or (x.get("status") or "active") != "active":
            continue
        row = by_key.get(key)
        cur = int((row or x).get("stars") or 0)
        new, note = apply_star_rule(cur, int(score))
        if new >= cur:
            continue
        if row is not None:
            row["stars"] = new
            row["stars_reason"] = ((row.get("stars_reason") or "") + note)[:300]
            row["what_changed"] = f"{row.get('what_changed') or ''} · 근거 점수 {score}/10 → ★{new}".strip(" ·")[:300]
            continue
        out.append({"idea_key": key, "status": "active", "trend": "weakened", **{k: x.get(k) for k in _KEEP}, "stars": new,
                    "stars_reason": ((x.get("stars_reason") or "") + note)[:300],
                    "what_changed": f"근거 점수 {score}/10 — ★ 규칙(★3 은 7점 이상, 2점 이하는 ★1)으로 ★{cur}→★{new}",
                    "last_signal_at": str(x.get("last_signal_at"))[:10] if x.get("last_signal_at") else None,
                    "updated_at": now.isoformat(), "model": model, "method": method})
    return out


def star3_audit(existing: dict[str, dict[str, Any]], touched: set[str], now: datetime, model: str, method: str) -> list[dict[str, Any]]:
    """손대지 않은(keep) ★3 아이디어도 주 기업 직접 근거가 30일 넘게 없으면 ★2 로 내린다 — ★3 규칙은 매일 다시 본다."""
    cut = (now - timedelta(days=DIRECT_STAR3_DAYS)).date().isoformat()
    out = []
    for key, x in existing.items():
        if key in touched or int(x.get("stars") or 0) != 3 or not x.get("last_signal_at"):
            continue
        at = company_signal_date(x)
        if at and at >= cut:
            continue
        out.append({"idea_key": key, "status": "active", "trend": "weakened", **{k: x.get(k) for k in _KEEP}, "stars": 2,
                    "stars_reason": ((x.get("stars_reason") or "") + f" (기업 직접 근거가 {DIRECT_STAR3_DAYS}일 넘게 없어 ★2)")[:300],
                    "what_changed": f"주 기업 자신의 최근 {DIRECT_STAR3_DAYS}일 근거가 없어 ★3→★2 (마지막 기업 직접 근거: {at or '없음'})",
                    "last_signal_at": str(x.get("last_signal_at"))[:10], "updated_at": now.isoformat(), "model": model, "method": method})
    return out


# ---------------------------------------------------------------- orchestration
def focus_companies(existing: list[dict[str, Any]]) -> set[str]:
    return {c.get("id") for x in existing for c in (x.get("companies") or []) if c.get("id")} | {x.get("primary_company") for x in existing if x.get("primary_company")}


def prepare(issues: list[dict[str, Any]], indicators: list[dict[str, Any]], graph: dict[str, Any], now: datetime, days: int,
            existing: list[dict[str, Any]], max_ideas: int, top: int, events: list[Any] | None = None, extras: dict[str, Any] | None = None
            ) -> tuple[Registry, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    reg = Registry()
    signals = load_signals(issues, indicators, graph, reg, now, days)
    if events:
        signals += company_signals(events, graph, reg, now, focus_companies(existing))
    candidates = build_candidates(graph, signals, reg, top=top, now=now)
    if extras and extras.get("prices_full"):
        # 후보·기존 아이디어 기업의 '이미 움직인 폭'만 입력에 (전체 가격표는 넣지 않는다)
        from wsj.ecosystems.assess import price_context

        nodes = {n["id"]: n for n in graph["nodes"]}
        want = {c["company_id"] for c in candidates} | focus_companies(existing)
        money = extras.get("money") or {}
        extras["prices"] = {}
        for cid in sorted(want):
            pc = price_context(extras["prices_full"], nodes.get(cid))
            if not pc:
                continue
            row = {k: v for k, v in pc.items() if k in ("r1m", "r12m", "from_high", "from_low", "market_cap_usd", "flags", "tenbagger")}
            m = money.get(cid)
            if m:  # 가치평가 재료: 종가·통화·주식수·재무
                row |= {k: m.get(k) for k in ("close", "currency", "as_of", "shares")}
                if m.get("fundamentals"):
                    row["fundamentals"] = m["fundamentals"]
            extras["prices"][cid] = row
    payload = build_payload(signals, candidates, reg, existing, max_ideas, now, extras)
    return reg, signals, candidates, payload


def merge_facts(prices: list[dict[str, Any]] | None, facts: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """가격 맥락(v_price_context) + 시가총액(v_company_facts) → 가격 키별 한 행. 시총은 USD 로 함께 둔다."""
    by_key = {p["ticker"]: dict(p) for p in prices or [] if p.get("ticker")}
    for f in facts or []:
        k = f.get("ticker")
        if not k or f.get("market_cap_usd") is None:
            continue
        by_key.setdefault(k, {"ticker": k, "close": f.get("close"), "as_of": f.get("price_as_of")})
        by_key[k]["market_cap_usd"] = f["market_cap_usd"]
        by_key[k]["shares_outstanding"] = f.get("shares_outstanding")
        by_key[k]["currency"] = f.get("currency")
        if by_key[k].get("from_low") is None and f.get("from_low") is not None:
            by_key[k]["from_low"] = f["from_low"]
    return by_key


CURRENCY_OF_EXCHANGE = {"TWSE": "TWD", "TPEx": "TWD", "KRX": "KRW", "KOSDAQ": "KRW", "SSE": "CNY", "SZSE": "CNY", "BJSE": "CNY", "HKEX": "HKD", "TSE": "JPY"}
FUND_KEYS = ("period", "period_end", "revenue", "operating_income", "net_income", "op_margin_pct", "net_margin_pct", "revenue_yoy_pct", "ps", "pe", "note")


def money_context(graph: dict[str, Any], by_key: dict[str, dict[str, Any]], fundamentals: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """기업 id → 가치평가 재료 {close, currency, as_of, shares, market_cap_usd, fundamentals}. 종가가 있는 기업만."""
    from wsj.ecosystems.assess import price_key

    fund = {f["company_id"]: f for f in fundamentals or [] if f.get("company_id")}
    out: dict[str, dict[str, Any]] = {}
    for n in graph["nodes"]:
        if n.get("kind") != "company":
            continue
        key = price_key(n)
        p = by_key.get(key) if key else None
        if not p or p.get("close") is None:
            continue
        f = fund.get(n["id"]) or {}
        ex = (n.get("listing") or {}).get("exchange")
        cur = p.get("currency") or f.get("currency") or CURRENCY_OF_EXCHANGE.get(ex, "USD")
        fd = {k: (_f(f[k]) if k not in ("period", "period_end", "note") else f[k]) for k in FUND_KEYS if f.get(k) is not None} if f else None
        if fd and f.get("currency") and f["currency"] != cur:
            fd["currency"] = f["currency"]  # 재무 통화가 가격 통화와 다르면 밝힌다 (ADR 보고 기업 등)
        out[n["id"]] = {"key": key, "close": _f(p.get("close")), "currency": cur, "as_of": str(p.get("as_of"))[:10] if p.get("as_of") else None,
                        "shares": _f(p.get("shares_outstanding")), "market_cap_usd": _f(p.get("market_cap_usd")), "fundamentals": fd}
    return out


def build_context(graph: dict[str, Any], issues: list[dict[str, Any]], indicators: list[dict[str, Any]], prices: list[dict[str, Any]],
                  events: list[Any], existing: list[dict[str, Any]], now: datetime, facts: list[dict[str, Any]] | None = None,
                  fundamentals: list[dict[str, Any]] | None = None, valuations: list[dict[str, Any]] | None = None
                  ) -> tuple[dict[str, Any], dict[str, Any]]:
    """판단(점수)에 쓰는 문맥과 LLM 입력에 더할 것 — 병목 상태 관측치·조사 단서·가격 맥락(시총 포함)·가치평가 재료(재무)·지난 평가."""
    from wsj.ecosystems import scan
    from wsj.ecosystems.assess import Structure

    st = Structure(graph)
    by_key = merge_facts(prices, facts)
    ld = scan.leads(graph, issues, indicators, events, existing, by_key, now)
    money = money_context(graph, by_key, fundamentals)
    vals = {v["idea_key"]: v for v in valuations or [] if v.get("idea_key")}
    ctx = {"structure": st, "issues": issues, "indicators": indicators, "prices": by_key, "leads": ld, "money": money, "valuations": vals}
    extras = {"states": scan.states(indicators, st), "leads": scan.compact(ld), "prices_full": by_key, "money": money, "valuations": vals}
    return ctx, extras


def refresh_rows(existing: dict[str, dict[str, Any]], touched: set[str], grades: dict[str, list[Any]], ctx: dict[str, Any],
                 now: datetime) -> list[dict[str, Any]]:
    """손대지 않은 아이디어의 판단(근거 나이·가격 맥락)과 확인 일정 채점을 다시 쓴다 → ideas.put_assessments (updated_at 그대로)."""
    from wsj.ecosystems import assess as A

    out = []
    for key, x in existing.items():
        if key in touched:
            continue
        watch = grades.get(key) or x.get("watch") or []
        watch, _ = A.expire_watch(watch, now)
        a = A.assess(x, ctx["structure"], ctx.get("issues") or [], ctx.get("indicators") or [], ctx.get("prices") or {}, now,
                     fallback_direct=company_signal_date(x))
        out.append({"idea_key": key, "assessment": a, "watch": watch})
    return out


def write_assess_sql(rows: list[dict[str, Any]], d: Path) -> Path | None:
    if not rows:
        return None
    body = json.dumps(rows, ensure_ascii=False, default=str)
    if "$wsj$" in body:
        raise ValueError("$wsj$ 가 있어 SQL 로 감쌀 수 없다")
    d.mkdir(parents=True, exist_ok=True)
    p = d / "zz_assessments.sql"
    p.write_text(f"select ideas.put_assessments($wsj${body}$wsj$::jsonb);\n", encoding="utf-8")
    return p


def write_valuation_sql(vals: list[dict[str, Any]], d: Path) -> Path | None:
    """가치평가 행 → `select ideas.put_valuations(...)` 한 문장 (zy_ = put_ideas 뒤, zz_assessments 앞)."""
    if not vals:
        return None
    body = json.dumps(vals, ensure_ascii=False, default=str)
    if "$wsj$" in body:
        raise ValueError("$wsj$ 가 있어 SQL 로 감쌀 수 없다")
    d.mkdir(parents=True, exist_ok=True)
    p = d / "zy_valuations.sql"
    p.write_text(f"select ideas.put_valuations($wsj${body}$wsj$::jsonb);\n", encoding="utf-8")
    return p


def save_valuations(store, vals: list[dict[str, Any]]) -> int:
    """API 경로(Actions)에서 가치평가 저장 — 0024 의 put_valuations RPC. 없으면 건너뛴다."""
    if not vals:
        return 0
    try:
        resp = store._req("POST", "ideas.rpc/put_valuations", body={"rows": vals})
        return int((resp.json() or {}).get("upserted") or 0)
    except Exception as exc:  # noqa: BLE001
        log.warning("put_valuations 실패 (0024 전?): %s", exc)
        return 0


def save_assessments(store, rows: list[dict[str, Any]]) -> int:
    """API 경로(Actions)에서 판단만 갱신 — 0021 의 put_assessments RPC. 없으면 건너뛴다."""
    if not rows:
        return 0
    try:
        resp = store._req("POST", "ideas.rpc/put_assessments", body={"rows": rows})
        return int((resp.json() or {}).get("updated") or 0)
    except Exception as exc:  # noqa: BLE001
        log.warning("put_assessments 실패 (0021 전?): %s", exc)
        return 0


def save(store, rows: list[dict[str, Any]]) -> int:
    """키 집합이 같은 행끼리 나눠 upsert — 종료(close) 행은 status·trend·사유만 바꾸고 나머지 열은 건드리지 않는다."""
    groups: dict[frozenset[str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[frozenset(r)].append(r)
    return sum(store.upsert("ideas.investment_ideas", g, ["idea_key"]) for g in groups.values())


def load_store_inputs(store, days: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]] | None]:
    """existing 이 None 이면 아이디어 테이블이 아직 없다 (마이그레이션 0017 전) → 저장하지 않는다."""
    issues = store.select("public.v_supply_chain_issues", ["*"], {})
    indicators = store.select("public.v_indicators", ["*"], {})
    try:
        existing: list[dict[str, Any]] | None = store.select("ideas.investment_ideas", ["*"], {"status": "active"})
    except Exception as exc:  # noqa: BLE001
        log.warning("ideas.investment_ideas 를 읽을 수 없음 (0017 적용 전?) — 저장 없이 실행: %s", exc)
        existing = None
    return issues, indicators, existing


def gather_events(args, settings, store, graph: dict[str, Any], existing: list[dict[str, Any]]) -> tuple[list[Any], dict[str, Any]]:
    """기업별 최신 소식: 오프라인이면 파일, 라이브면 지금 수집 + DB 에 쌓인 최근 14일 (대만 중대공시는 당일분만 오므로 누적이 필요)."""
    from wsj.ecosystems.company_feed import CompanyEvent, collect, load_events, merge_events, save_events

    path = args.events or (args.snapshot / "events.json" if args.snapshot and (args.snapshot / "events.json").exists() else None)
    if path:
        return [CompanyEvent.from_public(d) for d in json.loads(path.read_text(encoding="utf-8"))], {"source": str(path)}
    if args.snapshot or store is None:
        return [], {"source": "none"}
    if args.no_feed:  # 수집은 워크플로가 이미 했다 → DB 에 쌓인 최근 소식만
        stored = load_events(store, args.feed_days)
        return stored, {"source": "db", "stored": len(stored)}
    from wsj.http import HttpClient

    http = HttpClient(settings.sec_user_agent, timeout=25, max_retries=2)
    try:
        fresh, stats = collect(http, graph, args.feed_days, focus_companies(existing), settings.dart_api_key or None)
    finally:
        http.close()
    stats["saved"] = 0 if args.dry_run else save_events(store, fresh)
    stored = load_events(store, args.feed_days)
    stats["stored"] = len(stored)
    return merge_events(fresh, stored), stats


# ---------------------------------------------------------------- session mode (Claude 예약작업이 LLM 단계를 맡을 때)
PUBLIC_VIEWS = {"issues": "v_supply_chain_issues", "indicators": "v_indicators", "existing": "v_investment_ideas", "events": "v_company_events",
                "prices": "v_price_context", "facts": "v_company_facts", "fundamentals": "v_company_fundamentals", "valuations": "v_valuations"}
OPTIONAL_VIEWS = {"prices", "facts", "fundamentals", "valuations"}  # 0021·0022·0024 적용 전에는 없다


def public_credentials() -> tuple[str, str]:
    import os

    from wsj.config import load_settings

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or load_settings().supabase_url
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_KEY")
    if not (url and key):
        raise SystemExit("SUPABASE_URL · SUPABASE_PUBLISHABLE_KEY 가 필요하다 (공개 읽기 키)")
    return url, key


def load_public_inputs(url: str, key: str, feed_days: int = FRESH_DAYS) -> dict[str, list[dict[str, Any]]]:
    """공개 읽기 뷰(publishable 키, RLS 읽기 전용)에서 엔진 입력을 읽는다. 쓰기 권한이 필요 없다."""
    from wsj.http import HttpClient

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    since = (datetime.now(UTC) - timedelta(days=feed_days + 1)).isoformat()
    out: dict[str, list[dict[str, Any]]] = {}
    http = HttpClient("WSJ-investment ideas session", timeout=30, max_retries=2)
    try:
        for name, view in PUBLIC_VIEWS.items():
            rows: list[dict[str, Any]] = []
            params: dict[str, str] = {"select": "*"}
            if name == "events":
                params |= {"published_at": f"gte.{since}", "order": "published_at.desc"}
            try:
                while True:
                    page = http.get_json(f"{url.rstrip('/')}/rest/v1/{view}", params={**params, "limit": "1000", "offset": str(len(rows))},
                                         headers=headers)
                    rows += page
                    if len(page) < 1000:
                        break
            except Exception as exc:  # noqa: BLE001
                if name not in OPTIONAL_VIEWS:
                    raise
                log.warning("%s 없음 (마이그레이션 0021 전?): %s", view, exc)
                rows = []
            out[name] = rows
    finally:
        http.close()
    for r in out["events"]:  # 뷰의 verified 열 → CompanyEvent.extra
        r["extra"] = {"verified_by": "claude"} if r.get("verified") else {}
    log.info("public inputs: %s", {k: len(v) for k, v in out.items()})
    return out


def write_snapshot(d: Path, inputs: dict[str, list[dict[str, Any]]], now: datetime) -> None:
    """같은 입력·같은 시각으로 프롬프트와 검증을 두 번 돌려도 근거 id 가 같도록 입력을 고정한다."""
    d.mkdir(parents=True, exist_ok=True)
    for name in PUBLIC_VIEWS:
        (d / f"{name}.json").write_text(json.dumps(inputs.get(name) or [], ensure_ascii=False, default=str), encoding="utf-8")
    (d / "meta.json").write_text(json.dumps({"now": now.isoformat()}), encoding="utf-8")


def research_targets(signals: list[dict[str, Any]], limit: int = 40) -> list[dict[str, Any]]:
    """원문 확인 후보: 기업 소식 중 ★2+ 이면서 아직 확인되지 않은 것 (신호 순서 = 중요도 순)."""
    out = []
    for s in signals:
        if s["kind"] != "company":
            continue
        for e in s.get("_events") or []:
            if e.importance >= 2 and not (e.extra or {}).get("verified_by"):
                out.append({"event_id": e.event_id, "sid": s["sid"], "company_id": e.company_id, "kind": e.kind,
                            "date": e.published_at.date().isoformat(), "importance": e.importance, "title": e.title, "url": e.url,
                            "publisher": e.publisher, "has_text": bool(e.text)})
    return out[:limit]


def write_sql(rows: list[dict[str, Any]], d: Path) -> list[Path]:
    """검증된 행 → 행마다 `select ideas.put_ideas(...)` 한 문장 (Supabase MCP execute_sql 로 실행)."""
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, r in enumerate(rows, 1):
        body = json.dumps([r], ensure_ascii=False)
        if "$wsj$" in body:
            raise ValueError("행에 $wsj$ 가 있어 SQL 로 감쌀 수 없다")
        p = d / f"{i:02d}_{r['idea_key']}.sql"
        p.write_text(f"select ideas.put_ideas($wsj${body}$wsj$::jsonb);\n", encoding="utf-8")
        paths.append(p)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-ideas", type=int, default=8)
    ap.add_argument("--top", type=int, default=36, help="LLM 에 넘길 후보 기업 수 (절반은 기업 최신 소식 몫)")
    ap.add_argument("--snapshot", type=Path, help="issues.json · indicators.json · existing.json(선택) 이 있는 폴더 (DB 대신)")
    ap.add_argument("--emit-prompt", type=Path, help="LLM 입력(system·payload)을 파일로 쓰고 끝낸다")
    ap.add_argument("--from-llm-json", type=Path, help="LLM 호출 대신 이 파일의 {'ideas': [...]} 를 검증")
    ap.add_argument("--method", default="llm")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--load", type=Path, help="검증된 아이디어 행(JSON 배열)을 DB 에 적재")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-feed", action="store_true", help="기업 소식을 새로 모으지 않고 DB 에 쌓인 것만 쓴다")
    ap.add_argument("--feed-days", type=int, default=FRESH_DAYS)
    ap.add_argument("--events", type=Path, help="company_feed 결과 JSON (오프라인 실행용; --snapshot 의 events.json 도 읽는다)")
    ap.add_argument("--events-out", type=Path, help="이번 실행에 쓴 기업 소식을 JSON 으로 남긴다")
    # session mode: Claude 예약작업이 LLM 단계를 맡는다 (ADR-0016 개정 2). 쓰기 키 없이 공개 뷰만 읽는다.
    ap.add_argument("--from-public", action="store_true", help="공개 읽기 뷰에서 입력을 읽는다 (SUPABASE_URL·SUPABASE_PUBLISHABLE_KEY)")
    ap.add_argument("--snapshot-out", type=Path, help="--from-public 입력과 기준 시각을 이 폴더에 고정한다 (이후 --snapshot 으로 검증)")
    ap.add_argument("--emit-research", type=Path, help="원문 확인 후보(기업 소식 ★2+, 미확인) 목록을 JSON 으로 쓴다")
    ap.add_argument("--emit-sql", type=Path, help="검증된 행을 ideas.put_ideas 호출 SQL 파일로 쓴다 (DB 에는 쓰지 않음)")
    ap.add_argument("--leads-out", type=Path, help="기회 스캔(조사 단서) 결과를 JSON 으로 쓴다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    from wsj.config import load_settings

    settings = load_settings()
    store = None
    if args.load or not (args.snapshot or args.from_public):
        from wsj.db import make_store

        store = make_store(settings)
    try:
        if args.load:
            rows = json.loads(args.load.read_text(encoding="utf-8"))
            print(json.dumps({"loaded": save(store, rows)}))
            return 0
        now = datetime.now(UTC)
        if args.from_public:
            inputs = load_public_inputs(*public_credentials(), args.feed_days)
            if args.snapshot_out:
                write_snapshot(args.snapshot_out, inputs, now)
                args.snapshot = args.snapshot_out
            else:
                tmp = Path(".ideas_public_snapshot")
                write_snapshot(tmp, inputs, now)
                args.snapshot = tmp
            args.dry_run = True
        prices: list[dict[str, Any]] = []
        facts: list[dict[str, Any]] = []
        fundamentals: list[dict[str, Any]] = []
        valuations: list[dict[str, Any]] = []
        if args.snapshot:
            issues = json.loads((args.snapshot / "issues.json").read_text(encoding="utf-8"))
            indicators = json.loads((args.snapshot / "indicators.json").read_text(encoding="utf-8"))
            pp = args.snapshot / "prices.json"
            prices = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else []
            fp = args.snapshot / "facts.json"
            facts = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else []
            fu = args.snapshot / "fundamentals.json"
            fundamentals = json.loads(fu.read_text(encoding="utf-8")) if fu.exists() else []
            vp = args.snapshot / "valuations.json"
            valuations = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else []
            ex_path = args.snapshot / "existing.json"
            existing = json.loads(ex_path.read_text(encoding="utf-8")) if ex_path.exists() else []
            meta = args.snapshot / "meta.json"
            if meta.exists():  # 프롬프트를 만든 시각으로 고정 — 최근성 가중·후보 순서·근거 id 가 같아야 검증이 맞는다
                now = datetime.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))["now"])
        else:
            issues, indicators, maybe = load_store_inputs(store, args.days)
            if maybe is None:
                args.dry_run = True
            existing = maybe or []
            try:
                prices = store.select("public.v_price_context", ["*"], {})
            except Exception as exc:  # noqa: BLE001
                log.warning("v_price_context 없음 (0021 전?): %s", exc)
            try:
                facts = store.select("public.v_company_facts", ["*"], {})
            except Exception as exc:  # noqa: BLE001
                log.warning("v_company_facts 없음 (0022 전?): %s", exc)
            try:
                fundamentals = store.select("public.v_company_fundamentals", ["*"], {})
                valuations = store.select("public.v_valuations", ["*"], {})
            except Exception as exc:  # noqa: BLE001
                log.warning("v_company_fundamentals·v_valuations 없음 (0024 전?): %s", exc)
        graph = load_graph()
        events, feed_stats = gather_events(args, settings, store, graph, existing)
        if args.events_out:
            args.events_out.parent.mkdir(parents=True, exist_ok=True)
            args.events_out.write_text(json.dumps([e.public() for e in events], ensure_ascii=False, indent=1), encoding="utf-8")
        ctx, extras = build_context(graph, issues, indicators, prices, events, existing, now, facts, fundamentals, valuations)
        reg, signals, candidates, payload = prepare(issues, indicators, graph, now, args.days, existing, args.max_ideas, args.top, events, extras)
        if args.leads_out:
            args.leads_out.write_text(json.dumps(ctx["leads"], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        log.info("feed %s", json.dumps(feed_stats, ensure_ascii=False))
        log.info("signals %d, candidates %d, evidence %d", len(signals), len(candidates), len(payload["evidence"]))
        if args.emit_research:
            targets = research_targets(signals)
            args.emit_research.write_text(json.dumps(targets, ensure_ascii=False, indent=1), encoding="utf-8")
            log.info("research targets: %d", len(targets))
        if args.emit_prompt:
            args.emit_prompt.write_text(json.dumps({"system": system_prompt(now), "payload": payload}, ensure_ascii=False, indent=1), encoding="utf-8")
            # 예약작업이 읽기 쉽게: 규칙은 마크다운으로, 입력은 payload 만 따로
            args.emit_prompt.with_suffix(".system.md").write_text(system_prompt(now), encoding="utf-8")
            args.emit_prompt.with_suffix(".payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            print(json.dumps({"signals": len(signals), "candidates": len(candidates), "evidence": len(payload["evidence"]),
                              "chars": len(json.dumps(payload, ensure_ascii=False))}))
            return 0
        usage: dict[str, Any] = {}
        model = args.model
        if args.from_llm_json:
            raw = json.loads(args.from_llm_json.read_text(encoding="utf-8"))
            model = raw.get("model", model)
        else:
            from wsj.briefs.llm import LLM, resolve_model, sum_usage

            if not settings.anthropic_api_key:
                raise SystemExit("ANTHROPIC_API_KEY 없음")
            model = resolve_model(args.model)
            out, comps = LLM(settings.anthropic_api_key).complete_json(
                system_prompt(now), json.dumps(payload, ensure_ascii=False), model,
                "직전 응답을 유효한 JSON 하나로 다시 출력하라. 오류: {error}", max_tokens=12000, effort="high")
            raw, usage = out, sum_usage(comps)
        ex_map = {x["idea_key"]: x for x in existing}
        vals: list[dict[str, Any]] = []
        rows, rejects = validate(raw.get("ideas") or [], reg, graph, signals, ex_map, now, model, args.method, ctx, vals)
        skipped = [f"#{i} {x.get('title') or x.get('idea_key')}: {x['valuation_skipped']}" for i, x in enumerate(raw.get("ideas") or []) if x.get("valuation_skipped")]
        for x in skipped:
            log.info("valuation skipped: %s", x)
        from wsj.ecosystems.assess import apply_grades

        grades = apply_grades(ex_map, raw.get("grades") or [], reg, now)
        for r in rows:
            r["usage"] = usage or None
            if r["idea_key"] in grades and r.get("status") == "active":  # 고친 아이디어에도 채점을 같은 문구로 옮긴다
                done = {w.get("what"): w for w in grades[r["idea_key"]] if isinstance(w, dict) and w.get("status") != "pending"}
                r["watch"] = [done.get(w.get("what"), w) if isinstance(w, dict) else w for w in r.get("watch") or []]
        refresh = refresh_rows(ex_map, judged_keys(rows), grades, ctx, now)
        rows += star_rule_audit(ex_map, rows, refresh, now, model, args.method)
        for x in rejects:
            log.warning("rejected: %s", x)
        if args.out:
            args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            args.out.with_name(args.out.stem + ".valuations.json").write_text(json.dumps(vals, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        if args.emit_sql:
            for x in write_sql(rows, args.emit_sql):
                log.info("sql: %s", x)
            v = write_valuation_sql(vals, args.emit_sql)
            if v:
                log.info("sql: %s (가치평가 %d건)", v, len(vals))
            a = write_assess_sql(refresh, args.emit_sql)
            if a:
                log.info("sql: %s (판단 %d건)", a, len(refresh))
        n = 0
        if not args.dry_run and store is not None:
            from wsj.runlog import logged_run

            with logged_run(store, "ideas", {"days": args.days, "model": model}) as run:
                n = save(store, rows)
                n_assess = save_assessments(store, refresh)
                n_val = save_valuations(store, vals)
                run["rows"] = n + n_assess + n_val
                run["notes"] = json.dumps({"signals": len(signals), "company_signals": sum(1 for x in signals if x["kind"] == "company"),
                                           "events": len(events), "candidates": len(candidates), "ideas": len(rows), "rejected": len(rejects),
                                           "cost_usd": usage.get("cost_usd")})
        print(json.dumps({"signals": len(signals), "company_signals": sum(1 for x in signals if x["kind"] == "company"), "events": len(events),
                          "candidates": len(candidates), "ideas": len(rows), "valuations": len(vals), "rejected": len(rejects), "saved": n,
                          "cost_usd": usage.get("cost_usd")}))
        return 0
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
