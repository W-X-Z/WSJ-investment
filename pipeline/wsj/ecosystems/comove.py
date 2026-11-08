"""업종 동반 급변 → 단서 (사용자 2026-11-04: 중간선거 다음 날 AI 전력주가 9~18% 빠지고 S&P500 은 +1.6% — 파이프라인이 몰랐다).

미국 장 마감 뒤(KST 06:00 이후) 한 번 돈다. 그래프의 미국 상장사를 생태계(power·hbm·optics)로 묶어 오늘 등락을 S&P500(SPY)과 비교하고,
묶음이 지수와 크게 벌어지면 (1) 그 사실을 단서 하나로, (2) 그날 원인을 다룬 기사 몇 건을 단서로 남긴다. LLM 을 쓰지 않는다.
아침 정리 작업(report.md)이 이 단서를 읽어 해당 기업이 든 아이디어의 history 에 'flow'/'external' 항목으로 넣는다.

가격: api.nasdaq.com quote/info (무료·무인증, 장 마감 직후 반영). 종목당 1회 — 140곳 ≈ 1~2분.
원인 기사: Google News RSS — 묶음 상위 하락(상승) 종목 이름으로 하루 창 검색, 제목에 원인(as/after/amid …)이 있는 것만.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

from wsj.http import HOST_RPS, HttpClient

log = logging.getLogger("wsj.ecosystems.comove")

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}
HOST_RPS.update({"api.nasdaq.com": 2.0, "news.google.com": 1.0})
QUOTE = "https://api.nasdaq.com/api/quote/{t}/info?assetclass={c}"
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
US = {"Nasdaq", "NYSE", "NYSE American"}
ECO_KO = {"power": "전력", "hbm": "메모리·패키징", "optics": "광통신"}
SECTOR_Q = {"power": "data center power stocks", "hbm": "memory chip stocks", "optics": "optical networking stocks"}
SITE = "https://wsj-investment.vercel.app/ecosystems/{eco}?move={d}"

# 묶음이 '움직였다'의 기준: 5곳 이상, 지수와 중앙값 차이 4%p 이상, 같은 방향으로 3%p 넘게 벌어진 종목이 60% 이상
MIN_N, GAP_PP, BREADTH, NAME_PP = 5, 4.0, 0.6, 3.0
CAUSE = re.compile(r"\b(?:as|after|amid|on|over|following|despite|because)\b", re.I)
SECTOR = re.compile(r"\b(?:AI|data[- ]cent\w*|chip\w*|semiconductor\w*|memory|optical|photonic\w*|power|electrical|grid|utilit\w*|infrastructure)\b.{0,40}"
                    r"\b(?:stocks?|shares|names|sector|trade)\b", re.I)


def short_name(label: str) -> str:
    """'Modine Manufacturing (MOD)' → 'Modine'. 첫 단어가 너무 짧으면 두 단어."""
    base = label.split(" (")[0].strip()
    w = base.split()
    return " ".join(w[:2]) if w and len(w[0]) < 4 and len(w) > 1 else (w[0] if w else base)


@dataclass
class Quote:
    company_id: str
    name: str
    ticker: str
    pct: float
    price: float
    day: date


def _num(s: Any) -> float | None:
    try:
        return float(str(s).replace("$", "").replace(",", "").replace("%", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _day(ts: str | None) -> date | None:
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", ts or "")
    return datetime.strptime(" ".join(m.groups()), "%b %d %Y").date() if m else None


def fetch_quote(http: HttpClient, ticker: str, assetclass: str = "stocks") -> tuple[float, float, date] | None:
    """(등락률 %, 가격, 거래일) — 실패·빈 값이면 None."""
    try:
        d = (http.get_json(QUOTE.format(t=ticker.replace(".", "-"), c=assetclass), headers=UA) or {}).get("data") or {}
    except Exception as exc:  # noqa: BLE001 - 종목 하나가 죽어도 나머지는 계속
        log.debug("quote %s failed: %s", ticker, exc)
        return None
    p = d.get("primaryData") or {}
    pct, px, day = _num(p.get("percentageChange")), _num(p.get("lastSalePrice")), _day(p.get("lastTradeTimestamp"))
    return (pct, px, day) if pct is not None and px and day else None


def us_companies(graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for n in graph["nodes"]:
        lst = n.get("listing") or {}
        if n.get("kind") == "company" and lst.get("exchange") in US and lst.get("ticker") and n.get("ecosystem") in ECO_KO:
            out.setdefault(n["ecosystem"], []).append(n)
    return out


def baskets(quotes: dict[str, list[Quote]], spy: float) -> list[dict[str, Any]]:
    """지수와 벌어진 생태계 묶음. 방향(down/up)·중앙값·폭·상위 종목."""
    out = []
    for eco, qs in quotes.items():
        if len(qs) < MIN_N:
            continue
        med = statistics.median(q.pct for q in qs)
        gap = med - spy
        if abs(gap) < GAP_PP:
            continue
        down = gap < 0
        same = [q for q in qs if (q.pct - spy <= -NAME_PP if down else q.pct - spy >= NAME_PP)]
        if len(same) / len(qs) < BREADTH:
            continue
        movers = sorted(qs, key=lambda q: q.pct if down else -q.pct)[:6]
        out.append({"ecosystem": eco, "direction": "down" if down else "up", "n": len(qs), "median": round(med, 2), "spy": round(spy, 2),
                    "breadth": round(len(same) / len(qs), 2), "day": max(q.day for q in qs).isoformat(),
                    "movers": [{"company": q.company_id, "name": q.name, "ticker": q.ticker, "pct": round(q.pct, 2)} for q in movers]})
    return out


def basket_clue(b: dict[str, Any]) -> dict[str, Any]:
    d = date.fromisoformat(b["day"])
    word = "동반 급락" if b["direction"] == "down" else "동반 급등"
    title = (f"[{word}] 그래프 {ECO_KO[b['ecosystem']]} 상장사 {b['n']}곳 중앙값 {b['median']:+.1f}% · S&P500 {b['spy']:+.1f}% "
             f"({d.month}/{d.day})")
    summary = " · ".join(f"{short_name(m['name'])} {m['pct']:+.1f}%" for m in b["movers"])
    return {"url": SITE.format(eco=b["ecosystem"], d=b["day"]), "title": title[:400], "summary": summary[:500],
            "published_at": datetime.combine(d, datetime.min.time(), UTC).replace(hour=21).isoformat(),
            "source_id": "comove", "source_name": "업종 동반 급변 (가격)", "source_kind": "market_move", "lang": "ko", "region": "US",
            "companies": [{"company": m["company"], "name": m["name"], "ticker": m["ticker"], "exchange": None} for m in b["movers"]],
            "nodes": [], "relevant": True, "note": f"{ECO_KO[b['ecosystem']]} 묶음 {word} — 원인 기사를 같이 본다",
            "extra": {"layer": "issue", "comove": b, "screen": "kept"}}


def cause_items(http: HttpClient, b: dict[str, Any], limit: int = 8) -> list[tuple[str, str, str, datetime]]:
    """[(url, title, publisher, published)] — 하루 창, 제목에 원인 구절이 있는 것만, 중복 제목 제거."""
    names = [m["name"].split(" (")[0] for m in b["movers"][:3]]
    pats = [short_name(m["name"]) for m in b["movers"]] + [m["ticker"] for m in b["movers"] if m.get("ticker")]
    queries = [" OR ".join(f'"{n}"' for n in names) + " stocks", SECTOR_Q[b["ecosystem"]], "AI infrastructure stocks"]
    day = datetime.combine(date.fromisoformat(b["day"]), datetime.min.time(), UTC)
    seen, out = set(), []
    for q in queries:
        try:
            root = ET.fromstring(http.get_text(GOOGLE_NEWS.format(q=quote_plus(f"{q} when:1d")), headers={"User-Agent": UA["User-Agent"]}))
        except Exception as exc:  # noqa: BLE001
            log.warning("news %s failed: %s", q, exc)
            continue
        for it in root.iter("item"):
            title, link, pub = (it.findtext("title") or "").strip(), it.findtext("link") or "", it.findtext("pubDate")
            publisher = (it.findtext("source") or "news").strip()
            if title.endswith(" - " + publisher):
                title = title[: -len(publisher) - 3]
            try:
                when = datetime.strptime(pub or "", "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
            except ValueError:
                continue
            key = re.sub(r"\W+", "", title.lower())[:70]
            if not link or key in seen or when < day - timedelta(hours=12) or not CAUSE.search(title):
                continue
            if not (SECTOR.search(title) or any(re.search(rf"\b{re.escape(n)}\b", title, re.I) for n in pats)):
                continue                                  # 묶음 종목 이름이나 업종 주식 이야기가 아닌 글
            seen.add(key)
            out.append((link, title, publisher, when))
    return out[:limit]


def cause_clue(b: dict[str, Any], item: tuple[str, str, str, datetime]) -> dict[str, Any]:
    url, title, publisher, when = item
    from wsj.ecosystems.clues import POLICY_CAUSE

    return {"url": url, "title": title[:400], "summary": None, "published_at": when.isoformat(),
            "source_id": "comove_cause", "source_name": publisher[:120], "source_kind": "market_move", "lang": "en", "region": "US",
            "companies": [], "nodes": [], "relevant": True, "note": f"{ECO_KO[b['ecosystem']]} 동반 {'급락' if b['direction'] == 'down' else '급등'}의 원인 기사",
            "extra": {"layer": "press", "comove_of": SITE.format(eco=b["ecosystem"], d=b["day"]), "screen": "kept",
                      **({"themes": ["politics"]} if POLICY_CAUSE.search(title) else {})}}


def run(http: HttpClient, graph: dict[str, Any], store: Any | None = None, today: date | None = None) -> dict[str, Any]:
    spy = fetch_quote(http, "SPY", "etf")
    if not spy:
        raise RuntimeError("SPY 시세를 받지 못함")
    spy_pct, _, spy_day = spy
    if today and spy_day != today:
        return {"skipped": f"마지막 거래일 {spy_day} ≠ {today}", "baskets": []}
    from concurrent.futures import ThreadPoolExecutor

    todo = [(eco, n) for eco, nodes in us_companies(graph).items() for n in nodes]
    with ThreadPoolExecutor(max_workers=8) as pool:              # 응답이 1~3초라 동시에 — 호스트 속도 제한(2/초)은 HttpClient 가 지킨다
        got = list(pool.map(lambda x: fetch_quote(http, x[1]["listing"]["ticker"]), todo))
    quotes: dict[str, list[Quote]] = {}
    missing = 0
    for (eco, n), q in zip(todo, got, strict=True):
        if not q or q[2] != spy_day:
            missing += 1
            continue
        quotes.setdefault(eco, []).append(Quote(n["id"], n.get("label", n["id"]), n["listing"]["ticker"], q[0], q[1], q[2]))
    found = baskets(quotes, spy_pct)
    rows: list[dict[str, Any]] = []
    for b in found:
        rows.append(basket_clue(b))
        rows += [cause_clue(b, it) for it in cause_items(http, b)]
    if rows:
        from wsj.ecosystems.clues import Clue, tag

        from_rows = [Clue(r["url"], r["title"], r["summary"] or "", None, r["source_id"], r["source_name"], r["source_kind"]) for r in rows]
        tag(from_rows, graph)                                   # 원인 기사에 나온 그래프 기업·노드
        for r, c in zip(rows, from_rows, strict=True):
            if not r["companies"]:
                r["companies"] = c.companies
            r["nodes"] = sorted(c.nodes)
    saved = store.upsert("ideas.clues", rows, ["url"]) if store is not None and rows else 0
    return {"day": spy_day.isoformat(), "spy": spy_pct, "by_ecosystem": {e: {"n": len(q), "median": round(statistics.median(x.pct for x in q), 2)}
                                                                         for e, q in quotes.items() if q},
            "missing": missing, "baskets": found, "clues": len(rows), "saved": saved}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--dry-run", action="store_true", help="저장하지 않고 결과만 출력")
    ap.add_argument("--any-day", action="store_true", help="마지막 거래일이 오늘(미 동부)이 아니어도 돈다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.ecosystems.ontology import load_graph

    graph = load_graph()
    http = HttpClient(UA["User-Agent"], timeout=20, max_retries=1)
    # KST 아침에 돌면 미 동부 날짜는 하루 전 — 그 날이 마지막 거래일이어야 한다 (주말·휴일이면 건너뜀)
    et_today = (datetime.now(UTC) - timedelta(hours=5)).date()
    today = None if args.any_day else et_today
    store = None
    try:
        if args.dry_run:
            res = run(http, graph, None, today)
        else:
            from wsj.config import load_settings
            from wsj.db import make_store
            from wsj.runlog import logged_run

            store = make_store(load_settings())
            with logged_run(store, "comove", {"day": str(today)}) as lr:
                res = run(http, graph, store, today)
                lr["rows"] = res.get("clues", 0)
                lr["notes"] = json.dumps({k: v for k, v in res.items() if k != "baskets"} | {"baskets": len(res.get("baskets", []))}, ensure_ascii=False)[:1500]
        print(json.dumps(res, ensure_ascii=False, indent=1))
    finally:
        http.close()
        if store is not None:
            store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
