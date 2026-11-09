"""python -m wsj ideate … — wsj/ideate/__init__.py 참고."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def add_parser(sub: Any) -> None:
    p = sub.add_parser("ideate", help="상상 단계: 원천 다이제스트 · 초기 아이디어 점검·저장 · 대기열")
    s = p.add_subparsers(dest="ideate_cmd", required=True)
    d = s.add_parser("digest", help="원천(ideas.clues) → 상상 단계 입력 마크다운")
    d.add_argument("--days", type=int, default=3)
    d.add_argument("--date", help="기준일 (기본 오늘)")
    d.add_argument("--from-json", help="DB 대신 clue 행 JSON 파일")
    d.add_argument("--out", help="마크다운을 쓸 파일 (기본 표준출력)")
    c = s.add_parser("check", help="초기 아이디어의 후보 종목 점검 (시세·시총·등락·역DCF)")
    c.add_argument("--file", required=True)
    c.add_argument("--out", help="점검 결과 JSON (기본: 입력 파일을 덮어씀)")
    v = s.add_parser("save", help="research.reports 'seeds:YYYY-MM-DD' 저장")
    v.add_argument("--file", required=True)
    v.add_argument("--check-only", action="store_true")
    q = s.add_parser("queue", help="선택·요청된 초기 아이디어")
    q.add_argument("--days", type=int, default=7)
    for x in (d, c, v, q):
        x.add_argument("-v", "--verbose", action="store_true")


def _store() -> Any:
    from wsj.deep.cli import _store as deep_store

    st = deep_store(False)
    if st is None:
        raise SystemExit("Supabase 연결 정보가 없다 (SUPABASE_URL·SUPABASE_SECRET_KEY)")
    return st


def cli(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, stream=sys.stderr,
                        format="%(levelname)-7s %(name)s: %(message)s")
    cmd = args.ideate_cmd
    if cmd == "digest":
        from wsj.ideate.digest import fetch, render

        as_of = args.date or date.today().isoformat()
        if args.from_json:
            rows = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        else:
            st = _store()
            try:
                rows = fetch(st, args.days, as_of)
            finally:
                st.close()
        md = render(rows, args.days, as_of)
        if args.out:
            Path(args.out).write_text(md, encoding="utf-8")
            print(json.dumps({"tool": "ideate.digest", "out": args.out, "rows": len(rows), "chars": len(md)}, ensure_ascii=False))
        else:
            print(md)
        return 0
    if cmd in ("check", "save"):
        from wsj.ideate.check import check, report_row, validate

        spec = json.loads(Path(args.file).read_text(encoding="utf-8"))
        errs = validate(spec)
        if errs:
            print(json.dumps({"tool": f"ideate.{cmd}", "ok": False, "errors": errs}, ensure_ascii=False, indent=1))
            return 1
        if cmd == "check":
            from wsj.tools.context import open_context

            with open_context() as ctx:
                spec = check(spec, ctx)
            out = args.out or args.file
            Path(out).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            brief = [{"id": s["id"], "headline": s["headline"],
                      "companies": [{"name": c["name"], **(c.get("resolved") or {}),
                                     **{k: (c.get("quick") or {}).get(k) for k in ("market_cap_usd", "change_pct", "from_52w_high_pct",
                                                                                  "reverse_dcf_cagr_pct")}}
                                    for c in s["companies"]]} for s in spec["seeds"]]
            print(json.dumps({"tool": "ideate.check", "out": out, "seeds": brief}, ensure_ascii=False, indent=1, default=str))
            return 0
        row = report_row(spec)
        if args.check_only:
            print(json.dumps({"tool": "ideate.save", "ok": True, "report_id": row["report_id"]}, ensure_ascii=False))
            return 0
        from wsj.monitor.run import save

        st = _store()
        try:
            res = save(st, row)
        finally:
            st.close()
        print(json.dumps({"tool": "ideate.save", "report_id": row["report_id"], **res}, ensure_ascii=False))
        return 0
    if cmd == "queue":
        st = _store()
        try:
            since = (date.today() - timedelta(days=args.days)).isoformat()
            rows = st.select("research.reports", ["report_id", "as_of", "body"], {"kind": "screen", "as_of": ("gte", since)},
                             order="as_of.desc")
        finally:
            st.close()
        out = [{"report_id": r["report_id"], **{k: s.get(k) for k in ("id", "headline", "status", "companies")}}
               for r in rows if str(r["report_id"]).startswith("seeds:")
               for s in (r["body"] or {}).get("seeds") or [] if s.get("status") in ("selected", "requested")]
        print(json.dumps({"tool": "ideate.queue", "items": out}, ensure_ascii=False, indent=1, default=str))
        return 0
    return 2
