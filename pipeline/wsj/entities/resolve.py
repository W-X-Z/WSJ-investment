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


def _company_index(store: Store) -> tuple[dict[str, int], dict[str, list[dict]]]:
    exact: dict[str, int] = {}
    loose: dict[str, list[dict]] = defaultdict(list)
    for c in store.select("core.companies", ["cik", "name", "ticker", "in_universe", "former_names"]):
        names = [c["name"]] + [fn.get("name") for fn in (c.get("former_names") or []) if isinstance(fn, dict)]
        for nm in names:
            n = normalize_name(nm)
            if n and n not in exact:
                exact[n] = int(c["cik"])
            ln = normalize_name(nm, strip_industry_words=True)
            if ln:
                loose[ln].append(
                    {
                        "cik": int(c["cik"]),
                        "name": c["name"],
                        "ticker": c.get("ticker"),
                        "in_universe": c.get("in_universe"),
                    }
                )
    return exact, loose


def resolve_all(store: Store, dry_run: bool = False) -> dict[str, Any]:
    exact, loose = _company_index(store)
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
            cik = exact.get(norm)
            if cik:
                matched.append(
                    {
                        "source": source,
                        "alias_type": alias_type,
                        "alias": raw_name,
                        "alias_norm": norm,
                        "cik": cik,
                        "confidence": 0.9,
                        "method": "normalized",
                        "verified_at": None,
                    }
                )
                continue
            cands = loose.get(normalize_name(raw_name, strip_industry_words=True), [])
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
