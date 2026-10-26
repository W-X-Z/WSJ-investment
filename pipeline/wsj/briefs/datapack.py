"""데이터팩 — 브리프 한 건의 입력을 결정론적으로 모은다 (LLM 없음). ADR-0009 §2.

구성:
  company / candidate / signals(180d) / insider(365d 거래 상세) / short_interest / clinical / fda / awards
  / peers(SIC 동일, 시총 근접) / filings(최근 12개월 제출 목록) / financials(XBRL 12분기) / prices(1y)
  / documents(10-K Item 1·1A·7, 최신 10-Q MD&A 는 Phase 2, 8-K ≤3)

렌더:
  render_core()  — 수치·목록만 (리서치·비평 단계 입력, ~10k 토큰)
  render_full()  — core + 원문 섹션 (종합 단계 입력)
  summary()      — DB 저장용 요약 (원문 제외)
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from wsj.briefs import edgar_docs, xbrl
from wsj.db.base import Store
from wsj.http import HttpClient
from wsj.marketdata import nasdaq

log = logging.getLogger("wsj.briefs.datapack")


@dataclass
class DataPack:
    cik: int
    as_of: date
    company: dict[str, Any]
    candidate: dict[str, Any] | None = None
    signals: list[dict[str, Any]] = field(default_factory=list)
    insider: list[dict[str, Any]] = field(default_factory=list)
    short_interest: list[dict[str, Any]] = field(default_factory=list)
    clinical: list[dict[str, Any]] = field(default_factory=list)
    fda: list[dict[str, Any]] = field(default_factory=list)
    awards: list[dict[str, Any]] = field(default_factory=list)
    peers: list[dict[str, Any]] = field(default_factory=list)
    filings: list[dict[str, Any]] = field(default_factory=list)
    financials: dict[str, Any] = field(default_factory=dict)
    prices: dict[str, Any] = field(default_factory=dict)
    event_returns: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ticker(self) -> str | None:
        return self.company.get("ticker")

    # ------------------------------------------------------------------ 저장용
    def summary(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "company": {
                k: self.company.get(k)
                for k in (
                    "cik",
                    "ticker",
                    "name",
                    "sector_bucket",
                    "sic",
                    "sic_description",
                    "exchange",
                    "public_float",
                    "public_float_asof",
                    "fiscal_year_end",
                    "business_state",
                )
            },
            "candidate": self.candidate,
            "signals": [
                {
                    k: s.get(k)
                    for k in ("signal_date", "family", "kind", "direction", "strength", "summary", "url")
                }
                for s in self.signals
            ],
            "insider": self.insider[:30],
            "short_interest": self.short_interest[:8],
            "clinical": [
                {
                    k: s.get(k)
                    for k in (
                        "nct_id",
                        "brief_title",
                        "overall_status",
                        "phases",
                        "primary_completion_date",
                        "enrollment_count",
                        "last_update_post_date",
                    )
                }
                for s in self.clinical[:15]
            ],
            "fda": self.fda[:10],
            "awards": self.awards[:10],
            "peers": self.peers,
            "filings": self.filings[:40],
            "financials": {
                "derived": self.financials.get("derived"),
                "quarters": self.financials.get("quarters"),
                "annual": self.financials.get("annual"),
                "shares_outstanding": self.financials.get("shares_outstanding"),
                "tags_used": self.financials.get("tags_used"),
            },
            "prices": self.prices,
            "event_returns": self.event_returns,
            "documents": [
                {
                    k: d.get(k)
                    for k in (
                        "form",
                        "section",
                        "accession_no",
                        "file_date",
                        "source_url",
                        "char_count",
                        "extracted_by",
                        "truncated",
                    )
                }
                for d in self.documents
            ],
            "notes": self.notes,
        }

    def to_json(self) -> str:
        d = self.summary()
        d["documents_text"] = [
            {"form": x["form"], "section": x["section"], "text": x["text"]} for x in self.documents
        ]
        return json.dumps(d, ensure_ascii=False, indent=1, default=str)

    # ------------------------------------------------------------------ 렌더
    def render_core(self) -> str:
        c = self.company
        fin = self.financials or {}
        der = fin.get("derived") or {}
        px = self.prices or {}
        out: list[str] = []
        out.append(
            f"# {c.get('name')} ({c.get('ticker') or 'no ticker'}) — 데이터팩 기준일 {self.as_of.isoformat()}"
        )
        out.append("")
        out.append("## 회사")
        out.append(
            f"- CIK {c.get('cik')} · 거래소 {c.get('exchange')} · SIC {c.get('sic')} {c.get('sic_description')} · 섹터 버킷 {c.get('sector_bucket')}"
        )
        out.append(
            f"- 소재지 {c.get('business_state')} · 설립지 {c.get('state_of_incorporation')} · 회계연도말 {c.get('fiscal_year_end')} · SEC 분류 {str(c.get('filer_category') or '').replace('<br>', ' ').strip()}"
        )
        out.append(
            f"- 공개유동 시가총액(최근 10-K dei:EntityPublicFloat) {_usd(c.get('public_float'))} (기준 {c.get('public_float_asof')})"
        )
        if c.get("former_names"):
            names = c["former_names"] if isinstance(c["former_names"], list) else []
            names = [
                n
                for n in names
                if (n.get("name") or "").strip().lower() != (c.get("name") or "").strip().lower()
            ]
            if names:
                out.append(
                    "- 옛 이름: "
                    + "; ".join(f"{n.get('name')} (~{str(n.get('to') or '')[:10]})" for n in names[:5])
                )
        out.append("")

        out.append("## 주가·유동성 (Nasdaq 일봉, 미조정)")
        if px.get("available"):
            out.append(
                f"- 종가 {px['last_close']:.2f} ({px['as_of']}) · 시총(주식수×종가) {_usd(px.get('market_cap'))} · 20일 평균 거래대금 {_usd(px.get('adv20_usd'))}"
            )
            out.append(
                f"- 수익률 1M {_pct(px.get('ret_1m'))} · 3M {_pct(px.get('ret_3m'))} · 6M {_pct(px.get('ret_6m'))} · 12M {_pct(px.get('ret_12m'))}"
            )
            out.append(
                f"- 52주 고가 {px['high_52w']:.2f} ({px['high_52w_date']}) 대비 {_pct(px.get('pct_from_52w_high'))} · 52주 저가 {px['low_52w']:.2f} ({px['low_52w_date']}) 대비 {_pct(px.get('pct_from_52w_low'))} · 1년 최대낙폭 {_pct(px.get('max_drawdown_1y'))} · 20일 실현변동성(연율) {_pct(px.get('realized_vol_20d_annualized'))}"
            )
            mc = px.get("monthly_closes") or []
            if mc:
                out.append("- 월말 종가: " + ", ".join(f"{m['date'][:7]} {m['close']:.2f}" for m in mc))
        else:
            out.append("- 시세 없음 (티커 없음 또는 조회 실패)")
        if self.event_returns:
            out.append("- 신호 전후 수익률 (T=신호일 이후 첫 거래일):")
            for e in self.event_returns:
                out.append(
                    f"  - {e['label']} {e['event_date']}: 직전5일 {_pct(e.get('ret_pre_5d'))} · 이후5일 {_pct(e.get('ret_post_5d'))} · 이후20일 {_pct(e.get('ret_post_20d'))} · 신호일 이후 현재까지 {_pct(e.get('ret_since_event'))} (T 종가 {e.get('close_t')})"
                )
        out.append("")

        out.append("## 재무 (XBRL companyfacts, USD)")
        if fin.get("quarters"):
            out.append(
                f"- 최근 분기말 {der.get('latest_period_end')} · TTM 매출 {_usd(der.get('ttm_revenue'))} (보고 분기 {der.get('ttm_revenue_quarters_reported')}/4, YoY {_pct(der.get('ttm_revenue_yoy'))}) · 최근 분기 매출 YoY {_pct(der.get('latest_quarter_revenue_yoy'))} · TTM 매출총이익률 {_pct(der.get('ttm_gross_margin'))}"
            )
            out.append(
                f"- TTM 순이익 {_usd(der.get('ttm_net_income'))} · TTM 영업현금흐름 {_usd(der.get('ttm_ocf'))} · TTM R&D {_usd(der.get('ttm_rnd'))} · TTM 주식보상 {_usd(der.get('ttm_sbc'))}"
            )
            out.append(
                f"- 현금+단기투자 {_usd(der.get('liquidity_cash_and_st_investments'))} · 부채 {_usd(der.get('debt_total'))} · 월 소진 {_usd(der.get('monthly_burn'))} · 런웨이 {_num(der.get('runway_months'), '개월')}"
            )
            sl = der.get("shares_latest") or {}
            out.append(
                f"- 발행주식수 {_num(sl.get('value'))} ({sl.get('as_of')}) · 희석 1Y {_pct(der.get('dilution_1y'))} · 2Y {_pct(der.get('dilution_2y'))}"
            )
            out.append("")
            out.append("분기 (백만 USD; 빈칸=미보고):")
            out.append(
                "| 분기말 | 매출 | 매출총이익 | R&D | SG&A | 영업이익 | 순이익 | 영업CF | 현금 | 단기투자 | 장기부채 | 이연매출 | 주식수(백만) |"
            )
            out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for q in fin["quarters"]:
                out.append(
                    "| "
                    + " | ".join(
                        [
                            q["period_end"],
                            _m(q.get("revenue")),
                            _m(q.get("gross_profit")),
                            _m(q.get("rnd")),
                            _m(q.get("sga")),
                            _m(q.get("op_income")),
                            _m(q.get("net_income")),
                            _m(q.get("ocf")),
                            _m(q.get("cash")),
                            _m(q.get("st_investments")),
                            _m(q.get("debt_lt")),
                            _m(q.get("deferred_revenue")),
                            _m(q.get("shares_out")),
                        ]
                    )
                    + " |"
                )
            if fin.get("annual"):
                out.append("")
                out.append("연간 (백만 USD):")
                out.append(
                    "| 회계연도말 | 매출 | R&D | SG&A | 영업이익 | 순이익 | 영업CF | 현금+단기투자 | 주식수(백만) |"
                )
                out.append("|---|---|---|---|---|---|---|---|---|")
                for a in fin["annual"]:
                    liq = (
                        (a.get("cash") or 0) + (a.get("st_investments") or 0)
                        if (a.get("cash") is not None or a.get("st_investments") is not None)
                        else None
                    )
                    out.append(
                        "| "
                        + " | ".join(
                            [
                                a["fiscal_year_end"],
                                _m(a.get("revenue")),
                                _m(a.get("rnd")),
                                _m(a.get("sga")),
                                _m(a.get("op_income")),
                                _m(a.get("net_income")),
                                _m(a.get("ocf")),
                                _m(liq),
                                _m(a.get("shares_out")),
                            ]
                        )
                        + " |"
                    )
            if fin.get("tags_used"):
                tags = ", ".join(
                    f"{k}={v.split(':')[1]}"
                    for k, v in fin["tags_used"].items()
                    if k in ("revenue", "cash", "shares_out")
                )
                out.append(f"- 사용 태그: {tags}")
        else:
            out.append("- XBRL 재무 없음")
        out.append("")

        out.append(f"## 신호 (core.signals, 최근 180일, {len(self.signals)}건)")
        if self.candidate:
            cd = self.candidate
            out.append(
                f"- 후보 점수 {cd.get('score')} · 계열 {cd.get('families')} · 90일 신호 {cd.get('signal_count_90d')} / 리스크 {cd.get('risk_count_90d')} · 첫 신호 {cd.get('first_signal_date')} · 마지막 {cd.get('last_signal_date')}"
            )
        for s in self.signals:
            arrow = "+" if s.get("direction", 0) > 0 else ("−" if s.get("direction", 0) < 0 else "·")
            out.append(
                f"- {s.get('signal_date')} [{arrow}{s.get('family')}/{s.get('kind')} 세기 {s.get('strength')}] {s.get('summary')} {('<' + s['url'] + '>') if s.get('url') else ''}"
            )
        out.append("")

        out.append(f"## 내부자 거래 (Form 4, 최근 365일 공개시장 매수·매도, {len(self.insider)}건)")
        if self.insider:
            out.append("| 거래일 | 보고자 | 직책 | 코드 | 주식수 | 단가 | 금액 | 거래 후 보유 | 원문 |")
            out.append("|---|---|---|---|---|---|---|---|---|")
            for t in self.insider[:40]:
                out.append(
                    f"| {t['transaction_date']} | {t['owner_name']} | {t.get('role')} | {t['code']} | {_num(t.get('shares'))} | {_num(t.get('price'), fmt='{:.2f}')} | {_usd(t.get('value'))} | {_num(t.get('owned_after'))} | {t.get('url') or ''} |"
                )
        else:
            out.append("- 없음")
        out.append("")

        out.append("## 공매도 잔고 (FINRA, 격주)")
        if self.short_interest:
            out.append("| 결제일 | 공매도 잔고 | 전기 대비 | 일평균 거래량 | 커버일수 |")
            out.append("|---|---|---|---|---|")
            for r in self.short_interest[:8]:
                out.append(
                    f"| {r['settlement_date']} | {_num(r.get('current_short_position_quantity'))} | {_pct((r.get('change_percent') or 0) / 100 if r.get('change_percent') is not None else None)} | {_num(r.get('average_daily_volume_quantity'))} | {_num(r.get('days_to_cover_quantity'), fmt='{:.1f}')} |"
                )
        else:
            out.append("- 없음")
        out.append("")

        if self.clinical:
            out.append(f"## 임상시험 (ClinicalTrials.gov, 스폰서 매칭 {len(self.clinical)}건, 최근 갱신순)")
            for s in self.clinical[:15]:
                out.append(
                    f"- {s['nct_id']} [{s.get('overall_status')}] {s.get('brief_title')} · 단계 {s.get('phases')} · 등록 {s.get('enrollment_count')} · 1차 완료 {s.get('primary_completion_date')} · 갱신 {s.get('last_update_post_date')}"
                    + (f" · 중단 사유: {s['why_stopped']}" if s.get("why_stopped") else "")
                )
            out.append("")
        if self.fda:
            out.append(f"## FDA (openFDA, {len(self.fda)}건)")
            for r in self.fda[:10]:
                out.append(f"- {r}")
            out.append("")
        if self.awards:
            out.append(f"## 연방 계약·보조금 (USAspending, 최근 24개월 금액순 {len(self.awards)}건)")
            for a in self.awards[:10]:
                out.append(
                    f"- {a.get('award_id')} {_usd(a.get('award_amount'))} · {a.get('awarding_agency')} / {a.get('awarding_sub_agency')} · {a.get('start_date')}~{a.get('end_date')} · {(a.get('description') or '')[:140]}"
                )
            out.append("")

        out.append(f"## 피어 (유니버스 내 SIC 동일, 공개유동 근접 {len(self.peers)}개)")
        if self.peers:
            out.append("| 티커 | 이름 | 공개유동 | 3M | 6M | 12M |")
            out.append("|---|---|---|---|---|---|")
            for p in self.peers:
                out.append(
                    f"| {p.get('ticker')} | {p.get('name')} | {_usd(p.get('public_float'))} | {_pct(p.get('ret_3m'))} | {_pct(p.get('ret_6m'))} | {_pct(p.get('ret_12m'))} |"
                )
        out.append("")

        out.append(f"## 최근 제출 목록 (EDGAR submissions, 최근 12개월, {len(self.filings)}건)")
        for f in self.filings[:40]:
            items = f" items={','.join(f['items'])}" if f.get("items") else ""
            out.append(f"- {f['file_date']} {f['form']}{items} {f.get('description') or ''} <{f['url']}>")
        out.append("")
        if self.notes:
            out.append("## 데이터 비고")
            for n in self.notes:
                out.append(f"- {n}")
        return "\n".join(out)

    def render_full(self) -> str:
        parts = [self.render_core(), ""]
        for d in self.documents:
            title = {
                "item_1": "Item 1. Business",
                "item_1a": "Item 1A. Risk Factors",
                "item_7": "Item 7. MD&A",
                "mdna": "Part I Item 2. MD&A (분기)",
                "full": "본문",
            }.get(d["section"], d["section"])
            parts.append(
                f"## 원문: {d['form']} {d.get('file_date')} — {title} (accession {d['accession_no']}, {d['char_count']}자{', 잘림' if d.get('truncated') else ''}) <{d['source_url']}>"
            )
            parts.append("")
            parts.append(d["text"])
            parts.append("")
        return "\n".join(parts)


# ---------------------------------------------------------------------- 포맷 헬퍼
def _usd(v: Any) -> str:
    if v is None:
        return "없음"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    if a >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _m(v: Any) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v) / 1e6:.1f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v: Any) -> str:
    if v is None:
        return "없음"
    try:
        return f"{float(v) * 100:+.1f}%"
    except (TypeError, ValueError):
        return str(v)


def _num(v: Any, unit: str = "", fmt: str = "{:,.0f}") -> str:
    if v is None:
        return "없음"
    try:
        return fmt.format(float(v)) + unit
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------- 조립
def _aliases(store: Store, cik: int, source: str) -> list[str]:
    rows = store.select("core.entity_aliases", ["alias"], {"cik": cik, "source": source})
    return [r["alias"] for r in rows]


def _insider_rows(store: Store, cik: int, since: date) -> list[dict[str, Any]]:
    filings = store.select(
        "raw.sec_form4_filings", None, {"issuer_cik": cik, "file_date": ("gte", since.isoformat())}
    )
    if not filings:
        return []
    by_acc = {f["accession_no"]: f for f in filings}
    txs = store.select("raw.sec_form4_transactions", None, {"accession_no": list(by_acc)})
    out: list[dict[str, Any]] = []
    for t in txs:
        if t.get("row_type") != "transaction" or t.get("table_type") != "nonDerivative":
            continue
        code = t.get("transaction_code")
        if code not in ("P", "S"):
            continue
        f = by_acc[t["accession_no"]]
        shares = float(t.get("shares") or 0)
        price = float(t["price_per_share"]) if t.get("price_per_share") is not None else None
        role = f.get("officer_title") or (
            "Director"
            if f.get("is_director")
            else ("10% owner" if f.get("is_ten_percent_owner") else "Other")
        )
        out.append(
            {
                "transaction_date": str(t.get("transaction_date"))[:10],
                "owner_name": f.get("owner_name"),
                "role": role,
                "code": code,
                "shares": shares,
                "price": price,
                "value": shares * price if price is not None else None,
                "owned_after": float(t["shares_owned_following"])
                if t.get("shares_owned_following") is not None
                else None,
                "url": f.get("file_url"),
                "accession_no": t["accession_no"],
            }
        )
    out.sort(key=lambda x: x["transaction_date"], reverse=True)
    return out


def _peers(store: Store, company: dict[str, Any], n: int = 8) -> list[dict[str, Any]]:
    cik = int(company["cik"])
    pf = float(company.get("public_float") or 0) or None
    rows: list[dict[str, Any]] = []
    if company.get("sic"):
        rows = store.select(
            "core.companies",
            ["cik", "ticker", "name", "public_float", "sic"],
            {"in_universe": True, "sic": company["sic"]},
        )
    if len(rows) < 5 and company.get("sector_bucket"):
        more = store.select(
            "core.companies",
            ["cik", "ticker", "name", "public_float", "sic"],
            {"in_universe": True, "sector_bucket": company["sector_bucket"]},
        )
        seen = {int(r["cik"]) for r in rows}
        rows += [r for r in more if int(r["cik"]) not in seen]
    rows = [r for r in rows if int(r["cik"]) != cik and r.get("ticker")]

    def dist(r: dict) -> float:
        v = float(r.get("public_float") or 0)
        if not pf or not v:
            return 99.0
        return abs(math.log(v / pf))

    rows.sort(key=dist)
    return rows[:n]


def build_datapack(
    store: Store,
    http: HttpClient,
    cik: int,
    as_of: date | None = None,
    with_documents: bool = True,
    peer_prices: int = 6,
) -> DataPack:
    as_of = as_of or date.today()
    comp = store.select("core.companies", None, {"cik": cik})
    if not comp:
        raise ValueError(f"core.companies 에 CIK {cik} 없음")
    company = comp[0]
    dp = DataPack(cik=cik, as_of=as_of, company=company)

    cand = store.select("core.candidates", None, {"cik": cik})
    dp.candidate = cand[0] if cand else None

    since180 = (as_of - timedelta(days=180)).isoformat()
    dp.signals = sorted(
        store.select("core.signals", None, {"cik": cik, "signal_date": ("gte", since180)}),
        key=lambda s: str(s["signal_date"]),
        reverse=True,
    )
    dp.insider = _insider_rows(store, cik, as_of - timedelta(days=365))

    ticker = company.get("ticker")
    if ticker:
        si = store.select(
            "raw.finra_short_interest", None, {"symbol": ticker}, order="settlement_date.desc", limit=8
        )
        dp.short_interest = sorted(si, key=lambda r: str(r["settlement_date"]), reverse=True)

    ct_names = _aliases(store, cik, "clinicaltrials")
    if ct_names:
        studies = store.select("raw.ct_studies", None, {"lead_sponsor_name": ct_names})
        dp.clinical = sorted(studies, key=lambda s: str(s.get("last_update_post_date") or ""), reverse=True)
    fda_names = _aliases(store, cik, "fda")
    if fda_names:
        apps = store.select(
            "raw.fda_drug_applications",
            [
                "application_number",
                "sponsor_name",
                "brand_names",
                "generic_names",
                "latest_submission_status",
                "latest_submission_status_date",
                "latest_submission_type",
            ],
            {"sponsor_name": fda_names},
        )
        devs = store.select(
            "raw.fda_device_510k",
            ["k_number", "applicant", "device_name", "decision_code", "decision_date", "product_code"],
            {"applicant": fda_names},
        )
        dp.fda = apps + devs
    gov_names = _aliases(store, cik, "usaspending")
    if gov_names:
        aw = store.select(
            "raw.gov_awards",
            [
                "award_id",
                "recipient_name",
                "award_amount",
                "description",
                "start_date",
                "end_date",
                "awarding_agency",
                "awarding_sub_agency",
                "naics_description",
                "psc_description",
                "last_modified_date",
            ],
            {"recipient_name": gov_names, "start_date": ("gte", (as_of - timedelta(days=730)).isoformat())},
        )
        dp.awards = sorted(aw, key=lambda a: float(a.get("award_amount") or 0), reverse=True)

    # XBRL
    try:
        cf = xbrl.load_companyfacts(http, cik)
        dp.financials = xbrl.build_financials(cf) if cf else {}
        if not cf:
            dp.notes.append("companyfacts 없음 (XBRL 미제출 또는 신규 등록)")
    except Exception as exc:  # noqa: BLE001
        log.warning("companyfacts failed %s: %s", cik, exc)
        dp.notes.append(f"companyfacts 조회 실패: {exc}")

    shares = ((dp.financials.get("derived") or {}).get("shares_latest") or {}).get("value")

    # 시세
    if ticker:
        rows = nasdaq.get_daily(store, http, ticker, as_of)
        dp.prices = nasdaq.price_metrics(rows, shares)
        if not dp.prices.get("available"):
            dp.notes.append("시세 조회 실패 — 가격 맥락 없음")
        # 신호 전후 수익률: 상위 신호(계열별 최근 1건, 최대 5)
        seen: set[str] = set()
        for s in dp.signals:
            if s.get("direction", 0) <= 0 or s["family"] in seen or len(seen) >= 5:
                continue
            seen.add(s["family"])
            er = nasdaq.event_window_returns(rows, str(s["signal_date"])[:10])
            if er:
                er["label"] = f"{s['family']}/{s['kind']}"
                dp.event_returns.append(er)
    else:
        dp.notes.append("티커 없음 — 시세·공매도 없음")

    # 피어
    peers = _peers(store, company)
    for i, p in enumerate(peers):
        row = {
            "cik": int(p["cik"]),
            "ticker": p.get("ticker"),
            "name": p.get("name"),
            "public_float": p.get("public_float"),
        }
        if i < peer_prices and p.get("ticker"):
            prow = nasdaq.get_daily(store, http, p["ticker"], as_of)
            pm = nasdaq.price_metrics(prow) if prow else {}
            row.update({k: pm.get(k) for k in ("ret_3m", "ret_6m", "ret_12m")})
        dp.peers.append(row)

    # 제출 목록 + 원문
    try:
        sub = edgar_docs.load_submissions(http, cik)
        filings = edgar_docs.recent_filings(sub)
        since365 = as_of - timedelta(days=365)
        dp.filings = [
            {
                "accession_no": f.accession_no,
                "form": f.form,
                "file_date": f.file_date.isoformat(),
                "items": f.items,
                "description": f.description,
                "url": f.index_url(cik),
            }
            for f in filings
            if f.file_date >= since365 and f.form not in ("4", "3", "5", "4/A", "144", "SC 13G", "SC 13G/A")
        ]
        if with_documents:
            picked = edgar_docs.pick_documents(filings, as_of)
            if picked["annual"]:
                for sec in edgar_docs.tenk_sections(store, http, cik, picked["annual"]):
                    dp.documents.append(_doc(sec))
            else:
                dp.notes.append("연차 보고서(10-K/20-F/S-1) 없음 — 사업 설명 원문 없음")
            if picked["quarterly"]:
                q = edgar_docs.tenq_mdna(store, http, cik, picked["quarterly"])
                if q:
                    dp.documents.append(_doc(q))
            for sec in edgar_docs.eightk_texts(store, http, cik, picked["eightks"]):
                dp.documents.append(_doc(sec))
    except Exception as exc:  # noqa: BLE001
        log.warning("edgar docs failed %s: %s", cik, exc)
        dp.notes.append(f"EDGAR 원문 조회 실패: {exc}")
    return dp


def _doc(sec: edgar_docs.DocSection) -> dict[str, Any]:
    return {
        "form": sec.form,
        "section": sec.section,
        "accession_no": sec.accession_no,
        "file_date": sec.file_date.isoformat() if sec.file_date else None,
        "source_url": sec.source_url,
        "char_count": len(sec.text),
        "extracted_by": sec.extracted_by,
        "truncated": sec.truncated,
        "text": sec.text,
    }
