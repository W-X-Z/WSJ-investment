"""Supabase PostgREST 구현. HTTPS 만으로 동작하므로 샌드박스·CI 에서도 쓸 수 있다.

- upsert: POST /rest/v1/<table>?on_conflict=a,b  + Prefer: resolution=merge-duplicates
- 스키마 선택: Content-Profile / Accept-Profile 헤더 (0001 마이그레이션에서 raw/core/ops 노출)
"""

from __future__ import annotations

import json
import logging
import socket
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from wsj.db.base import Filters, split_table
from wsj.util import chunked

log = logging.getLogger(__name__)

UPSERT_CHUNK = 500
IN_CHUNK = 150  # URL 길이 보호


def _json_default(o: Any) -> Any:
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"not serializable: {type(o)}")


class PostgrestError(RuntimeError):
    """PostgREST 4xx/5xx. status·code(PGRST202 등)를 들고 있어 호출하는 쪽이 '함수 없음'과 다른 실패를 가를 수 있다.
    RuntimeError 를 이어받아 예전 except RuntimeError 경로는 그대로 동작한다."""

    def __init__(self, message: str, status: int, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def _encode_filter_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    return str(v)


class PostgrestStore:
    def __init__(self, url: str, secret_key: str, timeout: float = 120.0) -> None:
        self.base = url.rstrip("/") + "/rest/v1"
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    # --- 내부 -----------------------------------------------------------------

    def _req(
        self,
        method: str,
        table: str,
        *,
        params: dict | None = None,
        body: Any = None,
        prefer: str | None = None,
    ):
        schema, name = split_table(table)
        headers = {"Accept-Profile": schema, "Content-Profile": schema}
        if prefer:
            headers["Prefer"] = prefer
        content = json.dumps(body, default=_json_default) if body is not None else None
        resp = self._client.request(
            method, f"{self.base}/{name}", params=params, content=content, headers=headers
        )
        if resp.status_code >= 400:
            code = None
            try:
                code = (resp.json() or {}).get("code")
            except ValueError:
                pass
            raise PostgrestError(f"PostgREST {method} {table} -> {resp.status_code}: {resp.text[:500]}", resp.status_code, code)
        return resp

    def rpc(self, fn: str, args: dict[str, Any], schema: str | None = None) -> Any:
        """POST /rest/v1/rpc/<function> + Content-Profile: <schema>. 두 호출 모양을 다 받는다:
        store.rpc("research.put_reports", {"rows": [...]}) · store.rpc("put_reports", {"rows": [...]}, schema="research").
        스키마를 안 주고 점도 없으면 public. 함수가 없으면 404(PGRST202), 스키마가 노출 목록(pgrst.db_schemas)에 없으면 406(PGRST106)."""
        if schema is None:
            schema, fn = split_table(fn) if "." in fn else ("public", fn)
        resp = self._req("POST", f"{schema}.rpc/{fn}", body=args)
        return resp.json() if resp.content else None

    @staticmethod
    def _filter_params(filters: Filters | None) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        for col, val in (filters or {}).items():
            if isinstance(val, (list, tuple, set)) and not (
                isinstance(val, tuple)
                and len(val) == 2
                and isinstance(val[0], str)
                and val[0] in ("gte", "gt", "lte", "lt", "neq", "like", "ilike")
            ):
                vals = ",".join(f'"{_encode_filter_value(v)}"' for v in val)
                params.append((col, f"in.({vals})"))
            elif isinstance(val, tuple):
                op, v = val
                params.append((col, f"{op}.{_encode_filter_value(v)}"))
            elif val is None:
                params.append((col, "is.null"))
            else:
                params.append((col, f"eq.{_encode_filter_value(val)}"))
        return params

    # --- Store ------------------------------------------------------------------

    def upsert(self, table: str, rows: list[dict[str, Any]], conflict: Sequence[str]) -> int:
        if not rows:
            return 0
        n = 0
        for chunk in chunked(rows, UPSERT_CHUNK):
            # PostgREST 는 모든 행이 같은 키 집합을 가져야 한다 → 합집합으로 채움
            keys = sorted({k for r in chunk for k in r})
            body = [{k: r.get(k) for k in keys} for r in chunk]
            self._req(
                "POST",
                table,
                params={"on_conflict": ",".join(conflict)},
                body=body,
                prefer="resolution=merge-duplicates,return=minimal",
            )
            n += len(chunk)
        return n

    def insert(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        n = 0
        for chunk in chunked(rows, UPSERT_CHUNK):
            keys = sorted({k for r in chunk for k in r})
            body = [{k: r.get(k) for k in keys} for r in chunk]
            self._req("POST", table, body=body, prefer="return=minimal")
            n += len(chunk)
        return n

    def insert_returning(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        resp = self._req("POST", table, body=[row], prefer="return=representation")
        data = resp.json()
        return data[0] if isinstance(data, list) and data else dict(row)

    def select(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        filters: Filters | None = None,
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        # IN 필터가 크면 쪼개서 여러 번 호출
        big_in = [
            (c, v) for c, v in (filters or {}).items() if isinstance(v, (list, set)) and len(v) > IN_CHUNK
        ]
        if big_in:
            col, vals = big_in[0]
            out: list[dict[str, Any]] = []
            for part in chunked(list(vals), IN_CHUNK):
                f = dict(filters or {})
                f[col] = part
                out.extend(self.select(table, columns, f, limit, order))
            return out

        params: list[tuple[str, str]] = [("select", ",".join(columns) if columns else "*")]
        params += self._filter_params(filters)
        if order:
            params.append(("order", order))
        page = 1000
        offset = 0
        out = []
        while True:
            p = params + [
                ("limit", str(min(page, (limit - offset) if limit else page))),
                ("offset", str(offset)),
            ]
            rows = self._req("GET", table, params=p).json()
            out.extend(rows)
            if len(rows) < page or (limit and len(out) >= limit):
                break
            offset += page
        return out[:limit] if limit else out

    def delete(self, table: str, filters: Filters) -> None:
        if not filters:
            raise ValueError("refusing to delete without filters")
        big_in = [(c, v) for c, v in filters.items() if isinstance(v, (list, set)) and len(v) > IN_CHUNK]
        if big_in:
            col, vals = big_in[0]
            for part in chunked(list(vals), IN_CHUNK):
                self.delete(table, {**filters, col: part})
            return
        if any(isinstance(v, (list, set)) and not v for v in filters.values()):
            return  # 빈 IN 목록 = 지울 것 없음
        self._req("DELETE", table, params=dict(self._filter_params(filters)), prefer="return=minimal")

    # --- 러너 전용 -------------------------------------------------------------

    def get_watermark(self, collector: str) -> dict[str, Any]:
        rows = self.select("ops.collector_state", ["watermark"], {"collector": collector}, limit=1)
        return rows[0]["watermark"] if rows else {}

    def set_watermark(self, collector: str, watermark: dict[str, Any]) -> None:
        self.upsert(
            "ops.collector_state",
            [{"collector": collector, "watermark": watermark, "updated_at": datetime.utcnow().isoformat()}],
            ["collector"],
        )

    def run_started(self, collector: str, params: dict[str, Any]) -> int:
        resp = self._req(
            "POST",
            "ops.collector_runs",
            body={
                "collector": collector,
                "status": "running",
                "params": params,
                "runner_host": socket.gethostname(),
            },
            prefer="return=representation",
        )
        return int(resp.json()[0]["id"])

    def run_finished(
        self, run_id: int, status: str, rows: int, watermark: dict[str, Any] | None, error: str | None
    ) -> None:
        self._req(
            "PATCH",
            "ops.collector_runs",
            params={"id": f"eq.{run_id}"},
            body={
                "status": status,
                "rows_upserted": rows,
                "watermark": watermark,
                "error": (error or None) and error[:4000],
                "finished_at": datetime.utcnow().isoformat(),
            },
            prefer="return=minimal",
        )
