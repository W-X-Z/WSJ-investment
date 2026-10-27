"""투자 아이디어 엔진 — 최근 변화에서 출발해 그래프로 추론하고, AI 가 직관적인 아이디어와 근거 사슬을 쓴다. ADR-0016.

    python -m wsj.ecosystems.ideas                         # 매일: 신호 → 후보 사슬 → LLM → 검증 → ideas.investment_ideas
    python -m wsj.ecosystems.ideas --dry-run --out x.json  # DB 에 쓰지 않음
    python -m wsj.ecosystems.ideas --snapshot DIR --emit-prompt p.json      # 오프라인: DIR/issues.json·indicators.json 으로 LLM 입력만
    python -m wsj.ecosystems.ideas --snapshot DIR --from-llm-json raw.json --out ideas.json  # 외부에서 쓴 LLM 출력 검증
    python -m wsj.ecosystems.ideas --load ideas.json       # 검증된 아이디어를 DB 에 적재

흐름
1. 신호(signal): 최근 이슈(★2 이상)와 눈에 띄는 지표(대만 공급사 월매출 YoY, 미국 PPI). 이슈 문장은 지금 그래프의 어휘로
   다시 태깅한다 — 그래프가 커지면 예전 이슈도 새 노드에 닿는다.
2. 후보 사슬(candidate): 신호 노드에서 impact.influence_paths 로 기업까지의 경로를 계산하고 점수를 매긴다.
   점수 = Σ(신호 ★ 가중 × 경로 신뢰도) × 규모 가중(소형 우대) × 공급 집중(공급사가 적을수록 큼).
   동종 공급사·기술 전환 관계(displaces·substitutes_for·develops·holds_ip)를 곁들인다.
3. 근거 목록(evidence): 신호의 출처(S…)와 경로 관계의 출처(G…)에 id 를 붙인다. AI 는 이 id 만 인용할 수 있다.
4. LLM: 직관적인 제목 + 두 문장 + ★1~3 + 기업 + 근거 사슬 + 리스크 + 다음 확인 신호. 기존 아이디어는 같은 key 로 갱신·약화·종료.
5. 검증: 없는 id·기업, 근거 없는 단계, 최근 신호 근거가 없는 새 아이디어는 버린다. 사람이 읽는 화면은 이 결과만 본다.
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
SUPPLY_RELS = ("offered_by", "develops", "holds_ip")
TRANSITION_RELS = ("displaces", "substitutes_for", "develops", "holds_ip", "defers", "adopts")
TIER_KO = {
    "independent_measurement": "독립 실측", "standard_body": "표준 문서", "official_issuer": "당사자 공시", "customer_statement": "고객 진술",
    "third_party_report": "보도·리서치", "vendor_claim": "공급사 주장", "technical_inference": "기술 추론", "hypothesis": "가설",
}
SOURCE_TIER = {"sec": "official_issuer", "newsroom": "official_issuer", "policy": "standard_body", "data": "official_issuer",
               "analyst": "third_party_report", "trade": "third_party_report", "news": "third_party_report", "research": "independent_measurement"}


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
        e = reg.add("S", m.get("source_url") or "", title, publisher="TWSE·TPEx 공시" if cat == "tw_revenue" else "US BLS", date=str(m.get("as_of"))[:10],
                    tier="official_issuer")
        if not e:
            continue
        out.append({"sid": f"M{sum(1 for s in out if s['kind'] == 'indicator') + 1}", "kind": "indicator", "ref": m["indicator_id"], "title": title,
                    "stars": 3 if (cat == "tw_revenue" and yoy >= 80) or (cat == "ppi" and yoy >= 30) else 2,
                    "date": str(m.get("as_of"))[:10], "what": title, "why": None, "nodes": [n for n in (m.get("nodes") or []) if n in nodes],
                    "companies": cos, "evidence": [e], "ecosystem": m.get("ecosystem")})
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


def build_candidates(graph: dict[str, Any], signals: list[dict[str, Any]], reg: Registry, top: int = 24, max_depth: int = 5) -> list[dict[str, Any]]:
    from wsj.ecosystems.impact import influence_paths

    onto = load_ontology()
    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = {e["id"]: e for e in graph["edges"]}
    sup = _suppliers(graph)
    cache: dict[str, list[dict[str, Any]]] = {}
    acc: dict[str, dict[str, Any]] = {}

    def slot(cid: str) -> dict[str, Any]:
        return acc.setdefault(cid, {"raw": 0.0, "signals": set(), "paths": [], "direct": set()})

    for s in signals:
        w = STAR_WEIGHT.get(s["stars"], 1.0)
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
                c["raw"] += w * spec * p["confidence"] * (1 if p["sign"] >= 0 else -1)
                c["signals"].add(s["sid"])
                c["paths"].append({**p, "_sid": s["sid"]})
        for cid in s["companies"]:
            c = slot(cid)
            c["raw"] += w * 0.7
            c["signals"].add(s["sid"])
            c["direct"].add(s["sid"])

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
        n_sup = len(sup.get(supply_node, [])) if supply_node else 0
        score = abs(c["raw"]) * SIZE_WEIGHT.get(size, 0.8) * _concentration(n_sup) * (1 + 0.15 * (len(c["signals"]) - 1))
        out.append({"company_id": cid, "score": round(score, 3), "sign": 1 if c["raw"] >= 0 else -1, "_paths": paths, "_supply": supply_node,
                    "_n_sup": n_sup, "_signals": sorted(c["signals"]), "_direct": sorted(c["direct"])})
    out.sort(key=lambda x: -x["score"])
    # 다양성: 같은 부품·공정의 공급사는 3곳까지, 생태계마다 최소 몫을 남긴다 (한 테마가 후보를 독식하지 않게)
    per_eco = max(3, top // 5)
    picked: list[dict[str, Any]] = []
    by_supply: dict[str, int] = defaultdict(int)
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
        })
    return result


# ---------------------------------------------------------------- LLM
LLM_SYSTEM = """너는 AI 공급망(HBM·첨단 패키징 / 800G·1.6T 광통신 / AI 데이터센터 800VDC 전력·냉각) 전문 투자 리서치 애널리스트다.
목표: 지금 투자 기회가 큰 상장 기업을 찾아, 바쁜 투자자가 한눈에 이해하는 '투자 아이디어'로 쓴다. 사람은 데이터를 보지 않고 아이디어와 근거만 본다.

입력
- signals: 최근 변화 (I=이슈, M=가격·실적 지표). 각 신호에 근거 id.
- candidates: 그래프가 계산한 '변화 → 병목·기술 → 공급 → 기업' 경로 후보. score 가 높을수록 신호가 강하고·소형이고·공급이 집중된 곳.
  chains.steps 는 관계 사슬(근거 id 'ev'), peers 는 같은 부품·공정의 다른 공급사, transitions 는 대체·개발·IP 관계(성숙도 stage).
- evidence: 인용 가능한 근거 목록 (S=최근 신호 출처, G=그래프 관계 출처). 이 목록의 id 만 인용한다.
- existing: 이미 피드에 있는 아이디어. 같은 논리면 같은 idea_key 로 갱신한다.

아이디어를 만드는 법
- 한 아이디어 = 하나의 논리: "무엇이 바뀌었나 → 그래서 어떤 병목/전환이 조여지나 → 공급이 왜 소수에게 몰리나 → 그래서 이 기업".
  유형: bottleneck(병목 수혜) | transition(기술 전환의 승자·새 병목) | confirmation(동종 실적·가격이 확인해 준 노출) | risk(대체·수요 이탈로 피해).
- 제목: 투자자가 바로 이해하는 한 문장 + 기업명. 업계 은어 대신 결과를 말한다. 40자 안팎. 예) "HBM이 높게 쌓일수록 번인 검사가 길어진다 — 유니테스트"
- thesis: 2문장. 첫 문장은 변화, 둘째 문장은 왜 이 기업인가.
- primary 는 상장 소형·중형 공급사를 우선한다. 대형·초대형은 논리가 압도적일 때만 primary, 보통은 수요처·경쟁 맥락으로 companies 에 넣는다.
- chain: 3~5 단계. 각 단계 claim 은 한 문장, evidence 에 근거 id 1개 이상. 기술 추론(technical_inference) 근거만 있는 단계는 claim 끝에 "(추론)".
  첫 단계는 반드시 최근 신호(S…) 근거.
- stars: 3 = 최근 사실이 병목·전환을 직접 확인하고 + 공급이 소수에 집중되고 + 기업 노출이 공식 근거로 확인. 2 = 셋 중 둘. 1 = 하나 또는 추론 의존.
- risks: 1~3개. 반대 근거·대체 경로·이미 알려진 정도(대형 고객 집중, 중국 경쟁 등). 근거 id 가 있으면 붙이고 없으면 빈 배열.
- watch: 2~3개. 다음에 무엇이 확인되면 강화/약화되는지 구체적으로 (예: "다음 달 TPEx 월매출 YoY", "SK hynix 16단 양산 공식 발표").
- 숫자·날짜는 입력에 있는 것만 쓴다. 주가·목표가·매수/매도 권유·시점 예측 금지.
- 서로 다른 아이디어가 같은 기업·같은 논리를 반복하지 않게 묶는다. 근거가 빈약하면 만들지 않는다 — 개수보다 질.

existing 처리
- 같은 논리가 새 근거로 강해지면 action=update (idea_key 그대로, what_changed 에 새 근거 한 줄).
- 근거가 약해지면 action=weaken, 반증·소멸되면 action=close (reason). 변화 없으면 action=keep (idea_key 만).

출력: JSON 하나만.
{"ideas": [{"action": "new|update|weaken|keep|close", "idea_key": "기존 key 또는 null", "type": "bottleneck|transition|confirmation|risk",
  "title": "...", "thesis": "...", "stars": 1, "stars_reason": "한 줄",
  "companies": [{"id": "company:...", "role": "primary|peer|customer|competitor|displaced", "why": "한 줄"}],
  "chain": [{"claim": "...", "evidence": ["S1", "G3"]}],
  "risks": [{"claim": "...", "evidence": []}], "watch": ["..."], "what_changed": "update 일 때만", "reason": "weaken/close 일 때"}]}"""


def build_payload(signals: list[dict[str, Any]], candidates: list[dict[str, Any]], reg: Registry, existing: list[dict[str, Any]],
                  max_ideas: int) -> dict[str, Any]:
    used = set()
    for s in signals:
        used.update(s["evidence"])
    for c in candidates:
        for ch in c["chains"]:
            used.update(st["ev"] for st in ch["steps"] if st["ev"])
        used.update(t["ev"] for t in c["transitions"] if t["ev"])
    evidence = [{"id": e.eid, "title": e.title, "publisher": e.publisher, "date": e.date, "tier": e.tier,
                 "excerpt": (e.excerpt or "")[:220] or None} for e in reg.items.values() if e.eid in used]
    return {
        "max_ideas": max_ideas,
        "signals": [{k: s[k] for k in ("sid", "kind", "title", "stars", "date", "what", "why", "evidence")} | {"nodes": s["nodes"], "companies": s["companies"]}
                    for s in signals],
        "candidates": candidates,
        "evidence": evidence,
        "existing": [{k: x.get(k) for k in ("idea_key", "type", "title", "thesis", "stars", "primary_company", "updated_at")} for x in existing],
    }


# ---------------------------------------------------------------- validation → rows
def make_key(kind: str, primary: str, title: str) -> str:
    slug = re.sub(r"\W+", "", title)[:24]
    return hashlib.sha1(f"{kind}|{primary}|{slug}".encode()).hexdigest()[:12]


def validate(raw: list[dict[str, Any]], reg: Registry, graph: dict[str, Any], signals: list[dict[str, Any]],
             existing: dict[str, dict[str, Any]], now: datetime, model: str, method: str) -> tuple[list[dict[str, Any]], list[str]]:
    nodes = {n["id"]: n for n in graph["nodes"]}
    sig_by_ev = {e: s for s in signals for e in s["evidence"]}
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
        risks = [{"claim": r["claim"].strip(), "evidence": [reg.items[e].public() for e in r.get("evidence") or [] if e in reg.items]}
                 for r in it.get("risks") or [] if isinstance(r, dict) and r.get("claim")]
        sig_refs = sorted({sig_by_ev[e["id"]]["ref"] for st in chain for e in st["evidence"] if e["id"] in sig_by_ev})
        last_sig = max((sig_by_ev[e["id"]]["date"] for st in chain for e in st["evidence"] if e["id"] in sig_by_ev), default=None)
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
def prepare(issues: list[dict[str, Any]], indicators: list[dict[str, Any]], graph: dict[str, Any], now: datetime, days: int,
            existing: list[dict[str, Any]], max_ideas: int, top: int) -> tuple[Registry, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    reg = Registry()
    signals = load_signals(issues, indicators, graph, reg, now, days)
    candidates = build_candidates(graph, signals, reg, top=top)
    payload = build_payload(signals, candidates, reg, existing, max_ideas)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-ideas", type=int, default=8)
    ap.add_argument("--top", type=int, default=30, help="LLM 에 넘길 후보 기업 수")
    ap.add_argument("--snapshot", type=Path, help="issues.json · indicators.json · existing.json(선택) 이 있는 폴더 (DB 대신)")
    ap.add_argument("--emit-prompt", type=Path, help="LLM 입력(system·payload)을 파일로 쓰고 끝낸다")
    ap.add_argument("--from-llm-json", type=Path, help="LLM 호출 대신 이 파일의 {'ideas': [...]} 를 검증")
    ap.add_argument("--method", default="llm")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--load", type=Path, help="검증된 아이디어 행(JSON 배열)을 DB 에 적재")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    from wsj.config import load_settings

    settings = load_settings()
    store = None
    if args.load or not args.snapshot:
        from wsj.db import make_store

        store = make_store(settings)
    try:
        if args.load:
            rows = json.loads(args.load.read_text(encoding="utf-8"))
            print(json.dumps({"loaded": save(store, rows)}))
            return 0
        now = datetime.now(UTC)
        if args.snapshot:
            issues = json.loads((args.snapshot / "issues.json").read_text(encoding="utf-8"))
            indicators = json.loads((args.snapshot / "indicators.json").read_text(encoding="utf-8"))
            ex_path = args.snapshot / "existing.json"
            existing = json.loads(ex_path.read_text(encoding="utf-8")) if ex_path.exists() else []
        else:
            issues, indicators, maybe = load_store_inputs(store, args.days)
            if maybe is None:
                args.dry_run = True
            existing = maybe or []
        graph = load_graph()
        reg, signals, candidates, payload = prepare(issues, indicators, graph, now, args.days, existing, args.max_ideas, args.top)
        log.info("signals %d, candidates %d, evidence %d", len(signals), len(candidates), len(payload["evidence"]))
        if args.emit_prompt:
            args.emit_prompt.write_text(json.dumps({"system": LLM_SYSTEM, "payload": payload}, ensure_ascii=False, indent=1), encoding="utf-8")
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
                LLM_SYSTEM, json.dumps(payload, ensure_ascii=False), model,
                "직전 응답을 유효한 JSON 하나로 다시 출력하라. 오류: {error}", max_tokens=12000, effort="high")
            raw, usage = out, sum_usage(comps)
        rows, rejects = validate(raw.get("ideas") or [], reg, graph, signals, {x["idea_key"]: x for x in existing}, now, model, args.method)
        for r in rows:
            r["usage"] = usage or None
        for x in rejects:
            log.warning("rejected: %s", x)
        if args.out:
            args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        n = 0
        if not args.dry_run and store is not None:
            from wsj.runlog import logged_run

            with logged_run(store, "ideas", {"days": args.days, "model": model}) as run:
                n = save(store, rows)
                run["rows"] = n
                run["notes"] = json.dumps({"signals": len(signals), "candidates": len(candidates), "ideas": len(rows), "rejected": len(rejects),
                                           "cost_usd": usage.get("cost_usd")})
        print(json.dumps({"signals": len(signals), "candidates": len(candidates), "ideas": len(rows), "rejected": len(rejects), "saved": n,
                          "cost_usd": usage.get("cost_usd")}))
        return 0
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
