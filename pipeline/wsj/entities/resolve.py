"""raw 테이블의 소스별 이름 → core.entity_aliases (정확·정규화 매칭) / core.entity_unresolved (나머지).

매칭 단계 (ADR-0005 §4):
  a) 정확 키 (티커) — 이 모듈에서는 FINRA 가 티커로 조인되므로 별칭 불필요
  b) 법인명 정규화 정확 일치 → method='normalized', confidence 0.9
  c) 업종어까지 제거한 정규화로 후보만 제시 → entity_unresolved.candidates (자동 승인 안 함)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from wsj.db.base import Store
from wsj.util import chunked, normalize_name

# (source, alias_type, raw table, column)
SOURCES: tuple[tuple[str, str, str, str], ...] = (
    ("clinicaltrials", "sponsor_name", "raw.ct_studies", "lead_sponsor_name"),
    ("fda", "sponsor_name", "raw.fda_drug_applications", "sponsor_name"),
    ("fda", "applicant", "raw.fda_device_510k", "applicant"),
    ("usaspending", "recipient_name", "raw.gov_awards", "recipient_name"),
)


def _company_index(store: Store) -> tuple[dict[str, set[int]], dict[str, set[int]], dict[str, list[dict]]]:
    """(현재 법인명 정규화 → CIK 집합, 구 사명 정규화 → CIK 집합, 업종어 제거 정규화 → 후보 목록).

    같은 정규화 이름이 둘 이상의 CIK 를 가리키면(동명·사명 승계) 자동 매칭하지 않고 큐로 보낸다.
    """
    exact_current: dict[str, set[int]] = defaultdict(set)
    exact_former: dict[str, set[int]] = defaultdict(set)
    loose: dict[str, list[dict]] = defaultdict(list)
    for c in store.select("core.companies", ["cik", "name", "ticker", "in_universe", "former_names"]):
        cik = int(c["cik"])
        cand = {"cik": cik, "name": c["name"], "ticker": c.get("ticker"), "in_universe": c.get("in_universe")}
        n = normalize_name(c["name"])
        if n:
            exact_current[n].add(cik)
        ln = normalize_name(c["name"], strip_industry_words=True)
        if ln:
            loose[ln].append(cand)
        for fn in c.get("former_names") or []:
            fname = fn.get("name") if isinstance(fn, dict) else None
            fn_norm = normalize_name(fname)
            if fn_norm:
                exact_former[fn_norm].add(cik)
                fln = normalize_name(fname, strip_industry_words=True)
                if fln and cand not in loose[fln]:
                    loose[fln].append(cand)
    return exact_current, exact_former, loose


def resolve_all(store: Store, dry_run: bool = False) -> dict[str, Any]:
    exact_current, exact_former, loose = _company_index(store)
    known = {
        (a["source"], a["alias_type"], a["alias"])
        for a in store.select("core.entity_aliases", ["source", "alias_type", "alias"])
    }
    now = datetime.utcnow().isoformat()
    summary: dict[str, Any] = {}

    for source, alias_type, table, column in SOURCES:
        names = {r[column] for r in store.select(table, [column]) if r.get(column)}
        new_names = [n for n in names if (source, alias_type, n) not in known]
        matched: list[dict] = []
        unresolved: list[dict] = []
        for raw_name in new_names:
            norm = normalize_name(raw_name)
            cur, former = exact_current.get(norm, set()), exact_former.get(norm, set())
            hit: tuple[int, float] | None = None
            if len(cur) == 1:
                hit = (next(iter(cur)), 0.9)
            elif not cur and len(former) == 1:
                hit = (next(iter(former)), 0.8)  # 구 사명 일치는 신뢰도 낮게
            if hit:
                matched.append(
                    {
                        "source": source,
                        "alias_type": alias_type,
                        "alias": raw_name,
                        "alias_norm": norm,
                        "cik": hit[0],
                        "confidence": hit[1],
                        "method": "normalized",
                        "verified_at": None,
                    }
                )
                continue
            # 동명 충돌(현재/구 사명이 2개 이상 CIK) 또는 업종어 제거 후보 → 큐
            cands = loose.get(normalize_name(raw_name, strip_industry_words=True), [])
            if cur or former:
                ambiguous = cur | former
                cands = [c for c in cands if c["cik"] in ambiguous] or [{"cik": k} for k in sorted(ambiguous)]
            if not cands:
                continue  # 후보조차 없으면 큐에 넣지 않는다 (대부분 비상장·대형사·대학)
            unresolved.append(
                {
                    "source": source,
                    "alias_type": alias_type,
                    "alias": raw_name,
                    "alias_norm": norm,
                    "candidates": cands[:5],
                    "last_seen": now,
                }
            )
        summary[f"{source}.{alias_type}"] = {
            "names": len(names),
            "new": len(new_names),
            "matched": len(matched),
            "queued": len(unresolved),
        }
        if dry_run:
            continue
        for chunk in chunked(matched, 300):
            store.upsert("core.entity_aliases", chunk, ["source", "alias_type", "alias"])
        for chunk in chunked(unresolved, 300):
            store.upsert("core.entity_unresolved", chunk, ["source", "alias_type", "alias"])
    return summary
