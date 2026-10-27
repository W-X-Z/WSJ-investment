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
        return {"id": self.eid, "url": self.url, "title": self.title, "publisher": self.publisher, "date": self.date,
                "tier": self.tier, "tier_ko": TIER_KO.get(self.tier or "", None)}


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
            chains.append({"signal": p["_sid"], "confidence": p["confidence"], "steps": steps})
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
  chains.steps 는 관계 사슬(근거 id 'ev'), peers 는 같은 부품·공정의 다른 공급사, transitions 는 대체·개발·IP 관계(성숙도 stage),
  offers 는 그 기업이 직접 공급·개발하는 부품·기술(그래프 근거). 기업 소식(E)으로 들어온 후보는 offers 로 '왜 AI 공급망인가'를 잇는다.
- evidence: 인용 가능한 근거 목록. S=최근 신호 출처(age_d = 며칠 전), G=그래프 관계 출처(배경 구조, 날짜가 오래됐을 수 있음). 이 목록의 id 만 인용한다.
- existing: 이미 피드에 있는 아이디어 (last_signal_at = 마지막 최신 근거 날짜). 같은 논리면 같은 idea_key 로 갱신한다.

최신성 규칙 (가장 중요)
- 아이디어는 최근 {fresh}일 안의 사실(S 근거, age_d ≤ {fresh})에서 출발한다. 그런 근거가 없으면 새 아이디어를 만들지 않는다.
- chain 첫 단계 claim 은 최근 사실 그 자체다 — 무엇이 언제 일어났나 (예: "10/21 유니테스트가 SK hynix와 162억원 검사장비 공급계약을 공시했다").
- G 근거는 '왜 그 변화가 이 기업에 닿는가'의 구조 설명에만 쓴다. 현재 상황(수요·부족·점유율)을 G 근거만으로 주장하지 않는다.
- E 신호(기업 자체의 공시·월매출·실적)는 노출을 직접 확인해 준다. 업계 이슈(I)와 기업 소식(E)이 같은 방향이면 강한 아이디어다.
- 시세 기사(주가 등락)는 근거로 쓰지 않는다.

아이디어를 만드는 법
- 한 아이디어 = 하나의 논리: "무엇이 바뀌었나(최근 사실) → 그래서 어떤 병목/전환이 조여지나 → 공급이 왜 소수에게 몰리나 → 그래서 이 기업".
  유형: bottleneck(병목 수혜) | transition(기술 전환의 승자·새 병목) | confirmation(실적·수주·가격이 확인해 준 노출) | risk(대체·수요 이탈로 피해).
- 제목: 투자자가 바로 이해하는 한 문장 + 기업명. 업계 은어 대신 결과를 말한다. 40자 안팎. 예) "HBM이 높게 쌓일수록 번인 검사가 길어진다 — 유니테스트"
- thesis: 2문장. 첫 문장은 최근 변화(날짜 포함), 둘째 문장은 왜 이 기업인가.
- primary 는 상장 소형·중형 공급사를 우선한다. 대형·초대형은 논리가 압도적일 때만 primary, 보통은 수요처·경쟁 맥락으로 companies 에 넣는다.
- chain: 3~5 단계. 각 단계 claim 은 한 문장, evidence 에 근거 id 1개 이상. 기술 추론(technical_inference) 근거만 있는 단계는 claim 끝에 "(추론)".
- stars: 3 = 최근 사실이 병목·전환을 직접 확인하고 + 공급이 소수에 집중되고 + 기업 노출이 최근 공식 근거(공시·실적)로 확인. 2 = 셋 중 둘. 1 = 하나 또는 추론 의존.
- risks: 1~3개. 반대 근거·대체 경로·이미 알려진 정도(대형 고객 집중, 중국 경쟁 등). 근거 id 가 있으면 붙이고 없으면 빈 배열.
- watch: 2~3개. 다음에 무엇이 확인되면 강화/약화되는지 구체적으로 (예: "11월 10일 전후 TPEx 10월 월매출 YoY", "SK hynix 16단 양산 공식 발표").
- 숫자·날짜는 입력에 있는 것만 쓴다. 주가·목표가·매수/매도 권유·시점 예측 금지.
- 서로 다른 아이디어가 같은 기업·같은 논리를 반복하지 않게 묶는다. 근거가 빈약하면 만들지 않는다 — 개수보다 질.

existing 처리
- 같은 논리에 최근 {fresh}일 안의 새 근거가 있으면 action=update (idea_key 그대로, chain 을 새 근거로 다시 쓰고, what_changed 에 "날짜 + 새 사실" 한 줄).
- 새 근거가 반대 방향이면 action=weaken, 반증·소멸되면 action=close (reason). 새 근거가 없으면 action=keep (idea_key 만).
- last_signal_at 이 {stale}일 넘게 지났고 이번 입력에도 새 근거가 없으면 action=weaken (reason: 최신 근거 없음).

출력: JSON 하나만.
{{"ideas": [{{"action": "new|update|weaken|keep|close", "idea_key": "기존 key 또는 null", "type": "bottleneck|transition|confirmation|risk",
  "title": "...", "thesis": "...", "stars": 1, "stars_reason": "한 줄",
  "companies": [{{"id": "company:...", "role": "primary|peer|customer|competitor|displaced", "why": "한 줄"}}],
  "chain": [{{"claim": "...", "evidence": ["S1", "G3"]}}],
  "risks": [{{"claim": "...", "evidence": []}}], "watch": ["..."], "what_changed": "update 일 때만", "reason": "weaken/close 일 때"}}]}}"""


def system_prompt(now: datetime) -> str:
    return LLM_SYSTEM.format(today=now.date().isoformat(), fresh=FRESH_DAYS, stale=21)


def build_payload(signals: list[dict[str, Any]], candidates: list[dict[str, Any]], reg: Registry, existing: list[dict[str, Any]],
                  max_ideas: int, now: datetime | None = None) -> dict[str, Any]:
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
    return {
        "today": now.date().isoformat(),
        "max_ideas": max_ideas,
        "signals": sigs,
        "candidates": candidates,
        "evidence": evidence,
        "existing": [{k: x.get(k) for k in ("idea_key", "type", "title", "thesis", "stars", "primary_company", "last_signal_at", "updated_at")}
                     | {"companies": [c.get("id") for c in x.get("companies") or []]} for x in existing],
    }


# ---------------------------------------------------------------- validation → rows
def make_key(kind: str, primary: str, title: str) -> str:
    slug = re.sub(r"\W+", "", title)[:24]
    return hashlib.sha1(f"{kind}|{primary}|{slug}".encode()).hexdigest()[:12]


def validate(raw: list[dict[str, Any]], reg: Registry, graph: dict[str, Any], signals: list[dict[str, Any]],
             existing: dict[str, dict[str, Any]], now: datetime, model: str, method: str) -> tuple[list[dict[str, Any]], list[str]]:
    nodes = {n["id"]: n for n in graph["nodes"]}
    sig_by_ev = {e: s for s in signals for e in s["evidence"]}
    fresh_cut = (now - timedelta(days=FRESH_DAYS)).date().isoformat()
    rows, rejects = [], []
    for i, it in enumerate(raw):
        action = it.get("action") or "new"
        key = it.get("idea_key") if it.get("idea_key") in existing else None
        if action in ("keep", "close", "weaken") and not key:
            rejects.append(f"#{i} {action} without known idea_key")
            continue
        if action == "keep":
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
                comps.append({"id": cid, "name": re.split(r"\s+\(", n["label"])[0], "ticker": lst.get("ticker"), "exchange": lst.get("exchange"),
                              "size_band": n.get("size_band"), "role": c.get("role") or "peer", "why": (c.get("why") or "")[:200]})
        primary = next((c for c in comps if c["role"] == "primary"), comps[0] if comps else None)
        if not primary:
            rejects.append(f"#{i} no valid company: {title[:40]}")
            continue
        chain = []
        for st in it.get("chain") or []:
            evs = [reg.items[e].public() for e in st.get("evidence") or [] if e in reg.items]
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
        risks = [{"claim": r["claim"].strip(), "evidence": [reg.items[e].public() for e in r.get("evidence") or [] if e in reg.items]}
                 for r in it.get("risks") or [] if isinstance(r, dict) and r.get("claim")]
        sig_refs = sorted({sig_by_ev[e["id"]]["ref"] for st in chain for e in st["evidence"] if e["id"] in sig_by_ev})
        # 마지막 최신 근거 날짜 = 인용한 S 근거 중 가장 최근 (신호 묶음 날짜가 아니라 근거 자체의 날짜)
        last_sig = s_dates[-1] if s_dates else (existing.get(key) or {}).get("last_signal_at") if key else None
        theme = sorted({n for s in signals if s["ref"] in sig_refs for n in s["nodes"]})
        pn = nodes[primary["id"]]
        ecos = sorted({x for x in [pn.get("ecosystem"), *(pn.get("also_in") or [])] if x})
        prev = existing.get(key) if key else None
        trend = "new" if not prev else ("weakened" if action == "weaken" or stars < (prev.get("stars") or 0)
                                        else "strengthened" if stars > (prev.get("stars") or 0) or action == "update" else "unchanged")
        rows.append({
            "idea_key": key or make_key(kind, primary["id"], title), "status": "active", "trend": trend, "type": kind,
            "title": title[:120], "thesis": thesis[:600], "stars": stars, "stars_reason": (it.get("stars_reason") or "")[:300],
            "primary_company": primary["id"], "companies": comps, "chain": chain, "risks": risks,
            "watch": [str(w)[:200] for w in (it.get("watch") or [])][:4], "what_changed": (it.get("what_changed") or None),
            "nodes": theme[:12], "ecosystems": ecos, "signal_refs": sig_refs,
            "evidence_count": len({e["id"] for st in chain for e in st["evidence"]}),
            "last_signal_at": last_sig, "updated_at": now.isoformat(), "model": model, "method": method,
        })
    return rows, rejects


# ---------------------------------------------------------------- orchestration
def focus_companies(existing: list[dict[str, Any]]) -> set[str]:
    return {c.get("id") for x in existing for c in (x.get("companies") or []) if c.get("id")} | {x.get("primary_company") for x in existing if x.get("primary_company")}


def prepare(issues: list[dict[str, Any]], indicators: list[dict[str, Any]], graph: dict[str, Any], now: datetime, days: int,
            existing: list[dict[str, Any]], max_ideas: int, top: int, events: list[Any] | None = None
            ) -> tuple[Registry, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    reg = Registry()
    signals = load_signals(issues, indicators, graph, reg, now, days)
    if events:
        signals += company_signals(events, graph, reg, now, focus_companies(existing))
    candidates = build_candidates(graph, signals, reg, top=top, now=now)
    payload = build_payload(signals, candidates, reg, existing, max_ideas, now)
    return reg, signals, candidates, payload


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
PUBLIC_VIEWS = {"issues": "v_supply_chain_issues", "indicators": "v_indicators", "existing": "v_investment_ideas", "events": "v_company_events"}


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
            while True:
                page = http.get_json(f"{url.rstrip('/')}/rest/v1/{view}", params={**params, "limit": "1000", "offset": str(len(rows))},
                                     headers=headers)
                rows += page
                if len(page) < 1000:
                    break
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
        (d / f"{name}.json").write_text(json.dumps(inputs[name], ensure_ascii=False), encoding="utf-8")
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
            import os

            url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or settings.supabase_url
            key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_KEY")
            if not (url and key):
                raise SystemExit("SUPABASE_URL · SUPABASE_PUBLISHABLE_KEY 가 필요하다 (공개 읽기 키)")
            inputs = load_public_inputs(url, key, args.feed_days)
            if args.snapshot_out:
                write_snapshot(args.snapshot_out, inputs, now)
                args.snapshot = args.snapshot_out
            else:
                tmp = Path(".ideas_public_snapshot")
                write_snapshot(tmp, inputs, now)
                args.snapshot = tmp
            args.dry_run = True
        if args.snapshot:
            issues = json.loads((args.snapshot / "issues.json").read_text(encoding="utf-8"))
            indicators = json.loads((args.snapshot / "indicators.json").read_text(encoding="utf-8"))
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
        graph = load_graph()
        events, feed_stats = gather_events(args, settings, store, graph, existing)
        if args.events_out:
            args.events_out.parent.mkdir(parents=True, exist_ok=True)
            args.events_out.write_text(json.dumps([e.public() for e in events], ensure_ascii=False, indent=1), encoding="utf-8")
        reg, signals, candidates, payload = prepare(issues, indicators, graph, now, args.days, existing, args.max_ideas, args.top, events)
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
        rows, rejects = validate(raw.get("ideas") or [], reg, graph, signals, {x["idea_key"]: x for x in existing}, now, model, args.method)
        for r in rows:
            r["usage"] = usage or None
        for x in rejects:
            log.warning("rejected: %s", x)
        if args.out:
            args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        if args.emit_sql:
            for x in write_sql(rows, args.emit_sql):
                log.info("sql: %s", x)
        n = 0
        if not args.dry_run and store is not None:
            from wsj.runlog import logged_run

            with logged_run(store, "ideas", {"days": args.days, "model": model}) as run:
                n = save(store, rows)
                run["rows"] = n
                run["notes"] = json.dumps({"signals": len(signals), "company_signals": sum(1 for x in signals if x["kind"] == "company"),
                                           "events": len(events), "candidates": len(candidates), "ideas": len(rows), "rejected": len(rejects),
                                           "cost_usd": usage.get("cost_usd")})
        print(json.dumps({"signals": len(signals), "company_signals": sum(1 for x in signals if x["kind"] == "company"), "events": len(events),
                          "candidates": len(candidates), "ideas": len(rows), "rejected": len(rejects), "saved": n,
                          "cost_usd": usage.get("cost_usd")}))
        return 0
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
