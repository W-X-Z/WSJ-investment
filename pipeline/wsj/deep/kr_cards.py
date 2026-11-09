"""N12 (한국): 공급망 지도(W-X-Z/supply-map) DB 의 조회 함수로 구조 카드를 읽는다. 쓰지 않는다.

  api.find_company(q)              종목코드·이름 → 고유번호
  api.company_card(corp, year)     기본 정보 · 재무 · 카드 7칸 · 빈 칸 · 확인 관계
연결: SUPPLYMAP_DB_URL (Postgres 접속 문자열, 읽기 전용 계정 권장). psycopg 가 필요하다 (pip install 'psycopg[binary]').
카드 칸은 미국 카드(deep.cards)와 같은 이름·모양으로 맞춰 돌려준다 → diff·리포트가 시장을 가리지 않는다.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from wsj.deep.cards import SLOTS

log = logging.getLogger("wsj.deep")


class SupplyMapUnavailable(RuntimeError):
    pass


def _connect(url: str) -> Any:
    if not url:
        raise SupplyMapUnavailable("SUPPLYMAP_DB_URL 이 없다 — 공급망 지도 DB 접속 문자열을 pipeline/.env 에")
    try:
        import psycopg
    except ImportError as exc:
        raise SupplyMapUnavailable("psycopg 가 없다 — pip install 'psycopg[binary]'") from exc
    url = url.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")  # 세션 풀러 → 트랜잭션 풀러
    return psycopg.connect(url, connect_timeout=10, prepare_threshold=None, autocommit=True)


def _slot(content: Any) -> dict[str, Any]:
    c = content if isinstance(content, dict) else {}
    items = []
    for it in c.get("items") or []:
        if not isinstance(it, dict) or not it.get("label"):
            continue
        items.append({"label": it.get("label"), "detail": it.get("detail") or "", "name": it.get("name"),
                      "value": it.get("value"), "evidence": it.get("evidence") or [],
                      "loc": ["사업보고서 사업의 내용"]})
    out = {"empty": not items, "summary": c.get("summary") or "", "items": items}
    for k in ("top_customers", "top2_pct", "top_n", "top_n_pct"):
        if k in c:
            out[k] = c[k]
    return out


def to_card(raw: dict[str, Any]) -> dict[str, Any]:
    cards = raw.get("cards") or {}
    card = {s: _slot(cards.get(s)) for s in SLOTS}
    for s in raw.get("empty_slots") or []:
        if s in card:
            card[s] = {"empty": True, "summary": "", "items": []}
    card["overview"] = {"summary": "", "segments": []}
    rels = []
    for r in raw.get("relations") or []:
        if not isinstance(r, dict):
            continue
        rels.append({"type": r.get("edge_type"), "name": r.get("dst_name") or r.get("src_name"),
                     "detail": f"{r.get('src_name')} → {r.get('dst_name')}", "value": r.get("amount") or r.get("share_pct"),
                     "evidence": [], "loc": [str(r.get("rcept_no") or r.get("source") or "공시")]})
    card["relations"] = rels
    return card


def kr_cards(stock_code: str, years: int = 3, url: str | None = None, conn: Any | None = None) -> dict[str, Any]:
    if conn is None:
        from wsj.config import load_settings

        conn = _connect(url if url is not None else load_settings().supplymap_db_url)
        own = True
    else:
        own = False
    try:
        with conn.cursor() as cur:
            cur.execute("select corp_code, corp_name, stock_code from api.find_company(%s) limit 5", (stock_code,))
            rows = cur.fetchall()
            found = [r for r in rows if (r[2] or "").strip() == stock_code] or rows
            if not found:
                return {"ticker": stock_code, "cards": [], "errors": [f"공급망 지도에 {stock_code} 없음"]}
            corp_code, corp_name = found[0][0], found[0][1]
            cur.execute("select api.company_card(%s, null)", (corp_code,))
            latest = cur.fetchone()[0]
            if isinstance(latest, str):
                latest = json.loads(latest)
            fy = latest.get("fiscal_year")
            out: dict[str, Any] = {"ticker": stock_code, "corp_code": corp_code, "company": corp_name,
                                   "financials": latest.get("financials"), "cards": [], "errors": []}
            for y in ([fy - i for i in range(years)] if fy else []):
                if y == fy:
                    raw = latest
                else:
                    cur.execute("select api.company_card(%s, %s)", (corp_code, y))
                    raw = cur.fetchone()[0]
                    raw = json.loads(raw) if isinstance(raw, str) else raw
                if not raw or not raw.get("cards"):
                    continue
                out["cards"].append({"report_id": None, "doc": {"key": f"사업보고서 FY{y}", "form": "사업보고서"},
                                     "card": to_card(raw), "missing": [], "source": "supply-map"})
            return out
    finally:
        if own:
            conn.close()
