"""N12 구조 카드: 연차보고서 한 건 → 7칸(공급망 지도와 같은 칸) + 사업 개요 + 확인 관계.

칸: 조달 · 고객 · 핵심 의존 · 수주·잔고 · 경쟁 · 가격 요인 · 리스크 (W-X-Z/supply-map sm/llm.py 의 칸·규칙을 10-K 용으로 옮김).
  - 번호 문단([P12])에 적힌 것만 쓴다. 항목마다 근거 문단 번호가 1개 이상 있어야 한다 → 근거 없는 항목은 코드가 버린다.
  - 공시에 없는 칸은 empty=true 로 비운다. 빈 칸이 곧 조사할 질문이다.
  - 수치는 원문 표기 그대로(\"$3.0 billion\", \"approximately 12%\"). 회사 주장 점유율은 '(회사 주장)'.
  - 글은 한국어, 이름·수치는 원문.

모델: 소형(Haiku). 한 번 호출 입력은 10만 토큰 미만(filings.ANNUAL_CAPS). 끝내 빠진 칸이 둘 이상이면 한 번 더 부른다.
저장: research.reports kind='company', report_id 'card:us:<티커>:<fy2026|s1-2026-01-30>' — 같은 접수번호면 다시 부르지 않는다.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from wsj.deep.filings import Document, numbered

log = logging.getLogger("wsj.deep")

SLOTS = ["sourcing", "customers", "dependencies", "orders", "competition", "pricing", "risks"]
SLOT_KO = {"sourcing": "조달", "customers": "고객", "dependencies": "핵심 의존", "orders": "수주·잔고",
           "competition": "경쟁", "pricing": "가격 요인", "risks": "리스크"}
EXTRACTOR = "deep.cards/v1"
CARD_MODEL = "claude-haiku-5-5"

CARD_SYSTEM = """너는 미국 상장사의 연차보고서(10-K Item 1 사업 · 1A 위험 · 7 MD&A, 또는 상장신고서)에서 회사의 사업 구조를 정리한다.
주체(당사)는 [회사]다. 번호가 붙은 문단([P1], [P2] …)에 적힌 것만 쓰고, 추측하거나 일반 상식으로 채우지 않는다.

칸(slot)과 기대 내용:
- sourcing 조달: 주요 원재료·부품, 공급처(이름 또는 유형), 단일·소수 공급 의존, 수입·관세 노출, 원가 전가 구조
- customers 고객: 최종 시장·고객 산업, 10% 이상 고객(이름 또는 'Customer A' 같은 익명 표현 그대로)과 매출 비중, 집중도, 계약 방식(MSA·장기계약·PO)
- dependencies 핵심 의존: 라이선스·인증·정부 허가·특정 고객·특정 설비·핵심 인력·지식재산 등 없으면 사업이 흔들리는 것
- orders 수주·잔고: 백로그·RPO 금액과 기준일, 증가율, 수주(book-to-bill), 대형 계약, 선수금, 납기
- competition 경쟁: 회사가 명시한 경쟁사 이름, 점유율(수치와 기준), 경쟁 요소, 진입장벽
- pricing 가격 요인: 판가 결정 방식(협상·입찰·연동), 원재료·환율·관세 영향, 가격 조정 조항
- risks 리스크: 1A 중 이 회사에만 해당하는 위험을 우선(일반적인 상투 문구는 뺀다). 규제, 전방 사이클, 고객 이탈, 기술 대체, 지배구조·대주주

작성 규칙:
1. 칸마다 summary 는 한국어 2~3문장. items 는 핵심 항목 1~6개, 각 항목에
   label(짧은 한국어 분류 라벨), detail(문단 근거 요약 한국어 1문장), name(회사·제품·계약 이름, 없으면 null),
   value(수치·비중·금액 원문 표기 그대로, 없으면 null), evidence(근거 문단 번호 정수 목록, 1개 이상 필수).
2. 근거 문단 번호를 댈 수 없는 항목은 쓰지 않는다. summary 도 items 근거 안에서만.
3. label 은 짧고 일반적으로: 예) "단일 공급처", "관세 노출", "10% 고객", "고객 집중", "장기공급계약", "백로그 공시",
   "선수금", "과점", "진입장벽(설비·인증)", "원재료 가격 연동", "입찰 단가", "전방 사이클", "규제·인허가", "기술 대체", "대주주 매각".
   한 칸 안에서 같은 label 을 두 번 쓰지 않는다.
4. 공시에 해당 내용이 없으면 그 칸은 empty=true, summary 는 "", items 는 []. 억지로 채우지 않는다.
5. 수치는 원문 표기 그대로(숫자·단위·기준일). 환산하지 않는다. 회사가 주장한 점유율은 "(회사 주장)"을 붙인다.
6. customers 칸에는 숫자 필드를 더 쓴다: top_customers([{name, share_pct, industry}]), top2_pct(상위 2사 합산 %),
   top_n·top_n_pct(공시가 '상위 N개 고객이 X%'처럼 쓴 경우). 공시에 없는 숫자는 null.
7. overview: 회사가 무엇을 팔아 어디서 돈을 버는지 한국어 2~3문장(summary)과 사업 부문·제품·최종시장별 매출 구성(segments:
   [{name, detail, value, evidence}]).
8. relations: 공시가 이름을 밝힌 확인 관계만 — 고객·공급사·계약 상대·지분·합작. [{type: customer|supplier|contract|ownership|jv,
   name, detail, value, evidence}]. 이름 없는 익명 고객은 relations 에 넣지 않는다.

출력은 JSON 객체 하나만(코드블록 없이):
{"overview": {"summary": "", "segments": []},
 "sourcing": {"empty": false, "summary": "", "items": [{"label": "", "detail": "", "name": null, "value": null, "evidence": [1]}]},
 "customers": {"empty": false, "summary": "", "items": [], "top_customers": [], "top2_pct": null, "top_n": null, "top_n_pct": null},
 "dependencies": {...}, "orders": {...}, "competition": {...}, "pricing": {...}, "risks": {...},
 "relations": []}"""

REPAIR = "응답을 JSON 으로 읽지 못했다({error}). 같은 내용을 위 형식의 JSON 객체 하나로만 다시 써라."


def report_id(market: str, code: str, doc: Document) -> str:
    tag = f"fy{doc.fiscal_label[2:]}" if doc.fiscal_label.startswith("FY") else \
        re.sub(r"[^a-z0-9.-]+", "-", f"{doc.form}-{doc.file_date.isoformat()}".lower())
    return f"card:{market}:{code.lower()}:{tag}"[:80]


def build_user(company: str, ticker: str, doc: Document) -> tuple[str, dict[int, str]]:
    body, where, _ = numbered(doc)
    head = f"[회사] {company} ({ticker})\n[문서] {doc.key} · 접수 {doc.file_date.isoformat()} · {doc.url}\n\n"
    return head + body, where


def _int_list(v: Any, valid: set[int]) -> list[int]:
    out = []
    for x in v if isinstance(v, list) else [v]:
        try:
            n = int(str(x).strip().lstrip("P"))
        except (TypeError, ValueError):
            continue
        if n in valid and n not in out:
            out.append(n)
    return out


def _items(raw: Any, valid: set[int], where: dict[int, str]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for it in raw if isinstance(raw, list) else []:
        if not isinstance(it, dict):
            continue
        ev = _int_list(it.get("evidence"), valid)
        label = str(it.get("label") or "").strip()
        if not ev or not label or label in seen:
            continue
        seen.add(label)
        out.append({"label": label[:40], "detail": str(it.get("detail") or "").strip()[:400],
                    "name": (str(it["name"]).strip()[:120] or None) if it.get("name") else None,
                    "value": (str(it["value"]).strip()[:160] or None) if it.get("value") not in (None, "") else None,
                    "evidence": ev, "loc": sorted({where[n] for n in ev})})
    return out


def _num(v: Any) -> float | None:
    try:
        return None if v in (None, "") else float(str(v).replace("%", "").strip())
    except ValueError:
        return None


def normalize(raw: dict[str, Any], where: dict[int, str]) -> tuple[dict[str, Any], list[str]]:
    """응답 → 정리된 카드. 칸 값이 JSON 문자열로 오면 풀고, 근거 없는 항목은 버린다. 반환: (카드, 끝내 빠진 칸)."""
    valid = set(where)
    card: dict[str, Any] = {}
    missing: list[str] = []
    for slot in SLOTS:
        v = raw.get(slot)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        if not isinstance(v, dict):
            missing.append(slot)
            card[slot] = {"empty": True, "summary": "", "items": [], "status": "missing"}
            continue
        items = _items(v.get("items"), valid, where)
        empty = bool(v.get("empty")) or not items
        s: dict[str, Any] = {"empty": empty, "summary": "" if empty else str(v.get("summary") or "").strip()[:800],
                             "items": items}
        if slot == "customers":
            tops = []
            for t in v.get("top_customers") or []:
                if isinstance(t, dict) and t.get("name"):
                    tops.append({"name": str(t["name"])[:120], "share_pct": _num(t.get("share_pct")),
                                 "industry": t.get("industry")})
            s.update(top_customers=tops, top2_pct=_num(v.get("top2_pct")),
                     top_n=int(_num(v.get("top_n")) or 0) or None, top_n_pct=_num(v.get("top_n_pct")))
        card[slot] = s
    ov = raw.get("overview") if isinstance(raw.get("overview"), dict) else {}
    card["overview"] = {"summary": str(ov.get("summary") or "").strip()[:800],
                        "segments": _items([dict(x, label=x.get("name") or x.get("label")) for x in ov.get("segments") or []
                                            if isinstance(x, dict)], valid, where)}
    rels = []
    for r in raw.get("relations") or []:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        ev = _int_list(r.get("evidence"), valid)
        if not ev:
            continue
        rels.append({"type": str(r.get("type") or "contract")[:20], "name": str(r["name"])[:120],
                     "detail": str(r.get("detail") or "")[:300], "value": r.get("value"), "evidence": ev,
                     "loc": sorted({where[n] for n in ev})})
    card["relations"] = rels
    return card, missing


def filled(card: dict[str, Any]) -> int:
    return sum(1 for s in SLOTS if not card.get(s, {}).get("empty", True))


def extract(llm: Any, company: str, ticker: str, doc: Document, model: str = CARD_MODEL) -> dict[str, Any]:
    """카드 한 장. 끝내 빠진 칸이 둘 이상이면 한 번 더 부르고 채운 칸이 많은 쪽을 쓴다."""
    user, where = build_user(company, ticker, doc)
    best: tuple[dict[str, Any], list[str]] | None = None
    comps: list[Any] = []
    for attempt in range(2):
        raw, cs = llm.complete_json(CARD_SYSTEM, user, model, REPAIR, max_tokens=12_000, minimize_thinking=True)
        comps += cs
        card, missing = normalize(raw, where)
        if best is None or filled(card) > filled(best[0]):
            best = (card, missing)
        if len(missing) < 2:
            break
        log.info("card %s %s: missing %s — retry %d", ticker, doc.key, missing, attempt + 1)
    from wsj.briefs.llm import sum_usage

    card, missing = best  # type: ignore[misc]
    return {"card": card, "missing": missing, "paragraphs": len(where), "usage": sum_usage(comps)}


# ── 저장·조회 ─────────────────────────────────────────────────────────────────

def cached(store: Any | None, rid: str, accession_no: str) -> dict[str, Any] | None:
    if store is None:
        return None
    try:
        rows = store.select("research.reports", ["report_id", "body"], {"report_id": rid}, limit=1)
    except Exception as exc:  # noqa: BLE001
        log.warning("reports read failed: %s", str(exc)[:120])
        return None
    if rows and (rows[0].get("body") or {}).get("doc", {}).get("accession_no") == accession_no:
        return rows[0]["body"]
    return None


def report_row(market: str, ticker: str, company: str, doc: Document, res: dict[str, Any]) -> dict[str, Any]:
    return {"report_id": report_id(market, ticker, doc), "kind": "company",
            "title": f"{ticker} 구조 카드 {doc.key}"[:200], "subjects": [f"ticker:{market}:{ticker.lower()}"],
            "as_of": doc.file_date.isoformat(),
            "body": {"type": "structure_card", "extractor": EXTRACTOR, "company": company, "ticker": ticker,
                     "market": market, "doc": doc.meta(), **res},
            "created_by": f"{EXTRACTOR} {res.get('usage', {}).get('model') or CARD_MODEL}"}


def save(store: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"ok": 0, "rejected": []}
    if not hasattr(store, "rpc"):
        raise RuntimeError(f"{type(store).__name__} 는 rpc 를 못 부른다 — WSJ_STORE=postgrest 로 실행")
    res = store.rpc("research.put_reports", {"rows": rows}) or {}
    if res.get("rejected"):
        raise RuntimeError(f"research.put_reports 거부: {res['rejected']}")
    return res


def us_cards(llm: Any | None, store: Any | None, ticker: str, company: str, docs: list[Document],
             write: bool = True, model: str = CARD_MODEL) -> dict[str, Any]:
    """문서마다 카드: 캐시 → 없으면 추출(llm 이 None 이면 건너뛰고 plan 만). write 면 research.reports 에 저장."""
    out: dict[str, Any] = {"ticker": ticker, "cards": [], "skipped": [], "usage_usd": 0.0}
    rows = []
    for d in docs:
        rid = report_id("us", ticker, d)
        hit = cached(store, rid, d.accession_no)
        if hit:
            out["cards"].append({"report_id": rid, "doc": d.meta(), "card": hit["card"], "missing": hit.get("missing", []),
                                 "source": "cache"})
            continue
        if llm is None:
            out["skipped"].append({"report_id": rid, "doc": d.key, "chars": sum(len(t) for t in d.sections.values())})
            continue
        res = extract(llm, company, ticker, d, model=model)
        out["usage_usd"] += res["usage"].get("cost_usd") or 0.0
        rows.append(report_row("us", ticker, company, d, res))
        out["cards"].append({"report_id": rid, "doc": d.meta(), "card": res["card"], "missing": res["missing"],
                             "source": "llm"})
    if write and rows and store is not None:
        out["saved"] = save(store, rows)
    out["usage_usd"] = round(out["usage_usd"], 4)
    out["as_of"] = date.today().isoformat()
    return out
