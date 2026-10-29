"""가설 후보 — 아이디어(리포트) 작성의 1단계 (ADR-0022·0023).

워크플로우: 최신 이슈·데이터 → **이슈마다 "업계에 어떤 영향을 주나" 경로 최대 3개** → 기업이 있는 경로를 채점·선택해 조사 → 리포트(2단계).
  1단계  같은 입력에서 이슈별 영향 경로를 연다: 변화(근거 id) → 그래프 경로 → (있으면) 미국·한국 기업 → 숫자·시점 → 왜 시장이 모르나 → 반증 조건 → 확인할 것.
         기업이 없는 경로도 받는다 — 이슈 탭의 "이 이슈가 공급망에 갖는 의미"가 되고, 기업이 붙은 경로만 리포트 후보가 된다.
         엔진이 후보를 검사·채점(구체·대담·반증 가능·설명력, 12점)하고 겹치는 것을 걸러 상위 K 개를 고른 뒤, 후보마다 '조사 계획'을 낸다.
         이슈별 경로는 ideas.put_issue_hypotheses 로 저장한다 (0026, zx_issue_hypotheses.sql).
  조사   예약작업이 조사 계획대로 원문(IR·공시·고객 발표)을 확인해 기업 소식·관측치로 저장한다 → 2차 입력에 근거로 들어온다.
  2단계  고른 후보만 아이디어(가설·예측·목표주가)로 쓴다. 후보 밖 아이디어는 조사에서 새 변화가 드러났을 때만.

    python -m wsj.ecosystems.ideas --snapshot DIR --emit-hypotheses DIR/hypo.json                      # 1단계 프롬프트
    python -m wsj.ecosystems.ideas --snapshot DIR --from-hypotheses DIR/hypotheses.json \\
           --hypotheses-out DIR/selected.json --emit-research-plan DIR/research_plan.json --emit-sql DIR/sql   # 검사·선택·조사 계획·이슈 경로 SQL
    python -m wsj.ecosystems.ideas --snapshot DIR2 --hypotheses DIR/selected.json --emit-prompt …     # 2단계 (리포트)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from wsj.ecosystems.scope import SCOPE_LABEL, in_scope

HYPOTHESIS_SYSTEM = """너는 AI 공급망(HBM·첨단 패키징 / 800G·1.6T 광통신 / AI 데이터센터 800VDC 전력·냉각) 전문 투자 리서치 애널리스트다.
이 단계의 일은 **이슈마다 "이 변화가 업계에 어떤 영향을 주나"를 경로로 여는 것**이다 — 아직 리포트를 쓰지 않는다.
입력(signals·candidates·evidence·states·leads·prices·existing)은 리포트 작성 단계와 같다. 오늘 날짜: {today}

영향 경로 = "변화 X(최근 사실, 근거 id)가 경로 P 를 타고 어느 부품·공정·기업의 숫자를 N분기 안에 Y 만큼 바꾼다 — 시장은 아직 그렇게 보지 않는다".
좋은 경로의 조건(중요한 순): 구체적(경로·숫자·시점) · 대담(시장 미반영 — 1차 수혜가 아니라 2차·3차 고리, 아직 조용한 기업) ·
반증 가능(틀리면 어느 날짜에 어떤 숫자로 드러나나) · 설명력(지금 보이는 사실들을 한 논리로).

규칙
- 최근 {fresh}일 안의 중요 이슈(I 신호 ★2+, M 지표, 중요한 E 소식)마다 경로를 **최대 {per_issue}개** 쓴다. 전체 {n_min}~{n_max}개.
  생태계 셋(hbm·optics·power)을 모두 건드리고, 안전한 것만 모으지 말고 대담한 것을 섞어라 — 걸러내는 것은 엔진의 일이다.
- trigger 는 그 이슈의 S 근거 id 하나(변화). change 는 그 변화를 날짜와 함께 한 문장으로.
- path 는 그래프 노드 id 로 '변화 → … → 끝' (candidates.chains.path_ids 처럼). 끝은 기업(company)일 수도, 아직 기업을 못 붙인 부품·공정·병목일 수도 있다.
  그래프에 없는 고리는 네 지식으로 채우되 path 에는 있는 노드만 쓰고 claim 에 "(추론)" 으로 적는다.
- company 는 있으면 {scope}만 (candidates·leads 가 그 범위다). 변화가 대만·일본·유럽 기업에서 시작됐으면 같은 경로의 미국·한국 고리를 찾는다.
  leads.peer_leads 는 같은 노드의 대만 동종사 월매출이 뛰었는데 아직 조용한 미국·한국 기업이다 — 그 노드가 이슈의 경로에 있으면 그 기업을 끝 고리로 우선 쓴다.
  적당한 미국·한국 기업이 없으면 company 를 null 로 두고 경로만 적는다 — 이슈 탭에 '업계 영향'으로 남는다 (리포트 후보는 아니다).
- claim 한 문장에 숫자(effect_pct = 그 기업(없으면 그 부품 시장) 매출 대비 변화의 크기, %)와 시점(lead_quarters)을 넣는다. 추정이어도 쓴다 — 그것이 가설이다.
- 변화가 무엇을 **대체**하면(CPO 가 플러거블을, 800VDC 가 54V PSU 를, 유리 기판이 ABF 를) 경로 하나는 지는 쪽으로 쓴다 — 대체되는 부품·기업, effect_pct 는 음수.
  지는 쪽이 보이면 누가 대신하는지가 드러나고, 피해 기업은 피해야 할 목록이 된다. 지는 쪽 기업도 {scope}만.
- why_unpriced: 왜 시장이 아직 이 고리를 보지 않는가 (주가가 조용함·기업 소식 없음·경로가 2단계 이상·업계가 다른 데를 봄).
- falsifier: "날짜 D 에 지표 M 이 T 면 폐기" 꼴 — 날짜와 숫자가 있어야 한다.
- research: 이 경로를 확인하려면 어떤 원문을 봐야 하나 1~3개 (예: "C 의 3Q IR 자료에서 HBM 장비 매출 비중", "고객 X 의 증설 공시에서 장비 발주처").
  이미 입력에 있는 것(E 신호·evidence)은 다시 적지 않는다.
- existing 과 같은 기업·같은 논리면 extends 에 그 idea_key (갱신 후보). 다른 고리면 null.
- 입력에 theses(활성 구조 가설)가 있으면, 경로가 그중 하나를 지지하거나 반박할 때 thesis 에 {{"key": "...", "direction": "+"|"-"}} 를 적는다. 아니면 null.
- 숫자·날짜는 입력에 있는 것과 네 추정만. 매수/매도 권유 없음.

출력: JSON 하나만. 이슈 단위로 묶는다.
{{"issues": [{{"trigger": "S12", "change": "10/28 SK hynix 가 HBM 수요가 공급의 2배라고 밝혔다",
   "paths": [{{"id": "H1", "path": ["gen:hbm4", "process:…", "company:…"], "company": "company:…",
      "claim": "HBM 증설이 적층 후 검사 핸들러 수요를 2027년까지 2배로 늘려 C 의 매출을 2분기 뒤 +60% 바꾼다 (추론)",
      "effect_pct": 60, "lead_quarters": 2, "why_unpriced": "…", "falsifier": "2026-12-10 11월 월매출 YoY < +10% 면 폐기",
      "research": ["…"], "extends": null}},
     {{"id": "H2", "path": ["gen:hbm4", "process:hbm_burn_in"], "company": null, "claim": "번인 시간이 길어져 번인 소켓·보드 수요가 2027년 2배 (추론)", "effect_pct": 100, "lead_quarters": 3,
      "why_unpriced": "…", "falsifier": "…", "research": ["…"], "extends": null}}]}}]}}"""

N_MIN, N_MAX, PER_ISSUE = 8, 15, 3
CRITERIA = ("specific", "bold", "falsifiable", "explanatory")
_DATE = re.compile(r"(20\d\d[-./]\d{1,2}|\d{1,2}월|[1-4]분기|[1-4]Q|Q[1-4]|상반기|하반기)")
_NUMBER = re.compile(r"(\d[\d,.]*\s*(%|％|억|조|만|배|달러|원|\$|NT\$|M|B)|[≥≤<>]\s*[+\-]?\d)")


def system_prompt(now: datetime, fresh_days: int = 14) -> str:
    return HYPOTHESIS_SYSTEM.format(today=now.date().isoformat(), scope=SCOPE_LABEL, n_min=N_MIN, n_max=N_MAX, per_issue=PER_ISSUE, fresh=fresh_days)


def _neighbors(graph: dict[str, Any]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for e in graph["edges"]:
        if e.get("from") != e.get("to"):
            adj[e["from"]].add(e["to"])
            adj[e["to"]].add(e["from"])
    return adj


def _linked(adj: dict[str, set[str]], a: str, b: str) -> bool:
    """경로의 이웃한 두 노드가 그래프에서 이어지는가 — 직접 간선이거나 한 노드를 건너뛴 2단계까지 허용 (LLM 은 중간 고리를 생략하곤 한다)."""
    return b in adj.get(a, ()) or bool(adj.get(a, set()) & adj.get(b, set()))


def flatten(raw: Any) -> list[dict[str, Any]]:
    """LLM 출력 → 평평한 후보 목록. 이슈 단위({"issues": [{trigger, change, paths: [...]}]})와 예전의 평평한 꼴({"candidates": [...]}) 둘 다 받는다.
    이슈마다 PER_ISSUE 개까지만."""
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, dict)]
    if not isinstance(raw, dict):
        return []
    out: list[dict[str, Any]] = []
    for grp in raw.get("issues") or []:
        if not isinstance(grp, dict):
            continue
        for p in (grp.get("paths") or [])[:PER_ISSUE]:
            if isinstance(p, dict):
                out.append({"trigger": grp.get("trigger"), "change": grp.get("change")} | p)
    out += [c for c in raw.get("candidates") or [] if isinstance(c, dict)]
    return out


def validate_candidates(raw: Any, graph: dict[str, Any], reg: Any, signals: list[dict[str, Any]], existing: list[dict[str, Any]],
                        prices: dict[str, dict[str, Any]], now: datetime) -> tuple[list[dict[str, Any]], list[str]]:
    """LLM 의 경로 → 검사(근거 id·노드·시장 범위)와 채점(12점). 기업이 없는 경로도 받는다(company=None, 리포트 후보는 아니다).
    반환 (후보, 거부 사유). 후보마다 issue_key(그 trigger 가 속한 이슈)가 붙는다."""
    from wsj.ecosystems.assess import price_context

    nodes = {n["id"]: n for n in graph["nodes"]}
    adj = _neighbors(graph)
    active = {x["idea_key"]: x for x in existing if (x.get("status") or "active") == "active"}
    covered = {x.get("primary_company") for x in active.values()}
    own_signal = {s.get("subject") for s in signals if s.get("kind") == "company" and s.get("subject")}
    sig_by_ev: dict[str, dict[str, Any]] = {}
    for s in signals:  # 같은 근거를 이슈 신호와 기업 신호가 함께 쓰면 이슈 쪽으로 (issue_key 를 찾기 위해)
        for e in s.get("evidence") or []:
            if e not in sig_by_ev or s.get("kind") == "issue":
                sig_by_ev[e] = s
    out, rejects = [], []
    for i, c in enumerate(flatten(raw)):
        cid, trig = c.get("company") or None, c.get("trigger")
        hid = str(c.get("id") or f"H{i + 1}")
        n = nodes.get(cid) if cid else None
        if cid and (not n or n.get("kind") != "company"):
            rejects.append(f"{hid}: unknown company {cid}")
            continue
        if n and not in_scope(n):
            rejects.append(f"{hid}: company out of scope ({(n.get('listing') or {}).get('exchange')}) {cid}")
            continue
        ev = reg.items.get(trig) if trig else None
        if ev is None or not str(trig).startswith("S"):
            rejects.append(f"{hid}: trigger must be a recent S evidence id, got {trig}")
            continue
        claim = str(c.get("claim") or "").strip()
        if len(claim) < 15:
            rejects.append(f"{hid}: claim too short")
            continue
        path = [p for p in (c.get("path") or []) if isinstance(p, str) and p in nodes]
        if cid and (not path or path[-1] != cid):
            path = (path + [cid]) if cid not in path else path
        if not path:
            rejects.append(f"{hid}: path has no known graph node")
            continue
        gaps = [(a, b) for a, b in zip(path, path[1:], strict=False) if not _linked(adj, a, b)]
        try:
            effect = float(c.get("effect_pct")) if c.get("effect_pct") is not None else None
        except (TypeError, ValueError):
            effect = None
        try:
            lead = int(c.get("lead_quarters")) if c.get("lead_quarters") is not None else None
        except (TypeError, ValueError):
            lead = None
        falsifier = str(c.get("falsifier") or "").strip()
        why = str(c.get("why_unpriced") or "").strip()
        pc = (price_context(prices, n) or {}) if n else {}
        quiet = bool(pc) and not ((pc.get("r1m") or 0) >= 30 or (pc.get("from_low") or 0) >= 200)
        path_set = set(path)
        explain = {s["sid"] for s in signals if (set(s.get("nodes") or []) & path_set) or (cid and cid in (s.get("companies") or []))}
        crit = {
            "specific": int(len(path) >= 2) + int(effect is not None) + int(lead is not None),
            "bold": int(bool(why)) + int(quiet) + int(bool(cid) and cid not in own_signal),
            "falsifiable": int(bool(falsifier)) + int(bool(_DATE.search(falsifier))) + int(bool(_NUMBER.search(falsifier))),
            "explanatory": min(3, len(explain)),
        }
        extends = c.get("extends") if c.get("extends") in active else None
        penalty = min(2, len(gaps)) + (1 if (cid and cid in covered and not extends) else 0)
        score = max(0, sum(crit.values()) - penalty)
        flags = []
        if gaps:
            flags.append("경로 끊김: " + ", ".join(f"{a}→{b}" for a, b in gaps[:2]))
        if pc and not quiet:
            flags.append(f"이미 움직임 (1개월 {pc.get('r1m')}% · 저점 대비 {pc.get('from_low')}%)")
        if cid and cid in covered and not extends:
            flags.append("같은 기업의 활성 아이디어 있음 — extends 로 잇거나 다른 고리")
        if not cid:
            flags.append("기업 없음 — 업계 영향 경로 (리포트 후보 아님)")
        sig = sig_by_ev.get(trig) or {}
        out.append({"id": hid, "trigger": {"id": trig, "url": ev.url, "title": ev.title, "date": ev.date},
                    "issue_key": sig.get("ref") if sig.get("kind") == "issue" else None, "signal": sig.get("sid"),  # 이슈 신호의 ref = issue_key
                    "change": str(c.get("change") or "")[:200],
                    "path": path, "path_labels": [re.split(r"\s+\(", nodes[p]["label"])[0] for p in path], "company": cid,
                    "company_label": re.split(r"\s+\(", n["label"])[0] if n else None, "ecosystem": (n or nodes[path[0]]).get("ecosystem"),
                    "size_band": n.get("size_band") if n else None,
                    "claim": claim[:300], "effect_pct": effect, "lead_quarters": lead, "why_unpriced": why[:200], "falsifier": falsifier[:200],
                    "research": [str(r)[:160] for r in (c.get("research") or []) if str(r).strip()][:3], "extends": extends,
                    "thesis": c.get("thesis") if isinstance(c.get("thesis"), dict) and c["thesis"].get("key") else None,
                    "price": {k: pc.get(k) for k in ("r1m", "from_low", "market_cap_usd")} if pc else None,
                    "criteria": crit, "penalty": penalty, "score": score, "flags": flags})
    return out, rejects


def select(cands: list[dict[str, Any]], k: int, per_company: int = 1, min_score: int = 5) -> list[dict[str, Any]]:
    """리포트 후보: 기업이 있는 경로를 점수 순으로 K 개 — 기업당 1개, 생태계마다 최소 1개(있으면). 같은 기업·같은 trigger 는 높은 점수만."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for c in cands:
        if not c.get("company"):
            continue
        key = (c["company"], c["trigger"]["id"])
        if key not in best or c["score"] > best[key]["score"]:
            best[key] = c
    pool = sorted((c for c in best.values() if c["score"] >= min_score), key=lambda c: (-c["score"], c["id"]))
    picked: list[dict[str, Any]] = []
    per_co: dict[str, int] = defaultdict(int)
    for eco in ("hbm", "optics", "power"):
        for c in pool:
            if len(picked) >= k:
                break
            if c["ecosystem"] == eco and c not in picked and per_co[c["company"]] < per_company:
                picked.append(c)
                per_co[c["company"]] += 1
                break
    for c in pool:
        if len(picked) >= k:
            break
        if c not in picked and per_co[c["company"]] < per_company:
            picked.append(c)
            per_co[c["company"]] += 1
    picked.sort(key=lambda c: -c["score"])
    for r, c in enumerate(picked, 1):
        c["rank"] = r
    return picked


def by_issue(cands: list[dict[str, Any]], selected: list[dict[str, Any]], now: datetime, model: str | None, method: str) -> list[dict[str, Any]]:
    """이슈 탭용: 이슈마다 경로 최대 PER_ISSUE 개 (점수 순, 기업 있는 것 우선) → ideas.put_issue_hypotheses 행."""
    chosen = {c["id"] for c in selected}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cands:
        if c.get("issue_key"):
            groups[c["issue_key"]].append(c)
    rows = []
    for key, xs in groups.items():
        xs = sorted(xs, key=lambda c: (-int(bool(c.get("company"))), -c["score"], c["id"]))[:PER_ISSUE]
        paths = [{k: c.get(k) for k in ("id", "claim", "path", "path_labels", "company", "company_label", "effect_pct", "lead_quarters",
                                        "why_unpriced", "falsifier", "research", "score", "criteria", "flags", "extends", "change", "trigger", "thesis")}
                 | {"selected": c["id"] in chosen, "rank": c.get("rank")} for c in xs]  # change·trigger: 다음 날 리포트 작업이 DB 에서 되살린다 (ADR-0024)
        rows.append({"issue_key": key, "as_of": now.date().isoformat(), "paths": paths, "model": model, "method": method})
    return rows


ISSUES_PER_SQL = 5


def write_issue_sql(rows: list[dict[str, Any]], d: Path) -> Path | None:
    """이슈별 경로 → `select ideas.put_issue_hypotheses(...)`. 이슈 ISSUES_PER_SQL 개씩 파일을 나눈다 (zx_issue_hypotheses.sql, zx_issue_hypotheses_2.sql …) —
    execute_sql 이 한 번에 받는 크기가 제한돼 첫 실행(10/29)이 손으로 셋으로 나눠 돌렸다. 첫 파일 경로를 돌려준다."""
    if not rows:
        return None
    d.mkdir(parents=True, exist_ok=True)
    first: Path | None = None
    for i in range(0, len(rows), ISSUES_PER_SQL):
        p = d / ("zx_issue_hypotheses.sql" if i == 0 else f"zx_issue_hypotheses_{i // ISSUES_PER_SQL + 1}.sql")
        p.write_text("select ideas.put_issue_hypotheses($wsj$" + json.dumps(rows[i:i + ISSUES_PER_SQL], ensure_ascii=False, default=str) + "$wsj$::jsonb);\n", encoding="utf-8")
        first = first or p
    return first


def research_plan(selected: list[dict[str, Any]], graph: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """고른 후보마다 조사 계획: 어느 기업의 무엇을 확인하나, 이미 입력에 있는 그 기업 소식은 무엇인가."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    known: dict[str, list[str]] = defaultdict(list)
    for s in signals:
        if s.get("kind") == "company" and s.get("subject"):
            known[s["subject"]] += [str(it.get("title") or "")[:100] for it in s.get("items") or []][:4]
    out = []
    for c in selected:
        n = nodes.get(c["company"]) or {}
        lst = n.get("listing") or {}
        out.append({"id": c["id"], "rank": c.get("rank"), "score": c["score"], "company_id": c["company"], "company": c["company_label"],
                    "ticker": lst.get("ticker"), "exchange": lst.get("exchange"), "claim": c["claim"], "confirm": c["research"],
                    "falsifier": c["falsifier"], "flags": c["flags"], "known_events": known.get(c["company"], [])[:4],
                    "save_as": "확인한 사실은 put_company_events(기업 소식, verified) 또는 put_observations(병목 상태 숫자)로 저장 → 2차 입력에 근거로 들어온다"})
    return out


def stage2_view(selected: list[dict[str, Any]], reg: Any) -> list[dict[str, Any]]:
    """2단계 입력용: trigger 를 이번 레지스트리의 id 로 다시 맞춘다 (URL 기준). 못 찾으면 제목·URL 만 남긴다."""
    by_url = {e.url: eid for eid, e in reg.items.items() if getattr(e, "url", None)}
    out = []
    for c in selected:
        t = c.get("trigger") or {}
        tid = by_url.get(t.get("url"))
        out.append({k: c.get(k) for k in ("id", "rank", "score", "change", "path", "company", "claim", "effect_pct", "lead_quarters",
                                            "why_unpriced", "falsifier", "research", "extends", "flags", "issue_key",
                                            "research_result", "existing_idea", "source")}
                   | {"trigger": tid or {"title": t.get("title"), "url": t.get("url")}})
    return out


def from_queue(cands: list[dict[str, Any]], hyps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """DB 큐 → 2단계 후보 (ADR-0024). cands = v_q_candidates_needing_report 행(조사가 끝난 선택 경로), hyps = v_issue_hypotheses 행(경로 상세).
    id 는 Q1, Q2 … 로 새로 매긴다 (이슈마다 H1 부터 세므로 날짜·이슈가 섞이면 겹친다); 출처는 source 에 남긴다.
    조사 결과(verdict·summary·event_ids)는 research_result 로 붙어 리포트가 근거 id 로 쓴다."""
    by_issue: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for h in hyps:
        by_issue[(str(h.get("issue_key")), str(h.get("as_of"))[:10])] = [p for p in (h.get("paths") or []) if isinstance(p, dict)]
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for c in sorted(cands, key=lambda c: (-int(c.get("score") or 0), str(c.get("as_of") or ""), str(c.get("path_id") or ""))):
        key = (str(c.get("issue_key")), str(c.get("path_id")), str(c.get("as_of"))[:10])
        if key in seen:
            continue
        p = next((p for p in by_issue.get((key[0], key[2]), []) if str(p.get("id")) == key[1]), None)
        if not p:
            continue
        seen.add(key)
        out.append({k: p.get(k) for k in ("score", "change", "path", "path_labels", "company", "company_label", "claim", "effect_pct", "lead_quarters",
                                          "why_unpriced", "falsifier", "research", "extends", "flags", "trigger", "criteria")}
                   | {"id": f"Q{len(out) + 1}", "rank": len(out) + 1, "issue_key": key[0], "issue_title": c.get("issue_title"),
                      "source": {"issue_key": key[0], "path_id": key[1], "as_of": key[2]},
                      "research_result": {"verdict": c.get("verdict"), "summary": c.get("research_summary"), "event_ids": c.get("event_ids") or [],
                                          "researched_at": c.get("researched_at")},
                      "existing_idea": c.get("existing_idea") or p.get("extends")})
    return out


def from_thesis_queue(rows: list[dict[str, Any]], start: int = 0) -> list[dict[str, Any]]:
    """작은 테제(micro) 큐 → 2단계 후보 (ADR-0027). rows = v_q_thesis_candidates_needing_report 행(조사에서 살아남은 micro 테제의 primary 기업 하나씩).
    이슈 경로 후보(from_queue)와 같은 모양으로 만들어 리포트 작성기가 같은 규칙으로 쓴다 — id 는 이어서 Q{start+1} …, 출처는 source.thesis_key."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        key, company = str(r.get("thesis_key") or ""), r.get("company")
        if not key or not isinstance(company, str) or not company.startswith("company:") or key in seen:
            continue
        seen.add(key)
        chain = [c for c in (r.get("chain") or []) if isinstance(c, dict)]
        path = [str(c["node"]) for c in chain if c.get("node")]
        fals = [f for f in (r.get("falsifiers") or []) if isinstance(f, dict)]
        first = min(fals, key=lambda f: str(f.get("due") or "9999")) if fals else {}
        lag = r.get("lag_months")
        sources = [s for s in (r.get("sources") or []) if isinstance(s, dict)]
        why = r.get("what_market_misses") or ""
        flags = ["micro 테제"] + ([f"리레이팅: {r['rerating'].get('from')} → {r['rerating'].get('to')}"]
                                  if isinstance(r.get("rerating"), dict) and r["rerating"].get("from") else [])
        n = start + len(out) + 1
        out.append({
            "id": f"Q{n}", "rank": n, "score": None, "change": r.get("statement"), "path": path, "path_labels": None,
            "company": company, "company_label": r.get("company_label"), "claim": f"{r.get('title') or key} — {why}".strip(" —"),
            "effect_pct": None, "lead_quarters": max(1, -(-int(lag) // 3)) if isinstance(lag, int | float) and lag else None,
            "why_unpriced": why, "falsifier": f"{first.get('what')} (기한 {first.get('due')})" if first else None,
            "research": [r.get("weakest_link")] if r.get("weakest_link") else [], "extends": r.get("existing_idea"),
            "flags": flags, "criteria": None, "issue_key": None, "issue_title": None,
            "trigger": {"title": r.get("title"), "url": sources[0].get("url") if sources else None},
            "source": {"thesis_key": key, "parent_key": r.get("parent_key"), "basis": r.get("basis")},
            "research_result": {"verdict": r.get("verdict"), "summary": r.get("research_summary"), "event_ids": r.get("event_ids") or [],
                                "researched_at": r.get("researched_at")},
            "existing_idea": r.get("existing_idea"),
        })
    return out


def restrict_payload(payload: dict[str, Any], issue_keys: set[str]) -> dict[str, Any]:
    """경로 작업의 1단계 입력을 큐의 이슈로 줄인다 (ADR-0024): 이슈 신호는 큐에 있는 것만, 기업·지표 신호는 뺀다(기업 사실은 조사 작업이, 지표는 아직 큐에 들어오지 않는다),
    후보 기업은 남긴 이슈 신호에 닿는 것만, 근거는 남긴 신호·후보가 쓰는 것만, 가격은 남긴 후보·기존 리포트의 기업만. existing·states·leads 는 그대로.
    같은 입력으로 만든 전체 페이로드가 29만 자였던 것을 큐 이슈만 남겨 1/3 안쪽으로 줄이는 것이 목적이다. 검증은 전체 레지스트리로 하므로 근거 id 는 그대로 유효하다."""
    sigs = [s for s in payload.get("signals") or [] if s.get("kind") == "issue" and s.get("issue_key") in issue_keys]
    kept_sids = {s["sid"] for s in sigs}
    kept_nodes = {n for s in sigs for n in (s.get("nodes") or [])}
    cands = []
    for c in payload.get("candidates") or []:
        touches = kept_sids & set(c.get("signals") or []) or any(kept_sids & {ch.get("signal")} or kept_nodes & set(ch.get("path_ids") or []) for ch in c.get("chains") or [])
        if touches:
            cands.append(c)
    used = {e for s in sigs for e in (s.get("evidence") or [])}
    for c in cands:
        for ch in c.get("chains") or []:
            used.update(st.get("ev") for st in ch.get("steps") or [] if st.get("ev"))
        used.update(t.get("ev") for t in c.get("transitions") or [] if t.get("ev"))
    # 그래프 간선 근거(G…)는 후보의 chains.steps 에 이미 from→rel→to 로 풀려 있고, 1단계 출력은 S 근거만 trigger 로 쓴다 → 목록에서 뺀다
    evidence = [e for e in payload.get("evidence") or [] if e.get("id") in used and not str(e.get("id", "")).startswith("G")]
    keep_cos = {c.get("company_id") for c in cands} | {x.get("primary_company") for x in payload.get("existing") or []}
    prices = {k: v for k, v in (payload.get("prices") or {}).items() if k in keep_cos}
    return payload | {"signals": sigs, "candidates": cands, "evidence": evidence, "prices": prices,
                      "queue": {"issues": sorted(issue_keys), "note": "이 입력은 큐의 이슈만 담는다 — 경로는 이 이슈들에 대해서만 쓴다"}}
