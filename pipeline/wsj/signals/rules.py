"""신호 규칙 — 순수 함수. 입력은 raw 행(dict), 출력은 core.signals 행(dict).

규칙을 바꾸면 여기만 바꾼다. 각 함수는 네트워크·DB 를 모른다 (테스트 대상).

가족(family)과 방향(direction):
  insider   +1 open_market_buy / cluster_buy / holder_buy,  -1 cluster_sell
  contract  +1 material_agreement / asset_acquisition,       -1 contract_termination
  dilution  -1 shelf_s3 / offering_424b5 / registration_s1
  activist  +1 schedule_13d ;  institution +1 schedule_13g
  clinical  +1 completed / enrollment_done / recruiting / date_pulled_in / enrollment_up / new_trial
            -1 terminated / date_pushed_out
  fda       +1 approval / supplement_approval / clearance_510k
  gov       +1 new_award / award_modification
  flow       0 short_interest_spike / high_days_to_cover  (정보성, 후보 집계에 안 들어감)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from wsj.util import parse_date

Signal = dict[str, Any]


def _sig(
    cik: int,
    signal_date: date,
    family: str,
    kind: str,
    summary: str,
    source_table: str,
    source_key: str,
    *,
    direction: int = 1,
    strength: float = 1.0,
    url: str | None = None,
    payload: dict | None = None,
) -> Signal:
    return {
        "cik": int(cik),
        "signal_date": signal_date,
        "family": family,
        "kind": kind,
        "direction": direction,
        "strength": round(float(min(max(strength, 0.0), 10.0)), 2),
        "summary": summary[:300],
        "source_table": source_table,
        "source_key": str(source_key),
        "url": url,
        "payload": payload or {},
    }


def _usd(v: float) -> str:
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _log_strength(value: float, base: float, step: float = 2.0, floor: float = 1.0) -> float:
    """value=base → floor, 이후 step 배마다 +1. 예: base $10k, step 2 → $80k = 4."""
    if value <= 0:
        return 0.0
    return floor + math.log(max(value, base) / base, step)


# --- insider ------------------------------------------------------------------------------------


def insider_signals(filings: list[dict], transactions: list[dict], cluster_days: int = 14) -> list[Signal]:
    """Form 4 → 개별 공개매수(open_market_buy/holder_buy), 클러스터 매수, 클러스터 매도(-1).

    filings: raw.sec_form4_filings 행, transactions: raw.sec_form4_transactions 행 (해당 필링들의).
    """
    by_adsh: dict[str, dict] = {f["accession_no"]: f for f in filings}
    buys: dict[str, dict] = {}  # adsh → {value, shares, first_date}
    sells: dict[str, dict] = {}
    for t in transactions:
        if t.get("row_type") != "transaction" or t.get("table_type") != "nonDerivative":
            continue
        f = by_adsh.get(t["accession_no"])
        if not f:
            continue
        shares, price = float(t.get("shares") or 0), float(t.get("price_per_share") or 0)
        d = parse_date(t.get("transaction_date"))
        if not d or shares <= 0:
            continue
        code = t.get("transaction_code")
        if code == "P" and t.get("acquired_disposed") == "A" and price > 0:
            agg = buys.setdefault(t["accession_no"], {"value": 0.0, "shares": 0.0, "first": d, "last": d})
            agg["value"] += shares * price
            agg["shares"] += shares
            agg["first"], agg["last"] = min(agg["first"], d), max(agg["last"], d)
        elif code == "S" and t.get("acquired_disposed") == "D" and price > 0:
            agg = sells.setdefault(t["accession_no"], {"value": 0.0, "first": d})
            agg["value"] += shares * price
            agg["first"] = min(agg["first"], d)

    out: list[Signal] = []
    per_cik_buys: dict[int, list[tuple[date, int, float, str]]] = defaultdict(
        list
    )  # (date, owner, value, adsh)
    for adsh, agg in buys.items():
        f = by_adsh[adsh]
        cik = int(f["issuer_cik"])
        is_insider = bool(f.get("is_officer") or f.get("is_director"))
        kind = "open_market_buy" if is_insider else "holder_buy"
        role = f.get("officer_title") or ("Director" if f.get("is_director") else "10% owner")
        strength = _log_strength(agg["value"], 10_000) * (1.0 if is_insider else 0.6)
        out.append(
            _sig(
                cik,
                agg["last"],
                "insider",
                kind,
                f"{f.get('owner_name')} ({role}) bought {_usd(agg['value'])} ({agg['shares']:,.0f} sh) {agg['first']}~{agg['last']}",
                "raw.sec_form4_filings",
                adsh,
                strength=strength,
                url=f.get("file_url"),
                payload={
                    "value": agg["value"],
                    "shares": agg["shares"],
                    "owner_cik": f.get("owner_cik"),
                    "role": role,
                },
            )
        )
        per_cik_buys[cik].append((agg["first"], int(f.get("owner_cik") or 0), agg["value"], adsh))

    # 클러스터: 같은 발행인, cluster_days 안에 서로 다른 보고자 2명 이상
    for cik, items in per_cik_buys.items():
        items.sort()
        i = 0
        while i < len(items):
            start = items[i][0]
            window = [it for it in items if start <= it[0] <= start + timedelta(days=cluster_days)]
            owners = {it[1] for it in window}
            if len(owners) >= 2:
                value = sum(it[2] for it in window)
                last = max(it[0] for it in window)
                out.append(
                    _sig(
                        cik,
                        last,
                        "insider",
                        "cluster_buy",
                        f"{len(owners)} insiders bought {_usd(value)} total between {start} and {last}",
                        "raw.sec_form4_filings",
                        f"{cik}:{start.isoformat()}",
                        strength=min(10.0, 2.0 * len(owners) + _log_strength(value, 50_000) - 1),
                        payload={
                            "owners": len(owners),
                            "value": value,
                            "accessions": [it[3] for it in window],
                        },
                    )
                )
                i += len(window)
            else:
                i += 1

    # 클러스터 매도 (리스크): 14일 내 임원·이사 3명 이상 매도
    per_cik_sells: dict[int, list[tuple[date, int, float]]] = defaultdict(list)
    for adsh, agg in sells.items():
        f = by_adsh[adsh]
        if f.get("is_officer") or f.get("is_director"):
            per_cik_sells[int(f["issuer_cik"])].append(
                (agg["first"], int(f.get("owner_cik") or 0), agg["value"])
            )
    for cik, items in per_cik_sells.items():
        items.sort()
        if len({o for _, o, _ in items}) >= 3:
            value = sum(v for _, _, v in items)
            out.append(
                _sig(
                    cik,
                    items[-1][0],
                    "insider",
                    "cluster_sell",
                    f"{len({o for _, o, _ in items})} insiders sold {_usd(value)} total between {items[0][0]} and {items[-1][0]}",
                    "raw.sec_form4_filings",
                    f"{cik}:{items[0][0].isoformat()}",
                    direction=-1,
                    strength=min(6.0, 1.0 + _log_strength(value, 100_000)),
                )
            )
    return out


# --- filings: contract / dilution / activist ----------------------------------------------------

_ITEM_RULES = {
    "1.01": ("contract", "material_agreement", 1, 3.0, "8-K 1.01 중요 계약 체결"),
    "2.01": ("contract", "asset_acquisition", 1, 2.0, "8-K 2.01 자산 인수/처분 완료"),
    "1.02": ("contract", "contract_termination", -1, 3.0, "8-K 1.02 중요 계약 종료"),
    "2.04": ("dilution", "acceleration", -1, 3.0, "8-K 2.04 채무 조기상환 트리거"),
    "3.01": ("dilution", "listing_notice", -1, 3.0, "8-K 3.01 상장 유지 요건 통지"),
    "4.02": ("dilution", "restatement", -1, 4.0, "8-K 4.02 재무제표 정정 예고"),
}
_FORM_RULES = {
    "S-1": ("dilution", "registration_s1", -1, 3.0, "S-1 증권 등록"),
    "S-3": ("dilution", "shelf_s3", -1, 2.0, "S-3 선반등록 (희석 가능)"),
    "424B5": ("dilution", "offering_424b5", -1, 4.0, "424B5 증권 발행 설명서 (유상증자)"),
    "SCHEDULE 13D": ("activist", "schedule_13d", 1, 4.0, "13D 5% 이상 적극적 보유 공시"),
    "SCHEDULE 13G": ("institution", "schedule_13g", 1, 1.0, "13G 5% 이상 수동적 보유 공시"),
}


def filing_signals(filings: list[dict]) -> list[Signal]:
    out: list[Signal] = []
    for f in filings:
        d = parse_date(f.get("file_date"))
        if not d:
            continue
        cik = int(f["cik"])
        form = f.get("form") or ""
        names = ", ".join((f.get("display_names") or [])[:1])
        if form == "8-K":
            for item in f.get("items") or []:
                rule = _ITEM_RULES.get(item)
                if rule:
                    fam, kind, direction, strength, label = rule
                    out.append(
                        _sig(
                            cik,
                            d,
                            fam,
                            kind,
                            f"{label} — {names}",
                            "raw.sec_filings",
                            f["accession_no"],
                            direction=direction,
                            strength=strength,
                            url=f.get("file_url"),
                            payload={"items": f.get("items")},
                        )
                    )
        elif form in _FORM_RULES:
            fam, kind, direction, strength, label = _FORM_RULES[form]
            out.append(
                _sig(
                    cik,
                    d,
                    fam,
                    kind,
                    f"{label} — {names}",
                    "raw.sec_filings",
                    f["accession_no"],
                    direction=direction,
                    strength=strength,
                    url=f.get("file_url"),
                )
            )
    return out


# --- clinical ------------------------------------------------------------------------------------

_STATUS_RULES = {
    "COMPLETED": ("completed", 1, 3.0),
    "ACTIVE_NOT_RECRUITING": ("enrollment_done", 1, 2.0),
    "RECRUITING": ("recruiting", 1, 2.0),
    "TERMINATED": ("terminated", -1, 5.0),
    "SUSPENDED": ("suspended", -1, 4.0),
    "WITHDRAWN": ("withdrawn", -1, 4.0),
}


def _ct_url(nct: str) -> str:
    return f"https://clinicaltrials.gov/study/{nct}"


def clinical_change_signals(
    changes: list[dict], studies: dict[str, dict], sponsor_to_cik: dict[str, int]
) -> list[Signal]:
    """raw.ct_study_changes → 상태 변경·완료일 이동·등록 증가. studies: nct_id → ct_studies 행."""
    out: list[Signal] = []
    for ch in changes:
        st = studies.get(ch["nct_id"])
        if not st:
            continue
        cik = sponsor_to_cik.get(st.get("lead_sponsor_name") or "")
        if not cik:
            continue
        d = parse_date(str(ch.get("detected_at"))[:10]) or date.today()
        title = (st.get("brief_title") or "")[:80]
        phases = ",".join(st.get("phases") or [])
        key = f"{ch['nct_id']}:{ch['field']}:{str(ch.get('detected_at'))[:10]}"
        field, old, new = ch["field"], ch.get("old_value"), ch.get("new_value")
        if field == "overall_status" and new in _STATUS_RULES:
            kind, direction, strength = _STATUS_RULES[new]
            if "PHASE3" in phases or "PHASE2" in phases:
                strength += 1
            out.append(
                _sig(
                    cik,
                    d,
                    "clinical",
                    kind,
                    f"{ch['nct_id']} {old}→{new} ({phases}) {title}",
                    "raw.ct_study_changes",
                    key,
                    direction=direction,
                    strength=strength,
                    url=_ct_url(ch["nct_id"]),
                )
            )
        elif field == "primary_completion_date" and old and new and len(old) >= 7 and len(new) >= 7:
            if new < old:
                out.append(
                    _sig(
                        cik,
                        d,
                        "clinical",
                        "date_pulled_in",
                        f"{ch['nct_id']} 1차 완료일 {old}→{new} 앞당김 {title}",
                        "raw.ct_study_changes",
                        key,
                        strength=2.0,
                        url=_ct_url(ch["nct_id"]),
                    )
                )
            elif new > old:
                out.append(
                    _sig(
                        cik,
                        d,
                        "clinical",
                        "date_pushed_out",
                        f"{ch['nct_id']} 1차 완료일 {old}→{new} 지연 {title}",
                        "raw.ct_study_changes",
                        key,
                        direction=-1,
                        strength=2.0,
                        url=_ct_url(ch["nct_id"]),
                    )
                )
        elif field == "enrollment_count" and old and new:
            try:
                if int(float(new)) > int(float(old)):
                    out.append(
                        _sig(
                            cik,
                            d,
                            "clinical",
                            "enrollment_up",
                            f"{ch['nct_id']} 등록 {old}→{new} {title}",
                            "raw.ct_study_changes",
                            key,
                            strength=1.0,
                            url=_ct_url(ch["nct_id"]),
                        )
                    )
            except ValueError:
                pass
    return out


def clinical_new_trial_signals(
    studies: list[dict], sponsor_to_cik: dict[str, int], since: date
) -> list[Signal]:
    out: list[Signal] = []
    for st in studies:
        d = parse_date(st.get("study_first_post_date"))
        if not d or d < since:
            continue
        cik = sponsor_to_cik.get(st.get("lead_sponsor_name") or "")
        if not cik:
            continue
        phases = st.get("phases") or []
        strength = 3.0 if "PHASE3" in phases else 2.0 if "PHASE2" in phases else 1.0
        out.append(
            _sig(
                cik,
                d,
                "clinical",
                "new_trial",
                f"{st['nct_id']} 신규 등록 ({','.join(phases) or 'N/A'}) {(st.get('brief_title') or '')[:80]}",
                "raw.ct_studies",
                st["nct_id"],
                strength=strength,
                url=_ct_url(st["nct_id"]),
            )
        )
    return out


# --- fda -----------------------------------------------------------------------------------------


def fda_drug_signals(apps: list[dict], sponsor_to_cik: dict[str, int]) -> list[Signal]:
    out: list[Signal] = []
    for a in apps:
        cik = sponsor_to_cik.get(a.get("sponsor_name") or "")
        d = parse_date(a.get("latest_submission_status_date"))
        if not cik or not d or a.get("latest_submission_status") != "AP":
            continue
        orig = a.get("latest_submission_type") == "ORIG"
        kind = "approval" if orig else "supplement_approval"
        brands = ", ".join(a.get("brand_names") or [])[:60]
        out.append(
            _sig(
                cik,
                d,
                "fda",
                kind,
                f"{a['application_number']} {'신약' if orig else '보충'} 승인 ({a.get('latest_submission_class') or ''}) {brands}",
                "raw.fda_drug_applications",
                f"{a['application_number']}:{d.isoformat()}",
                strength=6.0 if orig else 2.0,
                url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={a['application_number'][3:]}",
            )
        )
    return out


def fda_510k_signals(devices: list[dict], applicant_to_cik: dict[str, int]) -> list[Signal]:
    out: list[Signal] = []
    for dv in devices:
        cik = applicant_to_cik.get(dv.get("applicant") or "")
        d = parse_date(dv.get("decision_date"))
        if not cik or not d or not str(dv.get("decision_code") or "").startswith("SE"):
            continue
        out.append(
            _sig(
                cik,
                d,
                "fda",
                "clearance_510k",
                f"{dv['k_number']} 510(k) 허가: {(dv.get('device_name') or '')[:70]}",
                "raw.fda_device_510k",
                dv["k_number"],
                strength=4.0,
                url=f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={dv['k_number']}",
            )
        )
    return out


# --- gov -----------------------------------------------------------------------------------------


def gov_award_signals(
    awards: list[dict], recipient_to_cik: dict[str, int], since: date, min_amount: float = 1_000_000
) -> list[Signal]:
    out: list[Signal] = []
    for a in awards:
        cik = recipient_to_cik.get(a.get("recipient_name") or "")
        amt = float(a.get("award_amount") or 0)
        d = parse_date(str(a.get("last_modified_date") or "")[:10])
        if not cik or not d or amt < min_amount or d < since:
            continue
        base = parse_date(a.get("base_obligation_date"))
        is_new = bool(base and base >= since)
        kind = "new_award" if is_new else "award_modification"
        out.append(
            _sig(
                cik,
                d,
                "gov",
                kind,
                f"{'신규 계약' if is_new else '계약 수정/옵션'} {_usd(amt)} — {a.get('awarding_agency')} — {(a.get('description') or '')[:60]}",
                "raw.gov_awards",
                a["generated_internal_id"],
                strength=min(10.0, 1.0 + 2.0 * math.log10(max(amt, 1e6) / 1e6)),
                url=f"https://www.usaspending.gov/award/{a['generated_internal_id']}",
                payload={"amount": amt, "agency": a.get("awarding_agency"), "naics": a.get("naics_code")},
            )
        )
    return out


# --- flow (정보성) -------------------------------------------------------------------------------


def short_interest_signals(rows: list[dict], ticker_to_cik: dict[str, int]) -> list[Signal]:
    """최신 결제일 기준: 잔고 급증(+25%) 또는 days-to-cover ≥ 8. direction 0 — 후보 집계에서 제외, 브리프 참고."""
    latest: dict[str, dict] = {}
    for r in rows:
        sym = r.get("symbol")
        if sym and (sym not in latest or str(r["settlement_date"]) > str(latest[sym]["settlement_date"])):
            latest[sym] = r
    out: list[Signal] = []
    for sym, r in latest.items():
        cik = ticker_to_cik.get(sym)
        d = parse_date(r.get("settlement_date"))
        if not cik or not d:
            continue
        chg, dtc = float(r.get("change_percent") or 0), float(r.get("days_to_cover_quantity") or 0)
        if chg >= 25:
            out.append(
                _sig(
                    cik,
                    d,
                    "flow",
                    "short_interest_spike",
                    f"{sym} 공매도 잔고 {chg:+.0f}% ({d}), days-to-cover {dtc:.1f}",
                    "raw.finra_short_interest",
                    f"{sym}:{d.isoformat()}",
                    direction=0,
                    strength=min(5.0, chg / 25),
                )
            )
        elif dtc >= 8:
            out.append(
                _sig(
                    cik,
                    d,
                    "flow",
                    "high_days_to_cover",
                    f"{sym} days-to-cover {dtc:.1f} ({d})",
                    "raw.finra_short_interest",
                    f"{sym}:{d.isoformat()}",
                    direction=0,
                    strength=min(5.0, dtc / 4),
                )
            )
    return out


# --- candidates ------------------------------------------------------------------------------------

INDEPENDENT_FAMILIES = ("insider", "contract", "clinical", "fda", "gov", "activist")


def score_candidates(signals: list[Signal], as_of: date, window_days: int = 90, top_n: int = 8) -> list[dict]:
    """90일 창의 신호를 종목별로 모아 후보 행을 만든다.

    후보 조건: 독립 가족 2개 이상 (긍정 신호) 또는 cluster_buy 1건.
    점수 = 가족별 최대 세기 합 + 2×(가족수-1) − 0.5×리스크수 (하한 0).
    """
    since = as_of - timedelta(days=window_days)
    by_cik: dict[int, list[Signal]] = defaultdict(list)
    for s in signals:
        d = s["signal_date"] if isinstance(s["signal_date"], date) else parse_date(str(s["signal_date"]))
        if d and since <= d <= as_of:
            by_cik[s["cik"]].append({**s, "signal_date": d})

    out: list[dict] = []
    for cik, sigs in by_cik.items():
        pos = [s for s in sigs if s["direction"] == 1 and s["family"] in INDEPENDENT_FAMILIES]
        neg = [s for s in sigs if s["direction"] == -1]
        fam_max: dict[str, float] = {}
        for s in pos:
            fam_max[s["family"]] = max(fam_max.get(s["family"], 0.0), float(s["strength"]))
        has_cluster = any(s["kind"] == "cluster_buy" for s in pos)
        if len(fam_max) < 2 and not has_cluster:
            continue
        score = sum(fam_max.values()) + 2.0 * (len(fam_max) - 1) - 0.5 * len(neg)
        ranked = sorted(pos, key=lambda s: (float(s["strength"]), s["signal_date"]), reverse=True)
        out.append(
            {
                "cik": cik,
                "as_of": as_of,
                "score": round(max(score, 0.0), 2),
                "families": sorted(fam_max),
                "family_count": len(fam_max),
                "signal_count_90d": len(pos),
                "risk_count_90d": len(neg),
                "first_signal_date": min(s["signal_date"] for s in pos),
                "last_signal_date": max(s["signal_date"] for s in pos),
                "top_signals": [
                    {
                        "family": s["family"],
                        "kind": s["kind"],
                        "date": s["signal_date"].isoformat(),
                        "strength": s["strength"],
                        "summary": s["summary"],
                        "url": s.get("url"),
                    }
                    for s in ranked[:top_n]
                ],
                "risks": [
                    {
                        "family": s["family"],
                        "kind": s["kind"],
                        "date": s["signal_date"].isoformat(),
                        "summary": s["summary"],
                        "url": s.get("url"),
                    }
                    for s in sorted(neg, key=lambda s: s["signal_date"], reverse=True)[:top_n]
                ],
            }
        )
    out.sort(key=lambda r: r["score"], reverse=True)
    return out
