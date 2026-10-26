"""Store 프로토콜 — 수집기가 DB에 대해 아는 전부. ADR-0003 참조.

테이블 이름은 항상 'schema.table'. 필터는 단순 동등/IN/비교만 지원한다:
    {"in_universe": True}                 -> eq
    {"cik": [1, 2, 3]}                    -> in
    {"file_date": ("gte", "2026-10-01")}  -> gte|gt|lte|lt|neq
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

Filters = dict[str, Any]


class Store(Protocol):
    def upsert(self, table: str, rows: list[dict[str, Any]], conflict: Sequence[str]) -> int:
        """자연키(conflict) 기준 upsert. 반환값은 보낸 행 수."""
        ...

    def insert(self, table: str, rows: list[dict[str, Any]]) -> int:
        """순수 insert (append-only 테이블용)."""
        ...

    def insert_returning(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """한 행 insert 후 DB 가 채운 값(identity id 등)을 포함한 행을 돌려준다."""
        ...

    def select(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        filters: Filters | None = None,
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def delete(self, table: str, filters: Filters) -> None: ...

    # --- 러너 전용 ----------------------------------------------------------
    def get_watermark(self, collector: str) -> dict[str, Any]: ...

    def set_watermark(self, collector: str, watermark: dict[str, Any]) -> None: ...

    def run_started(self, collector: str, params: dict[str, Any]) -> int: ...

    def run_finished(
        self, run_id: int, status: str, rows: int, watermark: dict[str, Any] | None, error: str | None
    ) -> None: ...

    def close(self) -> None: ...


def split_table(table: str) -> tuple[str, str]:
    if "." not in table:
        raise ValueError(f"table must be 'schema.table', got {table!r}")
    schema, name = table.split(".", 1)
    return schema, name
