"""openfda — drugsfda (제출 이력 기준 증분) + device/510k (결정일 기준 증분).

스폰서명으로 검색하지 않는다: sponsor_name 은 정확 일치 전용 필드라 변형에 약하다.
대신 날짜 창으로 전부 받아 raw 에 두고 entities resolve 가 매칭한다 (ADR-0005).
키가 없으면 1,000/일 한도 — OPENFDA_API_KEY 권장.
"""

from __future__ import annotations

from datetime import date, timedelta

from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import chunked, parse_date

BASE = "https://api.fda.gov"
PAGE = 100  # limit 최대 1000 이지만 안전하게
MAX_SKIP = 25000  # openFDA skip 상한


def _ymd(d: date) -> str:
    return d.strftime("%Y%m%d")


def _paged(
    http, endpoint: str, search: str, api_key: str, limit_rows: int | None, key_field: str, notes: list[str]
) -> list[dict]:
    """skip 페이징. 키는 basic auth(username=key) 로 보내 URL·로그에 남기지 않는다.
    같은 레코드가 페이지 사이에서 중복될 수 있어 key_field 로 dedupe 한다 (PG 21000 방지)."""
    out: dict[str, dict] = {}
    skip = 0
    auth = (api_key, "") if api_key else None
    while True:
        params = {"search": search, "limit": PAGE, "skip": skip}
        data = http.get_json_or_none(f"{BASE}/{endpoint}.json", params=params, auth=auth)
        if not data or "results" not in data:
            break
        for r in data["results"]:
            if r.get(key_field):
                out[r[key_field]] = r
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        skip += PAGE
        if skip >= MAX_SKIP and skip < total:
            notes.append(f"{endpoint}: skip cap {MAX_SKIP} hit (total={total}) — 창을 줄여 재수집 필요")
            break
        if skip >= total or (limit_rows and len(out) >= limit_rows):
            break
    return list(out.values())


class OpenFdaCollector(Collector):
    name = "openfda"
    tables = ("raw.fda_drug_applications", "raw.fda_device_510k")
    schedule = "daily"
    description = "FDA 의약품 신청·제출 이력(drugsfda), 의료기기 510(k) — 날짜 창 증분"

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        key = ctx.settings.openfda_api_key
        end = ctx.today()
        wm = dict(ctx.watermark)

        # 1) drugsfda — 제출 상태일이 창에 있는 신청
        start = self.start_date(ctx, "drugsfda_last", default_lookback_days=30)
        search = f"submissions.submission_status_date:[{_ymd(start)} TO {_ymd(end)}]"
        apps = _paged(http, "drug/drugsfda", search, key, ctx.limit, "application_number", res.notes)
        rows = []
        for a in apps:
            subs = a.get("submissions") or []
            latest = max(subs, key=lambda s: s.get("submission_status_date") or "", default={})
            products = a.get("products") or []
            rows.append(
                {
                    "application_number": a["application_number"],
                    "sponsor_name": a.get("sponsor_name"),
                    "brand_names": sorted({p.get("brand_name") for p in products if p.get("brand_name")}),
                    "generic_names": sorted(
                        {
                            ai.get("name")
                            for p in products
                            for ai in (p.get("active_ingredients") or [])
                            if ai.get("name")
                        }
                    ),
                    "product_count": len(products),
                    "latest_submission_status": latest.get("submission_status"),
                    "latest_submission_status_date": parse_date(latest.get("submission_status_date")),
                    "latest_submission_type": latest.get("submission_type"),
                    "latest_submission_class": latest.get("submission_class_code"),
                    "submissions": subs,
                    "products": products,
                    "payload": {"openfda": a.get("openfda")},
                }
            )
        for chunk in chunked(rows, 200):
            res.add(store.upsert("raw.fda_drug_applications", chunk, ["application_number"]))
        log.info("drugsfda applications in window: %d", len(rows))
        wm["drugsfda_last"] = (end - timedelta(days=3)).isoformat()  # 늦게 반영되는 제출 대비 겹침

        # 2) device/510k — 결정일 창
        start = self.start_date(ctx, "k510_last", default_lookback_days=60)
        search = f"decision_date:[{_ymd(start)} TO {_ymd(end)}]"
        devs = _paged(http, "device/510k", search, key, ctx.limit, "k_number", res.notes)
        rows = [
            {
                "k_number": d["k_number"],
                "applicant": d.get("applicant"),
                "device_name": d.get("device_name"),
                "product_code": d.get("product_code"),
                "decision_code": d.get("decision_code"),
                "decision_date": parse_date(d.get("decision_date")),
                "date_received": parse_date(d.get("date_received")),
                "clearance_type": d.get("clearance_type"),
                "advisory_committee": d.get("advisory_committee"),
                "third_party_flag": d.get("third_party_flag"),
                "payload": {k: v for k, v in d.items() if k not in ("k_number",)},
            }
            for d in devs
            if d.get("k_number")
        ]
        for chunk in chunked(rows, 200):
            res.add(store.upsert("raw.fda_device_510k", chunk, ["k_number"]))
        log.info("510k decisions in window: %d", len(rows))
        wm["k510_last"] = (end - timedelta(days=45)).isoformat()  # 월간 갱신이라 한 달 반 겹침

        res.notes.append(f"drugsfda={len(apps)} k510={len(devs)} api_key={'yes' if key else 'no'}")
        res.watermark = wm
        return res
