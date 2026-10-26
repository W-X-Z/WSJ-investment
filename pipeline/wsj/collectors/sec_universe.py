"""sec_universe — core.companies 를 만든다. ADR-0004.

1. company_tickers_exchange.json → 모든 상장 티커 (CIK 허브 시드)
2. XBRL frames dei:EntityPublicFloat 최근 8개 분기 → CIK 별 최신 공개유동
3. 후보(거래소 Nasdaq/NYSE, 공개유동 0 < x < $1B) 의 submissions → SIC·거래소·주 등
4. SIC 집합으로 sector_bucket / in_universe 결정

전체 재구축이 기본. submissions 는 30일 이내 동기화된 CIK 는 건너뛴다 (--since 를 주면 강제).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from wsj.collectors.base import Collector, RunContext, RunResult
from wsj.util import chunked, parse_date

SEC = "https://www.sec.gov"
DATA = "https://data.sec.gov"

PUBLIC_FLOAT_MAX = 1_000_000_000
# 하한: XBRL 공개유동이 "천 달러" 단위로 잘못 태깅된 대형주(PTCT 3,350,589 등)를 걸러내고,
# 어차피 유동성 없는 초소형도 제외한다. 가격×주식수 기반 시총으로 대체 예정 (BACKLOG C-19).
PUBLIC_FLOAT_MIN = 10_000_000
UNIVERSE_EXCHANGES = {"Nasdaq", "NYSE"}  # NYSE American 은 이 파일에서 'NYSE'

# 버킷 순서 = 겹칠 때 우선순위. ADR-0004 (biotech/medtech/gov) + ADR-0008 (energy/ai_software/semis).
SECTOR_SIC: dict[str, set[int]] = {
    "biotech": {2834, 2835, 2836, 8731},
    "medtech": {3841, 3842, 3845, 3826, 5047},
    "semis": {3674, 3672, 3559, 3825, 3576, 3577, 3661},
    "energy": {
        1311,
        1381,
        1382,
        1389,
        2911,
        3433,
        3511,
        3690,
        3692,
        4911,
        4931,
        4932,
        4991,
        1040,
        1090,
        1094,
    },
    "ai_software": {7370, 7371, 7372, 7373, 7374},
    "gov_procurement": {3812, 3720, 3721, 3724, 3728, 3760, 3764, 3769, 3663, 3669, 8711},
}


def sector_for(sic: int | None) -> str:
    if sic is None:
        return "other"
    for bucket, codes in SECTOR_SIC.items():
        if sic in codes:
            return bucket
    return "other"


def _frames_to_try(today: date, n: int = 8) -> list[str]:
    """최근 n 개 분기 프레임 이름, 최신부터. 예: CY2026Q3I, CY2026Q2I, ..."""
    y, q = today.year, (today.month - 1) // 3 + 1
    out = []
    for _ in range(n):
        out.append(f"CY{y}Q{q}I")
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out


class SecUniverseCollector(Collector):
    name = "sec_universe"
    tables = ("core.companies",)
    schedule = "weekly"
    description = "상장 티커 + 공개유동(EntityPublicFloat) + SIC 로 유니버스 구축"

    def run(self, ctx: RunContext) -> RunResult:
        res = RunResult()
        http, store, log = ctx.http, ctx.store, ctx.log

        # 1) 티커 시드
        cte = http.get_json(f"{SEC}/files/company_tickers_exchange.json")
        fields = cte["fields"]
        idx = {f: i for i, f in enumerate(fields)}
        seed: dict[int, dict] = {}
        for r in cte["data"]:
            cik = int(r[idx["cik"]])
            row = {
                "cik": cik,
                "name": r[idx["name"]],
                "ticker": r[idx["ticker"]],
                "exchange": r[idx["exchange"]],
            }
            # 한 CIK 에 여러 티커(우선주 등)가 있으면 첫 번째(보통 보통주)를 유지
            seed.setdefault(cik, row)
        log.info("tickers: %d ciks", len(seed))

        # 2) 공개유동
        latest: dict[int, dict] = {}
        for frame in _frames_to_try(ctx.today()):
            resp = http.request("GET", f"{DATA}/api/xbrl/frames/dei/EntityPublicFloat/USD/{frame}.json")
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            for pt in resp.json().get("data", []):
                cik = int(pt["cik"])
                end = parse_date(pt.get("end"))
                cur = latest.get(cik)
                if cur is None or (end and cur["end"] and end > cur["end"]):
                    latest[cik] = {"end": end, "val": pt.get("val"), "accn": pt.get("accn")}
        log.info("public float points: %d ciks", len(latest))

        # 3) 후보 선정 → submissions
        # 기존 행 전체를 가져와 병합한다: PostgREST upsert 는 빠진 컬럼을 null 로 덮어쓰기 때문.
        existing = {r["cik"]: r for r in store.select("core.companies")}
        cutoff = datetime.utcnow() - timedelta(days=30)
        candidates = [
            cik
            for cik, row in seed.items()
            if row["exchange"] in UNIVERSE_EXCHANGES
            and cik in latest
            and latest[cik]["val"] is not None
            and PUBLIC_FLOAT_MIN <= float(latest[cik]["val"]) < PUBLIC_FLOAT_MAX
        ]
        all_candidates = candidates
        if ctx.limit:
            candidates = candidates[: ctx.limit]
        log.info("candidates (exchange ok, $10M <= float < $1B): %d", len(candidates))

        subs: dict[int, dict] = {}
        fetched = 0
        for cik in candidates:
            prev = existing.get(cik)
            synced = parse_datetime(prev.get("submissions_synced_at")) if prev else None
            if prev and prev.get("sic") is not None and synced and synced > cutoff and not ctx.since:
                continue
            resp = http.request("GET", f"{DATA}/submissions/CIK{cik:010d}.json")
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            s = resp.json()
            s.pop("filings", None)  # 공시 목록(최대 1,000건)은 여기서 안 쓴다 — 메모리 절약
            subs[cik] = s
            fetched += 1
            if fetched % 200 == 0:
                log.info("submissions fetched: %d", fetched)
        log.info("submissions fetched: %d (skipped recent: %d)", fetched, len(candidates) - fetched)

        # 4) 행 조립 — 모든 티커는 companies 에 들어가고, 후보만 상세·유니버스 판정
        now = datetime.utcnow().isoformat()
        rows: list[dict] = []
        cand_set = set(all_candidates)
        # --limit 스모크는 후보 일부만 건드린다. 전체를 쓰면 나머지 유니버스가 false 로 지워진다.
        targets = {c: seed[c] for c in candidates} if ctx.limit else seed
        for cik, base in targets.items():
            row = dict(existing.get(cik, {}))  # 기존 값 보존 (sic 등)
            row.update(base)
            pf = latest.get(cik)
            if pf:
                row.update(
                    {
                        "public_float": pf["val"],
                        "public_float_asof": pf["end"],
                        "public_float_accn": pf["accn"],
                    }
                )
            s = subs.get(cik)
            if s:
                row.update(
                    {
                        "sic": int(s["sic"]) if s.get("sic") else None,
                        "sic_description": s.get("sicDescription") or None,
                        "entity_type": s.get("entityType") or None,
                        "filer_category": s.get("category") or None,
                        "state_of_incorporation": s.get("stateOfIncorporation") or None,
                        "business_state": (s.get("addresses", {}).get("business", {}) or {}).get(
                            "stateOrCountry"
                        ),
                        "fiscal_year_end": s.get("fiscalYearEnd") or None,
                        "former_names": s.get("formerNames") or [],
                        "submissions_synced_at": now,
                    }
                )
                if s.get("tickers"):
                    row["ticker"] = s["tickers"][0]
                if s.get("exchanges"):
                    row["exchange"] = s["exchanges"][0]
            sic_val = row.get("sic")
            bucket = sector_for(sic_val)
            in_universe = cik in cand_set and bucket != "other"
            if str(row.get("universe_reason") or "").startswith("ontology"):
                # 온톨로지(공급망 그래프)로 승격된 회사는 SIC 버킷과 무관하게 유지한다 (ADR-0013)
                row.update({"sector_bucket": row.get("sector_bucket") or "supply_chain", "updated_at": now})
            else:
                row.update(
                    {
                        "sector_bucket": bucket,
                        "in_universe": in_universe,
                        "universe_reason": (
                            f"float={row.get('public_float')} sic={sic_val} bucket={bucket}"
                            if in_universe
                            else None
                        ),
                        "updated_at": now,
                    }
                )
            rows.append(row)

        # 상폐·티커 소멸: 현재 목록에 없는 기존 CIK 는 유니버스에서 뺀다
        if not ctx.limit:
            for cik, prev in existing.items():
                if cik not in seed and prev.get("in_universe"):
                    rows.append(
                        {**prev, "in_universe": False, "universe_reason": "delisted", "updated_at": now}
                    )

        for chunk in chunked(rows, 500):
            res.add(store.upsert("core.companies", chunk, ["cik"]))

        n_universe = sum(1 for r in rows if r.get("in_universe"))
        res.notes.append(
            f"tickers={len(seed)} float_points={len(latest)} candidates={len(candidates)} universe={n_universe}"
        )
        res.watermark = {"built_at": now, "universe_size": n_universe}
        return res


def parse_datetime(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
