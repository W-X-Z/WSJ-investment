"""노출도 재료 (ADR-0031, 백로그 G-8 무료 경로) — 미국 공시의 매출 구성 숫자를 모아 둔다. LLM 을 쓰지 않는다.

    python -m wsj.ecosystems.exposure run [--max 20] [--bands micro,small,mid] [--only company:mxl ...] [--dry-run]

그래프의 SEC 필러 중 공급 관계(offered_by)에 매출 비중이 비어 있는 곳의 가장 최근 연차 보고서(10-K·20-F·40-F)를 열어
1) 인라인 XBRL 의 차원별 매출(제품·사업부·지역 축)과 그 해 총매출 대비 비중,
2) 고객·제품 집중도(ConcentrationRiskPercentage1),
3) 본문에서 '매출의 N%' 꼴 문장(제품 비중을 숫자로만 적는 소형사가 많다)
을 `ideas.exposure_facts` 에 넣는다. 이 숫자를 공급 관계의 `exposure_pct`·`exposure_year`·`exposure_source` 로 옮기는 것은
주간 개선과 해석 작업이 한다 (축 이름 → 그래프 부품 대응은 판단이다). 이미 읽은 보고서는 다시 받지 않는다.
SEC 공정 접근 규칙: User-Agent 에 연락처, 초당 10회 아래.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
from datetime import UTC, date, datetime
from typing import Any

from wsj.ecosystems.ontology import load_graph

log = logging.getLogger("wsj.ecosystems.exposure")

ANNUAL = ("10-K", "20-F", "40-F")
REVENUE = {"us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
           "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", "us-gaap:SalesRevenueNet",
           "ifrs-full:Revenue", "ifrs-full:RevenueFromContractsWithCustomers"}
CONCENTRATION = "us-gaap:ConcentrationRiskPercentage1"
CTX_RE = re.compile(r'<(?:\w+:)?context\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</(?:\w+:)?context>', re.S)
MEMBER_RE = re.compile(r'<(?:\w+:)?explicitMember\b[^>]*\bdimension="([^"]+)"[^>]*>\s*([^<\s]+)\s*</', re.S)
FACT_RE = re.compile(r'<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>', re.S)
ATTR_RE = re.compile(r'\b([\w:]+)="([^"]*)"')
_SPAN = r"(?:[^.;]|\.(?=\d))"     # 소수점·금액의 마침표는 문장 끝이 아니다
PCT_SENT_RE = re.compile(_SPAN + r"{0,260}\b\d{1,3}(?:\.\d+)?\s?%\s+of\s+(?:our\s+)?(?:total\s+|net\s+|consolidated\s+)*(?:revenues?|net\s+sales|sales)\b" + _SPAN + r"{0,200}", re.I)
# 비용·이자·세금 비율 문장은 매출 구성이 아니다
COST_RE = re.compile(r"interest (?:income|expense)|income tax|tax rate|expenses?\b|research and development|selling, general|gross (?:margin|profit)|cost of (?:revenue|sales|goods)|operating (?:income|loss|margin)|net (?:income|loss)|amortization|depreciation|stock-based|backlog", re.I)


def label(member: str) -> str:
    """'mxl:BroadbandMember' → 'Broadband', 'us-gaap:CustomerConcentrationRiskMember' → 'Customer Concentration Risk'."""
    s = member.split(":")[-1]
    s = re.sub(r"(Member|Axis)$", "", s)
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", s).strip()


def parse_contexts(doc: str) -> dict[str, dict[str, Any]]:
    out = {}
    for cid, body in CTX_RE.findall(doc):
        start = re.search(r"<(?:\w+:)?startDate>([^<]+)<", body)
        end = re.search(r"<(?:\w+:)?endDate>([^<]+)<", body)
        inst = re.search(r"<(?:\w+:)?instant>([^<]+)<", body)
        out[cid] = {"dims": {d: m for d, m in MEMBER_RE.findall(body)},
                    "start": start.group(1).strip() if start else None,
                    "end": (end or inst).group(1).strip() if (end or inst) else None}
    return out


def fact_value(attrs: dict[str, str], inner: str) -> float | None:
    text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
    fmt = attrs.get("format", "")
    if "zero" in fmt or text in ("-", "—", "–"):
        v = 0.0
    else:
        num = re.sub(r"[^\d.]", "", text.replace(",", "") if "comma" not in fmt else text.replace(".", "").replace(",", "."))
        if not num or num == ".":
            return None
        try:
            v = float(num)
        except ValueError:
            return None
    v *= 10 ** int(attrs.get("scale") or 0)
    return -v if attrs.get("sign") == "-" else v


def parse_facts(doc: str, contexts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for raw, inner in FACT_RE.findall(doc):
        a = dict(ATTR_RE.findall(raw))
        name = a.get("name")
        if name not in REVENUE and name != CONCENTRATION:
            continue
        ctx = contexts.get(a.get("contextRef", ""))
        v = fact_value(a, inner)
        if ctx is None or v is None:
            continue
        out.append({"concept": name, "value": v, "dims": ctx["dims"], "start": ctx["start"], "end": ctx["end"]})
    return out


def _days(a: str | None, b: str | None) -> int:
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days  # type: ignore[index]
    except (TypeError, ValueError):
        return 0


def annual_rows(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """가장 최근 회계연도(기간 330~380일)의 차원별 매출과 비중, 그 해의 집중도. 같은 (개념, 축) 은 하나만."""
    yearly = [f for f in facts if f["concept"] in REVENUE and 330 <= _days(f["start"], f["end"]) <= 380]
    if not yearly:
        return []
    end = max(f["end"] for f in yearly)
    year = [f for f in yearly if f["end"] == end]
    totals = [f["value"] for f in year if not f["dims"]]
    total = max(totals) if totals else None
    rows, seen = [], set()
    for f in year:
        if not f["dims"]:
            continue
        key = (f["concept"], tuple(sorted(f["dims"].items())))
        if key in seen:
            continue
        seen.add(key)
        rows.append({"kind": "revenue", "concept": f["concept"], "axes": f["dims"], "value": f["value"], "period_end": end,
                     "pct": round(100 * f["value"] / total, 2) if total else None,
                     "label": " · ".join(f"{label(d)}={label(m)}" for d, m in sorted(f["dims"].items()))})
    for f in facts:
        if f["concept"] != CONCENTRATION or f["end"] != end:
            continue
        key = (f["concept"], tuple(sorted(f["dims"].items())))
        if key in seen:
            continue
        seen.add(key)
        pct = f["value"] * 100 if f["value"] <= 1.5 else f["value"]
        rows.append({"kind": "concentration", "concept": f["concept"], "axes": f["dims"], "value": f["value"], "period_end": end,
                     "pct": round(pct, 2), "label": " · ".join(f"{label(d)}={label(m)}" for d, m in sorted(f["dims"].items()))})
    if total:
        rows.append({"kind": "total", "concept": "revenue_total", "axes": {}, "value": total, "period_end": end, "pct": 100.0, "label": "총매출"})
    return rows


def visible_text(doc: str) -> str:
    doc = re.sub(r"<ix:header>.*?</ix:header>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<(script|style)\b.*?</\1>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"</(?:p|div|tr|td|li|h\d|table)>|<br\s*/?>", " ; ", doc, flags=re.I)   # 블록 경계 = 문장 경계 (표 칸이 문장에 붙지 않게)
    doc = re.sub(r"<[^>]+>", " ", doc)
    return re.sub(r"\s+", " ", html.unescape(doc))


def pct_sentences(text: str, cap: int = 25) -> list[str]:
    out: list[str] = []
    for m in PCT_SENT_RE.finditer(text):
        s = m.group(0).strip(" ,;")
        if len(s) > 40 and s not in out and not COST_RE.search(s):
            out.append(s[:460])
        if len(out) >= cap:
            break
    return out


def latest_annual(http: Any, cik: int) -> dict[str, Any] | None:
    sub = http.get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    r = (sub.get("filings") or {}).get("recent") or {}
    for i, form in enumerate(r.get("form") or []):
        if form in ANNUAL:
            acc = r["accessionNumber"][i]
            return {"form": form, "filed": r["filingDate"][i], "report": r.get("reportDate", [None] * (i + 1))[i],
                    "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{r['primaryDocument'][i]}"}
    return None


def targets(graph: dict[str, Any], bands: set[str], only: set[str] | None = None) -> list[dict[str, Any]]:
    """매출 비중이 빈 공급 관계가 많은 SEC 필러부터."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    count: dict[str, int] = {}
    for e in graph["edges"]:
        if e["relation"] == "offered_by" and e.get("exposure_pct") is None and not e.get("exposure"):
            count[e["to"]] = count.get(e["to"], 0) + 1
    out = []
    for cid, k in count.items():
        n = nodes.get(cid) or {}
        lst = n.get("listing") or {}
        if not lst.get("cik") or (only and cid not in only) or (not only and n.get("size_band") not in bands):
            continue
        out.append({"company": cid, "cik": int(lst["cik"]), "ticker": lst.get("ticker"), "edges": k})
    out.sort(key=lambda x: (-x["edges"], x["company"]))
    return out


def fact_key(company: str, url: str, kind: str, concept: str, label_: str) -> str:
    return hashlib.md5(f"{company}|{url}|{kind}|{concept}|{label_}".encode()).hexdigest()


def rows_for(t: dict[str, Any], filing: dict[str, Any], doc: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC).isoformat()
    base = {"company_id": t["company"], "cik": t["cik"], "ticker": t["ticker"], "form": filing["form"], "filed": filing["filed"],
            "url": filing["url"], "fetched_at": now}
    out = []
    facts = parse_facts(doc, parse_contexts(doc))
    for r in annual_rows(facts):
        out.append(base | {"fact_key": fact_key(t["company"], filing["url"], r["kind"], r["concept"], r["label"]), "kind": r["kind"],
                           "concept": r["concept"], "axes": r["axes"], "label": r["label"][:400], "value": r["value"], "pct": r["pct"],
                           "period_end": r["period_end"]})
    for s in pct_sentences(visible_text(doc)):
        out.append(base | {"fact_key": fact_key(t["company"], filing["url"], "text", "", s), "kind": "text", "concept": None, "axes": {},
                           "label": s, "value": None, "pct": None, "period_end": filing.get("report")})
    if not out:   # 읽었다는 표시 — 다음 주에 같은 보고서를 다시 받지 않는다
        out.append(base | {"fact_key": fact_key(t["company"], filing["url"], "none", "", ""), "kind": "none", "concept": None, "axes": {},
                           "label": "매출 구성 숫자를 찾지 못함", "value": None, "pct": None, "period_end": filing.get("report")})
    return out


def run(http: Any, store: Any | None, graph: dict[str, Any], bands: set[str], max_n: int = 20, only: set[str] | None = None) -> dict[str, Any]:
    ts = targets(graph, bands, only)
    done: set[str] = set()
    if store is not None:
        try:
            done = {r["url"] for r in store.select("ideas.exposure_facts", ["url"], {"company_id": [t["company"] for t in ts]})} if ts else set()
        except Exception as exc:  # noqa: BLE001 - 0036 전
            log.warning("ideas.exposure_facts 를 읽지 못함 (0036 적용 전?): %s", exc)
            return {"targets": len(ts), "skipped": "0036 전"}
    stats: dict[str, Any] = {"targets": len(ts), "read": 0, "already": 0, "rows": 0, "failed": [], "by_company": {}}
    rows: list[dict[str, Any]] = []
    for t in ts:
        if stats["read"] >= max_n:
            break
        try:
            filing = latest_annual(http, t["cik"])
            if not filing:
                stats["failed"].append({"company": t["company"], "error": "연차 보고서 없음"})
                continue
            if filing["url"] in done:
                stats["already"] += 1
                continue
            doc = http.get_text(filing["url"])
            got = rows_for(t, filing, doc)
        except Exception as exc:  # noqa: BLE001 - 한 회사가 죽어도 나머지는 계속
            stats["failed"].append({"company": t["company"], "error": str(exc)[:160]})
            continue
        stats["read"] += 1
        stats["by_company"][t["company"]] = {k: sum(1 for r in got if r["kind"] == k) for k in ("revenue", "concentration", "text")}
        rows += got
    stats["rows"] = len(rows)
    if store is not None and rows:
        stats["saved"] = store.upsert("ideas.exposure_facts", rows, ["fact_key"])
    stats["sample"] = rows[:0] if store is not None else rows[:40]
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--max", type=int, default=20, help="한 번에 새로 읽을 보고서 수")
    ap.add_argument("--bands", default="micro,small,mid")
    ap.add_argument("--only", nargs="*", help="이 기업 id 만 (규모 무시)")
    ap.add_argument("--dry-run", action="store_true", help="DB 에 쓰지 않고 행을 보인다")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    from wsj.config import load_settings
    from wsj.http import HttpClient

    settings = load_settings()
    http = HttpClient(settings.sec_user_agent, timeout=60, max_retries=2)
    store = None
    if not args.dry_run:
        from wsj.db import make_store

        store = make_store(settings)
    run_id = None
    try:
        if store is not None:
            run_id = store.run_started("exposure", {"max": args.max, "bands": args.bands})
        stats = run(http, store, load_graph(), set(args.bands.split(",")), args.max, set(args.only) if args.only else None)
        if store is not None and run_id is not None:
            store.run_finished(run_id, "succeeded", int(stats.get("saved") or 0), {k: v for k, v in stats.items() if k != "sample"}, None)
        print(json.dumps(stats, ensure_ascii=False, default=str, indent=1 if args.dry_run else None))
    except Exception as exc:
        if store is not None and run_id is not None:
            store.run_finished(run_id, "failed", 0, {}, str(exc)[:500])
        raise
    finally:
        http.close()
        if store is not None:
            store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
