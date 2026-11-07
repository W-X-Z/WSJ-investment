"""도구 공용 컨텍스트: 페처(네트워크), 읽기 전용 DB(있으면), 기준일, 실행 중 메모.

    from wsj.tools import quote, open_context
    with open_context() as ctx:          # 여러 도구를 연달아 쓸 때 HTTP 연결·환율·티커 목록을 재사용
        a = quote("FPS", ctx=ctx)
        b = quote("001440", ctx=ctx)
    quote("FPS")                          # ctx 없이 부르면 알아서 열고 닫는다

DB 는 SUPABASE_URL·SUPABASE_SECRET_KEY 가 있을 때만 붙고, select 만 노출한 래퍼로 감싼다 (도구는 DB 에 쓰지 않는다).
키가 없거나 DB 가 응답하지 않으면 조용히 라이브 출처로 간다 — 결과의 source 필드에 어디서 왔는지 남는다.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

log = logging.getLogger("wsj.tools")


class ToolError(Exception):
    """입력이 잘못됐거나 어떤 출처에서도 값을 못 얻었을 때. CLI 는 {"error": ...} 로 내보내고 종료코드 1."""


class ReadOnlyStore:
    """Store 의 select 만 통과시킨다."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def select(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self._inner.select(*args, **kwargs)

    def close(self) -> None:
        try:
            self._inner.close()
        except Exception:  # noqa: BLE001
            pass


@dataclass
class ToolContext:
    fetch: Any                      # wsj.tools.fetch.Fetchers 또는 테스트용 가짜
    store: Any | None = None        # ReadOnlyStore | None
    today: date = field(default_factory=date.today)
    use_px_cache: bool = True       # raw.px_daily 를 먼저 볼지 (--live 면 False)
    memo: dict[str, Any] = field(default_factory=dict)
    _closers: list[Any] = field(default_factory=list)

    def db_select(self, table: str, columns: list[str] | None = None, filters: dict[str, Any] | None = None,
                  order: str | None = None, limit: int | None = None) -> list[dict[str, Any]] | None:
        """DB 가 없거나 실패하면 None (빈 결과 [] 와 구분)."""
        if self.store is None:
            return None
        try:
            return self.store.select(table, columns, filters, limit=limit, order=order)
        except Exception as exc:  # noqa: BLE001 - DB 실패는 라이브 경로로 대체
            log.warning("db select %s failed: %s", table, str(exc)[:160])
            return None

    def close(self) -> None:
        for c in self._closers:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        self._closers.clear()


def _readonly_store(settings: Any) -> ReadOnlyStore | None:
    try:
        if settings.wsj_store == "sqlite":
            if not settings.wsj_sqlite_path.exists():
                return None
            from wsj.db.sqlite import SqliteStore

            return ReadOnlyStore(SqliteStore(settings.wsj_sqlite_path))
        if not (settings.supabase_url and settings.supabase_secret_key):
            return None
        from wsj.db.postgrest import PostgrestStore

        return ReadOnlyStore(PostgrestStore(settings.supabase_url, settings.supabase_secret_key, timeout=30.0))
    except Exception as exc:  # noqa: BLE001
        log.warning("store unavailable: %s", str(exc)[:160])
        return None


def new_context(db: bool = True, live: bool = False, today: date | None = None) -> ToolContext:
    from wsj.config import load_settings
    from wsj.http import HttpClient
    from wsj.tools.fetch import BROWSER_UA, Fetchers

    settings = load_settings()
    http = HttpClient(BROWSER_UA, timeout=25.0, max_retries=1)
    fetch = Fetchers(http, settings.sec_user_agent, settings.wsj_data_dir / "cache")
    store = _readonly_store(settings) if db else None
    ctx = ToolContext(fetch=fetch, store=store, today=today or date.today(), use_px_cache=not live)
    ctx._closers += [http] + ([store] if store else [])
    return ctx


@contextmanager
def open_context(db: bool = True, live: bool = False, today: date | None = None) -> Iterator[ToolContext]:
    ctx = new_context(db=db, live=live, today=today)
    try:
        yield ctx
    finally:
        ctx.close()


@contextmanager
def ensure_context(ctx: ToolContext | None) -> Iterator[ToolContext]:
    if ctx is not None:
        yield ctx
        return
    with open_context() as c:
        yield c


def parse_day(v: str | date | None, default: date | None = None) -> date | None:
    if v is None or v == "":
        return default
    if isinstance(v, date):
        return v
    from wsj.util import parse_date

    d = parse_date(str(v))
    if d is None:
        raise ToolError(f"날짜 형식을 읽을 수 없습니다: {v!r} (YYYY-MM-DD)")
    return d
