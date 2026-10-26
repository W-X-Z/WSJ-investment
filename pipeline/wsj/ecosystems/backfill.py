"""Reproducible historical evidence backfill for 3 technical supply-chain ecosystems.

Collect *historical source metadata*, not hindsight investment signals. Separate the
published date from the time this system first observed the source. Never inject
backfilled documents into the live 6-hour "new signal" alert stream.

Sources: OpenAlex, Crossref (DOI metadata), Federal Register, SEC EDGAR (recent +
older submission fragments). All source calls are bounded by year/page/cap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from wsj.ecosystems.monitor import ECOSYSTEMS, rebuild_abstract, relevant

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = ROOT / "research" / "backfill"
HOSTS = frozenset({"api.openalex.org", "api.crossref.org",
                   "www.federalregister.gov", "www.sec.gov", "data.sec.gov"})
SEC_FORMS = frozenset({"8-K", "6-K", "10-K", "10-Q", "20-F", "S-3", "F-3"})
SEC_TICKERS = {
    "hbm": ("CAMT", "ONTO", "ACLS"),
    "optics": ("POET", "COHR", "LITE"),
    "power": ("AEHR", "VRT", "POWI"),
}
# Two complementary research phrases per ecosystem, not stock ticker-based queries.
QUERIES = {
    "hbm": ("high bandwidth memory hybrid bonding", "advanced packaging wafer inspection metrology"),
    "optics": ("silicon photonics 1.6T optical transceiver", "co packaged optics laser optical interposer"),
    "power": ("800V DC data center power conversion", "silicon carbide wide bandgap power converter"),
}
FEDERAL_TERMS = {
    "hbm": "semiconductor advanced packaging",
    "optics": "optical photonics communications",
    "power": "data center electrical power distribution",
}
USER_AGENT = os.environ.get("SEC_USER_AGENT", "WSJ-investment public research research@example.com")
MAX_BYTES = 4_000_000


def iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fingerprint(*values: str) -> str:
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:24]


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    x = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi.strip(), flags=re.I).lower()
    return x if x.startswith("10.") and "/" in x else None


def pub_date(item: dict) -> str | None:
    """Crossref multiple date forms; use bibliographic publication date (not indexed date)."""
    fields = ("published", "published-online", "published-print", "issued")
    for field in fields:
        value = item.get(field)
        if not isinstance(value, dict):
            continue
        parts = value.get("date-parts", [])
        if not parts or not parts[0]:
            continue
        try:
            y = int(parts[0][0]); m = int(parts[0][1]) if len(parts[0]) > 1 else 12
            d = int(parts[0][2]) if len(parts[0]) > 2 else 28
            return date(y, m, d).isoformat()
        except (TypeError, ValueError):
            continue
    return None


def fetch_json(url: str) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username:
        raise ValueError(f"Backfill source not allowlisted: {parsed.hostname}")
    error: Exception | None = None
    for attempt in range(3):
        try:
            req = Request(url, headers={
                "User-Agent": USER_AGENT, "Accept": "application/json",
            })
            with urlopen(req, timeout=24) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError("Backfill source payload size limit exceeded")
                return json.loads(body)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            error = exc
            if isinstance(exc, HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                break
            if attempt < 2:
                time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"Backfill fetch failed {parsed.hostname}: {type(error).__name__} {getattr(error,'code','')}")


def record(*, source: str, source_id: str, ecosystem: str, kind: str, day: str,
           title: str, url: str, excerpt: str, observed_at: str, doi: str | None = None,
           extra: dict | None = None) -> dict:
    normalized = normalize_doi(doi)
    canonical = "doi:" + normalized if normalized else f"{source}:{source_id}"
    return {
        "id": fingerprint(source, source_id, ecosystem),
        "canonical_id": canonical, "ecosystem": ecosystem, "kind": kind,
        "source": source, "source_group": "scholarly_bibliography" if source in {"openalex", "crossref"} else source,
        "source_id": source_id,
        "published_at": day, "first_seen_at": observed_at,
        "historical_backfill": True, "historical_investor_observation_unverified": True,
        "title": re.sub(r"\s+", " ", title).strip()[:300],
        "excerpt": re.sub(r"\s+", " ", excerpt).strip()[:620],
        "url": url, "doi": normalized, "details": extra or {},
        "provenance_status": "bibliographic_metadata_only" if source in {"openalex","crossref"} else "official_record_metadata_only",
        "research_priority": "unrated", "not_a_live_trigger": True,
    }


def openalex(ecosystem: str, year: int, observed_at: str, per_page: int, pages: int) -> list[dict]:
    output: list[dict] = []
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    for query in QUERIES[ecosystem]:
        for page in range(1, pages + 1):
            params = {
                "search": query,
                "filter": f"from_publication_date:{year}-01-01,to_publication_date:{year}-12-31",
                "select": "id,display_name,doi,publication_date,abstract_inverted_index,cited_by_count",
                "per_page": min(per_page, 100), "page": page,
            }
            if key:
                params["api_key"] = key
            data = fetch_json("https://api.openalex.org/works?" + urlencode(params))
            works = data.get("results", [])
            for item in works:
                title = item.get("display_name") or ""
                when = item.get("publication_date") or ""
                if not title or not when.startswith(str(year)) or not relevant(title, ecosystem):
                    continue
                source_id = item.get("id") or ""
                if not source_id:
                    continue
                abstract = rebuild_abstract(item.get("abstract_inverted_index") or {})[:600]
                output.append(record(
                    source="openalex", source_id=source_id, ecosystem=ecosystem, kind="paper",
                    day=when, title=title,
                    url=f"https://api.openalex.org/works/{source_id.rsplit('/',1)[-1]}",
                    excerpt=abstract or "Abstract absent; title-only bibliographic record",
                    observed_at=observed_at, doi=item.get("doi"),
                    extra={"query": query, "cited_by_count_current_snapshot": item.get("cited_by_count"),
                           "abstract_available": bool(abstract)},
                ))
            if len(works) < min(per_page, 100):
                break
            time.sleep(.15)
    return list({row["id"]:row for row in output}.values())


def crossref(ecosystem: str, year: int, observed_at: str, per_page: int, pages: int) -> list[dict]:
    output = []
    for query in QUERIES[ecosystem]:
        for page in range(pages):
            params = {
                "query.title": query, "filter": f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31",
                "rows": min(per_page, 100), "offset": page * min(per_page, 100),
                "select": "DOI,title,abstract,published,published-online,published-print,issued,URL,type",
            }
            data = fetch_json("https://api.crossref.org/works?" + urlencode(params))
            items = data.get("message", {}).get("items", [])
            for item in items:
                title = (item.get("title") or [""])[0]
                when = pub_date(item)
                doi = normalize_doi(item.get("DOI"))
                if not title or not when or when[:4] != str(year) or not relevant(title, ecosystem) or not doi:
                    continue
                excerpt = re.sub(r"<[^>]+>", " ", item.get("abstract") or "").strip()
                output.append(record(
                    source="crossref", source_id=doi, ecosystem=ecosystem, kind="paper",
                    day=when, title=title, url=f"https://api.crossref.org/works/{doi}",
                    excerpt=excerpt or "Title/DOI bibliographic record; primary technical result not verified",
                    observed_at=observed_at, doi=doi,
                    extra={"query": query, "work_type": item.get("type")},
                ))
            if len(items) < min(per_page, 100):
                break
            time.sleep(.15)
    return list({row["id"]:row for row in output}.values())


def federal(ecosystem: str, year: int, observed_at: str, per_page: int, pages: int) -> list[dict]:
    output = []
    for page in range(1, pages + 1):
        params = {
            "conditions[term]": FEDERAL_TERMS[ecosystem],
            "conditions[publication_date][gte]": f"{year}-01-01",
            "conditions[publication_date][lte]": f"{year}-12-31",
            "per_page": min(per_page, 100), "page": page, "order": "newest",
        }
        data = fetch_json("https://www.federalregister.gov/api/v1/documents.json?" + urlencode(params))
        items = data.get("results", [])
        for item in items:
            title = item.get("title") or ""
            excerpt = item.get("abstract") or ""
            when = item.get("publication_date") or ""
            url = item.get("html_url") or ""
            if not title or not when.startswith(str(year)) or not url.startswith("https://www.federalregister.gov/") or not relevant(title + " " + excerpt, ecosystem):
                continue
            output.append(record(
                source="federalregister", source_id=str(item.get("document_number") or url),
                ecosystem=ecosystem, kind="regulatory", day=when,
                title=title, url=url, excerpt=excerpt,
                observed_at=observed_at, extra={"agency": [x.get("name") for x in item.get("agencies", [])]},
            ))
        if len(items) < min(per_page, 100):
            break
        time.sleep(.15)
    return list({row["id"]:row for row in output}.values())


def _sec_rows(submissions: dict) -> list[dict]:
    r = (submissions.get("filings") or {}).get("recent") or {}
    fields = ("form", "filingDate", "accessionNumber", "primaryDocument")
    return [dict(zip(fields, row)) for row in zip(*(r.get(x, []) for x in fields))]


def sec_filings(ecosystem: str, ticker: str, cik: int, start_year: int, end_year: int,
                observed_at: str, max_per_year: int, include_archives: bool = True) -> tuple[list[dict], list[str]]:
    base = fetch_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    batches = [_sec_rows(base)]
    failures = []
    if include_archives:
        for item in (base.get("filings") or {}).get("files") or []:
            if not item.get("name"):
                continue
            # Guard expensive or irrelevant historical fragments by reported filing range.
            oldest = str(item.get("filingFrom") or "0000")[:4]
            newest = str(item.get("filingTo") or "9999")[:4]
            if oldest > str(end_year) or newest < str(start_year):
                continue
            try:
                archive = fetch_json("https://data.sec.gov/submissions/" + item["name"])
                r = archive if "filings" in archive else {"filings": {"recent": archive}}
                batches.append(_sec_rows(r))
            except Exception as exc:
                failures.append(f"{ticker} archive {item['name']}: {str(exc)[:120]}")
            time.sleep(.12)
    by_year: dict[int, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for batch in batches:
        for row in batch:
            when = row.get("filingDate") or ""
            accession = row.get("accessionNumber") or ""
            if not when or not accession or row.get("form") not in SEC_FORMS or accession in seen:
                continue
            seen.add(accession)
            y = int(when[:4])
            if start_year <= y <= end_year:
                by_year[y].append(row)
    output: list[dict] = []
    for year, rows in by_year.items():
        # 8-K has many exhibits, trim only after prioritizing period reports.
        priority = {"10-K": 0, "20-F": 0, "10-Q": 1, "6-K": 2, "8-K": 3}
        for row in sorted(rows, key=lambda x: (priority.get(x["form"],4), x["filingDate"]))[:max_per_year]:
            acc = row["accessionNumber"]
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{row['primaryDocument']}"
            output.append(record(
                source="sec", source_id=f"{cik}:{acc}", ecosystem=ecosystem,
                kind="company_filing", day=row["filingDate"],
                title=f"{ticker} {row['form']} {row['filingDate']}",
                url=url, excerpt="Official historical SEC filing metadata; original document and exhibits require further research",
                observed_at=observed_at,
                extra={"ticker": ticker,"cik": cik,"form":row["form"],"accession":acc},
            ))
    return output, failures


def reconcile(records: list[dict]) -> list[dict]:
    """DOIs from multiple indices are one scholarly record, not independent evidence."""
    output: dict[tuple[str,str], dict] = {}
    for item in records:
        key = item["ecosystem"], item["canonical_id"]
        prior = output.get(key)
        if prior is None:
            output[key] = {**item, "also_indexed_by": [item["source"]]}
        else:
            indexed = set(prior["also_indexed_by"]); indexed.add(item["source"])
            best = item if len(item.get("excerpt","")) > len(prior.get("excerpt","")) and item.get("source")=="openalex" else prior
            output[key] = {**best, "also_indexed_by": sorted(indexed)}
    return sorted(output.values(), key=lambda x: (x["published_at"], x["id"]), reverse=True)


def create_summary(rows: list[dict], failures: list[dict], start: int, end: int, observed: str) -> dict:
    by_source = Counter(item["source"] for item in rows)
    by_eco = Counter(item["ecosystem"] for item in rows)
    years = Counter(item["published_at"][:4] for item in rows)
    return {
        "status": "partial_with_errors" if failures else "completed_with_limits",
        "collected_at": observed, "historical_period": [start,end],
        "records": len(rows), "by_source":dict(by_source),
        "by_ecosystem":dict(by_eco), "by_publication_year":dict(sorted(years.items())),
        "failed_source_segments": failures,
        "interpretation": "Historical metadata sample (bounded pagination), not exhaustive corpus, real-time alerts, or point-in-time investment proof",
        "limits": [
            "Only a few bounded pages per year and search term; unreturned records may exist.",
            "OpenAlex may need OPENALEX_API_KEY for sustained searching; failures must not be hidden.",
            "Crossref and OpenAlex are bibliographic indexes, not independent validation of paper contents.",
            "SEC submission archive availability and filing caps differ by issuer.",
            "Original publication date != first_seen_at; historical index snapshots were NOT retained.",
        ],
    }


def run(*, out: Path, since: int, until: int, per_page: int = 35,
        pages: int = 2, max_sec_year: int = 35, sources: tuple[str,...] = ("openalex","crossref","federal","sec")) -> dict:
    if since < 2010 or until > datetime.now(timezone.utc).year or since > until or until-since > 12:
        raise ValueError("Backfill years outside safe bounded window")
    if not 1 <= per_page <= 100 or not 1 <= pages <= 4 or not 1 <= max_sec_year <= 100:
        raise ValueError("Backfill request bound exceeded")
    observed=iso_utc()
    records: list[dict] = []
    failures: list[dict] = []
    for eco in ECOSYSTEMS:
        for year in range(since,until+1):
            for source, fn in (("openalex",openalex),("crossref",crossref),("federal",federal)):
                if source not in sources:
                    continue
                try:
                    fresh=fn(eco,year,observed,per_page,pages)
                    records.extend(fresh)
                    print(f"Collected {source}/{eco}/{year}: {len(fresh)} records",flush=True)
                except Exception as exc:
                    failures.append({"source":source,"ecosystem":eco,"year":year,"error":str(exc)[:240]})
                    print(f"WARNING {source}/{eco}/{year}: {exc}",flush=True)
                time.sleep(.12)
    if "sec" in sources:
        try:
            idx=__import__("wsj.ecosystems.monitor",fromlist=["sec_ticker_index"]).sec_ticker_index()
        except Exception as exc:
            idx={}
            failures.append({"source":"sec_ticker_index","year":None,"error":str(exc)[:240]})
        for eco,tickers in SEC_TICKERS.items():
            for ticker in tickers:
                cik=idx.get(ticker)
                if not cik:
                    failures.append({"source":"sec","ecosystem":eco,"ticker":ticker,"error":"CIK not resolved"})
                    continue
                try:
                    got,err=sec_filings(eco,ticker,cik,since,until,observed,max_sec_year)
                    records.extend(got)
                    failures += [{"source":"sec_archive","ticker":ticker,"error":e} for e in err]
                    print(f"Collected SEC/{eco}/{ticker}: {len(got)} filings",flush=True)
                except Exception as exc:
                    failures.append({"source":"sec","ecosystem":eco,"ticker":ticker,"error":str(exc)[:240]})
    rows=reconcile(records)
    if not rows:
        raise RuntimeError(f"Backfill produced zero records; refusing empty success ({len(failures)} errors)")
    out.mkdir(parents=True,exist_ok=True)
    for eco in ECOSYSTEMS:
        with (out/f"{eco}.jsonl").open("w",encoding="utf-8") as fp:
            for item in rows:
                if item["ecosystem"]==eco:
                    fp.write(json.dumps(item,ensure_ascii=False,sort_keys=True)+"\n")
    # Compact, year-balanced browser index: oldest technical inflections remain
    # discoverable instead of taking only 2026's most recent headlines.
    index=[]
    for eco in ECOSYSTEMS:
        for year in range(since,until+1):
            for source in ("openalex","crossref","sec","federalregister"):
                group=[x for x in rows if x["ecosystem"]==eco
                       and x["published_at"].startswith(str(year))
                       and x["source"]==source]
                group.sort(key=lambda x:x["published_at"],reverse=True)
                index.extend(group[:5])
    index.sort(key=lambda x:(x["published_at"],x["ecosystem"]),reverse=True)
    (out/"feed-index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=create_summary(rows,failures,since,until,observed)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--since-year",type=int,default=2020)
    p.add_argument("--until-year",type=int,default=datetime.now(timezone.utc).year)
    p.add_argument("--per-page",type=int,default=35)
    p.add_argument("--pages",type=int,default=2)
    p.add_argument("--max-sec-year",type=int,default=35)
    p.add_argument("--out-dir",type=Path,default=DEFAULT_OUT)
    args=p.parse_args()
    report=run(out=args.out_dir,since=args.since_year,until=args.until_year,
        per_page=args.per_page,pages=args.pages,max_sec_year=args.max_sec_year)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
