"""논문·특허 백필 — 기술의 긴 시계열을 한 번 채워 두고, 해석 작업이 온톨로지 노드로 찾아보게 한다 (사용자 요청 2026-10-30).

사용자 PC 에서 돈다 (클라우드 작업 환경이 아니라). 키워드 검색이 아니라 분류 체계로 먼저 고른다:
  특허 — Google Patents 공개 데이터(BigQuery `patents-public-data.patents.publications`)에서 CPC 묶음(research/techdocs/cpc_domains.json)
  논문 — OpenAlex 주제(research/techdocs/openalex_topics.json), 기업 소속 저자가 있는 논문
고른 문서는 그래프 어휘(node_aliases.json + patent_terms.json)로 노드를 붙이고, 노드별로 묶어 세 가지를 만든다:
  tech_series — 노드 × 출처 × 분기 건수 (특허는 공개일, 논문은 출판일 기준)
  tech_orgs   — 노드 × 출처 × 기간의 상위 기관(출원인·소속), 그래프 기업이면 id, 그 노드에 처음 나온 해
  tech_docs   — 노드마다 최근 대표 문서 (그래프 기업 → 새로 나타난 기관 → 여러 나라에 낸 특허 → 최신 순)

    cd pipeline
    python -m wsj.ecosystems.techdocs patents --gcp-project <프로젝트> --dry-run   # 스캔 용량만 확인 (무료 1TB/월)
    python -m wsj.ecosystems.techdocs patents --gcp-project <프로젝트>
    python -m wsj.ecosystems.techdocs papers                                       # OPENALEX_API_KEY
    python -m wsj.ecosystems.techdocs build                                        # → data/techdocs/out/, summary.md
    python -m wsj.ecosystems.techdocs upload --replace                             # pipeline/.env 의 SUPABASE_URL·SUPABASE_SECRET_KEY

원본은 data/techdocs/raw/ 에 남는다 (다시 받지 않고 build 만 다시 돌릴 수 있다).
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

log = logging.getLogger("wsj.techdocs")

ROOT = Path(__file__).resolve().parents[3]
CONF_DIR = ROOT / "research" / "techdocs"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "techdocs"
RAW, OUT = DATA_DIR / "raw", DATA_DIR / "out"
OPENALEX = "https://api.openalex.org"
BQ_TABLE = "patents-public-data.patents.publications"
DEFAULT_COUNTRIES = ("US", "KR", "JP", "TW", "EP", "WO")


# ---------------------------------------------------------------- 설정
def load_conf() -> tuple[dict[str, list[str]], dict[str, str], dict[str, list[str]]]:
    domains = json.loads((CONF_DIR / "cpc_domains.json").read_text(encoding="utf-8"))["domains"]
    topics = json.loads((CONF_DIR / "openalex_topics.json").read_text(encoding="utf-8"))["topics"]
    terms = json.loads((CONF_DIR / "patent_terms.json").read_text(encoding="utf-8"))["terms"]
    return domains, topics, terms


def cpc_regex(prefixes: Iterable[str]) -> str:
    return "^(?:" + "|".join(re.escape(p) for p in sorted(set(prefixes))) + ")"


def domain_of(code: str, domains: dict[str, list[str]]) -> str | None:
    for d, prefixes in domains.items():
        if any(code.startswith(p) for p in prefixes):
            return d
    return None


@dataclass
class Lexicon:
    node_pats: list[tuple[re.Pattern, str]]
    comp_pats: list[tuple[re.Pattern, str]]
    phrases: list[str]
    context: dict[str, tuple[re.Pattern, re.Pattern | None]] = field(default_factory=dict)

    def nodes(self, text: str) -> set[str]:
        got = {nid for pat, nid in self.node_pats if pat.search(text)}
        if self.context and got & self.context.keys():
            low = text.lower()
            got = {n for n in got if n not in self.context or in_context(self.context[n], low)}
        return got

    def company(self, name: str) -> str | None:
        return next((cid for pat, cid in self.comp_pats if pat.search(name)), None)


def in_context(rule: tuple[re.Pattern, re.Pattern | None], low: str) -> bool:
    req, exc = rule
    return bool(req.search(low)) and not (exc is not None and exc.search(low))


def load_context(path: Path | None = None) -> dict[str, tuple[re.Pattern, re.Pattern | None]]:
    """research/techdocs/node_context.json — 다른 산업과 말이 겹치는 노드는 문맥이 맞을 때만 붙인다."""
    path = path or CONF_DIR / "node_context.json"
    if not path.exists():
        return {}
    out = {}
    for g in json.loads(path.read_text(encoding="utf-8"))["groups"].values():
        req = re.compile("|".join(g["require"]))
        exc = re.compile("|".join(g["exclude"])) if g.get("exclude") else None
        for nid in g["nodes"]:
            out[nid] = (req, exc)
    return out


LEGAL = re.compile(r"\b(?:CO LTD|COMPANY LIMITED|CORPORATION|CORP|INCORPORATED|INC|LLC|LTD|LIMITED|GMBH|AG|NV|BV|SA|SAS|PLC|KK|CO|PTE|HOLDINGS?|GROUP)\b")


def org_key(name: str) -> str:
    """기관 이름 묶기: 'TOYOTA MOTOR CO LTD'·'TOYOTA MOTOR CORP' → 'TOYOTA MOTOR', OpenAlex 의 '(China)' 꼬리도 뗀다.
    이름만 다른 같은 기관이 '새로 나타난 기관' 으로 잘못 잡히지 않게."""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", name or "").upper().replace("&", " AND ")
    s = re.sub(r"[^\w ]", " ", s)
    s = " ".join(s.split())
    prev = None
    while prev != s:
        prev, s = s, " ".join(LEGAL.sub(" ", s).split())
    return s or (name or "").upper()


def build_lex(graph: dict[str, Any], terms: dict[str, list[str]]) -> Lexicon:
    """그래프 어휘(issues.build_lexicon) + 특허식 표현. phrases 는 BigQuery 의 거친 1차 거르기용 (소문자 부분 일치)."""
    from wsj.ecosystems.issues import build_lexicon

    node_pats, comp_pats = build_lexicon(graph)
    ids = {n["id"] for n in graph["nodes"]}
    pats = [(_plural(p), nid) for p, nid in node_pats if _plain(p.pattern) not in TECH_STOP]
    for nid, words in terms.items():
        if nid not in ids:
            continue
        for w in words:
            w = w.strip().lower()
            if len(w) >= 4:
                pats.append((_plural(re.compile(r"(?<![a-z0-9])" + re.escape(w).replace(r"\ ", r"[\s-]") + r"(?![a-z])", re.I)), nid))
    phrases = sorted({_plain(p.pattern) for p, _ in pats} - {""}, key=len)
    return Lexicon(pats, comp_pats, phrases, load_context())


# 뉴스 어휘 중 특허·논문 문장에서는 흔한 영어 낱말이거나 뜻이 다른 것 — 여기서는 쓰지 않는다 (긴 표현은 patent_terms.json 에)
TECH_STOP = {"goes", "lide", "bert", "dynamo", "coupe", "esun", "seware", "e-tube", "novec", "영상 생성", "긴 컨텍스트", "kv 캐시", "구글 tpu", "tpu v8"}


def _plural(p: re.Pattern) -> re.Pattern:
    """특허 문장은 복수형이 많다 ('through silicon vias', 'micro bumps') — 끝에 s/es 를 허용한다."""
    if p.pattern.endswith("(?![a-z])"):
        return re.compile(p.pattern[: -len("(?![a-z])")] + "(?:e?s)?(?![a-z])", p.flags)
    return p


def _plain(pattern: str) -> str:
    """정규식 패턴 → 1차 거르기용 짧은 소문자 조각 (첫 단어 경계 앞까지). 길게 맞출 필요 없다 — 정확한 태깅은 로컬에서 다시 한다."""
    s = re.sub(r"\(\?:e\?s\)\?\(\?!\[a-z\]\)$", "", pattern)
    s = re.sub(r"^\(\?<!\[a-z0-9\]\)|\(\?!\[a-z\]\)$|\(\?<!\[A-Za-z0-9\]\)|\(\?!\[A-Za-z0-9\]\)$", "", s)
    s = s.replace(r"[\s-]", " ").replace("\\", "")
    return s.lower().strip()[:40]


def term_regex(phrases: list[str]) -> str:
    """BigQuery RE2 용: 구절들의 OR. 공백은 공백·하이픈 모두."""
    def one(p: str) -> str:
        r = re.escape(p).replace(r"\ ", "[ -]")
        return rf"\b{r}\b" if len(p) <= 6 and p.isascii() else r     # 짧은 약어는 낱말 경계로 ('mlcc' 가 다른 낱말 속에 걸리지 않게)

    parts = sorted({one(p) for p in phrases if len(p) >= 4}, key=len, reverse=True)
    return "(?:" + "|".join(parts) + ")"


# ---------------------------------------------------------------- 특허 (BigQuery)
def patents_sql(domains: dict[str, list[str]]) -> str:
    return f"""
SELECT * FROM (
  SELECT
    p.publication_number, p.family_id, p.country_code, p.kind_code,
    p.publication_date, p.priority_date, p.filing_date,
    ARRAY(SELECT c.code FROM UNNEST(p.cpc) c WHERE REGEXP_CONTAINS(c.code, @cpc_re) LIMIT 12) AS cpc,
    ARRAY(SELECT AS STRUCT a.name, a.country_code FROM UNNEST(p.assignee_harmonized) a LIMIT 6) AS assignees,
    (SELECT AS STRUCT SUBSTR(t.text, 1, 300) AS text, t.language FROM UNNEST(p.title_localized) t
       ORDER BY IF(t.language = 'en', 0, 1) LIMIT 1) AS title,
    (SELECT SUBSTR(t.text, 1, 600) FROM UNNEST(p.abstract_localized) t
       ORDER BY IF(t.language = 'en', 0, 1) LIMIT 1) AS abstract
  FROM `{BQ_TABLE}` p
  WHERE p.publication_date >= @since
    AND p.country_code IN UNNEST(@countries)
    AND EXISTS (SELECT 1 FROM UNNEST(p.cpc) c WHERE REGEXP_CONTAINS(c.code, @cpc_re))
)
WHERE REGEXP_CONTAINS(LOWER(CONCAT(IFNULL(title.text, ''), ' ', IFNULL(abstract, ''))), @term_re)
"""


def domain_series_sql(domains: dict[str, list[str]]) -> str:
    rows = ",\n    ".join(f"STRUCT('{d}' AS domain, r'{cpc_regex(p)}' AS re)" for d, p in domains.items())
    return f"""
SELECT d.domain, p.country_code, DIV(p.publication_date, 10000) AS year, COUNT(DISTINCT p.family_id) AS families
FROM `{BQ_TABLE}` p, UNNEST([
    {rows}
  ]) d
WHERE p.publication_date >= @since AND p.country_code IN UNNEST(@countries)
  AND EXISTS (SELECT 1 FROM UNNEST(p.cpc) c WHERE REGEXP_CONTAINS(c.code, d.re))
GROUP BY 1, 2, 3
"""


def run_patents(args: argparse.Namespace) -> int:
    try:
        from google.cloud import bigquery
    except ImportError:
        print("google-cloud-bigquery 가 없습니다: pip install -e '.[techdocs]'", file=sys.stderr)
        return 2
    from wsj.ecosystems.ontology import load_graph

    domains, _, terms = load_conf()
    lex = build_lex(load_graph(), terms)
    since = int(args.since.replace("-", ""))
    params = [
        bigquery.ScalarQueryParameter("since", "INT64", since),
        bigquery.ArrayQueryParameter("countries", "STRING", list(args.countries)),
        bigquery.ScalarQueryParameter("cpc_re", "STRING", cpc_regex(p for ps in domains.values() for p in ps)),
        bigquery.ScalarQueryParameter("term_re", "STRING", term_regex(lex.phrases)),
    ]
    client = bigquery.Client(project=args.gcp_project)
    jobs = {"patents": patents_sql(domains), "domain_series": domain_series_sql(domains)}
    total = 0
    for name, sql in jobs.items():
        p = params if name == "patents" else params[:2]
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=p, dry_run=True, use_query_cache=False))
        gb = dry.total_bytes_processed / 1e9
        total += gb
        print(f"{name}: 스캔 {gb:,.0f} GB")
    print(f"합계 {total:,.0f} GB (BigQuery 무료 사용량은 월 1,000 GB)")
    if args.dry_run:
        return 0
    if total > args.max_gb:
        print(f"--max-gb {args.max_gb} 을 넘습니다. 국가·기간을 줄이거나 --max-gb 를 올리세요.", file=sys.stderr)
        return 2
    RAW.mkdir(parents=True, exist_ok=True)
    n = 0
    job = client.query(jobs["patents"], job_config=bigquery.QueryJobConfig(query_parameters=params))
    with gzip.open(RAW / "patents.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in job.result(page_size=20000):
            f.write(json.dumps(_bq_row(row), ensure_ascii=False) + "\n")
            n += 1
            if n % 50000 == 0:
                print(f"  특허 {n:,}건 받음")
    series = [dict(r.items()) for r in client.query(jobs["domain_series"], job_config=bigquery.QueryJobConfig(query_parameters=params[:2])).result()]
    (RAW / "patent_domain_series.json").write_text(json.dumps(series, ensure_ascii=False), encoding="utf-8")
    print(f"특허 {n:,}건 · 분류 묶음 시계열 {len(series):,}행 → {RAW}")
    return 0


def _bq_row(row: Any) -> dict[str, Any]:
    d = dict(row.items())
    t = d.get("title") or {}
    d["title"] = (t.get("text") if isinstance(t, dict) else t) or ""
    d["title_lang"] = t.get("language") if isinstance(t, dict) else None
    d["assignees"] = [dict(a) for a in d.get("assignees") or []]
    return d


# ---------------------------------------------------------------- 논문 (OpenAlex)
class OpenAlex:
    def __init__(self, api_key: str | None, mailto: str | None = None, opener=urlopen) -> None:
        self.key, self.mailto, self.opener, self.calls = api_key, mailto, opener, Counter()

    def get(self, path: str, params: dict[str, Any], kind: str = "list") -> dict[str, Any]:
        q = {k: v for k, v in params.items() if v is not None}
        if self.key:
            q["api_key"] = self.key
        if self.mailto:
            q["mailto"] = self.mailto
        url = f"{OPENALEX}{path}?{urlencode(q)}"
        for attempt in range(6):
            try:
                with self.opener(Request(url, headers={"User-Agent": "WSJ-investment techdocs"}), timeout=60) as r:
                    self.calls[kind] += 1
                    return json.loads(r.read().decode("utf-8"))
            except HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except URLError:
                if attempt < 5:
                    time.sleep(2 ** attempt)
                    continue
                raise
        raise RuntimeError("unreachable")

    def pages(self, path: str, params: dict[str, Any], cap: int) -> Iterator[dict[str, Any]]:
        cursor, n = "*", 0
        while cursor and n < cap:
            data = self.get(path, {**params, "per_page": 200, "cursor": cursor})
            for item in data.get("results") or []:
                yield item
                n += 1
                if n >= cap:
                    return
            cursor = (data.get("meta") or {}).get("next_cursor")


def resolve_topics(oa: OpenAlex, phrases: dict[str, str]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for phrase, domain in phrases.items():
        res = oa.get("/topics", {"search": phrase, "per_page": 3, "select": "id,display_name,works_count,subfield"}, "search").get("results") or []
        if not res:
            log.warning("주제를 못 찾음: %s", phrase)
            continue
        t = res[0]
        tid = t["id"].rsplit("/", 1)[-1]
        if tid in seen:
            continue
        seen.add(tid)
        out.append({"id": tid, "name": t.get("display_name"), "query": phrase, "domain": domain,
                    "works_count": t.get("works_count"), "subfield": (t.get("subfield") or {}).get("display_name")})
    return out


def run_papers(args: argparse.Namespace) -> int:
    _, phrases, _ = load_conf()
    from wsj.config import load_settings

    settings = load_settings()                              # pipeline/.env 도 읽는다
    key = os.environ.get("OPENALEX_API_KEY") or settings.openalex_api_key
    if not key:
        print("OPENALEX_API_KEY 가 없습니다 (openalex.org 에서 무료 발급). 키 없이는 하루 사용량이 매우 작습니다.", file=sys.stderr)
    oa = OpenAlex(key, os.environ.get("OPENALEX_MAILTO") or settings.openalex_mailto or None)
    RAW.mkdir(parents=True, exist_ok=True)
    topics = resolve_topics(oa, phrases)
    (RAW / "openalex_topics.json").write_text(json.dumps(topics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"주제 {len(topics)}개 확인 → {RAW / 'openalex_topics.json'}")
    series: list[dict[str, Any]] = []
    n = 0
    with gzip.open(RAW / "papers.jsonl.gz", "wt", encoding="utf-8") as f:
        for t in topics:
            base = f"primary_topic.id:{t['id']},from_publication_date:{args.since}-01-01"
            for scope, flt in (("all", base), ("company", base + ",authorships.institutions.type:company")):
                for g in oa.get("/works", {"filter": flt, "group_by": "publication_year"}).get("group_by") or []:
                    series.append({"topic": t["id"], "scope": scope, "year": int(g["key"]), "n": g["count"]})
            flt = f"primary_topic.id:{t['id']},authorships.institutions.type:company,from_publication_date:{args.docs_since}-01-01"
            sel = "id,doi,display_name,publication_date,primary_topic,authorships,cited_by_count,abstract_inverted_index,type"
            k = 0
            for w in oa.pages("/works", {"filter": flt, "select": sel, "sort": "publication_date:desc"}, args.max_per_topic):
                f.write(json.dumps(slim_work(w, t["id"]), ensure_ascii=False) + "\n")
                k += 1
            n += k
            print(f"  {t['name']}: 기업 논문 {k:,}건")
    (RAW / "paper_series.json").write_text(json.dumps(series), encoding="utf-8")
    print(f"논문 {n:,}건 · 주제 시계열 {len(series)}행 · 호출 {dict(oa.calls)} → {RAW}")
    return 0


def slim_work(w: dict[str, Any], topic: str) -> dict[str, Any]:
    from wsj.ecosystems.monitor import rebuild_abstract

    insts = []
    for a in w.get("authorships") or []:
        for i in a.get("institutions") or []:
            insts.append({"name": i.get("display_name"), "type": i.get("type"), "country": i.get("country_code")})
    uniq = list({(i["name"], i["type"]): i for i in insts if i.get("name")}.values())
    inv = w.get("abstract_inverted_index") or {}
    return {"id": (w.get("id") or "").rsplit("/", 1)[-1], "doi": w.get("doi"), "title": w.get("display_name") or "",
            "publication_date": w.get("publication_date"), "topic": topic, "institutions": uniq[:12],
            "cited_by": w.get("cited_by_count") or 0, "abstract": rebuild_abstract(inv)[:600] if inv else "", "type": w.get("type")}


# ---------------------------------------------------------------- 묶기 (노드 태깅·집계)
@dataclass
class Doc:
    doc_id: str
    source: str
    title: str
    abstract: str
    published: date | None
    priority: date | None = None
    orgs: list[dict[str, Any]] = field(default_factory=list)
    countries: set[str] = field(default_factory=set)
    codes: set[str] = field(default_factory=set)
    nodes: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    url: str | None = None
    cited_by: int | None = None

    def row(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "source": self.source, "title": self.title[:300], "abstract": (self.abstract or "")[:400] or None,
                "published_on": self.published.isoformat() if self.published else None,
                "priority_on": self.priority.isoformat() if self.priority else None,
                "orgs": self.orgs[:8], "countries": sorted(self.countries), "codes": sorted(self.codes)[:12], "nodes": sorted(self.nodes),
                "url": self.url, "cited_by": self.cited_by, "family_size": len(self.countries) if self.source == "patent" else None}


def _ymd(v: Any) -> date | None:
    if v in (None, "", 0):
        return None
    s = str(v)
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8])) if s.isdigit() and len(s) == 8 else date.fromisoformat(s[:10])
    except ValueError:
        return None


def patent_docs(rows: Iterable[dict[str, Any]], lex: Lexicon, domains: dict[str, list[str]]) -> list[Doc]:
    """공개 문서 → 패밀리(같은 발명)로 묶는다. 대표는 가장 이른 공개, 제목·초록은 영어가 있으면 영어."""
    fam: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        fid = str(r.get("family_id") or "")
        fam[fid if fid and fid != "-1" else r["publication_number"]].append(r)
    docs = []
    for rs in fam.values():
        rs.sort(key=lambda r: r.get("publication_date") or 99999999)
        first = rs[0]
        en = next((r for r in rs if r.get("title_lang") == "en"), first)
        names: dict[str, dict[str, Any]] = {}
        for r in rs:
            for a in r.get("assignees") or []:
                nm = (a.get("name") or "").strip()
                if nm and nm.upper() not in {k.upper() for k in names}:
                    names[nm] = {"name": nm, "country": a.get("country_code"), "company": lex.company(nm)}
        codes = {c for r in rs for c in r.get("cpc") or []}
        d = Doc(doc_id=f"patent:{first['publication_number']}", source="patent", title=en.get("title") or first.get("title") or "",
                abstract=en.get("abstract") or first.get("abstract") or "", published=_ymd(first.get("publication_date")),
                priority=min((p for p in (_ymd(r.get("priority_date")) for r in rs) if p), default=None),
                orgs=list(names.values()), countries={r["country_code"] for r in rs if r.get("country_code")}, codes=codes,
                url=f"https://patents.google.com/patent/{first['publication_number'].replace('-', '')}")
        d.domains = {x for x in (domain_of(c, domains) for c in codes) if x}
        d.nodes = lex.nodes(f"{d.title} {d.abstract}")
        docs.append(d)
    return docs


def paper_docs(rows: Iterable[dict[str, Any]], lex: Lexicon, topic_domain: dict[str, str]) -> list[Doc]:
    seen: dict[str, Doc] = {}
    for r in rows:
        if r["id"] in seen:
            seen[r["id"]].codes.add(r["topic"])
            continue
        orgs = [{"name": i["name"], "country": i.get("country"), "company": lex.company(i["name"])}
                for i in r.get("institutions") or [] if i.get("type") == "company"]
        d = Doc(doc_id=f"paper:{r['id']}", source="paper", title=r.get("title") or "", abstract=r.get("abstract") or "",
                published=_ymd(r.get("publication_date")), orgs=orgs, countries={o["country"] for o in orgs if o.get("country")},
                codes={r["topic"]}, url=r.get("doi") or f"https://openalex.org/{r['id']}", cited_by=r.get("cited_by"))
        d.domains = {topic_domain[r["topic"]]} if r["topic"] in topic_domain else set()
        d.nodes = lex.nodes(f"{d.title} {d.abstract}")
        seen[r["id"]] = d
    return list(seen.values())


def quarter(d: date) -> str:
    return f"{d.year}-{(d.month - 1) // 3 * 3 + 1:02d}-01"


WINDOWS = (("~2021", 0, 2021), ("2022-2023", 2022, 2023), ("2024~", 2024, 9999))


def window_of(year: int) -> str:
    return next(w for w, lo, hi in WINDOWS if lo <= year <= hi)


def aggregate(docs: list[Doc], top_orgs: int = 25, cap_docs: int = 120, docs_since: date = date(2023, 1, 1),
              new_from: int = 2024) -> tuple[list[dict], list[dict], list[dict]]:
    by_node: dict[tuple[str, str], list[Doc]] = defaultdict(list)
    for d in docs:
        for nid in d.nodes:
            by_node[(nid, d.source)].append(d)
    series: list[dict] = []
    orgs: list[dict] = []
    picked: dict[str, Doc] = {}
    for (nid, src), ds in sorted(by_node.items()):
        cnt: Counter = Counter()
        comp: Counter = Counter()
        for d in ds:
            if d.published:
                q = quarter(d.published)
                cnt[q] += 1
                comp[q] += any(o.get("company") for o in d.orgs)
        series += [{"node": nid, "source": src, "period": q, "n": n, "n_company": comp[q]} for q, n in sorted(cnt.items())]
        first: dict[str, int] = {}
        per_window: dict[str, Counter] = defaultdict(Counter)
        company_of: dict[str, str | None] = {}
        names: dict[str, Counter] = defaultdict(Counter)
        for d in ds:
            if not d.published:
                continue
            for o in d.orgs:
                k = org_key(o["name"])
                names[k][o["name"]] += 1
                first[k] = min(first.get(k, 9999), d.published.year)
                per_window[window_of(d.published.year)][k] += 1
                if o.get("company") and not company_of.get(k):
                    company_of[k] = o["company"]
        for w, c in per_window.items():
            for rank, (k, n) in enumerate(c.most_common(top_orgs), 1):
                orgs.append({"node": nid, "source": src, "span": w, "rank": rank, "org": names[k].most_common(1)[0][0][:200],
                             "company": company_of.get(k), "n": n, "first_year": first[k]})
        recent = [d for d in ds if d.published and d.published >= docs_since]
        recent.sort(key=lambda d: (not any(o.get("company") for o in d.orgs),
                                   not any(first.get(org_key(o["name"]), 0) >= new_from for o in d.orgs),
                                   -len(d.countries) if src == "patent" else -(d.cited_by or 0),
                                   -(d.published.toordinal() if d.published else 0)))
        for d in recent[:cap_docs]:
            picked[d.doc_id] = d
    return series, orgs, [d.row() for d in picked.values()]


def domain_series_rows(patent_series: list[dict[str, Any]], paper_series: list[dict[str, Any]], topics: list[dict[str, Any]]) -> list[dict]:
    """노드가 안 붙은 문서도 버리지 않는다: 분류 묶음(cpc:<묶음>)·OpenAlex 주제(topic:<id>) 단위 연 건수."""
    rows: Counter = Counter()
    for r in patent_series:
        rows[(f"cpc:{r['domain']}", "patent", f"{int(r['year'])}-01-01")] += int(r["families"])
    names = {t["id"]: t for t in topics}
    out = [{"node": k, "source": s, "period": p, "n": n, "n_company": None} for (k, s, p), n in sorted(rows.items())]
    comp = {(r["topic"], r["year"]): r["n"] for r in paper_series if r["scope"] == "company"}
    for r in paper_series:
        if r["scope"] == "all" and r["topic"] in names:
            out.append({"node": f"topic:{r['topic']}", "source": "paper", "period": f"{r['year']}-01-01", "n": r["n"],
                        "n_company": comp.get((r["topic"], r["year"]), 0)})
    return out


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def run_build(args: argparse.Namespace) -> int:
    from wsj.ecosystems.ontology import load_graph

    domains, _, terms = load_conf()
    graph = load_graph()
    lex = build_lex(graph, terms)
    topics = json.loads((RAW / "openalex_topics.json").read_text(encoding="utf-8")) if (RAW / "openalex_topics.json").exists() else []
    pats = patent_docs(_read_jsonl(RAW / "patents.jsonl.gz"), lex, domains)
    paps = paper_docs(_read_jsonl(RAW / "papers.jsonl.gz"), lex, {t["id"]: t["domain"] for t in topics})
    docs = [d for d in pats + paps if d.nodes]
    since = date.fromisoformat(f"{args.docs_since}-01-01")
    series, orgs, rows = aggregate(docs, cap_docs=args.cap_docs, docs_since=since)
    pseries = json.loads((RAW / "patent_domain_series.json").read_text()) if (RAW / "patent_domain_series.json").exists() else []
    tseries = json.loads((RAW / "paper_series.json").read_text()) if (RAW / "paper_series.json").exists() else []
    series += domain_series_rows(pseries, tseries, topics)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("tech_series", series), ("tech_orgs", orgs), ("tech_docs", rows)):
        with gzip.open(OUT / f"{name}.jsonl.gz", "wt", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    labels = {n["id"]: n.get("label", n["id"]) for n in graph["nodes"]}
    (OUT / "summary.md").write_text(summary(series, orgs, labels, len(pats), len(paps), len(docs)), encoding="utf-8")
    print(f"특허 패밀리 {len(pats):,} · 논문 {len(paps):,} → 노드가 붙은 문서 {len(docs):,}")
    print(f"tech_series {len(series):,}행 · tech_orgs {len(orgs):,}행 · tech_docs {len(rows):,}행 → {OUT} (요약: summary.md)")
    return 0


def rising(series: list[dict[str, Any]], today: date | None = None, min_recent: int = 8) -> list[dict[str, Any]]:
    """노드별 최근 2년(끝난 분기만) vs 그 전 2년. 화면에 내지 않는 탐색용 표 — 해석 작업이 어디를 먼저 볼지 고르는 데만 쓴다."""
    today = today or date.today()
    cur = date.fromisoformat(quarter(today))
    lo1 = date(cur.year - 2, cur.month, 1)
    lo0 = date(cur.year - 4, cur.month, 1)
    acc: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for r in series:
        if ":" in r["node"] and r["node"].split(":", 1)[0] in ("cpc", "topic"):
            continue
        p = date.fromisoformat(r["period"])
        if lo1 <= p < cur:
            acc[(r["node"], r["source"])][1] += r["n"]
        elif lo0 <= p < lo1:
            acc[(r["node"], r["source"])][0] += r["n"]
    out = [{"node": k[0], "source": k[1], "prior": a, "recent": b, "ratio": round(b / a, 2) if a else None}
           for k, (a, b) in acc.items() if b >= min_recent]
    out.sort(key=lambda r: (r["ratio"] is None, -(r["ratio"] or 0), -r["recent"]))
    return out


def summary(series, orgs, labels, n_pat, n_pap, n_docs) -> str:
    lines = ["# 논문·특허 백필 요약", "", f"특허 패밀리 {n_pat:,} · 기업 논문 {n_pap:,} · 노드가 붙은 문서 {n_docs:,}", "",
             "## 최근 2년에 가장 빨리 늘어난 노드 (그 전 2년 대비)", "", "| 노드 | 출처 | 그 전 2년 | 최근 2년 | 배수 |", "|---|---|---:|---:|---:|"]
    for r in rising(series)[:40]:
        lines.append(f"| {labels.get(r['node'], r['node'])} | {r['source']} | {r['prior']} | {r['recent']} | {r['ratio'] if r['ratio'] else '새로'} |")
    lines += ["", "## 2024년 이후 처음 나타난 기관 (노드별 상위)", "", "| 노드 | 출처 | 기관 | 건수 |", "|---|---|---|---:|"]
    new = [o for o in orgs if o["span"] == "2024~" and o["first_year"] >= 2024 and o["n"] >= 3]
    new.sort(key=lambda o: -o["n"])
    for o in new[:60]:
        lines.append(f"| {labels.get(o['node'], o['node'])} | {o['source']} | {o['org']} | {o['n']} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 올리기
TABLES = {"tech_series": ["node", "source", "period"], "tech_orgs": ["node", "source", "span", "org"], "tech_docs": ["doc_id"]}


def run_upload(args: argparse.Namespace, store: Any | None = None) -> int:
    if store is None:
        from wsj.config import load_settings
        from wsj.db import make_store

        store = make_store(load_settings())
    for name, keys in TABLES.items():
        rows = list(_read_jsonl(OUT / f"{name}.jsonl.gz"))
        if not rows:
            print(f"{name}: 올릴 것이 없습니다 (build 를 먼저)")
            continue
        if args.replace:
            for src in sorted({r["source"] for r in rows}):
                store.delete(f"ideas.{name}", {"source": src})
        n = 0
        for i in range(0, len(rows), args.batch):
            n += store.upsert(f"ideas.{name}", rows[i:i + args.batch], keys)
        print(f"{name}: {n:,}행 올림")
    return 0


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="python -m wsj.ecosystems.techdocs", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("patents", help="Google Patents(BigQuery) → data/techdocs/raw")
    p.add_argument("--gcp-project", required=True, help="BigQuery 를 돌릴 GCP 프로젝트 (샌드박스 가능)")
    p.add_argument("--since", default="2018-01-01", help="공개일 시작 (YYYY-MM-DD)")
    p.add_argument("--countries", type=lambda s: s.split(","), default=list(DEFAULT_COUNTRIES), help="쉼표로: US,KR,JP,TW,EP,WO (CN 은 기본 제외)")
    p.add_argument("--dry-run", action="store_true", help="스캔 용량만 보고 끝낸다")
    p.add_argument("--max-gb", type=float, default=900, help="이보다 많이 스캔하면 멈춘다 (무료 1,000GB/월)")
    q = sub.add_parser("papers", help="OpenAlex → data/techdocs/raw (OPENALEX_API_KEY)")
    q.add_argument("--since", type=int, default=2015, help="주제 시계열 시작 연도")
    q.add_argument("--docs-since", type=int, default=2021, help="기업 논문을 받을 시작 연도")
    q.add_argument("--max-per-topic", type=int, default=4000)
    b = sub.add_parser("build", help="노드 태깅·집계 → data/techdocs/out")
    b.add_argument("--docs-since", type=int, default=2023, help="대표 문서를 고를 시작 연도")
    b.add_argument("--cap-docs", type=int, default=120, help="노드·출처마다 대표 문서 수")
    u = sub.add_parser("upload", help="data/techdocs/out → Supabase (0033 필요)")
    u.add_argument("--replace", action="store_true", help="같은 출처의 기존 행을 지우고 올린다")
    u.add_argument("--batch", type=int, default=500)
    args = ap.parse_args(argv)
    return {"patents": run_patents, "papers": run_papers, "build": run_build, "upload": run_upload}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
