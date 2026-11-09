"""1·2단계 실행: 'screen:YYYY-MM-DD' → 경로·후보·반응·선별 → 'candidates:YYYY-MM-DD' (research.reports kind='screen').

    python -m wsj monitor run [--date 2026-11-10] [--max-events 10] [--searches 3] [--plan] [--dry-run] [--out f.json]
    python -m wsj monitor queue [--days 7]                       3단계 대기열(selected·requested, done 제외)
    python -m wsj monitor mark CANDIDATE_ID --status done [--idea idea:us:fps:2026-11-10] [--date …]

비용(추정): 진행 사건당 중형 모델 1회 + 웹 검색 ≤3회 ≈ $0.05~0.1, 선별 1회 ≈ $0.03 → 하루 진행 사건 10건이면 ≈ $1.
상한: --max-events(기본 10), MONITOR_MAX_USD(기본 $2) — 넘을 것 같으면 남은 사건은 다음 날로 넘기지 않고 이 보고서에 skipped 로 남긴다.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from typing import Any

from wsj.monitor import candidates as CA
from wsj.monitor import paths as PA
from wsj.monitor import pick as PK

log = logging.getLogger("wsj.monitor")

CREATED_BY = "monitor-v3"
STATUSES = ("open", "selected", "requested", "done", "dropped")


def kst_today() -> str:
    from datetime import UTC, datetime

    return (datetime.now(UTC) + timedelta(hours=9)).date().isoformat()


def load_screen(store: Any, as_of: str) -> dict[str, Any] | None:
    for d in (as_of, (date.fromisoformat(as_of) - timedelta(days=1)).isoformat()):
        rows = store.select("research.reports", ["report_id", "as_of", "body"], {"report_id": f"screen:{d}"}, limit=1)
        if rows:
            return rows[0]
    return None


def event_dates(store: Any, events: list[dict[str, Any]]) -> None:
    ids = sorted({c for e in events for c in e.get("clue_ids") or []})
    if not ids:
        return
    try:
        rows = store.select("ideas.clues", ["clue_id", "published_at", "seen_at"], {"clue_id": ids[:300]})
    except Exception as exc:  # noqa: BLE001
        log.warning("clue dates failed: %s", str(exc)[:120])
        return
    when = {r["clue_id"]: (r.get("published_at") or r.get("seen_at") or "")[:10] for r in rows}
    for e in events:
        ds = sorted(d for d in (when.get(c) for c in e.get("clue_ids") or []) if d)
        e["date"] = ds[0] if ds else None


def run(store: Any, llm: Any | None, ctx: Any, as_of: str, max_events: int = 10, max_searches: int = 3,
        n_pick: int = PK.MAX_PICK, max_usd: float = 2.0, path_model: str = PA.PATH_MODEL,
        pick_model: str = PK.PICK_MODEL) -> dict[str, Any]:
    scr = load_screen(store, as_of)
    if scr is None:
        return {"error": f"선별 보고서 screen:{as_of} 없음 — python -m wsj screen 을 먼저"}
    events = [e for e in (scr["body"].get("events") or []) if e.get("proceed")]
    event_dates(store, events)
    for e in events:
        e["date"] = e.get("date") or scr["as_of"]
    todo, skipped = events[:max_events], events[max_events:]
    explored, cands, spent = [], [], 0.0
    for e in todo:
        if llm is None:
            explored.append({"event_id": e["event_id"], "title": e["title"], "planned": True})
            continue
        if spent >= max_usd:
            skipped.append(e)
            continue
        graph = PA.graph_context(store, e.get("entities") or [])
        try:
            x = PA.explore(llm, e, graph, model=path_model, max_searches=max_searches)
        except Exception as exc:  # noqa: BLE001 - 한 사건 실패가 나머지를 막지 않게
            log.warning("explore %s failed: %s", e["event_id"], str(exc)[:160])
            explored.append({"event_id": e["event_id"], "title": e["title"], "error": str(exc)[:200]})
            continue
        spent += (x.get("usage") or {}).get("cost_usd") or 0.0
        explored.append({"event_id": e["event_id"], "title": e["title"], "date": e["date"], **x})
        cands += CA.resolve(ctx, e["event_id"], e, x)
    for c in cands:
        if c["role"] == "beneficiary":
            c["reaction"] = PK.reaction(ctx, c["symbol"] if c["market"] == "us" else c["symbol"], c.get("event_date"))
    chosen = {"picks": [], "usage": None}
    if llm is not None and cands:
        chosen = PK.choose(llm, cands, n=n_pick, model=pick_model)
        PK.apply_picks(cands, chosen["picks"])
        spent += (chosen.get("usage") or {}).get("cost_usd") or 0.0
    body = {"type": "candidates", "screen_report": scr["report_id"], "events": explored,
            "skipped_events": [{"event_id": e["event_id"], "title": e["title"]} for e in skipped],
            "candidates": cands, "pick_note": chosen.get("skipped_note"),
            "usage": {"cost_usd": round(spent, 4), "events_explored": sum(1 for x in explored if "paths" in x)}}
    n_sel = sum(1 for c in cands if c["status"] == "selected")
    subjects = sorted({f"ticker:{c['market']}:{c['symbol'].lower()}" for c in cands})[:40]
    return {"report_id": f"candidates:{as_of}", "kind": "screen", "as_of": as_of,
            "title": f"{as_of} 후보: 사건 {len(explored)} · 후보 {len(cands)} · 선택 {n_sel}",
            "subjects": subjects, "body": body, "created_by": CREATED_BY}


def save(store: Any, row: dict[str, Any]) -> dict[str, Any]:
    res = store.rpc("research.put_reports", {"rows": [row]}) or {}
    if res.get("rejected"):
        raise RuntimeError(f"research.put_reports 거부: {res['rejected']}")
    return res


# ── 대기열 ────────────────────────────────────────────────────────────────────

def recent_reports(store: Any, days: int = 7, as_of: str | None = None) -> list[dict[str, Any]]:
    since = (date.fromisoformat(as_of or kst_today()) - timedelta(days=days)).isoformat()
    rows = store.select("research.reports", ["report_id", "kind", "title", "as_of", "subjects", "body", "created_by"],
                        {"kind": "screen", "as_of": ("gte", since)}, order="as_of.desc")
    return [r for r in rows if str(r["report_id"]).startswith("candidates:")]


def queue(store: Any, days: int = 7, as_of: str | None = None) -> list[dict[str, Any]]:
    out = []
    for r in recent_reports(store, days, as_of):
        for c in (r["body"] or {}).get("candidates") or []:
            if c.get("status") in ("selected", "requested"):
                out.append({"report_id": r["report_id"], **c})
    order = {"requested": 0, "selected": 1}
    return sorted(out, key=lambda c: (order[c["status"]], c["report_id"]), reverse=False)


def mark(store: Any, cand_id: str, status: str, idea: str | None = None, as_of: str | None = None,
         days: int = 14) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status 는 {STATUSES}")
    for r in recent_reports(store, days, as_of):
        cs = (r["body"] or {}).get("candidates") or []
        hit = next((c for c in cs if c.get("id") == cand_id), None)
        if hit is None:
            continue
        hit["status"] = status
        if idea:
            hit["idea_report"] = idea
        row = {"report_id": r["report_id"], "kind": r["kind"], "title": r["title"], "as_of": r["as_of"], "body": r["body"]}
        save(store, row)
        return {"report_id": r["report_id"], "candidate": hit}
    raise LookupError(f"후보 {cand_id} 를 최근 {days}일 candidates 보고서에서 찾지 못했다")


# ── CLI ───────────────────────────────────────────────────────────────────────

def add_parser(sub: Any) -> None:
    m = sub.add_parser("monitor", help="1·2단계: 진행 사건 → 경로 → 후보 → 반응 → 선택 (candidates:YYYY-MM-DD)")
    ms = m.add_subparsers(dest="monitor_cmd", required=True)
    r = ms.add_parser("run")
    r.add_argument("--date", help="기준일 KST (기본 오늘)")
    r.add_argument("--max-events", type=int, default=10)
    r.add_argument("--searches", type=int, default=3, help="사건당 웹 검색 상한")
    r.add_argument("--pick", type=int, default=PK.MAX_PICK)
    r.add_argument("--max-usd", type=float, default=2.0)
    r.add_argument("--plan", action="store_true", help="모델을 부르지 않고 진행 사건만")
    r.add_argument("--dry-run", action="store_true", help="모델은 부르되 저장하지 않는다")
    r.add_argument("--out")
    q = ms.add_parser("queue")
    q.add_argument("--days", type=int, default=7)
    k = ms.add_parser("mark")
    k.add_argument("candidate_id")
    k.add_argument("--status", required=True, choices=STATUSES)
    k.add_argument("--idea", help="이 후보로 만든 리포트 id (idea:…)")
    k.add_argument("--date")


def cli(args: Any) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.config import load_settings
    from wsj.db import make_store
    from wsj.tools.cli import emit
    from wsj.tools.context import open_context

    settings = load_settings()
    settings.require_supabase()
    store = make_store(settings)
    try:
        if args.monitor_cmd == "queue":
            emit({"tool": "monitor.queue", "queue": queue(store, args.days)})
            return 0
        if args.monitor_cmd == "mark":
            emit({"tool": "monitor.mark", **mark(store, args.candidate_id, args.status, args.idea, args.date)})
            return 0
        llm = None
        if not args.plan:
            if not settings.anthropic_api_key:
                raise SystemExit("ANTHROPIC_API_KEY 가 없다 (--plan 은 키 없이)")
            from wsj.briefs.llm import LLM

            llm = LLM(settings.anthropic_api_key)
        as_of = args.date or kst_today()
        with open_context() as ctx:
            row = run(store, llm, ctx, as_of, max_events=args.max_events, max_searches=args.searches, n_pick=args.pick,
                      max_usd=args.max_usd)
        if "error" in row:
            emit({"tool": "monitor.run", **row})
            return 1
        if args.out:
            with open(args.out, "w") as f:
                json.dump(row, f, ensure_ascii=False, indent=1, default=str)
        saved = None
        if not args.plan and not args.dry_run:
            saved = save(store, row)
        b = row["body"]
        emit({"tool": "monitor.run", "report_id": row["report_id"], "title": row["title"], "saved": saved,
              "usage": b["usage"], "selected": [{k: c.get(k) for k in ("id", "symbol", "name", "headline", "pick_reason")}
                                                for c in b["candidates"] if c["status"] == "selected"],
              "events": [{k: x.get(k) for k in ("event_id", "title", "headline", "error", "planned")} for x in b["events"]]})
        return 0
    finally:
        store.close()
