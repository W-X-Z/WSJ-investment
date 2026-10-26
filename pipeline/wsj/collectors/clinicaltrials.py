"""clinicaltrials — ClinicalTrials.gov API v2 스냅샷 + diff.

이력 엔드포인트가 없으므로(2026-10 검증) 매 실행마다 유니버스(바이오·의료기기) 스폰서로 검색한
스터디를 통째로 받아 raw.ct_studies 와 비교하고, 달라진 필드를 raw.ct_study_changes 에 남긴다.
스폰서명 매칭은 하지 않는다 — lead_sponsor_name 원문을 두고 entities resolve 가 맡는다 (ADR-0005).
"""

from __future__ import annotations

from datetime import datetime

from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import chunked, normalize_name, parse_date

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ",".join(
    [
        "NCTId",
        "BriefTitle",
        "OverallStatus",
        "WhyStopped",
        "StatusVerifiedDate",
        "StartDate",
        "PrimaryCompletionDate",
        "CompletionDate",
        "StudyFirstPostDate",
        "LastUpdateSubmitDate",
        "LastUpdatePostDate",
        "Phase",
        "EnrollmentCount",
        "EnrollmentType",
        "StudyType",
        "LeadSponsorName",
        "Condition",
        "InterventionName",
    ]
)
TRACKED = (
    "overall_status",
    "why_stopped",
    "primary_completion_date",
    "completion_date",
    "enrollment_count",
    "phases",
    "status_verified_date",
)


def _flatten(study: dict) -> dict:
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    st = ps.get("statusModule", {})
    sp = ps.get("sponsorCollaboratorsModule", {})
    dz = ps.get("designModule", {})
    cond = ps.get("conditionsModule", {})
    arms = ps.get("armsInterventionsModule", {})

    def d(key: str) -> str | None:
        return (st.get(key) or {}).get("date")

    return {
        "nct_id": ident.get("nctId"),
        "brief_title": ident.get("briefTitle"),
        "lead_sponsor_name": (sp.get("leadSponsor") or {}).get("name"),
        "overall_status": st.get("overallStatus"),
        "why_stopped": st.get("whyStopped"),
        "status_verified_date": st.get("statusVerifiedDate"),
        "start_date": d("startDateStruct"),
        "primary_completion_date": d("primaryCompletionDateStruct"),
        "completion_date": d("completionDateStruct"),
        "study_first_post_date": parse_date(d("studyFirstPostDateStruct")),
        "last_update_submit_date": parse_date(st.get("lastUpdateSubmitDate")),
        "last_update_post_date": parse_date(d("lastUpdatePostDateStruct")),
        "phases": dz.get("phases") or [],
        "enrollment_count": (dz.get("enrollmentInfo") or {}).get("count"),
        "enrollment_type": (dz.get("enrollmentInfo") or {}).get("type"),
        "study_type": dz.get("studyType"),
        "conditions": cond.get("conditions") or [],
        "interventions": [i.get("name") for i in arms.get("interventions") or [] if i.get("name")],
        "payload": study,
    }


def _norm(v) -> str | None:
    if v is None or v == [] or v == "":
        return None
    if isinstance(v, list):
        return ",".join(map(str, v))
    return str(v)


class ClinicalTrialsCollector(Collector):
    name = "clinicaltrials"
    tables = ("raw.ct_studies", "raw.ct_study_changes")
    schedule = "daily"
    description = "바이오·의료기기 유니버스 스폰서의 임상 스냅샷 + 변경 감지"
    needs_universe = True

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log
        companies = [c for c in self.universe(ctx) if c.get("sector_bucket") in ("biotech", "medtech")]
        if ctx.limit:
            companies = companies[: ctx.limit]
        queries = sorted(
            {normalize_name(c["name"], strip_industry_words=True) or c["name"] for c in companies}
        )
        log.info("sponsor queries: %d", len(queries))

        fetched: dict[str, dict] = {}
        for q in queries:
            token = None
            while True:
                params = {"query.spons": q, "fields": FIELDS, "pageSize": 100, "format": "json"}
                if token:
                    params["pageToken"] = token
                data = http.get_json(API, params=params)
                for s in data.get("studies", []):
                    row = _flatten(s)
                    if row["nct_id"]:
                        fetched[row["nct_id"]] = row
                token = data.get("nextPageToken")
                if not token:
                    break
        log.info("studies fetched: %d", len(fetched))

        # diff
        now = datetime.utcnow().isoformat()
        existing: dict[str, dict] = {}
        for ids in chunked(list(fetched), 150):
            for r in store.select("raw.ct_studies", ["nct_id", *TRACKED, "first_seen_at"], {"nct_id": ids}):
                existing[r["nct_id"]] = r
        changes: list[dict] = []
        for nct, new in fetched.items():
            old = existing.get(nct)
            new["snapshot_at"] = now
            if old is None:
                new["first_seen_at"] = now
                continue
            new["first_seen_at"] = old.get("first_seen_at") or now
            for f in TRACKED:
                ov, nv = _norm(old.get(f)), _norm(new.get(f))
                if ov != nv:
                    changes.append(
                        {"nct_id": nct, "detected_at": now, "field": f, "old_value": ov, "new_value": nv}
                    )

        for chunk in chunked(list(fetched.values()), 200):
            res.add(store.upsert("raw.ct_studies", chunk, ["nct_id"]))
        if changes:
            res.add(store.insert("raw.ct_study_changes", changes))
        res.notes.append(
            f"queries={len(queries)} studies={len(fetched)} new={len(fetched) - len(existing)} changes={len(changes)}"
        )
        res.watermark = {"last_snapshot_at": now, "studies": len(fetched)}
        return res
