"""수집기 규약. ADR-0003 참조.

새 수집기 = 이 파일의 Collector 를 상속한 클래스 하나 + registry 등록 한 줄 + 마이그레이션.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from wsj.config import Settings
from wsj.db.base import Store
from wsj.http import HttpClient


@dataclass
class RunContext:
    settings: Settings
    http: HttpClient
    store: Store
    since: date | None = None  # --since: 워터마크 대신 강제 시작점
    until: date | None = None  # --until: 기본 오늘
    limit: int | None = None  # --limit: 스모크 테스트용 상한 (행/페이지)
    watermark: dict[str, Any] = field(default_factory=dict)
    log: logging.Logger = field(default_factory=lambda: logging.getLogger("wsj"))

    def today(self) -> date:
        return self.until or date.today()


@dataclass
class RunResult:
    rows: int = 0
    watermark: dict[str, Any] | None = None  # None 이면 워터마크를 갱신하지 않는다
    notes: list[str] = field(default_factory=list)

    def add(self, n: int) -> None:
        self.rows += n


class Collector:
    """서브클래스는 name/tables/schedule 과 run() 을 정의한다."""

    name: str = ""
    tables: tuple[str, ...] = ()
    schedule: str = ""  # 문서용: 'daily' | 'weekly' | 'monthly' | 'manual' | 'paused'
    description: str = ""
    needs_universe: bool = False  # True 면 core.companies(in_universe) 가 비어 있을 때 건너뜀

    def run(self, ctx: RunContext) -> RunResult:  # pragma: no cover - 인터페이스
        raise NotImplementedError

    # --- 공용 헬퍼 -------------------------------------------------------------

    @staticmethod
    def universe(
        ctx: RunContext, columns: tuple[str, ...] = ("cik", "ticker", "name", "sector_bucket")
    ) -> list[dict]:
        rows = ctx.store.select("core.companies", list(columns), {"in_universe": True})
        return rows

    @staticmethod
    def start_date(ctx: RunContext, wm_key: str, default_lookback_days: int) -> date:
        """--since > 워터마크 > (오늘 - lookback) 순으로 시작일 결정."""
        from datetime import timedelta

        from wsj.util import parse_date

        if ctx.since:
            return ctx.since
        wm = ctx.watermark.get(wm_key)
        d = parse_date(wm) if wm else None
        return d or (ctx.today() - timedelta(days=default_lookback_days))
