"""Free public-API smoke probe for historical technology investment hypotheses.

No tokens, LLMs, secrets, or database writes. The result is *not* a valid historical
backtest: today's API snapshot may contain retrospectively amended records.
Run from pipeline/: python -m wsj.studies.technology_evidence --out /tmp/probe.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ALLOWED_HOSTS = frozenset({
    "api.fda.gov", "clinicaltrials.gov", "www.ebi.ac.uk", "api.openalex.org",
    "data.sec.gov", "api.usaspending.gov", "api.github.com",
    "www.federalregister.gov", "web.archive.org",
})
OUTPUT_DEFAULT = Path(__file__).resolve().parents[3] / "research" / "probe_sample.json"
MAX_BYTES = 1_500_000
REQUEST_TIMEOUT = 12

# A deliberately tiny, bounded cross-source sample; no automatic broad crawling.
QUERIES = [
    {"id": "TMDX-fda-liver", "ticker": "TMDX", "h": "H01", "source": "fda", "url": "https://api.fda.gov/device/pma.json", "params": {"search": 'pma_number:"P200031"', "limit": "5"}, "as_of": "2022-06-30"},
    {"id": "TMDX-fda-heart", "ticker": "TMDX", "h": "H01", "source": "fda", "url": "https://api.fda.gov/device/pma.json", "params": {"search": 'pma_number:"P180051"', "limit": "10"}, "as_of": "2022-06-30"},
    {"id": "TMDX-clinical", "ticker": "TMDX", "h": "H02", "source": "clinical", "url": "https://clinicaltrials.gov/api/v2/studies/NCT02522871", "as_of": "2022-06-30"},
    {"id": "TMDX-europepmc", "ticker": "TMDX", "h": "H02", "source": "europepmc", "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search", "params": {"query": "normothermic AND liver AND FIRST_PDATE:[2019-01-01 TO 2022-06-30]", "format": "json", "pageSize": "5"}, "as_of": "2022-06-30"},
    {"id": "TMDX-openalex", "ticker": "TMDX", "h": "H02", "source": "openalex", "url": "https://api.openalex.org/works", "params": {"search": "normothermic machine perfusion liver transplantation", "filter": "to_publication_date:2022-06-30", "per_page": "5", "select": "id,display_name,publication_date,doi"}, "as_of": "2022-06-30"},
    {"id": "TMDX-sec", "ticker": "TMDX", "h": "H03", "source": "sec", "url": "https://data.sec.gov/submissions/CIK0001756262.json", "as_of": "2022-11-15"},
    {"id": "ASTS-sec", "ticker": "ASTS", "h": "H04", "source": "sec", "url": "https://data.sec.gov/submissions/CIK0001780312.json", "as_of": "2023-09-30"},
    {"id": "ASTS-federalregister", "ticker": "ASTS", "h": "H06", "source": "federalregister", "url": "https://www.federalregister.gov/api/v1/documents.json", "params": {"conditions[term]": "AST SpaceMobile", "conditions[publication_date][lte]": "2023-09-30", "per_page": "5"}, "as_of": "2023-09-30"},
    {"id": "RKLB-sec", "ticker": "RKLB", "h": "H07", "source": "sec", "url": "https://data.sec.gov/submissions/CIK0001819994.json", "as_of": "2023-12-22"},
    {"id": "RKLB-usaspending", "ticker": "RKLB", "h": "H07", "source": "usaspending", "url": "https://api.usaspending.gov/api/v2/search/spending_by_award/", "as_of": "2023-12-22", "body": {"filters": {"award_type_codes": ["A", "B", "C", "D"], "recipient_search_text": ["ROCKET LAB"], "time_period": [{"start_date": "2021-01-01", "end_date": "2023-12-22"}]}, "fields": ["Award ID", "Recipient Name", "Award Amount", "Base Obligation Date", "Description", "generated_internal_id"], "limit": 5, "page": 1, "sort": "Award Amount", "order": "desc"}},
    {"id": "IONQ-openalex", "ticker": "IONQ", "h": "H10", "source": "openalex", "url": "https://api.openalex.org/works", "params": {"search": "trapped ion quantum computing benchmark", "filter": "to_publication_date:2023-07-01", "per_page": "5", "select": "id,display_name,publication_date,doi"}, "as_of": "2023-07-01"},
    {"id": "IONQ-github", "ticker": "IONQ", "h": "H11", "source": "github", "url": "https://api.github.com/search/repositories", "params": {"q": "ionq in:name,description created:2022-01-01..2023-12-31", "per_page": "5"}, "as_of": "2023-12-31"},
    {"id": "SERV-wayback", "ticker": "SERV", "h": "H12", "source": "wayback", "url": "https://web.archive.org/cdx/search/cdx", "params": {"url": "serverobotics.com", "output": "json", "from": "2022", "to": "2024", "filter": "statuscode:200", "limit": "5"}, "as_of": "2024-06-30"},
]


def _is_historical_date(value: str | None, as_of: str) -> bool:
    return bool(value and len(str(value)) >= 10 and str(value)[:10] <= as_of)


def parse_records(source: str, payload: object, as_of: str) -> tuple[list[dict], str]:
    """Only pass records whose documented date is <= as_of. Conservative for undated sources."""
    if source == "fda":
        items = payload.get("results", []) if isinstance(payload, dict) else []
        out = [
            {"id": x.get("pma_number"), "date": x.get("decision_date"), "name": x.get("device_name"), "supplement": x.get("supplement_number"), "applicant": x.get("applicant")}
            for x in items if _is_historical_date(x.get("decision_date"), as_of)
        ]
        return out, "PMA decision date; later-added supplements in current API not historic snapshot"
    if source == "clinical":
        data = payload.get("protocolSection", {}) if isinstance(payload, dict) else {}
        ident, status = data.get("identificationModule", {}), data.get("statusModule", {})
        first = (status.get("studyFirstPostDateStruct") or {}).get("date", "")
        if not _is_historical_date(first, as_of):
            return [], "first study posting after cutoff or missing"
        return [{"id": ident.get("nctId"), "date": first, "name": ident.get("briefTitle"), "study_type": (data.get("designModule") or {}).get("studyType")}], "Record is currently updated; study historical change history must be requested separately"
    if source == "europepmc":
        items = (payload.get("resultList") or {}).get("result", []) if isinstance(payload, dict) else []
        out = [{"id": x.get("id"), "date": x.get("firstPublicationDate"), "name": x.get("title"), "doi": x.get("doi")} for x in items if _is_historical_date(x.get("firstPublicationDate"), as_of)]
        return out, "Topic publications, not necessarily issued by/for the company"
    if source == "openalex":
        items = payload.get("results", []) if isinstance(payload, dict) else []
        out = [{"id": x.get("id"), "date": x.get("publication_date"), "name": x.get("display_name"), "doi": x.get("doi")} for x in items if _is_historical_date(x.get("publication_date"), as_of)]
        return out, "Current discovery index; topic-level not company-specific; modern citation statistics intentionally omitted"
    if source == "sec":
        recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, dict) else {}
        cols = ("form", "filingDate", "accessionNumber", "primaryDocument")
        rows = zip(*(recent.get(c, []) for c in cols))
        out = [{"id": a, "date": d, "name": f, "document": p} for f, d, a, p in rows if f in ("8-K", "10-Q", "10-K") and _is_historical_date(d, as_of)]
        return out[-8:], "Most recent array is partial; filing date not exact intraday publication; archive indexes are needed"
    if source == "usaspending":
        items = payload.get("results", []) if isinstance(payload, dict) else []
        # Base Obligation Date is NOT the public release date; do not mark as contemporaneously available.
        out = [{"id": x.get("Award ID"), "date": x.get("Base Obligation Date"), "name": x.get("Recipient Name"), "amount": x.get("Award Amount")} for x in items]
        return out, "Disclosure lag incl. DoD 90d+: award date is not public availability, cannot assert signal timing"
    if source == "federalregister":
        items = payload.get("results", []) if isinstance(payload, dict) else []
        return ([{"id": x.get("document_number"), "date": x.get("publication_date"), "name": x.get("title")} for x in items if _is_historical_date(x.get("publication_date"), as_of)], "Official publication_date; empty result does not mean no FCC license")
    if source == "github":
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return ([{"id": x.get("full_name"), "date": str(x.get("created_at", ""))[:10], "name": x.get("description"), "url": x.get("html_url")} for x in items if _is_historical_date(x.get("created_at"), as_of)], "Repository creation is historical; current stars and content not usable as past adoption evidence")
    if source == "wayback":
        # CDX rows include timestamp YYYYMMDDhhmmss; query may include captures after cutoff.
        items = payload[1:] if isinstance(payload, list) else []
        out = []
        for x in items:
            if isinstance(x, list) and len(x) >= 3 and str(x[1])[:8] <= as_of.replace("-", ""):
                out.append({"id": x[1], "date": str(x[1])[:8], "name": str(x[2])[:180]})
        return out, "Capture date establishes existence of a snapshot, not truth of claims in it"
    raise ValueError(f"Unknown source: {source}")


def _request(query: dict) -> object:
    url = query["url"]
    if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in ALLOWED_HOSTS:
        raise ValueError("Request outside allowed public source hosts")
    params = query.get("params")
    if params:
        url = url + "?" + urlencode(params)
    body = json.dumps(query["body"]).encode("utf-8") if "body" in query else None
    headers = {
        "User-Agent": "WSJ-investment academic research contact research@example.com",
        "Accept": "application/json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, method="POST" if body is not None else "GET", headers=headers)
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        length = resp.headers.get("Content-Length", "")
        if length.isdigit() and int(length) > MAX_BYTES:
            raise ValueError("Public API response too large")
        raw = resp.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Public API response exceeded cap")
    return json.loads(raw)


def run_probe(query: dict) -> dict:
    result = {
        "id": query["id"], "ticker": query["ticker"], "hypothesis": query["h"],
        "source": query["source"], "as_of": query["as_of"],
        "source_url": query["url"], "observed_at": datetime.now(timezone.utc).isoformat(),
        "availability_class": "retrospective_current_api_not_historical_snapshot",
        "status": "unattempted", "records": [], "count": 0, "note": "",
    }
    try:
        payload = _request(query)
        items, note = parse_records(query["source"], payload, query["as_of"])
        result.update(status="ok" if items else "empty", records=items[:8], count=len(items), note=note)
    except (HTTPError, URLError, OSError, ValueError, TimeoutError, KeyError, TypeError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, HTTPError) else None
        result.update(status="blocked_or_error", http_status=code, note=f"{type(exc).__name__}: {str(exc)[:130]}")
    return result


def build_report(probes: list[dict]) -> dict:
    statuses = {name: sum(p["status"] == name for p in probes) for name in ("ok", "empty", "blocked_or_error")}
    return {
        "schema_version": "2026-10-26.1",
        "research_warning": "Today's API view filtered by record date is not a true point-in-time snapshot.",
        "source_first_seen_at": None,
        "total": len(probes), "statuses": statuses,
        "probes": probes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--max-probes", type=int, default=len(QUERIES))
    args = parser.parse_args(argv)
    if not 1 <= args.max_probes <= len(QUERIES):
        parser.error("max-probes outside valid range")
    probes = []
    for query in QUERIES[:args.max_probes]:
        result = run_probe(query)
        probes.append(result)
        print(f"[{result['status']:<16}] {result['id']:<24} {result['count']} records  {result['note'][:90]}", flush=True)
    report = build_report(probes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("summary:", json.dumps(report["statuses"]))
    # Availability failures are reported as data, not hidden as successful source validation.
    return 0


if __name__ == "__main__":
    sys.exit(main())
