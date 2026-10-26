"""`wsj briefs build` — 후보 → 데이터팩 → 리서치 → 종합 → 비평 → ideas.briefs / ideas.predictions. ADR-0009 §1·§4.

--dry-run: LLM 없이 데이터팩과 세 단계의 프롬프트를 파일로 떨어뜨린다 (프롬프트 검토·비용 추정용).
실패는 종목 단위로 격리한다: 한 종목의 예외는 status='failed' 행으로 남기고 다음 종목으로 간다.
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
from wsj.briefs.llm import LLM, Completion, JSONGenerationError, resolve_model, sum_usage
from wsj.db.base import Store
from wsj.http import HttpClient

log = logging.getLogger("wsj.briefs")


@dataclass
class BriefOptions:
    model: str = "haiku"  # 기본: Haiku, 정밀 검토 시 --model sonnet
    research_model: str = "haiku"
    critique_model: str = "haiku"
    research_searches: int = 4
    effort: str = "medium"
    skip_research: bool = False
    skip_critique: bool = False
    synthesis_max_tokens: int = 20_000
    thinking_budget: int = 0  # 레거시 모델 옵션, Claude 5.5는 effort 사용
    dry_run: bool = False
    out_dir: Path | None = None
    force: bool = False  # 같은 as_of 에 이미 브리프가 있어도 다시 만든다


def _business_summary(dp: DataPack, n: int = 2500) -> str:
    for key in ("item_1", "mdna", "full"):
        for d in dp.documents:
            if d["section"] == key:
                return d["text"][:n]
    return "(사업 설명 원문 없음)"


def _token_estimate(text: str) -> int:
    # 영어 ~4자/토큰, 한글 ~1.5자/토큰 — 대략 혼합 3.2자/토큰
    return int(len(text) / 3.2)


def write_dry_run(dp: DataPack, out_dir: Path, as_of: date) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    core, full = dp.render_core(), dp.render_full()
    summary = _business_summary(dp)
    files = {
        "datapack.md": full,
        "datapack.json": dp.to_json(),
        "prompt_1_research.md": "# SYSTEM\n\n"
        + prompts.RESEARCH_SYSTEM
        + "\n\n# USER\n\n"
        + prompts.research_user(core, summary, as_of.isoformat()),
        "prompt_2_synthesis.md": "# SYSTEM\n\n"
        + prompts.SYNTHESIS_SYSTEM
        + "\n\n# USER\n\n"
        + prompts.synthesis_user(full, "{ ... 리서치 JSON ... }", as_of.isoformat()),
        "prompt_3_critique.md": "# SYSTEM\n\n"
        + prompts.CRITIQUE_SYSTEM
        + "\n\n# USER\n\n"
        + prompts.critique_user(
            core, "{ ... 브리프 JSON ... }", "{ ... 리서치 JSON ... }", as_of.isoformat()
        ),
    }
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    est = {
        "core_chars": len(core),
        "full_chars": len(full),
        "research_input_tokens_est": _token_estimate(prompts.RESEARCH_SYSTEM + core + summary),
        "synthesis_input_tokens_est": _token_estimate(prompts.SYNTHESIS_SYSTEM + full) + 3000,
        "critique_input_tokens_est": _token_estimate(prompts.CRITIQUE_SYSTEM + core) + 8000,
        "documents": [(d["form"], d["section"], d["char_count"]) for d in dp.documents],
        "notes": dp.notes,
    }
    (out_dir / "estimate.json").write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")
    return est


def _predictions_rows(brief_id: Any, cik: int, brief: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in brief.get("predictions") or []:
        if not isinstance(p, dict) or not p.get("claim") or not p.get("due_date"):
            continue
        rows.append(
            {
                "brief_id": brief_id,
                "cik": cik,
                "claim": str(p["claim"])[:1000],
                "measurable": (str(p.get("measurable")) if p.get("measurable") else None),
                "due_date": str(p["due_date"])[:10],
                "scenario": p.get("scenario"),
            }
        )
    for f in brief.get("falsifiers") or []:
        if not isinstance(f, dict) or not f.get("statement") or not f.get("check_by"):
            continue
        rows.append(
            {
                "brief_id": brief_id,
                "cik": cik,
                "claim": "[반증] " + str(f["statement"])[:980],
                "measurable": " / ".join(str(f.get(k)) for k in ("metric", "threshold") if f.get(k)) or None,
                "due_date": str(f["check_by"])[:10],
                "scenario": "falsifier",
            }
        )
    return rows


def _scores(brief: dict[str, Any], critique: dict[str, Any] | None) -> dict[str, Any]:
    s = dict(brief.get("scores") or {})
    if critique:
        fs = critique.get("final_scores") or {}
        s["final_conviction"] = fs.get("conviction")
        s["final_asymmetry"] = fs.get("asymmetry")
        s["verdict"] = critique.get("verdict")
        adj = critique.get("scenario_probability_adjustments") or {}
        s["risk_probabilities"] = {k: adj.get(k) for k in ("bull", "base", "bear")}
    sc = brief.get("scenarios") or {}
    s["analyst_probabilities"] = {k: (sc.get(k) or {}).get("probability") for k in ("bull", "base", "bear")}
    return s


def build_one(
    store: Store, http: HttpClient, llm: LLM | None, cik: int, as_of: date, opt: BriefOptions
) -> dict[str, Any]:
    dp = build_datapack(store, http, cik, as_of)
    ticker = dp.ticker or str(cik)
    log.info(
        "[%s] datapack: docs=%d signals=%d insider=%d px=%s notes=%s",
        ticker,
        len(dp.documents),
        len(dp.signals),
        len(dp.insider),
        dp.prices.get("available"),
        dp.notes,
    )

    if opt.dry_run or llm is None:
        out_dir = (opt.out_dir or Path("data/briefs")) / f"{ticker}_{as_of.isoformat()}"
        est = write_dry_run(dp, out_dir, as_of)
        log.info(
            "[%s] dry-run written to %s (synthesis ≈ %d input tokens)",
            ticker,
            out_dir,
            est["synthesis_input_tokens_est"],
        )
        return {"cik": cik, "ticker": ticker, "dry_run": True, "out_dir": str(out_dir), **est}

    existing = store.select("ideas.briefs", ["id", "version", "as_of", "status"], {"cik": cik})
    if not opt.force and any(
        str(r.get("as_of")) == as_of.isoformat() and r.get("status") != "failed" for r in existing
    ):
        log.info("[%s] brief for %s exists — skip (use --force)", ticker, as_of)
        return {"cik": cik, "ticker": ticker, "skipped": True}
    version = 1 + max((int(r.get("version") or 0) for r in existing), default=0)

    core, full = dp.render_core(), dp.render_full()
    comps: dict[str, list[Completion]] = {}
    research: dict[str, Any] = {}
    brief: dict[str, Any] = {}
    critique: dict[str, Any] | None = None
    error: str | None = None

    def call_stage(stage: str, system: str, user: str, model: str, **kwargs: Any) -> dict[str, Any]:
        assert llm is not None
        try:
            result, calls = llm.complete_json(system, user, model, prompts.REPAIR_USER, **kwargs)
        except JSONGenerationError as exc:
            comps[stage] = exc.completions
            raise
        comps[stage] = calls
        return result

    try:
        # ② 리서치
        if not opt.skip_research:
            research = call_stage(
                "research",
                prompts.RESEARCH_SYSTEM,
                prompts.research_user(core, _business_summary(dp), as_of.isoformat()),
                resolve_model(opt.research_model),
                max_tokens=8000,
                web_search_max_uses=opt.research_searches,
                effort="medium",
            )
            research["_citations"] = comps["research"][0].citations[:60]
        research_json = (
            json.dumps(research, ensure_ascii=False, indent=1) if research else "(리서치 단계 생략)"
        )

        # ③ 종합
        brief = call_stage(
            "synthesis",
            prompts.SYNTHESIS_SYSTEM,
            prompts.synthesis_user(full, research_json, as_of.isoformat()),
            resolve_model(opt.model),
            max_tokens=opt.synthesis_max_tokens,
            thinking_budget=opt.thinking_budget or None,
            effort=opt.effort,
            minimize_thinking=True,
        )

        # ④ 비평
        if not opt.skip_critique:
            critique = call_stage(
                "critique",
                prompts.CRITIQUE_SYSTEM,
                prompts.critique_user(
                    core, json.dumps(brief, ensure_ascii=False, indent=1), research_json, as_of.isoformat()
                ),
                resolve_model(opt.critique_model),
                max_tokens=8000,
                thinking_budget=min(opt.thinking_budget, 4000) or None,
                effort="low",
                minimize_thinking=True,
            )
    except Exception as exc:  # noqa: BLE001 - 종목 단위 격리
        error = "".join(traceback.format_exception(exc))[-4000:]
        log.error("[%s] brief failed: %s", ticker, exc)

    usage = {k: [x.usage() for x in v] for k, v in comps.items()}
    usage["total"] = sum_usage([x for v in comps.values() for x in v])
    row = {
        "cik": cik,
        "ticker": dp.ticker,
        "as_of": as_of.isoformat(),
        "version": version,
        "status": "failed" if error else "final",
        "title": (brief.get("title") or None) if brief else None,
        "brief": brief or None,
        "research": research or None,
        "critique": critique,
        "datapack_summary": dp.summary(),
        "scores": _scores(brief, critique) if brief else None,
        "model": resolve_model(opt.model),
        "prompt_version": prompts.PROMPT_VERSION,
        "usage": usage,
        "error": error,
    }
    saved = store.insert_returning("ideas.briefs", row)
    brief_id = saved.get("id")
    n_pred = 0
    if brief and brief_id is not None:
        preds = _predictions_rows(brief_id, cik, brief)
        if preds:
            n_pred = store.insert("ideas.predictions", preds)
    if not error and brief and dp.candidate:
        _mark_briefed(store, dp.candidate)
    log.info(
        "[%s] brief #%s v%d %s — predictions %d, cost $%s",
        ticker,
        brief_id,
        version,
        row["status"],
        n_pred,
        usage["total"]["cost_usd"],
    )
    if opt.out_dir:
        out_dir = opt.out_dir / f"{ticker}_{as_of.isoformat()}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "brief.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
    return {
        "cik": cik,
        "ticker": ticker,
        "brief_id": brief_id,
        "version": version,
        "status": row["status"],
        "predictions": n_pred,
        "usage": usage["total"],
        "title": row["title"],
    }


def _mark_briefed(store: Store, candidate: dict[str, Any]) -> None:
    """candidates.status → briefed (dismissed 는 건드리지 않는다). upsert 는 전체 행을 요구하므로 기존 행을 그대로 보낸다."""
    if candidate.get("status") == "dismissed":
        return
    row = {k: v for k, v in candidate.items()}
    row["status"] = "briefed"
    store.upsert("core.candidates", [row], ["cik"])


def select_targets(
    store: Store, ciks: list[int] | None, top: int | None, statuses: tuple[str, ...] = ("new", "watch")
) -> list[int]:
    if ciks:
        return ciks
    rows = store.select(
        "core.candidates", ["cik", "score", "status"], {"status": list(statuses)}, order="score.desc"
    )
    out = [int(r["cik"]) for r in rows]
    return out[:top] if top else out


def build(
    store: Store,
    http: HttpClient,
    api_key: str | None,
    as_of: date | None,
    ciks: list[int] | None,
    top: int | None,
    opt: BriefOptions,
) -> list[dict[str, Any]]:
    as_of = as_of or date.today()
    llm = None
    if not opt.dry_run:
        if not api_key:
            raise SystemExit(
                "ANTHROPIC_API_KEY 가 없습니다. --dry-run 으로 데이터팩·프롬프트만 만들거나 pipeline/.env 에 키를 넣으세요."
            )
        llm = LLM(api_key)
    targets = select_targets(store, ciks, top)
    if not targets:
        log.warning("대상 없음 (candidates status new/watch 가 비어 있음). --cik 로 지정 가능")
    results: list[dict[str, Any]] = []
    for cik in targets:
        try:
            results.append(build_one(store, http, llm, cik, as_of, opt))
        except Exception as exc:  # noqa: BLE001 - 데이터팩 단계의 실패도 격리
            log.error("[%s] failed before LLM: %s", cik, exc)
            results.append({"cik": cik, "status": "failed", "error": str(exc)[:500]})
    return results
