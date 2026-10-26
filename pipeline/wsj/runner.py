"""CLI.

  python -m wsj list
  python -m wsj run sec_form4 [--since 2026-10-01] [--until 2026-10-23] [--limit 50]
  python -m wsj run --all
  python -m wsj entities resolve

러너가 하는 일: 워터마크 읽기 → run() → ops.collector_runs 기록 → 워터마크 갱신.
수집기 예외는 잡아서 failed 로 남기고 다음으로 넘어간다 (ADR-0003 §7).
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from datetime import date

from wsj.collectors import all_collectors, get_collector
from wsj.collectors.base import RunContext, RunResult
from wsj.config import load_settings
from wsj.db import make_store
from wsj.http import HttpClient
from wsj.util import parse_date

log = logging.getLogger("wsj")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def run_one(name: str, ctx: RunContext) -> RunResult | None:
    collector = get_collector(name)
    store = ctx.store
    if collector.schedule == "paused":
        log.info("[%s] paused — skipped", name)
        return None
    if collector.needs_universe and not store.select(
        "core.companies", ["cik"], {"in_universe": True}, limit=1
    ):
        log.warning("[%s] core.companies 에 유니버스가 없어 건너뜀. 먼저 `run sec_universe`", name)
        run_id = store.run_started(name, _params(ctx))
        store.run_finished(run_id, "skipped", 0, None, "universe empty")
        return None

    ctx.watermark = store.get_watermark(name)
    run_id = store.run_started(name, _params(ctx))
    log.info(
        "[%s] start (watermark=%s since=%s until=%s limit=%s)",
        name,
        ctx.watermark,
        ctx.since,
        ctx.until,
        ctx.limit,
    )
    try:
        result = collector.run(ctx)
    except Exception as exc:  # noqa: BLE001 - 실패 격리가 목적
        err = "".join(traceback.format_exception(exc))
        log.error("[%s] FAILED: %s", name, exc)
        store.run_finished(run_id, "failed", 0, None, err)
        return "failed"
    if result.watermark is not None and not ctx.limit:
        # --limit 스모크 실행은 워터마크를 건드리지 않는다
        store.set_watermark(name, result.watermark)
    store.run_finished(run_id, "succeeded", result.rows, result.watermark, "\n".join(result.notes) or None)
    log.info(
        "[%s] done rows=%d watermark=%s %s", name, result.rows, result.watermark, "; ".join(result.notes)
    )
    return result


def _params(ctx: RunContext) -> dict:
    return {
        "since": ctx.since and ctx.since.isoformat(),
        "until": ctx.until and ctx.until.isoformat(),
        "limit": ctx.limit,
    }


def cmd_list() -> int:
    for c in all_collectors():
        print(f"{c.name:<18} {c.schedule:<8} {', '.join(c.tables)}")
        if c.description:
            print(f"{'':<18} {c.description}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    settings = load_settings()
    _setup_logging(settings.wsj_log_level)
    if args.store:
        settings.wsj_store = args.store
    names = [c.name for c in all_collectors()] if args.all else args.names
    if not names:
        print("수집기 이름을 주거나 --all 을 쓰세요. `python -m wsj list`", file=sys.stderr)
        return 2
    store = make_store(settings)
    http = HttpClient(user_agent=settings.sec_user_agent)
    failed = 0
    try:
        for name in names:
            ctx = RunContext(
                settings=settings,
                http=http,
                store=store,
                since=parse_date(args.since) if args.since else None,
                until=parse_date(args.until) if args.until else None,
                limit=args.limit,
            )
            try:
                status = run_one(name, ctx)
            except Exception as exc:  # noqa: BLE001 - 북키핑(워터마크·런 로그) 단계의 실패도 격리
                log.error("[%s] runner error: %s", name, exc)
                status = "failed"
            if status == "failed":
                failed += 1
    finally:
        http.close()
        store.close()
    log.info("http stats: %s", http.stats)
    return 1 if failed else 0


def cmd_entities(args: argparse.Namespace) -> int:
    settings = load_settings()
    _setup_logging(settings.wsj_log_level)
    if args.store:
        settings.wsj_store = args.store
    store = make_store(settings)
    try:
        if args.entities_cmd == "resolve":
            from wsj.entities.resolve import resolve_all

            summary = resolve_all(store, dry_run=args.dry_run)
            for k, v in summary.items():
                print(f"{k}: {v}")
            return 0
    finally:
        store.close()
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wsj", description="WSJ-investment 데이터 수집 파이프라인")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="수집기 목록")

    r = sub.add_parser("run", help="수집기 실행")
    r.add_argument("names", nargs="*", help="수집기 이름")
    r.add_argument("--all", action="store_true", help="레지스트리 순서대로 전부 실행")
    r.add_argument("--since", help="시작일 YYYY-MM-DD (워터마크 무시)")
    r.add_argument("--until", help="종료일 YYYY-MM-DD (기본 오늘)")
    r.add_argument("--limit", type=int, help="스모크 테스트 상한. 지정 시 워터마크를 갱신하지 않음")
    r.add_argument("--store", choices=["postgrest", "sqlite"], help="WSJ_STORE 덮어쓰기")

    e = sub.add_parser("entities", help="엔티티 매칭")
    es = e.add_subparsers(dest="entities_cmd", required=True)
    rs = es.add_parser("resolve", help="raw 의 소스별 이름을 core.entity_aliases 로 매칭")
    rs.add_argument("--dry-run", action="store_true")
    rs.add_argument("--store", choices=["postgrest", "sqlite"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "entities":
        return cmd_entities(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "run_one", "RunContext", "date"]
