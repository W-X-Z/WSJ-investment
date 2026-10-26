"""`wsj signals build` — raw 를 읽어 core.signals 를 upsert 하고 core.candidates 를 재계산한다.

흐름: 유니버스·별칭 로드 → 소스별 창(window) 로드 → rules.* → signals upsert → score_candidates → candidates upsert.
candidates 의 status/notes 는 사람이 바꾸므로 재계산 시 보존한다. 더 이상 조건을 못 채우는 후보는
status 가 new 일 때만 지운다 (watch/briefed/dismissed 는 남긴다).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from wsj.db.base import Store
from wsj.signals import rules
from wsj.util import chunked

log = logging.getLogger("wsj.signals")


def _alias_map(store: Store, source: str) -> dict[str, int]:
    rows = store.select("core.entity_aliases", ["alias", "cik"], {"source": source})
    return {r["alias"]: int(r["cik"]) for r in rows if r.get("cik")}


def _select_in(
    store: Store, table: str, columns: list[str] | None, col: str, values: list, extra: dict | None = None
) -> list[dict]:
    out: list[dict] = []
    for part in chunked(values, 150):
        f = dict(extra or {})
        f[col] = part
        out.extend(store.select(table, columns, f))
    return out


def build(
    store: Store, as_of: date | None = None, window_days: int = 120, candidate_window: int = 90
) -> dict[str, Any]:
    as_of = as_of or date.today()
    since = as_of - timedelta(days=window_days)
    companies = store.select(
        "core.companies", ["cik", "ticker", "name", "sector_bucket"], {"in_universe": True}
    )
    universe = [int(c["cik"]) for c in companies]
    ticker_to_cik = {c["ticker"]: int(c["cik"]) for c in companies if c.get("ticker")}
    log.info("signals build as_of=%s window=%s..%s universe=%d", as_of, since, as_of, len(universe))

    signals: list[dict] = []
    counts: dict[str, int] = {}

    # insider
    f4 = _select_in(
        store,
        "raw.sec_form4_filings",
        None,
        "issuer_cik",
        universe,
        {"file_date": ("gte", since.isoformat())},
    )
    tx = (
        _select_in(store, "raw.sec_form4_transactions", None, "accession_no", [f["accession_no"] for f in f4])
        if f4
        else []
    )
    s = rules.insider_signals(f4, tx)
    signals += s
    counts["insider"] = len(s)

    # filings: contract / dilution / activist / institution
    fl = _select_in(
        store, "raw.sec_filings", None, "cik", universe, {"file_date": ("gte", since.isoformat())}
    )
    s = rules.filing_signals(fl)
    signals += s
    counts["filings"] = len(s)

    # clinical
    sponsor_to_cik = _alias_map(store, "clinicaltrials")
    changes = store.select("raw.ct_study_changes", None, {"detected_at": ("gte", since.isoformat())})
    nct_ids = sorted({c["nct_id"] for c in changes})
    studies_changed = _select_in(store, "raw.ct_studies", None, "nct_id", nct_ids) if nct_ids else []
    s = rules.clinical_change_signals(changes, {st["nct_id"]: st for st in studies_changed}, sponsor_to_cik)
    new_studies = store.select("raw.ct_studies", None, {"study_first_post_date": ("gte", since.isoformat())})
    s += rules.clinical_new_trial_signals(new_studies, sponsor_to_cik, since)
    signals += s
    counts["clinical"] = len(s)

    # fda
    fda_sponsor = _alias_map(store, "fda")
    apps = store.select(
        "raw.fda_drug_applications", None, {"latest_submission_status_date": ("gte", since.isoformat())}
    )
    s = rules.fda_drug_signals(apps, fda_sponsor)
    devs = store.select("raw.fda_device_510k", None, {"decision_date": ("gte", since.isoformat())})
    s += rules.fda_510k_signals(devs, fda_sponsor)
    signals += s
    counts["fda"] = len(s)

    # gov
    recipient_to_cik = _alias_map(store, "usaspending")
    awards = store.select("raw.gov_awards", None, {"last_modified_date": ("gte", since.isoformat())})
    s = rules.gov_award_signals(awards, recipient_to_cik, since)
    signals += s
    counts["gov"] = len(s)

    # flow (정보성)
    si = store.select(
        "raw.finra_short_interest",
        None,
        {"settlement_date": ("gte", (as_of - timedelta(days=45)).isoformat())},
    )
    s = rules.short_interest_signals(si, ticker_to_cik)
    signals += s
    counts["flow"] = len(s)

    # 유니버스 밖 CIK(별칭이 비유니버스 회사에 붙은 경우)는 버린다 — 브리프 대상이 아니다
    uset = set(universe)
    dropped = sum(1 for x in signals if x["cik"] not in uset)
    signals = [x for x in signals if x["cik"] in uset]
    if dropped:
        log.info("dropped non-universe signals: %d", dropped)

    # upsert signals
    n = 0
    for chunk in chunked(signals, 300):
        n += store.upsert("core.signals", chunk, ["cik", "family", "kind", "source_key"])
    log.info("signals upserted: %d %s", n, counts)

    # candidates — 창 안의 모든 신호(기존 저장분 포함)로 재계산
    stored = store.select(
        "core.signals", None, {"signal_date": ("gte", (as_of - timedelta(days=candidate_window)).isoformat())}
    )
    cands = rules.score_candidates(stored, as_of, candidate_window)
    existing = {int(r["cik"]): r for r in store.select("core.candidates", ["cik", "status", "notes"])}
    rows = []
    for c in cands:
        prev = existing.get(c["cik"])
        rows.append(
            {
                **c,
                "status": prev["status"] if prev else "new",
                "notes": prev.get("notes") if prev else None,
                "updated_at": as_of.isoformat(),
            }
        )
    for chunk in chunked(rows, 300):
        store.upsert("core.candidates", chunk, ["cik"])
    qualified = {c["cik"] for c in cands}
    stale_new = [cik for cik, r in existing.items() if cik not in qualified and r.get("status") == "new"]
    if stale_new:
        store.delete("core.candidates", {"cik": stale_new})
    log.info("candidates: %d (removed stale new: %d)", len(rows), len(stale_new))
    return {"signals": n, "by_family": counts, "candidates": len(rows), "removed": len(stale_new)}
