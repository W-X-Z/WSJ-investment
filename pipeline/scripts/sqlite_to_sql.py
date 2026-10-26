"""로컬 SQLite(검증 실행 결과)를 Supabase 에 넣을 수 있는 upsert SQL 로 변환한다.

용도: 서비스 롤 키 없이 샌드박스에서 수집한 결과를 한 번 옮길 때. 평상시에는 쓰지 않는다
(파이프라인이 PostgREST 로 직접 쓴다). 컬럼 타입은 supabase/migrations/*.sql 에서 읽는다.

  python scripts/sqlite_to_sql.py data/wsj.sqlite out/ [--batch 500] [--tables raw.sec_filings,...]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "supabase" / "migrations"
TYPE_WORDS = {
    "text",
    "bigint",
    "integer",
    "numeric",
    "boolean",
    "date",
    "timestamptz",
    "jsonb",
    "text[]",
    "bigint[]",
    "int",
    "int4",
    "int8",
}
STOP = {"not", "null", "default", "primary", "references", "check", "generated", "unique"}


def parse_schema() -> dict[str, dict]:
    """{'raw.sec_filings': {'cols': {'col': 'type'}, 'pk': ['accession_no'], 'identity': {'id'}}}"""
    out: dict[str, dict] = {}
    for f in sorted(MIGRATIONS.glob("*.sql")):
        sql = f.read_text()
        for m in re.finditer(r"create table if not exists (\w+\.\w+) \((.*?)\n\);", sql, re.S):
            table, body = m.group(1), m.group(2)
            cols: dict[str, str] = {}
            pk: list[str] = []
            identity: set[str] = set()
            for line in body.splitlines():
                line = line.split("--")[0].strip().rstrip(",")
                if not line:
                    continue
                if line.lower().startswith("primary key"):
                    pk = [c.strip() for c in re.search(r"\((.*?)\)", line).group(1).split(",")]
                    continue
                if line.lower().startswith(("unique", "check", "constraint")):
                    continue
                toks = line.split()
                col, typ = toks[0], toks[1].lower()
                if typ not in TYPE_WORDS:
                    continue
                cols[col] = typ
                if "primary key" in line.lower() and not line.lower().startswith("primary"):
                    pk = [col]
                if "generated always as identity" in line.lower():
                    identity.add(col)
            out[table] = {"cols": cols, "pk": pk, "identity": identity}
    return out


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def lit(value, typ: str) -> str:
    if value is None or value == "":
        return "null"
    if typ == "boolean":
        return "true" if value in (1, "1", True, "true") else "false"
    if typ == "jsonb":
        return q(value if isinstance(value, str) else json.dumps(value, default=str)) + "::jsonb"
    if typ.endswith("[]"):
        items = json.loads(value) if isinstance(value, str) else (value or [])
        if not items:
            return f"'{{}}'::{typ}"
        return "array[" + ",".join(q(str(x)) for x in items) + f"]::{typ}"
    return q(str(value))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sqlite")
    ap.add_argument("outdir")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--tables", default="", help="schema.table 를 콤마로")
    ap.add_argument("--exclude-cols", default="", help="제외할 컬럼 (payload 등 큰 jsonb)")
    ap.add_argument("--filter", action="append", default=[], help="schema.table=<sqlite where 절>")
    args = ap.parse_args()
    exclude = set(args.exclude_cols.split(",")) if args.exclude_cols else set()
    filters = dict(f.split("=", 1) for f in args.filter)

    schema = parse_schema()
    conn = sqlite3.connect(args.sqlite)
    conn.row_factory = sqlite3.Row
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    wanted = set(args.tables.split(",")) if args.tables else None

    for table, meta in schema.items():
        if wanted and table not in wanted:
            continue
        st = table.replace(".", "__")
        if not conn.execute("select 1 from sqlite_master where name=?", (st,)).fetchone():
            continue
        have = [r[1] for r in conn.execute(f'pragma table_info("{st}")')]
        cols = [c for c in meta["cols"] if c in have and c not in meta["identity"] and c not in exclude]
        pk = meta["pk"]
        where = f" where {filters[table]}" if table in filters else ""
        rows = conn.execute(
            f'select {", ".join(chr(34) + c + chr(34) for c in cols)} from "{st}"{where}'
        ).fetchall()
        if not rows:
            continue
        upd = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in pk)
        conflict = (
            f"on conflict ({', '.join(pk)}) do update set {upd}"
            if pk and upd
            else ("on conflict do nothing" if pk else "")
        )
        n = 0
        for i in range(0, len(rows), args.batch):
            chunk = rows[i : i + args.batch]
            values = ",\n".join(
                "(" + ", ".join(lit(r[c], meta["cols"][c]) for c in cols) + ")" for r in chunk
            )
            sql = f"insert into {table} ({', '.join(cols)}) values\n{values}\n{conflict};\n"
            (outdir / f"{table}.{n:03d}.sql").write_text(sql)
            n += 1
        print(f"{table}: {len(rows)} rows -> {n} files")


if __name__ == "__main__":
    main()
