"""이슈 피드 출처 레지스트리 — 업계지·회사 뉴스룸·정책 RSS, 리서치 기관 보도자료, 논문. ADR-0014 개정.

issues.run 이 다른 수집기(Google News·SEC·Federal Register·DB 신호·지표)와 함께 부른다. 모든 출처는 무료·무인증.
출처를 늘릴 때는 FEEDS 에 한 줄을 더하면 된다 — 일반 RSS/Atom 이면 파서는 공통.

source_type (issues.SOURCE_WEIGHT 의 가중치):
  trade          업계지 (어휘 태깅에 걸린 것만 남는다)
  newsroom       회사 뉴스룸·IR (1차 출처)
  policy         정부·의회 (제목 필터 통과분만; 노드 태그 없이도 후보)
  analyst        리서치 기관 보도자료 (TrendForce: 가격·출하·캐파 전망)
  research       논문 (arXiv, OpenAlex — 온톨로지 노드 구문으로 검색)
"""

from __future__ import annotations

import html
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from wsj.http import HttpClient

if TYPE_CHECKING:
    from wsj.ecosystems.issues import Item

log = logging.getLogger("wsj.ecosystems.sources")
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
              "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5"}
ATOM = "{http://www.w3.org/2005/Atom}"

POLICY_FILTER = (r"semiconductor|chip|integrated circuit|export control|entity list|tariff|section 232|section 301|critical mineral|"
                 r"gallium|germanium|rare earth|data cent|artificial intelligence|\bAI\b|grid|transformer|large load|CHIPS|"
                 r"advanced packaging|photonic|optical|memory")


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    source_type: str
    ecosystem: str | None = None
    title_filter: str | None = None  # 정규식, 제목(+요약)에 걸려야 통과


FEEDS: list[Feed] = [
    # 업계지 (Semiconductor Today 는 issues.TRADE_RSS 에서 이미 받는다)
    Feed("EE Times", "https://www.eetimes.com/feed/", "trade"),
    Feed("Semiconductor Engineering", "https://semiengineering.com/feed/", "trade"),
    Feed("eeNews Europe", "https://www.eenewseurope.com/en/feed/", "trade"),
    Feed("Power Electronics News", "https://www.powerelectronicsnews.com/feed/", "trade", "power"),
    Feed("DCD", "https://www.datacenterdynamics.com/en/rss/", "trade"),
    Feed("ServeTheHome", "https://www.servethehome.com/feed/", "trade"),
    Feed("Tom's Hardware", "https://www.tomshardware.com/feeds/all", "trade"),
    Feed("DigiTimes", "https://www.digitimes.com/rss/daily.xml", "trade"),
    # 회사 뉴스룸·IR (미국 상장사 보도자료는 SEC 8-K EX-99 로도 들어온다)
    Feed("Samsung Newsroom", "https://news.samsung.com/global/feed", "newsroom", "hbm",
         r"HBM|DRAM|memory|foundry|packaging|semiconductor|chip|AI|data cent"),
    Feed("SK hynix Newsroom", "https://news.skhynix.com/feed/", "newsroom", "hbm"),
    Feed("NVIDIA Newsroom", "https://nvidianews.nvidia.com/releases.xml", "newsroom", None,
         r"data cent|Rubin|Blackwell|NVLink|Spectrum|photonic|800|power|supply|factory|manufactur|partner"),
    Feed("PR Newswire · Semiconductors", "https://www.prnewswire.com/rss/consumer-technology-latest-news/semiconductors-list.rss", "newsroom"),
    # 정책
    Feed("White House · Presidential Actions", "https://www.whitehouse.gov/presidential-actions/feed/", "policy", "cross", POLICY_FILTER),
    Feed("NIST News", "https://www.nist.gov/news-events/news/rss.xml", "policy", "cross", r"CHIPS|semiconductor|advanced packaging|chip"),
]

TRENDFORCE = "https://www.trendforce.com/presscenter/news"
TRENDFORCE_FILTER = re.compile(
    r"HBM|DRAM|NAND|memory|CoWoS|packaging|foundry|wafer|AI server|GPU|ASIC|optical|fiber|transceiver|CPO|silicon photonics|"
    r"power|SiC|GaN|liquid cool|data cent|CSP|capex|substrate|ABF|test", re.I)
ARXIV = "https://export.arxiv.org/api/query"
OPENALEX = "https://api.openalex.org/works"
INDUSTRY = re.compile(  # 저자 소속의 산업체 — 대소문자 구분·단어 경계 (ASE 가 phase 에 걸리지 않게)
    r"\b(TSMC|Taiwan Semiconductor|Samsung|SK hynix|SK Hynix|Micron|Intel|NVIDIA|Nvidia|AMD|Broadcom|Marvell|Applied Materials|"
    r"Lam Research|KLA|ASML|imec|IMEC|Infineon|Wolfspeed|onsemi|Texas Instruments|Coherent|Lumentum|Cisco|Google|Meta Platforms|"
    r"Microsoft|Amazon|IBM|Huawei|ASE Technology|Amkor|Kioxia|BE Semiconductor|Tokyo Electron|Hitachi|Corning|Ayar Labs|Lightmatter|Celestial AI)\b")


def _strip(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).replace("\xa0", " ").strip()


def _dt(s: str | None) -> datetime | None:
    from wsj.ecosystems.issues import _dt as parse

    return parse(s)


def parse_feed(xml_text: str) -> list[tuple[str, str, datetime | None, str]]:
    """RSS 2.0 / Atom → [(link, title, published, summary)]."""
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter("item"):
        out.append((it.findtext("link") or "", _strip(it.findtext("title")), _dt(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
                    _strip(it.findtext("description"))[:500]))
    for e in root.iter(f"{ATOM}entry"):
        link = next((ln.get("href") for ln in e.findall(f"{ATOM}link") if ln.get("rel") in (None, "alternate")), "") or ""
        out.append((link, _strip(e.findtext(f"{ATOM}title")), _dt(e.findtext(f"{ATOM}published") or e.findtext(f"{ATOM}updated")),
                    _strip(e.findtext(f"{ATOM}summary") or e.findtext(f"{ATOM}content"))[:500]))
    return out


def collect_feeds(http: HttpClient, since: datetime, feeds: list[Feed] | None = None) -> list[Item]:
    from wsj.ecosystems.issues import Item

    out: list[Item] = []
    for f in feeds or FEEDS:
        try:
            entries = parse_feed(http.get_text(f.url, headers=BROWSER_UA))
        except Exception as exc:  # noqa: BLE001 - 출처 하나가 죽어도 나머지는 계속
            log.warning("feed %s failed: %s", f.name, exc)
            continue
        n = 0
        for link, title, d, summary in entries:
            if not link or not title or not d or d < since:
                continue
            if f.title_filter and not re.search(f.title_filter, f"{title} {summary}", re.I):
                continue
            out.append(Item(link, title, d, f.name, f.source_type, summary, f.name, f.ecosystem))
            n += 1
        log.info("feed %-34s %3d/%d", f.name, n, len(entries))
    return out


def collect_trendforce(http: HttpClient, since: datetime) -> list[Item]:
    """TrendForce 보도자료 목록 (가격·출하·캐파 전망). 목록 페이지에 날짜가 URL 에 들어 있다 (/presscenter/news/YYYYMMDD-n.html)."""
    from wsj.ecosystems.issues import Item

    try:
        page = http.get_text(TRENDFORCE, headers=BROWSER_UA)
    except Exception as exc:  # noqa: BLE001
        log.warning("trendforce failed: %s", exc)
        return []
    out, seen = [], set()
    for m in re.finditer(r'href="(/presscenter/news/\d{8}-\d+\.html)"[^>]*>(.*?)</a>', page, re.S):
        path, title = m.group(1), _strip(m.group(2))
        if not title or path in seen:
            continue
        seen.add(path)
        d = datetime.strptime(path.split("/")[-1][:8], "%Y%m%d").replace(tzinfo=UTC)
        if d < since or not TRENDFORCE_FILTER.search(title):
            continue
        out.append(Item("https://www.trendforce.com" + path, title, d, "TrendForce", "analyst", "", "trendforce", None))
    log.info("trendforce items: %d", len(out))
    return out


# ---------------------------------------------------------------------- 논문
def research_queries(discovery: dict[str, list[str]], per_node: int = 1) -> list[tuple[str, str]]:
    """(노드 id, 따옴표 없는 구문). 발굴 구문의 첫 인용구 — 이미 사람이 고른 주제어다."""
    out = []
    for nid, qs in discovery.items():
        for q in qs[:per_node]:
            m = re.findall(r'"([^"]+)"', q)
            if m and len(m[0]) >= 5:
                out.append((nid, m[0]))
    return out


def collect_arxiv(http: HttpClient, queries: list[tuple[str, str]], since: datetime, pause: float = 3.0) -> list[Item]:
    from wsj.ecosystems.issues import Item

    out: list[Item] = []
    for nid, phrase in queries:
        params = {"search_query": f'all:"{phrase}"', "sortBy": "submittedDate", "sortOrder": "descending", "max_results": "10"}
        try:
            entries = ET.fromstring(http.get_text(ARXIV, params=params, headers=BROWSER_UA)).findall(f"{ATOM}entry")
        except Exception as exc:  # noqa: BLE001
            log.warning("arxiv %r failed: %s", phrase, exc)
            continue
        finally:
            time.sleep(pause)  # arXiv API 이용 규칙: 3초에 1회
        for e in entries:
            d = _dt(e.findtext(f"{ATOM}published"))
            if not d or d < since:
                continue
            link = (e.findtext(f"{ATOM}id") or "").strip()
            authors = [a.findtext(f"{ATOM}name") or "" for a in e.findall(f"{ATOM}author")]
            summary = _strip(e.findtext(f"{ATOM}summary"))
            it = Item(link, _strip(e.findtext(f"{ATOM}title")), d, "arXiv", "research",
                      f"{', '.join(authors[:4])}{' 외' if len(authors) > 4 else ''}. {summary[:420]}", phrase, None)
            it.nodes.add(nid)
            out.append(it)
    log.info("arxiv items: %d (%d queries)", len(out), len(queries))
    return out


def _inverted(abstract_index: dict[str, list[int]] | None, limit: int = 420) -> str:
    if not abstract_index:
        return ""
    words = sorted(((p, w) for w, ps in abstract_index.items() for p in ps))
    return " ".join(w for _, w in words)[:limit]


def collect_openalex(http: HttpClient, queries: list[tuple[str, str]], since: datetime, mailto: str | None = None) -> list[Item]:
    """OpenAlex — IEEE·Elsevier 등 학회지·저널 메타데이터 (ECTC·OFC·ISSCC 포함). 저자 소속에 산업체가 있으면 스니펫 앞에 표시."""
    from wsj.ecosystems.issues import Item

    out: list[Item] = []
    fails = 0
    for nid, phrase in queries:
        params: dict[str, Any] = {"search": f'"{phrase}"', "filter": f"from_publication_date:{since.date().isoformat()},type:article|proceedings-article|preprint",
                                  "sort": "publication_date:desc", "per_page": "10",
                                  "select": "id,doi,title,publication_date,primary_location,authorships,abstract_inverted_index"}
        if mailto:
            params["mailto"] = mailto
        key = os.environ.get("OPENALEX_API_KEY", "").strip()
        if key:
            params["api_key"] = key
        try:
            data = http.get_json(OPENALEX, params=params)
        except Exception as exc:  # noqa: BLE001
            log.warning("openalex %r failed: %s", phrase, exc)
            fails += 1
            if fails >= 3:  # 일일 한도(429) — 나머지 질의는 건너뛴다
                log.warning("openalex: too many failures, stopping")
                break
            continue
        for w in data.get("results") or []:
            try:
                d = datetime.fromisoformat(w["publication_date"]).replace(tzinfo=UTC)
            except (KeyError, TypeError, ValueError):
                continue
            if d < since or d > datetime.now(UTC) + timedelta(days=1):
                continue
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or "OpenAlex"
            insts = sorted({i.get("display_name", "") for a in w.get("authorships") or [] for i in a.get("institutions") or [] if i.get("display_name")})
            industry = [i for i in insts if INDUSTRY.search(i)]
            lead = f"[산업체: {', '.join(industry[:3])}] " if industry else (f"[{insts[0]}] " if insts else "")
            it = Item(w.get("doi") or w.get("id") or "", _strip(w.get("title")), d, venue[:80], "research",
                      lead + _inverted(w.get("abstract_inverted_index")), phrase, None)
            if not it.url or not it.title:
                continue
            it.nodes.add(nid)
            out.append(it)
    log.info("openalex items: %d (%d queries)", len(out), len(queries))
    return out
