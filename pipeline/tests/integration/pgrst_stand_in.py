"""PostgREST 대역 — 통합 테스트용. 실제 Postgres 위에서 PostgrestStore 가 쓰는 HTTP 계약만 흉내 낸다.

흉내 내는 것 (PostgREST v12 동작 기준):
- 스키마 고르기: GET 은 Accept-Profile, POST 는 Content-Profile. 노출 목록 밖이면 406 PGRST106.
- 권한: Bearer 키가 service_key 면 service_role, 아니면 anon 으로 `set local role` 한 뒤 실행 — GRANT 가 그대로 걸린다.
- POST /rest/v1/rpc/<fn>: 본문 객체의 키 = 이름 붙은 인자. 인자 이름이 맞는 함수가 없으면 404 PGRST202. 권한 없음은 401/403 (42501).
- GET /rest/v1/<relation>: select=, 필터 eq·neq·gt·gte·lt·lte·like·ilike·in.(…)·is.null|true|false, order=col.asc|desc, limit, offset.
  없는 테이블·뷰는 404 PGRST205.
흉내 내지 않는 것: 쓰기(POST/PATCH/DELETE 테이블), 임베딩, JWT 검증, Prefer 헤더.
"""

from __future__ import annotations

import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import psycopg
from psycopg import sql

OPS = {"eq": "=", "neq": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "like": "LIKE", "ilike": "ILIKE"}


class PgrstStandIn:
    def __init__(self, dsn: str, service_key: str, schemas: tuple[str, ...] = ("public", "ideas", "research", "ops")) -> None:
        self.dsn, self.service_key, self.schemas = dsn, service_key, schemas
        self.log: list[dict[str, Any]] = []
        self._srv: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------------ 수명
    def start(self) -> str:
        stand_in = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401 - 조용히
                pass

            def do_GET(self):
                stand_in._handle(self, "GET")

            def do_POST(self):
                stand_in._handle(self, "POST")

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self._srv.server_address[1]}"

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()

    # ------------------------------------------------------------------ 요청
    def _handle(self, h: BaseHTTPRequestHandler, method: str) -> None:
        parts = urlsplit(h.path)
        if not parts.path.startswith("/rest/v1/"):
            return self._send(h, 404, {"code": "PGRST000", "message": "not a REST path"})
        rest = parts.path[len("/rest/v1/"):]
        profile = h.headers.get("Accept-Profile" if method == "GET" else "Content-Profile") or "public"
        key = (h.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        role = "service_role" if key == self.service_key else "anon"
        body = None
        if method == "POST":
            n = int(h.headers.get("Content-Length") or 0)
            body = json.loads(h.rfile.read(n) or b"null")
        self.log.append({"method": method, "path": rest, "profile": profile, "role": role, "body": body,
                         "query": parse_qsl(parts.query, keep_blank_values=True)})
        if profile not in self.schemas:
            return self._send(h, 406, {"code": "PGRST106", "message": f"Invalid schema: {profile}"})
        try:
            if method == "POST" and rest.startswith("rpc/"):
                status, out = self._rpc(profile, rest[4:], body or {}, role)
            elif method == "GET":
                status, out = self._select(profile, rest, parse_qsl(parts.query, keep_blank_values=True), role)
            else:
                status, out = 501, {"code": "STANDIN", "message": f"{method} {rest} 은 대역이 흉내 내지 않는다"}
        except psycopg.Error as exc:
            st = exc.sqlstate or "XX000"
            status = (401 if role == "anon" else 403) if st == "42501" else 400
            out = {"code": st, "message": str(exc).splitlines()[0]}
        self._send(h, status, out)

    @staticmethod
    def _send(h: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode()
        h.send_response(status)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(data)))
        h.end_headers()
        h.wfile.write(data)

    # ------------------------------------------------------------------ RPC
    def _rpc(self, schema: str, fn: str, args: dict[str, Any], role: str) -> tuple[int, Any]:
        with psycopg.connect(self.dsn, autocommit=False) as conn:
            cands = conn.execute(
                """select p.proargnames, (select array_agg(format_type(t, null) order by o)
                                            from unnest(p.proargtypes) with ordinality as a(t, o))
                     from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                    where n.nspname = %s and p.proname = %s""", (schema, fn)).fetchall()
            match = next(((names or [], types or []) for names, types in cands if set(names or []) == set(args)), None)
            if match is None:
                return 404, {"code": "PGRST202", "message": f"Could not find the function {schema}.{fn}({', '.join(sorted(args))})"}
            names, types = match
            parts, vals = [], []
            for name, typ in zip(names, types, strict=False):
                v = args[name]
                parts.append(sql.SQL("{} := %s::" + typ).format(sql.Identifier(name)))
                vals.append(json.dumps(v, ensure_ascii=False) if typ in ("jsonb", "json") else (None if v is None else str(v)))
            conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
            q = sql.SQL("select to_jsonb({}.{}({}))").format(sql.Identifier(schema), sql.Identifier(fn), sql.SQL(", ").join(parts))
            (res,) = conn.execute(q, vals).fetchone()
            conn.commit()
            return 200, res

    # ------------------------------------------------------------------ 읽기
    def _select(self, schema: str, rel: str, query: list[tuple[str, str]], role: str) -> tuple[int, Any]:
        cols: sql.Composable = sql.SQL("*")
        where: list[sql.Composable] = []
        order: list[sql.Composable] = []
        limit = offset = None
        for k, v in query:
            if k == "select":
                if v and v != "*":
                    cols = sql.SQL(", ").join(sql.Identifier(c.strip()) for c in v.split(",") if c.strip())
            elif k == "order":
                for term in v.split(","):
                    c, _, d = term.partition(".")
                    order.append(sql.SQL("{} {}").format(sql.Identifier(c), sql.SQL("DESC" if d.startswith("desc") else "ASC")))
            elif k == "limit":
                limit = int(v)
            elif k == "offset":
                offset = int(v)
            else:
                op, _, val = v.partition(".")
                col = sql.Identifier(k)
                if op == "in":
                    items = next(csv.reader([val.strip("()")], skipinitialspace=True)) if val.strip("()") else []
                    where.append(sql.SQL("{} = any({})").format(col, sql.Literal(items)) if items else sql.SQL("false"))
                elif op == "is":
                    where.append(sql.SQL("{} is {}").format(col, sql.SQL({"null": "NULL", "true": "TRUE", "false": "FALSE"}[val])))
                elif op in OPS:
                    where.append(sql.SQL("{} {} {}").format(col, sql.SQL(OPS[op]), sql.Literal(val)))
                else:
                    return 400, {"code": "PGRST100", "message": f"대역이 모르는 연산자 {op}"}
        q = sql.SQL("select {} from {}.{}").format(cols, sql.Identifier(schema), sql.Identifier(rel))
        if where:
            q += sql.SQL(" where ") + sql.SQL(" and ").join(where)
        if order:
            q += sql.SQL(" order by ") + sql.SQL(", ").join(order)
        if limit is not None:
            q += sql.SQL(" limit {}").format(sql.Literal(limit))
        if offset is not None:
            q += sql.SQL(" offset {}").format(sql.Literal(offset))
        with psycopg.connect(self.dsn, autocommit=False) as conn:
            exists = conn.execute("select to_regclass(%s)", (f"{schema}.{rel}",)).fetchone()[0]
            if exists is None:
                return 404, {"code": "PGRST205", "message": f"Could not find the table '{schema}.{rel}' in the schema cache"}
            conn.execute(sql.SQL("set local role {}").format(sql.Identifier(role)))
            (rows,) = conn.execute(sql.SQL("select coalesce(json_agg(t), '[]'::json) from ({}) t").format(q)).fetchone()
            conn.commit()
            return 200, rows
