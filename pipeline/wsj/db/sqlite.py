"""로컬 검증용 SQLite 구현. Supabase 없이 수집기 로직을 끝까지 돌려볼 때 쓴다.

테이블은 첫 upsert 때 행의 키로 만들어진다 (타입은 느슨하게). 운영 스키마의 정답은
supabase/migrations 이고, 여기서는 "수집기가 어떤 행을 만드는가" 만 확인한다.
dict/list 값은 JSON 문자열로 저장한다.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from wsj.db.base import Filters


def _enc(v: Any) -> Any:
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, bool):
        return int(v)
    return v


def _dec(v: Any) -> Any:
    if isinstance(v, str) and v[:1] in ("{", "["):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


class SqliteStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "create table if not exists ops__collector_state (collector text primary key, watermark text, updated_at text)"
        )
        self.conn.execute(
            "create table if not exists ops__collector_runs (id integer primary key autoincrement, collector text, "
            "started_at text, finished_at text, status text, rows_upserted integer, params text, watermark text, error text)"
        )

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _t(table: str) -> str:
        return table.replace(".", "__")

    def _ensure(self, table: str, keys: Sequence[str], conflict: Sequence[str] | None) -> None:
        t = self._t(table)
        exists = self.conn.execute("select 1 from sqlite_master where name=?", (t,)).fetchone()
        if not exists:
            cols = ", ".join(f'"{k}"' for k in keys)
            pk = f", primary key ({', '.join(conflict)})" if conflict else ""
            self.conn.execute(f'create table "{t}" ({cols}{pk})')
            return
        have = {r[1] for r in self.conn.execute(f'pragma table_info("{t}")')}
        for k in keys:
            if k not in have:
                self.conn.execute(f'alter table "{t}" add column "{k}"')

    def upsert(self, table: str, rows: list[dict[str, Any]], conflict: Sequence[str]) -> int:
        if not rows:
            return 0
        keys = sorted({k for r in rows for k in r})
        self._ensure(table, keys, conflict)
        t = self._t(table)
        cols = ", ".join(f'"{k}"' for k in keys)
        ph = ", ".join("?" for _ in keys)
        upd = ", ".join(f'"{k}"=excluded."{k}"' for k in keys if k not in conflict)
        sql = (
            f'insert into "{t}" ({cols}) values ({ph}) on conflict ({", ".join(conflict)}) do update set {upd}'
            if upd
            else f'insert or ignore into "{t}" ({cols}) values ({ph})'
        )
        self.conn.executemany(sql, [[_enc(r.get(k)) for k in keys] for r in rows])
        self.conn.commit()
        return len(rows)

    def insert(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        keys = sorted({k for r in rows for k in r})
        self._ensure(table, keys, None)
        t = self._t(table)
        cols = ", ".join(f'"{k}"' for k in keys)
        ph = ", ".join("?" for _ in keys)
        self.conn.executemany(
            f'insert into "{t}" ({cols}) values ({ph})', [[_enc(r.get(k)) for k in keys] for r in rows]
        )
        self.conn.commit()
        return len(rows)

    def _where(self, filters: Filters | None) -> tuple[str, list[Any]]:
        if not filters:
            return "", []
        parts, args = [], []
        ops = {"gte": ">=", "gt": ">", "lte": "<=", "lt": "<", "neq": "!=", "like": "like", "ilike": "like"}
        for col, val in filters.items():
            if isinstance(val, (list, set)) or (
                isinstance(val, tuple) and not (len(val) == 2 and val[0] in ops)
            ):
                vals = list(val)
                if not vals:
                    parts.append("0")
                    continue
                parts.append(f'"{col}" in ({", ".join("?" for _ in vals)})')
                args += [_enc(v) for v in vals]
            elif isinstance(val, tuple):
                parts.append(f'"{col}" {ops[val[0]]} ?')
                args.append(_enc(val[1]))
            elif val is None:
                parts.append(f'"{col}" is null')
            else:
                parts.append(f'"{col}" = ?')
                args.append(_enc(val))
        return " where " + " and ".join(parts), args

    def select(self, table, columns=None, filters=None, limit=None, order=None) -> list[dict[str, Any]]:
        t = self._t(table)
        if not self.conn.execute("select 1 from sqlite_master where name=?", (t,)).fetchone():
            return []
        where, args = self._where(filters)
        cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        sql = f'select {cols} from "{t}"{where}'
        if order:
            col, _, direction = order.partition(".")
            sql += f' order by "{col}" {"desc" if direction == "desc" else "asc"}'
        if limit:
            sql += f" limit {int(limit)}"
        return [{k: _dec(v) for k, v in dict(r).items()} for r in self.conn.execute(sql, args)]

    def delete(self, table: str, filters: Filters) -> None:
        if not filters:
            raise ValueError("refusing to delete without filters")
        where, args = self._where(filters)
        self.conn.execute(f'delete from "{self._t(table)}"{where}', args)
        self.conn.commit()

    def get_watermark(self, collector: str) -> dict[str, Any]:
        r = self.conn.execute(
            "select watermark from ops__collector_state where collector=?", (collector,)
        ).fetchone()
        return json.loads(r[0]) if r and r[0] else {}

    def set_watermark(self, collector: str, watermark: dict[str, Any]) -> None:
        self.conn.execute(
            "insert into ops__collector_state (collector, watermark, updated_at) values (?,?,?) "
            "on conflict (collector) do update set watermark=excluded.watermark, updated_at=excluded.updated_at",
            (collector, json.dumps(watermark, default=str), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def run_started(self, collector: str, params: dict[str, Any]) -> int:
        cur = self.conn.execute(
            "insert into ops__collector_runs (collector, started_at, status, params) values (?,?,?,?)",
            (collector, datetime.utcnow().isoformat(), "running", json.dumps(params, default=str)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def run_finished(self, run_id, status, rows, watermark, error) -> None:
        self.conn.execute(
            "update ops__collector_runs set status=?, rows_upserted=?, watermark=?, error=?, finished_at=? where id=?",
            (
                status,
                rows,
                json.dumps(watermark, default=str) if watermark else None,
                error,
                datetime.utcnow().isoformat(),
                run_id,
            ),
        )
        self.conn.commit()
