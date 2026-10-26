"""해자 카드 (moat card) — 온톨로지에 승격된 소형 공급사의 기술·해자·잠재성을 공시 원문 + 그래프 맥락으로 판정한다. ADR-0013.

    python -m wsj moat build --ticker LWLG [--dry-run] [--model sonnet]
    python -m wsj moat build --all                 # 그래프의 in_universe 기업 전부 (같은 기준일 카드가 있으면 건너뜀)

입력 = 브리프 데이터팩(10-K Item 1/1A/7 · 10-Q MD&A · 8-K · XBRL 12분기 · 1y 주가, ADR-0009) + 온톨로지 맥락
      (어느 병목·공정·소재 노드에 붙어 있는지, 그 노드를 쥔 다른 회사, 그 노드를 키우는 세대·표준과 시점,
       대체·잠식 위협, 영향 전파 결과). LLM 은 종합 1회 (검색 없음). 결과는 ideas.briefs(kind='moat').
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from wsj.briefs import prompts
from wsj.briefs.datapack import DataPack, build_datapack
from wsj.briefs.llm import LLM, JSONGenerationError, resolve_model, sum_usage
from wsj.db.base import Store
from wsj.ecosystems.impact import impact_report
from wsj.ecosystems.ontology import load_graph, load_ontology
from wsj.http import HttpClient

log = logging.getLogger("wsj.moat")
MOAT_PROMPT_VERSION = "moat-2026-10-27.1"


@dataclass
class MoatOptions:
    model: str = "sonnet"  # 해자 판정은 추론 품질이 중요 — 기본 Sonnet
    effort: str = "medium"
    dry_run: bool = False
    out_dir: Path | None = None
    force: bool = False


# ---------------------------------------------------------------------- 온톨로지 맥락
def ontology_context(graph: dict[str, Any], cik: int) -> dict[str, Any] | None:
    nodes = {n["id"]: n for n in graph["nodes"]}
    company = next(
        (n for n in graph["nodes"] if n["kind"] == "company" and (n.get("listing") or {}).get("cik") == cik),
        None,
    )
    if company is None:
        return None
    onto = load_ontology()
    incoming = [e for e in graph["edges"] if e["to"] == company["id"] and e["relation"] == "offered_by"]
    positions: list[dict[str, Any]] = []
    for e in incoming:
        node = nodes[e["from"]]
        peers = [
            nodes[x["to"]]
            for x in graph["edges"]
            if x["from"] == e["from"] and x["relation"] == "offered_by" and x["to"] != company["id"]
        ]
        # 이 노드를 키우는 상류: 거꾸로 올라가 요구·세대·표준
        upstream: list[str] = []
        frontier = [e["from"]]
        seen = set(frontier)
        for _ in range(5):
            nxt = []
            for x in graph["edges"]:
                if (
                    x["to"] in frontier
                    and x["relation"]
                    in (
                        "mitigated_by",
                        "creates_bottleneck",
                        "drives_requirement",
                        "requires",
                        "specified_by",
                    )
                    and x["from"] not in seen
                ):
                    seen.add(x["from"])
                    nxt.append(x["from"])
                    upstream.append(f"{nodes[x['from']]['label']} ({nodes[x['from']]['kind']})")
            frontier = nxt
            if not frontier:
                break
        threats = [
            f"{nodes[x['from']]['label']} --{x['relation']}--> {nodes[x['to']]['label']} [{x.get('evidence_tier')}] {x.get('note', '')}"
            for x in graph["edges"]
            if x["relation"] in ("displaces", "substitutes_for", "defers")
            and (x["to"] == e["from"] or x["from"] == e["from"])
        ]
        positions.append(
            {
                "node_id": e["from"],
                "node": node["label"],
                "kind": node["kind"],
                "ecosystem": node.get("ecosystem"),
                "evidence_tier": e.get("evidence_tier"),
                "evidence_note": (e.get("evidence") or [{}])[0].get("note"),
                "metrics": node.get("measured_metrics", []),
                "peers_on_node": [f"{p['label']} [{p.get('size_band')}]" for p in peers],
                "upstream_demand": upstream[:8],
                "threats": threats,
            }
        )
    competitors = [
        nodes[x["to"] if x["from"] == company["id"] else x["from"]]["label"]
        for x in graph["edges"]
        if x["relation"] == "competes_with" and company["id"] in (x["from"], x["to"])
    ]
    # 세대·표준 이벤트 (타이밍)
    eco_ids = {f"eco:{p['ecosystem']}" for p in positions if p.get("ecosystem")}
    events = [
        {
            "date": ev.get("published_at"),
            "summary": ev["summary"],
            "interpretation": ev.get("interpretation"),
            "url": ev["source_url"],
        }
        for ev in graph.get("events", [])
        if ev.get("ecosystem") in eco_ids
    ]
    impacts = []
    for p in positions:
        rep = impact_report(graph, p["node_id"], onto=onto)
        impacts.append(
            {
                "node": p["node"],
                "companies": [
                    f"{c['company']} {c['direction']} {c['best_confidence']}" for c in rep["companies"][:6]
                ],
            }
        )
    return {
        "company_node": company["id"],
        "label": company["label"],
        "size_band": company.get("size_band"),
        "public_float": company.get("public_float"),
        "discovery": company.get("discovery"),
        "positions": positions,
        "competitors_in_graph": competitors,
        "ecosystem_events": sorted(events, key=lambda x: x["date"] or "", reverse=True)[:12],
        "impact_on_nodes": impacts,
    }


def render_context(ctx: dict[str, Any]) -> str:
    out = [f"# 온톨로지 맥락 — {ctx['label']} (규모 {ctx['size_band']}, 공개유동 {ctx.get('public_float')})"]
    if ctx.get("discovery"):
        out.append(f"- 발굴: {ctx['discovery']}")
    out.append("")
    for p in ctx["positions"]:
        out.append(f"## 위치: {p['node']} [{p['kind']}, {p['ecosystem']}] — 근거 등급 {p['evidence_tier']}")
        if p.get("evidence_note"):
            out.append(f"- 근거 메모: {p['evidence_note']}")
        out.append(f"- 관측 지표: {', '.join(p['metrics']) or '없음'}")
        out.append(
            f"- 같은 노드의 다른 회사: {', '.join(p['peers_on_node']) or '없음 (단독 — 발굴 범위 내)'}"
        )
        out.append(f"- 이 노드를 키우는 상류 요구·세대·표준: {' / '.join(p['upstream_demand']) or '없음'}")
        out.append(f"- 대체·잠식·연기 위협: {' / '.join(p['threats']) or '없음'}")
        out.append("")
    out.append(f"## 그래프상 경쟁사: {', '.join(ctx['competitors_in_graph']) or '없음'}")
    out.append("## 생태계 이벤트 (시점)")
    for ev in ctx["ecosystem_events"]:
        out.append(f"- {ev['date']}: {ev['summary']} — {ev['interpretation']} <{ev['url']}>")
    out.append("## 노드별 영향 전파 결과 (이 노드가 바뀌면 누가)")
    for i in ctx["impact_on_nodes"]:
        out.append(f"- {i['node']}: {', '.join(i['companies']) or '—'}")
    return "\n".join(out)


# ---------------------------------------------------------------------- 프롬프트
MOAT_SYSTEM = (
    """\
당신은 반도체·광통신·전력 공급망을 담당하는 소형주 애널리스트다. 대상은 공급망의 소재·부품·공정·테스트·IP 층에 있는
소형 상장사이고, 질문은 하나다: **이 회사가 쥔 병목은 진짜이고, 독점적이며, 수요 세대 전환과 함께 커지는가 — 그래서 10배가 가능한가.**

판정 순서:
1. 기술 위치: 온톨로지 맥락의 노드가 10-K Item 1 과 실제로 맞는가. 회사가 그 노드를 '제품으로 파는지' '언급만 하는지' 구분 (원문 인용).
2. 해자 유형과 근거: IP(특허·라이선스 매출), 공정 노하우(수율·고객 인증 기간), 전환비용(고객 적격성·설계 고정), 규모·비용, 규제·표준 선점, 없음.
   각 유형은 10-K·XBRL 에서 관측 가능한 근거(매출총이익률 수준·추세, R&D/매출, 고객 집중도, 인증·qualification 언급, 특허 수·라이선스 매출)로만 주장한다.
3. 고객 증거: 고객명 공개 여부, 상위 고객 비중(Item 1A·Note), 세대 전환 고객(NVIDIA·메모리 3사·하이퍼스케일러)과의 연결 — 언급과 납품을 구분.
4. 재무 포착: 매출 성장, 매출총이익률, 영업현금흐름, 런웨이, 희석. 매출 전(pre-revenue)이면 그 사실과 상업화까지의 거리.
5. 타이밍: 온톨로지의 세대·표준 이벤트(HBM4→HBM4E→HBM5, 800G→1.6T, 54V→800VDC)에서 이 회사의 노드 수요가 언제 커지는지. 연기·대체 위협(예: 하이브리드 본딩 HBM5 연기)이 이 회사에 유리한지 불리한지.
6. 경쟁: 같은 노드의 다른 회사(규모 포함). 대형사가 이미 쥔 노드면 소형사의 해자는 '틈새' 로 축소 평가.
7. 텐배거 역산: 현재 시총 ×10 을 정당화할 매출·마진·배수, 소요 기간, 필요한 희석.
8. 반증 조건(날짜·지표) 과 데이터 공백.

규칙: 모든 수치·사실에 출처(데이터팩: 절/필드, 원문: 10-K Item, 온톨로지 맥락: 노드/이벤트). 없으면 '데이터 없음'. 사전지식으로 최근 사건을 쓰지 않는다.
한국어, 고유명사·재무 용어 원문. 과장 형용사 금지. 전체 2,500~4,500자.
"""
    + prompts.EVIDENCE_RULES
    + """
출력: ```json 블록 하나.
{
  "one_liner": "무엇을 파는 회사인지 한 문장",
  "position_in_chain": [{"node": "온톨로지 노드", "fit": "product|capability|mention_only", "evidence": "10-K 인용 요지", "source": "..."}],
  "moat": {"type": "ip|process_knowhow|switching_cost|scale|standard|none", "strength": 1, "evidence": [{"claim": "...", "source": "..."}], "what_breaks_it": "..."},
  "customers": {"named": ["..."], "concentration": "상위 고객 비중·출처 또는 데이터 없음", "qualification_events": ["..."], "generation_customers": "세대 전환 고객과의 연결 (언급/납품 구분)"},
  "financial_capture": {"revenue_ttm": "...", "revenue_growth": "...", "gross_margin": "수준·추세", "rnd_intensity": "...", "ocf_and_runway": "...", "dilution": "...", "stage": "pre_revenue|early_revenue|scaling|mature"},
  "timing": {"demand_unlock": "어느 세대·표준·이벤트가 수요를 키우는가", "when": "YYYY-Q# 또는 범위", "first_evidence": "먼저 관측될 것", "threat_direction": "연기·대체 위협이 유리/불리한 이유"},
  "competition": [{"name": "...", "relative_size": "larger|similar|smaller", "position": "..."}],
  "tenbagger_path": {"current_market_cap": "...", "target_market_cap": "...", "required_revenue_and_multiple": "...", "years": 0, "dilution_assumption": "...", "feasibility": "plausible|stretch|implausible", "why": "..."},
  "scores": {"moat": 1, "timing": 1, "financial": 1, "data_quality": 1, "overall": 1, "rationale": "..."},
  "falsifiers": [{"statement": "...", "check_by": "YYYY-MM-DD", "metric": "...", "threshold": "..."}],
  "data_gaps": ["..."],
  "hard_data": [{"label": "...", "url": "..."}]
}
"""
)


def moat_user(full_md: str, ctx_md: str, as_of: str) -> str:
    return f"""기준일: {as_of}

=== 온톨로지 맥락 ===
{ctx_md}

=== 데이터팩 전문 (공시 원문 포함) ===
{full_md}

시스템 지시의 판정 순서대로 분석하고 해자 카드 JSON 을 작성하라."""


# ---------------------------------------------------------------------- 실행
def build_one(
    store: Store,
    http: HttpClient,
    llm: LLM | None,
    cik: int,
    as_of: date,
    opt: MoatOptions,
    graph: dict[str, Any],
) -> dict[str, Any]:
    ctx = ontology_context(graph, cik)
    if ctx is None:
        return {"cik": cik, "status": "skipped", "reason": "그래프에 없는 기업 — 먼저 promote"}
    dp: DataPack = build_datapack(store, http, cik, as_of)
    ticker = dp.ticker or str(cik)
    ctx_md = render_context(ctx)
    full = dp.render_full()
    node_ids = [p["node_id"] for p in ctx["positions"]]
    if opt.dry_run or llm is None:
        out_dir = (opt.out_dir or Path("data/moat")) / f"{ticker}_{as_of.isoformat()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "context.md").write_text(ctx_md, encoding="utf-8")
        (out_dir / "datapack.md").write_text(full, encoding="utf-8")
        (out_dir / "prompt.md").write_text(
            "# SYSTEM\n\n" + MOAT_SYSTEM + "\n\n# USER\n\n" + moat_user(full, ctx_md, as_of.isoformat()),
            encoding="utf-8",
        )
        log.info("[%s] dry-run → %s (≈%d input tokens)", ticker, out_dir, int(len(full + ctx_md) / 3.2))
        return {
            "cik": cik,
            "ticker": ticker,
            "dry_run": True,
            "out_dir": str(out_dir),
            "nodes": node_ids,
            "input_chars": len(full) + len(ctx_md),
        }

    existing = store.select(
        "ideas.briefs", ["id", "version", "as_of", "status"], {"cik": cik, "kind": "moat"}
    )
    if not opt.force and any(
        str(r.get("as_of")) == as_of.isoformat() and r.get("status") != "failed" for r in existing
    ):
        return {"cik": cik, "ticker": ticker, "skipped": True}
    version = 1 + max((int(r.get("version") or 0) for r in existing), default=0)
    card: dict[str, Any] = {}
    comps = []
    error = None
    try:
        card, comps = llm.complete_json(
            MOAT_SYSTEM,
            moat_user(full, ctx_md, as_of.isoformat()),
            resolve_model(opt.model),
            prompts.REPAIR_USER,
            max_tokens=12000,
            effort=opt.effort,
        )
    except JSONGenerationError as exc:
        comps = exc.completions
        error = str(exc)
    except Exception as exc:  # noqa: BLE001
        error = "".join(traceback.format_exception(exc))[-3000:]
    usage = {"synthesis": [c.usage() for c in comps], "total": sum_usage(comps)}
    row = {
        "kind": "moat",
        "ontology_nodes": node_ids,
        "cik": cik,
        "ticker": dp.ticker,
        "as_of": as_of.isoformat(),
        "version": version,
        "status": "failed" if error else "final",
        "title": (card.get("one_liner") or None) if card else None,
        "brief": card or None,
        "research": None,
        "critique": None,
        "datapack_summary": {**dp.summary(), "ontology_context": ctx},
        "scores": card.get("scores") if card else None,
        "model": resolve_model(opt.model),
        "prompt_version": MOAT_PROMPT_VERSION,
        "usage": usage,
        "error": error,
    }
    saved = store.insert_returning("ideas.briefs", row)
    if card and saved.get("id") is not None:
        preds = [
            {
                "brief_id": saved["id"],
                "cik": cik,
                "claim": "[반증] " + str(f.get("statement"))[:980],
                "measurable": " / ".join(str(f.get(k)) for k in ("metric", "threshold") if f.get(k)) or None,
                "due_date": str(f.get("check_by"))[:10],
                "scenario": "falsifier",
            }
            for f in card.get("falsifiers") or []
            if isinstance(f, dict) and f.get("statement") and f.get("check_by")
        ]
        if preds:
            store.insert("ideas.predictions", preds)
    if opt.out_dir:
        d = opt.out_dir / f"{ticker}_{as_of.isoformat()}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "moat.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
    log.info(
        "[%s] moat #%s %s — cost $%s", ticker, saved.get("id"), row["status"], usage["total"]["cost_usd"]
    )
    return {
        "cik": cik,
        "ticker": ticker,
        "brief_id": saved.get("id"),
        "status": row["status"],
        "scores": row["scores"],
        "usage": usage["total"],
        "title": row["title"],
    }


def build(
    store: Store,
    http: HttpClient,
    api_key: str | None,
    as_of: date | None,
    ciks: list[int] | None,
    all_universe: bool,
    opt: MoatOptions,
) -> list[dict[str, Any]]:
    as_of = as_of or date.today()
    graph = load_graph()
    llm = None
    if not opt.dry_run:
        if not api_key:
            raise SystemExit("ANTHROPIC_API_KEY 가 없습니다. --dry-run 으로 입력만 만들 수 있습니다.")
        llm = LLM(api_key)
    targets = list(ciks or [])
    if all_universe:
        targets += [
            int(n["listing"]["cik"])
            for n in graph["nodes"]
            if n["kind"] == "company" and n.get("in_universe") and (n.get("listing") or {}).get("cik")
        ]
    results = []
    for cik in dict.fromkeys(targets):
        try:
            results.append(build_one(store, http, llm, cik, as_of, opt, graph))
        except Exception as exc:  # noqa: BLE001
            log.error("[%s] moat failed before LLM: %s", cik, exc)
            results.append({"cik": cik, "status": "failed", "error": str(exc)[:400]})
    return results


def ticker_to_cik(graph: dict[str, Any], ticker: str) -> int | None:
    for n in graph["nodes"]:
        if n["kind"] == "company" and (n.get("listing") or {}).get("ticker") == ticker.upper():
            return (n.get("listing") or {}).get("cik")
    return None
