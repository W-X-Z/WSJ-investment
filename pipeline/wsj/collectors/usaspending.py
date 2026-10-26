"""usaspending — 정부조달 유니버스 기업의 계약 awards (USAspending API v2).

recipient_search_text 로 회사명(정규화)을 검색하고 last_modified_date 창으로 증분.
옵션 행사·수정(modification)이 신규 수주보다 강한 신호라 '마지막 수정일' 기준으로 본다.
수신자명 매칭은 raw 에 search_text 로 남기고 entities resolve 가 확정한다.
국방부 계약은 FPDS 90일 지연 — 같은 날 알려면 war.gov RSS (BACKLOG C-10).
"""

from __future__ import annotations

from datetime import timedelta

from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import chunked, normalize_name, parse_date

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
FIELDS = [
    "Award ID",
    "Recipient Name",
    "Recipient UEI",
    "Award Amount",
    "Total Outlays",
    "Description",
    "Start Date",
    "End Date",
    "Base Obligation Date",
    "Last Modified Date",
    "Awarding Agency",
    "Awarding Sub Agency",
    "NAICS",
    "PSC",
    "Contract Award Type",
    "def_codes",
    "generated_internal_id",
]
CONTRACT_TYPES = ["A", "B", "C", "D"]  # BPA call, purchase order, delivery order, definitive contract
PAGE = 100


def _to_dt(v: str | None) -> str | None:
    if not v:
        return None
    return v.replace(" ", "T")


class UsaSpendingCollector(Collector):
    name = "usaspending"
    tables = ("raw.gov_awards",)
    schedule = "daily"
    description = "정부조달 유니버스 기업의 연방 계약 awards (최종 수정일 기준 증분)"
    needs_universe = True

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        companies = [c for c in self.universe(ctx) if c.get("sector_bucket") == "gov_procurement"]
        if ctx.limit:
            companies = companies[: ctx.limit]
        start = self.start_date(ctx, "last_modified", default_lookback_days=90)
        end = ctx.today()
        log.info("usaspending companies=%d window %s..%s", len(companies), start, end)

        rows: dict[str, dict] = {}
        for c in companies:
            q = normalize_name(c["name"])
            if len(q) < 4:
                continue
            page = 1
            while True:
                body = {
                    "filters": {
                        "award_type_codes": CONTRACT_TYPES,
                        "recipient_search_text": [q],
                        "time_period": [
                            {
                                "start_date": start.isoformat(),
                                "end_date": end.isoformat(),
                                "date_type": "last_modified_date",
                            }
                        ],
                    },
                    "fields": FIELDS,
                    "limit": PAGE,
                    "page": page,
                    "sort": "Last Modified Date",
                    "order": "desc",
                }
                data = http.post_json(API, body)
                for a in data.get("results", []):
                    gid = a.get("generated_internal_id")
                    if not gid:
                        continue
                    naics, psc = a.get("NAICS") or {}, a.get("PSC") or {}
                    rows[gid] = {
                        "generated_internal_id": gid,
                        "award_id": a.get("Award ID"),
                        "recipient_name": a.get("Recipient Name"),
                        "recipient_uei": a.get("Recipient UEI"),
                        "award_amount": a.get("Award Amount"),
                        "total_outlays": a.get("Total Outlays"),
                        "description": a.get("Description"),
                        "start_date": parse_date(a.get("Start Date")),
                        "end_date": parse_date(a.get("End Date")),
                        "base_obligation_date": parse_date(a.get("Base Obligation Date")),
                        "last_modified_date": _to_dt(a.get("Last Modified Date")),
                        "awarding_agency": a.get("Awarding Agency"),
                        "awarding_sub_agency": a.get("Awarding Sub Agency"),
                        "naics_code": naics.get("code"),
                        "naics_description": naics.get("description"),
                        "psc_code": psc.get("code"),
                        "psc_description": psc.get("description"),
                        "contract_award_type": a.get("Contract Award Type"),
                        "def_codes": a.get("def_codes") or [],
                        "search_text": q,
                        "payload": {"internal_id": a.get("internal_id"), "agency_slug": a.get("agency_slug")},
                    }
                if not data.get("page_metadata", {}).get("hasNext") or page >= 20:
                    break
                page += 1
        for chunk in chunked(list(rows.values()), 200):
            res.add(store.upsert("raw.gov_awards", chunk, ["generated_internal_id"]))
        res.notes.append(f"companies={len(companies)} awards={len(rows)}")
        res.watermark = {"last_modified": (end - timedelta(days=7)).isoformat()}
        return res
