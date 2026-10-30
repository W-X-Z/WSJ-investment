"""꺼내 쓰기 (ADR-0028 3단계) — 단서 하나를 해석하기 전에, 그 기업·노드에 대해 이미 아는 것을 한 장으로 모은다.

    python -m wsj.ecosystems.recall --company company:ls_materials
    python -m wsj.ecosystems.recall --node component:supercapacitor --node component:fuel_cell
    python -m wsj.ecosystems.recall --name "티엘비" --text "SOCAMM2 기판 수주"     # 그래프 밖이면 이름·어휘로 찾는다

모으는 것 (해석 작업이 읽는다 — 화면에는 나오지 않는다):
  1. 그래프 자리: 이 기업이 파는 것 → 그것을 누가 왜 쓰나(위로 두 단계) → 같이 파는 회사, 노드라면 아래로 두 단계의 공급사.
  2. 관련 패턴 카드 (research/playbook/patterns — '관련 노드' 가 겹치는 것).
  3. 지난 사례: 같은 기업·노드를 지난 투자 아이디어 (v_opportunities; 내린 것은 해석 작업이 execute_sql 로 따로 본다).
  4. 지난 단서: 같은 기업·노드의 최근 90일 단서 (v_clues) — 횟수가 아니라 이야기의 연결을 보라고.
  5. 가격: 그래프 상장사면 v_price_context 한 줄.
  6. 논문·특허: 이 노드의 연도별 특허·기업 논문 수, 최근 많이 낸 기관과 새로 나타난 기관, 최근 대표 문서 (0033 + techdocs 백필 뒤).
읽기는 공개 뷰(publishable 키)와 저장소 파일뿐이다. 점수는 없다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from wsj.ecosystems.ontology import GRAPH_PATH, load_graph

PATTERNS_DIR = GRAPH_PATH.parents[1] / "playbook" / "patterns"
UP = {"requires", "implements", "mitigated_by"}          # X —(UP)→ Y : X 가 Y 를 쓴다 (Y 의 수요자 = X)
SUPPLY = {"offered_by"}                                    # Y —offered_by→ C
DEVELOPS = {"develops", "holds_ip"}                        # C —develops→ Y
REL_KO = {"requires": "필요로 한다", "implements": "구현한다", "mitigated_by": "로 완화된다", "offered_by": "공급사", "develops": "개발 중",
          "holds_ip": "특허 보유", "creates_bottleneck": "병목을 만든다", "drives_requirement": "요구를 만든다", "displaces": "수요를 잠식",
          "substitutes_for": "대체 가능", "competes_with": "경쟁", "supplied_to": "납품", "qualifying_with": "인증 진행", "adopts": "채택",
          "raises_content": "대당 함량을 늘린다"}


class Graph:
    def __init__(self, graph: dict[str, Any]):
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.out: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.inc: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in graph["edges"]:
            self.out[e["from"]].append(e)
            self.inc[e["to"]].append(e)

    def label(self, nid: str) -> str:
        return (self.nodes.get(nid) or {}).get("label", nid)

    def offers(self, cid: str) -> list[str]:
        """기업이 파는·개발하는 것."""
        got = [e["from"] for e in self.inc.get(cid, []) if e["relation"] in SUPPLY]
        got += [e["to"] for e in self.out.get(cid, []) if e["relation"] in DEVELOPS]
        return list(dict.fromkeys(got))

    def demanders(self, nid: str, depth: int = 2) -> list[tuple[str, str, str]]:
        """nid 를 쓰는 쪽으로 위로 — (수요자, 관계, 피수요자)."""
        out, frontier, seen = [], [nid], {nid}
        for _ in range(depth):
            nxt = []
            for y in frontier:
                for e in self.inc.get(y, []):
                    if e["relation"] in UP | {"creates_bottleneck", "drives_requirement", "raises_content"} and e["from"] not in seen:
                        out.append((e["from"], e["relation"], y))
                        seen.add(e["from"])
                        nxt.append(e["from"])
            frontier = nxt
        return out

    def suppliers(self, nid: str) -> list[str]:
        got = [e["to"] for e in self.out.get(nid, []) if e["relation"] in SUPPLY]
        got += [e["from"] for e in self.inc.get(nid, []) if e["relation"] in DEVELOPS]
        return [c for c in dict.fromkeys(got) if (self.nodes.get(c) or {}).get("kind") == "company"]

    def downstream_suppliers(self, nid: str, depth: int = 2) -> list[tuple[list[str], str]]:
        """노드에서 아래로(쓰는 것 쪽으로) depth 단계 → 그 단계의 공급사. (경로, 기업)."""
        out, frontier = [], [[nid]]
        for _ in range(depth + 1):
            nxt = []
            for path in frontier:
                for c in self.suppliers(path[-1]):
                    out.append((path, c))
                for e in self.out.get(path[-1], []):
                    if e["relation"] in UP | {"raises_content"} and e["to"] not in path:
                        nxt.append(path + [e["to"]])
            frontier = nxt
        seen, uniq = set(), []
        for p, c in out:
            if c not in seen:
                seen.add(c)
                uniq.append((p, c))
        return uniq

    def listed_kr_us(self, cid: str) -> bool:
        ex = ((self.nodes.get(cid) or {}).get("listing") or {}).get("exchange")
        return ex in {"KRX", "KOSDAQ", "NYSE", "Nasdaq", "NYSE American"}


def load_patterns(d: Path = PATTERNS_DIR) -> list[dict[str, Any]]:
    out = []
    for f in sorted(d.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), f.stem)
        nodes_line = next((ln for ln in text.splitlines() if ln.startswith("- 관련 노드")), "")
        out.append({"file": f.name, "title": title, "nodes": set(re.findall(r"[a-z_]+:[a-z0-9_]+", nodes_line)), "text": text})
    return out


def find_companies(g: Graph, name: str) -> list[str]:
    """이름·티커·현지어 이름·별칭으로 그래프 기업을 찾는다."""
    from wsj.ecosystems.company_feed import native_names

    n = name.strip().lower()
    native = {k: v.lower() for k, v in native_names().items()}
    try:
        aliases = json.loads((GRAPH_PATH.parent / "node_aliases.json").read_text(encoding="utf-8"))["aliases"]
    except (OSError, KeyError, ValueError):
        aliases = {}
    hits = []
    for nid, node in g.nodes.items():
        if node.get("kind") != "company":
            continue
        lst = node.get("listing") or {}
        names = {str(lst.get("ticker") or "").lower(), native.get(nid, "")} | {a.lower() for a in aliases.get(nid, [])}
        if n in names or n in node.get("label", "").lower():
            hits.append(nid)
    return hits


def neighborhood(g: Graph, companies: list[str], nodes: list[str]) -> dict[str, Any]:
    lines, touched = [], set(nodes)
    for cid in companies:
        sells = g.offers(cid)
        touched |= set(sells)
        lines.append(f"## {g.label(cid)} ({cid})")
        if not sells:
            lines.append("- 그래프에 이 기업이 파는 것이 없다 → 해석에서 찾은 제품을 `offered_by` 간선으로 더할 것")
        for y in sells:
            lines.append(f"- 판다: {g.label(y)} ({y})")
            for frm, rel, to in g.demanders(y):
                touched.add(frm)
                lines.append(f"  - {g.label(frm)} —{REL_KO.get(rel, rel)}→ {g.label(to)}")
            peers = [c for c in g.suppliers(y) if c != cid]
            if peers:
                lines.append("  - 같이 파는 회사: " + ", ".join(g.label(c) for c in peers[:12]))
    for nid in nodes:
        lines.append(f"## {g.label(nid)} ({nid})")
        for frm, rel, to in g.demanders(nid):
            touched.add(frm)
            lines.append(f"- 위: {g.label(frm)} —{REL_KO.get(rel, rel)}→ {g.label(to)}")
        down = [(p, c) for p, c in g.downstream_suppliers(nid) if g.listed_kr_us(c)]
        for p, c in down[:20]:
            size = (g.nodes.get(c) or {}).get("size_band") or "?"
            lines.append(f"- 아래 공급사(미국·한국): {g.label(c)} [{size}] ← " + " → ".join(g.label(x) for x in p))
            touched |= set(p)
    return {"text": "\n".join(lines), "touched": touched}


def fetch_public(view: str, params: dict[str, str]) -> list[dict[str, Any]]:
    from wsj.ecosystems.ideas import fetch_public_view
    from wsj.http import HttpClient

    url = os.environ.get("SUPABASE_URL") or "https://dcatgfivsvbktylmtvgf.supabase.co"
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if not key:
        return []
    http = HttpClient("WSJ-investment recall", timeout=30, max_retries=1)
    try:
        return fetch_public_view(http, url, key, view, params)
    except Exception:  # noqa: BLE001 - 뷰가 없으면(0031·0032 전) 빈 것
        return []
    finally:
        http.close()


def recall(graph: dict[str, Any], companies: list[str], nodes: list[str], names: list[str], text: str = "",
           opportunities: list[dict[str, Any]] | None = None, clues: list[dict[str, Any]] | None = None,
           prices: list[dict[str, Any]] | None = None, tech_fetch: Any = None) -> str:
    g = Graph(graph)
    for nm in names:
        companies += [c for c in find_companies(g, nm) if c not in companies]
    if text:
        from wsj.ecosystems.issues import build_lexicon

        node_pats, comp_pats = build_lexicon(graph)
        nodes += [nid for pat, nid in node_pats if pat.search(text) and nid not in nodes][:6]
        companies += [cid for pat, cid in comp_pats if pat.search(text) and cid not in companies][:4]
    nb = neighborhood(g, companies, nodes)
    touched = nb["touched"] | set(companies)
    parts = ["# 그래프 자리", nb["text"] or "- (그래프에 없음 — 해석에서 고리를 찾아 더할 것)"]
    pats = [p for p in load_patterns() if p["nodes"] & touched]
    parts.append("\n# 관련 패턴 카드")
    parts += [f"\n---\n{p['text'].strip()}" for p in pats] or ["- 없음 — 새 메커니즘이면 카드 초안을 제안할 것"]
    cases = [o for o in (opportunities or []) if set(o.get("nodes") or []) & touched
             or {c.get("company") for c in o.get("companies") or []} & set(companies)]
    parts.append("\n# 지난 사례 (투자 아이디어)")
    parts += [f"- [{o.get('status')}] ★{o.get('stars')} {o.get('title')} ({str(o.get('updated_at'))[:10]}) — {o.get('status_note') or ''}".rstrip(" —")
              for o in cases[:12]] or ["- 없음"]
    lc = [c for c in (clues or []) if set(c.get("nodes") or []) & touched or {x.get("company") for x in c.get("companies") or []} & set(companies)
          or any(nm.lower() in (c.get("title") or "").lower() for nm in names)]
    parts.append("\n# 지난 단서 (최근 90일, 최신 순)")
    parts += [f"- {str(c.get('published_at') or c.get('seen_at'))[:10]} {c.get('title')} — {c.get('source_name')} {c.get('url')}" for c in lc[:20]] or ["- 없음"]
    if prices:
        from wsj.ecosystems.quiet import listing_keys

        keys = listing_keys(graph)
        px = {p["ticker"]: p for p in prices}
        rows = [(cid, px.get(keys.get(cid, ""))) for cid in companies]
        parts.append("\n# 가격 (최근)")
        parts += [f"- {g.label(cid)}: 12개월 {p.get('r12m')}% · 3개월 {p.get('r3m')}% · 고점 대비 {p.get('from_high')}% ({p.get('as_of')})" if p
                  else f"- {g.label(cid)}: 가격 없음" for cid, p in rows] or ["- 없음"]
    if tech_fetch is not None:
        focus = list(dict.fromkeys(nodes + [n for c in companies for n in g.offers(c)]))[:6]
        parts += tech_section(g, focus, tech_fetch(focus) if focus else {})
    return "\n".join(parts)


def tech_section(g: Graph, focus: list[str], tech: dict[str, list[dict[str, Any]]]) -> list[str]:
    """논문·특허 백필(techdocs)에서 이 노드들의 흐름. 건수는 판단 기준이 아니라 '어디서 무엇이 움직이나'를 보는 재료다."""
    out = ["\n# 논문·특허 (노드별, techdocs 백필)"]
    if not any(tech.values()):
        return out + ["- 없음 (백필 전이거나 이 노드에 붙은 문서가 없다)"]
    by = defaultdict(lambda: defaultdict(Counter))
    for r in tech.get("series") or []:
        by[r["node"]][r["source"]][str(r["period"])[:4]] += int(r.get("n") or 0)
    for nid in focus:
        lines = []
        for src, ko in (("patent", "특허"), ("paper", "기업 논문")):
            years = by[nid][src]
            if years:
                lines.append(f"- {ko} 연도별: " + " · ".join(f"{y} {n}" for y, n in sorted(years.items())[-7:]))
            orgs = [o for o in tech.get("orgs") or [] if o["node"] == nid and o["source"] == src and o.get("span") == "2024~"]
            orgs.sort(key=lambda o: o.get("rank") or 99)
            if orgs:
                lines.append("  - 2024~ 많이 낸 곳: " + ", ".join(f"{g.label(o['company']) if o.get('company') else o['org']} {o['n']}" for o in orgs[:6]))
                new = [o for o in orgs if (o.get("first_year") or 0) >= 2024 and o["n"] >= 2]
                if new:
                    lines.append("  - 2024~ 새로 나타난 곳: " + ", ".join(f"{o['org']} {o['n']}" for o in new[:6]))
        docs = [d for d in tech.get("docs") or [] if nid in (d.get("nodes") or [])]
        docs.sort(key=lambda d: str(d.get("published_on") or ""), reverse=True)
        for d in docs[:4]:
            who = ", ".join(o.get("name") or "" for o in (d.get("orgs") or [])[:2])
            lines.append(f"  - {str(d.get('published_on'))[:10]} [{'특허' if d['source'] == 'patent' else '논문'}] {who} — {d.get('title')} {d.get('url') or ''}".rstrip())
        if lines:
            out += [f"\n## {g.label(nid)} ({nid})"] + lines
    return out if len(out) > 1 else out + ["- 이 노드들에 붙은 문서가 없다"]


def fetch_tech(nodes: list[str]) -> dict[str, list[dict[str, Any]]]:
    inn = "in.(" + ",".join(f'"{n}"' for n in nodes) + ")"
    ov = "ov.{" + ",".join(f'"{n}"' for n in nodes) + "}"
    return {"series": fetch_public("v_tech_series", {"node": inn}),
            "orgs": fetch_public("v_tech_orgs", {"node": inn, "span": "eq.2024~"}),
            "docs": fetch_public("v_tech_docs", {"nodes": ov, "order": "published_on.desc", "published_on": "gte.2024-01-01"})}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", action="append", default=[], help="company:… (여러 번)")
    ap.add_argument("--node", action="append", default=[], help="그래프 노드 id (여러 번)")
    ap.add_argument("--name", action="append", default=[], help="기업 이름·티커 (그래프 밖일 수도)")
    ap.add_argument("--text", default="", help="단서 제목·요약 — 그래프 어휘로 노드·기업을 더 찾는다")
    ap.add_argument("--offline", action="store_true", help="DB 를 읽지 않는다 (그래프·패턴만)")
    args = ap.parse_args(argv)
    graph = load_graph()
    opps = clues = prices = None
    if not args.offline:
        opps = fetch_public("v_opportunities", {})
        clues = fetch_public("v_clues", {"order": "seen_at.desc"})
        prices = fetch_public("v_price_context", {})
    print(recall(graph, list(args.company), list(args.node), list(args.name), args.text, opps, clues, prices,
                 tech_fetch=None if args.offline else fetch_tech))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
