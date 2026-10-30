"""공급망 이슈 피드 — 여러 출처에서 최근 이슈를 모아 온톨로지에 태깅하고, 선별·요약해 ideas.supply_chain_issues 에 저장한다. ADR-0014.

    python -m wsj.ecosystems.issues run [--days 14] [--no-llm] [--model sonnet] [--out data/issues/latest.json]

출처 (모두 무료·무인증):
  news      Google News RSS 검색 (생태계 주제·표준·가격·정책 질의 + 그래프 기업명, when:Nd)
  trade     업계지 RSS (Semiconductor Today, EE Times, SemiEngineering, DCD 등 — sources.FEEDS) — 어휘에 걸리는 것만
  newsroom  회사 뉴스룸·IR (Samsung, SK hynix, NVIDIA, PR Newswire 반도체)
  sec       EDGAR 전문검색 8-K/6-K (온톨로지 구문, 원문 EX-99 헤드라인)
  regulator Federal Register API (BIS·투자안보실·ITC·DOE·상무부 232·USTR·FERC·NIST)
  policy    백악관 대통령 조치·NIST 뉴스 (반도체·관세·핵심광물·데이터센터 필터)
  analyst   TrendForce 보도자료 (메모리·광·전력 가격·출하 전망)
  research  논문 — arXiv, OpenAlex (학회·저널; 노드 구문 검색, 최근 30일)
  data      지표 변화 — 메모리 현물가, 미국 PPI·원자재, 대만 공급사 월매출 (indicators.py)
  signals   core.signals (공급망 유니버스 기업의 내부자·공시 신호)

흐름: 수집 → 정규화·중복 제거 → 어휘 태깅(노드·기업) → 클러스터링 → 규칙 점수 → (선택) LLM 선별·한국어 요약·영향 판정 → upsert.
LLM 은 입력에 있는 노드 id·기업 id·출처 번호만 쓰도록 제한하고, 그 밖의 값은 버린다.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from wsj.ecosystems.discover import QUERIES as DISCOVERY_QUERIES
from wsj.ecosystems.ontology import GRAPH_PATH, load_graph
from wsj.http import HttpClient

log = logging.getLogger("wsj.ecosystems.issues")
ALIASES_PATH = GRAPH_PATH.parent / "node_aliases.json"
IMPACT_PATH = GRAPH_PATH.parents[2] / "apps" / "web" / "src" / "data" / "impact-index.json"

# ---------------------------------------------------------------------- 출처 정의
NEWS_TOPICS: dict[str, list[str]] = {
    "hbm": ["HBM4", "HBM4E", "hybrid bonding HBM", "CoWoS capacity", "advanced packaging AI chips",
            "thermocompression bonder", "HBM supply shortage", "wafer level burn-in"],
    "optics": ["co-packaged optics", "1.6T transceiver", "silicon photonics AI data center", "800G optical transceiver",
               "EML laser supply", "indium phosphide substrate", "optical DSP 200G lane"],
    "power": ["800 VDC data center", "800V HVDC NVIDIA", "silicon carbide data center power", "GaN data center power supply",
              "liquid cooling data center supply chain", "solid-state transformer data center", "megawatt rack power"],
    "cross": ["AI data center supply chain bottleneck", "semiconductor export controls", "gallium germanium export",
              # 표준
              "JEDEC HBM standard", "IEEE 802.3dj", "OCP 800 VDC specification", "OIF 1.6T",
              # 가격·리드타임
              "DRAM contract prices", "HBM price negotiation", "optical fiber price shortage", "transformer lead times data center",
              "CoWoS price increase", "ABF substrate shortage",
              # 정책
              "Section 232 semiconductor tariffs", "CHIPS Act award", "FERC large load interconnection", "AI chip export rule China",
              "Korea semiconductor policy HBM", "Taiwan export controls semiconductor"],
}
# (기관 slug, 제목 필터 정규식 또는 None=전부). 전문 검색은 무관 문서가 너무 많아 기관 단위로 받는다.
FEDREG_AGENCIES: list[tuple[str, str | None]] = [
    ("industry-and-security-bureau", r"^(?!.*(information collection|temporary denial|renewing)).*"),
    ("investment-security-office", None),
    ("international-trade-commission", r"semiconductor|integrated circuit|memory|optical|photonic|laser|transceiver|wafer|silicon|power (supply|module|converter)|connector|gallium|germanium"),
    ("energy-department", r"data cent|large load|co-located load|transformer"),
    ("commerce-department", r"section 232|semiconductor|polysilicon|critical mineral|copper|integrated circuit|wafer"),
    ("trade-representative-office-of-united-states", r"semiconductor|section 301|legacy chip|integrated circuit"),
    ("federal-energy-regulatory-commission", r"large load|co-locat|data cent|interconnection"),
    ("national-institute-of-standards-and-technology", r"CHIPS|semiconductor|advanced packaging"),
]
TRADE_RSS = ["https://www.semiconductor-today.com/rss/news.xml"]
SEC_PHRASES_PER_NODE = 1  # 노드당 첫 구문만 8-K 검색 (호출 수 제한)
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
FEDREG = "https://www.federalregister.gov/api/v1/documents.json"
EFTS = "https://efts.sec.gov/LATEST/search-index"

SOURCE_WEIGHT = {"sec": 3.0, "regulator": 3.0, "policy": 3.0, "press_release": 2.5, "newsroom": 2.5, "analyst": 2.5, "data": 2.5,
                 "trade": 2.0, "signal": 2.0, "research": 1.5, "news": 1.5}
ALWAYS_RELEVANT = {"regulator", "policy", "analyst", "data"}  # 출처 단계에서 이미 주제 필터를 통과
QUOTA = {"research": 6, "data": 8, "analyst": 5, "policy": 4, "regulator": 4, "newsroom": 4}  # 규칙 점수와 무관하게 후보에 넣는 유형별 최소치
RESEARCH_DAYS = 30
PRESS_WIRES = ("business wire", "businesswire", "globe newswire", "globenewswire", "pr newswire", "prnewswire", "accesswire")
EVENT_TYPES = ("capacity", "technology", "standard", "regulation", "order", "earnings", "m_and_a", "supply_disruption", "pricing", "research", "other")
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
STOP = set(("the a an of for and to in on with by from at as is are be its this that new ai into how why what will over says said "
             "stock stocks shares price prices forecast forecasts analyst analysts predictions today results result quarter third second "
             "fourth first fiscal financial conference call inc corp ltd co company nasdaq nyse 2025 2026 2027 q1 q2 q3 q4 report reports "
             "announces announce update news week market").split())
# 주가·일정·투자자 기사 — 공급망 사건이 아니다
NOISE = re.compile(
    r"stock (forecast|price|too expensive|analysis|rating)|price today|tokenized|price target|short interest|"
    r"(schedules|announces date|to release|to report|will report).{0,60}(results|earnings|conference call)|"
    r"(shares|stock) (rise|rises|fall|falls|jump|jumps|drop|drops|gap|gaps|surge|surges|slide|slides|rebound|rebounds|soar|soars|sink|sinks)|"
    r"(rebounds|jumps|soars|slides|sinks|surges) \d+%|(buys|sells|acquires|trims|boosts|cuts) (shares|stake|position)|"
    r"stake in|holdings in|position in|(is|are) .{0,30}(buy|sell|hold)\b|motley fool|zacks rank|top .{0,20} stocks|should you buy|"
    r"options (activity|trading)|unusual options|earnings preview|what to expect|ex-dividend|estimates [–-]|"
    r"investment (narrative|story)|undervalued|overvalued|shareholders got|holders bought|price prediction|live price|"
    r"robinhood token|reports next week|wall street expects|form 4 |tdr overview|explained|investors are watching|"
    r"skyrocket|(climbs|gains|falls|drops|sinks|tumbles|slips) \d+(\.\d+)?%|topping estimates|now covered by|analysts thinking|"
    r"\bgf value\b|stock looks|stock is (up|down)|why .{0,40} stock",
    re.I,
)


@dataclass
class Item:
    url: str
    title: str
    published_at: datetime
    publisher: str
    source_type: str
    snippet: str = ""
    query: str = ""
    ecosystem_hint: str | None = None
    nodes: set[str] = field(default_factory=set)
    companies: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return hashlib.sha1(self.url.encode()).hexdigest()[:16]

    def as_source(self) -> dict[str, Any]:
        return {"url": self.url, "title": self.title, "publisher": self.publisher, "published_at": self.published_at.isoformat(), "source_type": self.source_type}


# ---------------------------------------------------------------------- 어휘
LEGACY_IDS = {
    "tech:hawk": "product:camt_hawk", "tech:onto_g3": "product:onto_dragonfly_g3", "tech:poet_interposer": "tech:optical_interposer",
    "tech:lessengers_dow": "tech:dow", "tech:lite_eml": "product:lite_eml_200g", "tech:cohr_1p6t": "product:cohr_1p6t_transceiver",
    "tech:aehr_fox": "product:aehr_fox_xp", "tech:vertiv_800v": "product:vrt_800vdc_portfolio",
}
GENERIC = {"dielectric", "fec", "serdes", "laser source", "power converter", "tsv", "cpo", "tcb", "gate driver", "coherent optical",
           "semiconductor inspection", "wafer cleaning", "copper bonding", "particle contamination", "optical receiver", "photodiode"}
GENERIC_WORDS = {"semiconductor", "power", "data center", "cable", "high-voltage", "transceiver", "wafer", "coolant", "sidecar", "busbar",
                 "underfill", "vcsel", "eml", "800g", "1.6t", "hbm4", "silicon carbide", "wafer-level", "burn-in", "lumentum",
                 "lessengers", "optical transceiver", "ofc 2026", "vertiv nvidia", "coherent 1.6t"}  # 너무 넓거나 다른 노드와 겹치는 단어
PHRASE_OVERRIDES = {  # 세대 노드로 직접
    "hbm4": "gen:hbm4", "hbm4e": "gen:hbm4e", "hbm5": "gen:hbm5", "hbm3e": "gen:hbm3e", "1.6t": "gen:1p6t", "800g": "gen:800g",
    "silicon carbide": "tech:sic", "vcsel": "component:vcsel", "underfill": "material:underfill",
}
COMPANY_NAMES = {  # 기사에 실제로 쓰이는 이름 (법인명 접미사 없이)
    "company:camt": ["Camtek"], "company:poet": ["POET Technologies"], "company:aehr": ["Aehr Test", "Aehr"], "company:onto": ["Onto Innovation"],
    "company:lite": ["Lumentum"], "company:cohr": ["Coherent Corp", "Coherent"], "company:vrt": ["Vertiv"], "company:skhynix": ["SK hynix", "SK Hynix"],
    "company:samsung": ["Samsung Electronics", "Samsung"], "company:mu": ["Micron"], "company:nvda": ["NVIDIA", "Nvidia"], "company:besi": ["BE Semiconductor", "Besi"],
    "company:amat": ["Applied Materials"], "company:klac": ["KLA Corp", "KLA"], "company:crdo": ["Credo Technology", "Credo"], "company:fn": ["Fabrinet"],
    "company:nvts": ["Navitas"], "company:on": ["onsemi", "ON Semiconductor"], "company:mpwr": ["Monolithic Power"], "company:txn": ["Texas Instruments"],
    "company:etn": ["Eaton"], "company:adea": ["Adeia", "Invensas", "Tessera Technologies", "Ziptronix"], "company:klic": ["Kulicke & Soffa", "Kulicke and Soffa", "K&S"], "company:form": ["FormFactor"],
    "company:cohu": ["Cohu"], "company:nvmi": ["Nova Ltd", "Nova Measuring"], "company:veco": ["Veeco"], "company:ichr": ["Ichor"],
    "company:lwlg": ["Lightwave Logic"], "company:almu": ["Aeluma"], "company:axti": ["AXT Inc", "AXT"], "company:mxl": ["MaxLinear"],
    "company:aaoi": ["Applied Optoelectronics"], "company:belfa": ["Bel Fuse"], "company:aosl": ["Alpha and Omega Semiconductor", "Alpha & Omega Semiconductor"],
    "company:ipwr": ["Ideal Power"], "company:asys": ["Amtech Systems"], "company:wolf": ["Wolfspeed"], "company:cvv": ["CVD Equipment"],
    "company:intt": ["inTEST"], "company:lessengers": ["Lessengers"],
    # 그래프 밖 대만 공급사 (core.entities, source=indicator) — TSMC·ASE 는 너무 자주 나와 태깅하지 않는다
    "company:unimicron": ["Unimicron"], "company:kyec": ["King Yuan Electronics", "KYEC"], "company:winway": ["WinWay"],
    "company:mpi": ["MPI Corp", "MPI Corporation"], "company:chunghwa_precision_test": ["Chunghwa Precision Test", "CHPT"],
    "company:accton": ["Accton"], "company:landmark_optoelectronics": ["LandMark Optoelectronics", "LandMark Opto"],
    "company:luxnet": ["Luxnet", "LuxNet"], "company:foci": ["FOCI Fiber Optic", "FOCI"], "company:browave": ["Browave"],
    "company:delta_electronics": ["Delta Electronics"], "company:lite_on": ["Lite-On", "LITEON", "Liteon"], "company:bizlink": ["BizLink"],
    "company:asia_vital_components": ["Asia Vital Components", "AVC"], "company:auras": ["Auras Technology", "Auras"],
}


def extra_company_nodes() -> list[dict[str, Any]]:
    """그래프 밖 기업(core.entities 에 source=indicator 로 등록)을 그래프 기업 노드와 같은 모양으로. 노드 목록(nodes)에는 쓰지 않는다.
    그래프로 승격된 기업(같은 id)은 그래프 노드가 원본이므로 빠진다."""
    from wsj.ecosystems.indicators import TW_ENTITIES

    in_graph = {n["id"] for n in load_graph()["nodes"]}
    return [{"id": eid, "kind": "company", "label": f"{e['name']} ({e['exchange']} {e['local_code']}, 비SEC)", "ecosystem": (e.get("ecosystems") or [None])[0],
             "listing": {"ticker": e["local_code"], "exchange": e["exchange"], "cik": None, "filer_type": "non_sec_listed"},
             "size_band": e.get("size_band"), "in_universe": False, "_extra": True} for eid, e in TW_ENTITIES.items() if eid not in in_graph]


_CORP_SUFFIX = re.compile(r",?\s+(Inc\.?|Corp\.?|Corporation|Co\.,?\s*Ltd\.?|Co\.?|Ltd\.?|Limited|Holdings?|Group|plc|AG|SE|N\.V\.|S\.A\.|S\.p\.A\.|GmbH|K\.K\.)$", re.I)


def graph_company_names(nodes: list[dict[str, Any]]) -> dict[str, list[str]]:
    """그래프 기업 중 COMPANY_NAMES 에 없는 곳의 기사용 이름 (라벨에서 티커·법인 접미사 제거). 태깅 전용 — 뉴스 질의는 COMPANY_NAMES 만."""
    from wsj.ecosystems.ontology import clean_name

    out: dict[str, list[str]] = {}
    for n in nodes:
        if n.get("kind") != "company" or n["id"] in COMPANY_NAMES:
            continue
        name = clean_name(n["label"])
        for _ in range(2):
            name = _CORP_SUFFIX.sub("", name).strip()
        if len(name) >= 5 or (name.isupper() and len(name) >= 3):
            out[n["id"]] = [name]
    return out


def build_lexicon(graph: dict[str, Any]) -> tuple[list[tuple[re.Pattern, str]], list[tuple[re.Pattern, str]]]:
    ids = {n["id"] for n in graph["nodes"]}
    company_ids = ids | {n["id"] for n in extra_company_nodes()}
    phrases: dict[str, str] = {k: v for k, v in PHRASE_OVERRIDES.items() if v in ids}
    # 발굴 구문(사람이 큐레이션)이 백필 별칭보다 우선 — 'hybrid bonding' 이 병목 노드로 가는 별칭 충돌 방지
    for nid, qs in DISCOVERY_QUERIES.items():
        for q in qs:
            quoted = re.findall(r'"([^"]+)"', q)
            # 질의의 첫 구문만 주제어다. 뒤의 구문("semiconductor", "power", "cable")은 EDGAR 검색을 좁히는 보조어라 태깅에 쓰면 오탐
            w = quoted[0].strip().lower() if quoted else ""
            if nid in ids and len(w) >= 4 and w not in GENERIC and w not in GENERIC_WORDS:
                phrases.setdefault(w, nid)
    try:
        aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))["aliases"]
    except (OSError, KeyError, ValueError):
        aliases = {}
    for nid, words in aliases.items():
        nid = LEGACY_IDS.get(nid, nid)
        if nid not in ids or nid.startswith(("company:", "eco:")):
            continue
        for w in words:
            w = w.strip().lower()
            if len(w) >= 4 and w not in GENERIC:
                phrases.setdefault(w, nid)
    node_pats = [(re.compile(r"(?<![a-z0-9])" + re.escape(p).replace(r"\ ", r"[\s-]") + r"(?![a-z])", re.I), nid) for p, nid in sorted(phrases.items(), key=lambda kv: -len(kv[0]))]
    comp_pats: list[tuple[re.Pattern, str]] = []
    for cid, names in {**graph_company_names(graph["nodes"]), **COMPANY_NAMES}.items():
        if cid not in company_ids:
            continue
        for nm in names:
            flags = 0 if nm.isupper() or len(nm) <= 4 else re.I  # 'KLA', 'AXT', 'K&S' 는 대소문자 구분
            comp_pats.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(nm) + r"(?![A-Za-z0-9])", flags), cid))
    return node_pats, comp_pats


def tag(items: list[Item], node_pats, comp_pats) -> None:
    for it in items:
        text = f"{it.title} {it.snippet}"
        for pat, nid in node_pats:
            if pat.search(text):
                it.nodes.add(nid)
        for pat, cid in comp_pats:
            if pat.search(text):
                it.companies.add(cid)


# ---------------------------------------------------------------------- 수집
def _strip(s: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace("\xa0", " ").strip()


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except ValueError:
        return None


def collect_news(http: HttpClient, days: int, company_queries: list[tuple[str, str]]) -> list[Item]:
    out: list[Item] = []
    queries = [(q, eco) for eco, qs in NEWS_TOPICS.items() for q in qs] + company_queries
    for q, eco in queries:
        url = GOOGLE_NEWS.format(q=quote_plus(f"{q} when:{days}d"))
        try:
            xml = http.get_text(url, headers=BROWSER_UA)
            root = ET.fromstring(xml)
        except Exception as exc:  # noqa: BLE001
            log.warning("news %r failed: %s", q, exc)
            continue
        for it in root.findall(".//item")[:25]:
            title = _strip(it.findtext("title"))
            publisher = _strip(it.findtext("source")) or "news"
            if title.endswith(" - " + publisher):
                title = title[: -len(publisher) - 3]
            d = _dt(it.findtext("pubDate"))
            link = it.findtext("link") or ""
            if not title or not d or not link:
                continue
            st = "press_release" if any(w in publisher.lower() for w in PRESS_WIRES) else "news"
            out.append(Item(link, title, d, publisher, st, "", q, eco if eco != "company" else None))
    log.info("news items: %d (%d queries)", len(out), len(queries))
    return out


def collect_trade(http: HttpClient, since: datetime) -> list[Item]:
    out: list[Item] = []
    for feed in TRADE_RSS:
        try:
            root = ET.fromstring(http.get_text(feed, headers=BROWSER_UA))
        except Exception as exc:  # noqa: BLE001
            log.warning("trade rss failed %s: %s", feed, exc)
            continue
        for it in root.findall(".//item"):
            d = _dt(it.findtext("pubDate"))
            if not d or d < since:
                continue
            out.append(Item(it.findtext("link") or "", _strip(it.findtext("title")), d, "Semiconductor Today", "trade", _strip(it.findtext("description"))[:400]))
    log.info("trade items: %d", len(out))
    return out


def collect_sec(http: HttpClient, start: date, end: date) -> list[Item]:
    out: list[Item] = []
    for nid, qs in DISCOVERY_QUERIES.items():
        for q in qs[:SEC_PHRASES_PER_NODE]:
            params = {"q": q, "forms": "8-K,6-K", "dateRange": "custom", "startdt": start.isoformat(), "enddt": end.isoformat()}
            try:
                data = http.get_json(EFTS, params=params)
            except Exception as exc:  # noqa: BLE001
                log.warning("efts %r failed: %s", q, exc)
                continue
            for h in data.get("hits", {}).get("hits", [])[:20]:
                s = h["_source"]
                adsh, fname = h["_id"].split(":", 1)
                cik = int(s["ciks"][0])
                name = (s.get("display_names") or ["?"])[0].split("  (")[0]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}"
                d = _dt(s.get("file_date"))
                if not d:
                    continue
                items = ",".join(s.get("items") or [])
                title = f"{name} {s.get('form')}{' items ' + items if items else ''} — mentions {q.strip(chr(34))}"
                it = Item(url, title, d, f"SEC EDGAR ({name})", "sec", "", q)
                it.nodes.add(nid)
                out.append(it)
    out = enrich_sec(http, out)
    log.info("sec items: %d", len(out))
    return out


_SEC_PREFIX = re.compile(r"^(?:\d+\s+\S+\.html?|EX-99\.\d+|Exhibit 99\.\d+|Document|PRESS RELEASE|News Release|EdgarFiling|FOR IMMEDIATE RELEASE|\d+)\s*", re.I)
_DATELINE = re.compile(r"\s(?:[A-Z][A-Za-z.]+(?: [A-Z][A-Za-z.]+)*,\s*(?:[A-Z][A-Za-z.]+\s*)?[–—-]?\s*)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? 20\d\d|\s•\s")


def sec_headline(text: str, phrase: str, company: str = "") -> tuple[str | None, bool]:
    """공시 본문 → (첫 헤드라인, 구문이 'About 회사' 상용구 안에만 있는가)."""
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
    for _ in range(12):
        t2 = _SEC_PREFIX.sub("", t, count=1)
        if t2 == t:
            break
        t = t2
    m = _DATELINE.search(t[:400])
    head = (t[: m.start()] if m else t[:140]).strip(" -–—:")
    if len(head) > 140:
        head = head[:140].rsplit(" ", 1)[0] + "…"
    low, p = t.lower(), phrase.strip('"').lower()
    hits = [x.start() for x in re.finditer(re.escape(p), low)] if p else []
    first = (company.split() or [""])[0].lower().strip(",.")
    about = low.find(f"about {first}") if first else -1
    boiler = bool(hits) and about >= 0 and min(hits) > about
    return head or None, boiler


def enrich_sec(http: HttpClient, items: list[Item], limit: int = 60) -> list[Item]:
    """8-K/6-K 원문을 열어 제목을 실제 헤드라인으로 바꾸고, 구문이 회사 소개 상용구에만 있으면 버린다."""
    out, seen = [], {}
    for it in items:
        name = it.publisher.removeprefix("SEC EDGAR (").rstrip(")")
        if it.url not in seen and len(seen) < limit:
            try:
                seen[it.url] = sec_headline(http.get_text(it.url), it.query or "", name)
            except Exception as exc:  # noqa: BLE001 - 원문 실패는 메타데이터 제목으로
                log.warning("sec doc %s failed: %s", it.url, exc)
                seen[it.url] = (None, False)
        head, boiler = seen.get(it.url, (None, False))
        if boiler:
            continue
        if head:
            it.snippet = it.title  # 메타데이터(서식·항목·구문)는 스니펫으로
            it.title = f"{name}: {head}"
        out.append(it)
    return out


def collect_fedreg(http: HttpClient, since: date) -> list[Item]:
    since = min(since, date.today() - timedelta(days=30))  # 관보는 빈도가 낮아 창을 넓힌다
    out: list[Item] = []
    for agency, title_re in FEDREG_AGENCIES:
        params = [("per_page", "100"), ("order", "newest"), ("conditions[agencies][]", agency), ("conditions[publication_date][gte]", since.isoformat())]
        params += [("fields[]", f) for f in ("title", "publication_date", "html_url", "agencies", "type", "abstract")]
        try:
            data = http.get_json(FEDREG, params=params)
        except Exception as exc:  # noqa: BLE001
            log.warning("fedreg %s failed: %s", agency, exc)
            continue
        for r in data.get("results") or []:
            if title_re and not re.search(title_re, r["title"], re.I):
                continue
            agencies = ", ".join(a.get("name", "") for a in r.get("agencies") or [] if a.get("name"))
            d = _dt(r.get("publication_date"))
            if not d:
                continue
            out.append(Item(r["html_url"], r["title"], d, f"Federal Register · {agencies}"[:120], "regulator", (r.get("abstract") or "")[:500], agency, "cross"))
    log.info("federal register items: %d", len(out))
    return out


def collect_signals(store, since: date, cik_to_node: dict[int, str]) -> list[Item]:
    if store is None or not cik_to_node:
        return []
    try:
        rows = store.select("core.signals", None, {"cik": list(cik_to_node), "signal_date": ("gte", since.isoformat())})
    except Exception as exc:  # noqa: BLE001
        log.warning("signals read failed: %s", exc)
        return []
    out = []
    for r in rows:
        if r.get("family") not in ("insider", "contract", "dilution", "activist", "gov"):
            continue
        d = _dt(str(r["signal_date"]))
        if not d or not r.get("url"):
            continue
        it = Item(r["url"], r["summary"], d, "WSJ signals", "signal", f"{r['family']}/{r['kind']}")
        it.companies.add(cik_to_node[int(r["cik"])])
        out.append(it)
    log.info("db signal items: %d", len(out))
    return out


# ---------------------------------------------------------------------- 정리·클러스터·점수
def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.+-]*", title.lower()) if w not in STOP and len(w) > 1}


def dedupe(items: list[Item]) -> list[Item]:
    by_url: dict[str, Item] = {}
    for it in items:
        prev = by_url.get(it.url)
        if prev:
            prev.nodes |= it.nodes
            prev.companies |= it.companies
            prev.ecosystem_hint = prev.ecosystem_hint or it.ecosystem_hint
        else:
            by_url[it.url] = it
    # 같은 출판사·거의 같은 제목 (Google News 가 같은 기사를 다른 URL 로 주는 경우)
    seen: dict[tuple[str, str], Item] = {}
    for it in by_url.values():
        k = (it.publisher.lower(), " ".join(sorted(_tokens(it.title)))[:120])
        if k in seen:
            seen[k].nodes |= it.nodes
            seen[k].companies |= it.companies
        else:
            seen[k] = it
    return list(seen.values())


def cluster(items: list[Item], threshold: float = 0.5, window_days: int = 5) -> list[list[Item]]:
    items = sorted(items, key=lambda i: i.published_at, reverse=True)
    clusters: list[tuple[set[str], list[Item]]] = []
    for it in items:
        tk = _tokens(it.title)
        if len(tk) < 3:
            clusters.append((set(tk), [it]))
            continue
        best, best_sim = None, 0.0
        for idx, (ctk, members) in enumerate(clusters):
            if abs((members[0].published_at - it.published_at).days) > window_days:
                continue
            ccos = set().union(*(m.companies for m in members))
            if it.companies and ccos and not (it.companies & ccos):
                continue
            inter = len(tk & ctk)
            if inter < 3:
                continue
            sim = inter / max(1, min(len(tk), len(ctk)))
            if sim > best_sim:
                best, best_sim = idx, sim
        if best is not None and best_sim >= threshold:
            clusters[best][1].append(it)
        else:
            clusters.append((set(tk), [it]))
    return [m for _, m in clusters]


def score(members: list[Item], graph_nodes: dict[str, dict], now: datetime) -> dict[str, Any]:
    nodes = set().union(*(m.nodes for m in members))
    companies = set().union(*(m.companies for m in members))
    publishers = {m.publisher for m in members}
    latest = max(m.published_at for m in members)
    age = (now - latest).days
    recency = 1.0 if age <= 3 else 0.7 if age <= 7 else 0.4
    w = max(SOURCE_WEIGHT.get(m.source_type, 1.0) for m in members)
    small = [c for c in companies if graph_nodes.get(c, {}).get("size_band") in ("micro", "small")]
    primary = any(m.source_type in ("sec", "regulator", "press_release", "newsroom", "policy", "data") for m in members)
    # 기술 노드에 닿아야 공급망 이슈다. 노드 없는 기업 기사는 1차 출처일 때만 소형사 가산
    graph_rel = min(3, len(nodes)) * 0.9 + (1.2 if small and (nodes or primary) else 0) + 0.3 * min(2, len(companies) - len(small))
    raw = w + math.log2(1 + len(publishers)) * 1.3 + graph_rel  # 대략 1.5 ~ 10
    importance = max(1, min(10, round(raw * recency * 0.85)))
    return {"nodes": sorted(nodes), "companies": sorted(companies), "publishers": sorted(publishers), "latest": latest,
            "rule_importance": importance, "raw": round(raw, 2), "recency": recency}


def ecosystem_of(nodes: list[str], companies: list[str], hint: str | None, graph_nodes: dict[str, dict]) -> str:
    votes: dict[str, int] = defaultdict(int)
    for x in nodes + companies:
        eco = graph_nodes.get(x, {}).get("ecosystem")
        if eco:
            votes[eco] += 1
    if votes:
        top = sorted(votes.items(), key=lambda kv: -kv[1])
        return top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "cross"
    return hint or "cross"


def issue_key(members: list[Item]) -> str:
    urls = sorted(m.url for m in members)[:3]
    return hashlib.sha1("|".join(urls).encode()).hexdigest()[:20]


# ---------------------------------------------------------------------- LLM 선별
LLM_SYSTEM = """\
당신은 AI 인프라 공급망(HBM·첨단 패키징 / 800G·1.6T 광통신 / 800VDC 전력·냉각) 담당 리서치 데스크다.
입력은 최근 기사·공시·관보를 묶은 후보 클러스터와, 우리 온톨로지의 노드·기업 목록, 노드별 영향 기업 힌트다.
할 일: 투자자가 알아야 할 '공급망 이슈' 를 최대 {max_issues}개 고른다. 같은 사건은 하나로 합친다.

선별 기준 (높을수록 중요):
- 공급 능력·수율·병목의 변화 (증설, 부족, 중단, 수율 개선), 표준·규제 변화, 대형 고객의 채택·연기, 수주·계약, 가격 변화
- 소형 공급사(size_band micro/small)에 닿는 사건은 가산
- 같은 사건을 여러 독립 출판사·1차 출처(SEC·관보·회사 보도자료)가 다룰수록 가산
- 마케팅성 기사, 일반 시장 전망, 주가 기사, 공급망과 무관한 기사는 제외

출처 유형(type)별 처리:
- data (지표 변화: 메모리 현물가·PPI·원자재·대만 공급사 월매출): 제목의 수치를 그대로 쓴다. 같은 방향의 기사가 있으면 묶고, 없으면 단독 이슈로 써도 된다 (event_type pricing 또는 earnings).
- analyst (TrendForce 등): 가격·출하·캐파 전망은 '전망'임을 명시한다.
- research (논문): 병목을 직접 푸는 결과(산업체 저자, 기록 성능, 양산 공정)만 골라 최대 3개, event_type research. 학술 일반론은 제외.
- policy·regulator: 세 공급망에 닿는 조항이 있을 때만. 관세·수출통제·전력망 규정은 대상 품목을 적는다.

규칙:
- nodes 는 입력의 node_catalog id 만, companies 는 입력의 company_catalog id 만 쓴다. 근거 없는 연결은 쓰지 않는다.
- direction: + (수혜), - (피해), ± (혼재). 근거가 기사에 있을 때만 +/-, 아니면 ±.
- 사실만 쓴다. 주가 전망·시나리오는 쓰지 않는다. 숫자는 출처에 있는 것만.
- importance 는 1~10 정수, importance_rationale 에 근거(출처 수·1차 출처 여부·병목 크기·대상 기업 규모)를 한 문장으로.
- 한국어. 회사명·제품명·기술 용어는 원문.
- unmapped (잔차, ADR-0026): 이슈의 핵심인데 node_catalog·company_catalog 에 **없는** 기술·부품·소재·표준·메커니즘·기업 용어를 이슈당 최대 4개 적는다 \
(예: 새 메모리 계층 이름, 새 커넥터 규격, 새 공정명). 일반 명사·마케팅 표현은 쓰지 않는다. 없으면 빈 배열. 이것은 온톨로지가 놓친 새 것을 찾는 신호다.

출력: ```json 블록 하나.
{{"issues": [{{"cluster_ids": [0], "title": "40자 이내", "summary": "2~3문장 사실 요약", "why_it_matters": "어느 병목·노드·기업에 어떻게 닿는지 1~2문장",
  "event_type": "{event_types}", "ecosystem": "hbm|optics|power|cross", "importance": 7, "importance_rationale": "...",
  "nodes": ["..."], "companies": [{{"id": "company:...", "direction": "+|-|±", "basis": "근거 한 줄"}}],
  "unmapped": [{{"term": "원문 용어", "kind_guess": "technology|component|material|standard|mechanism|company|other", "context": "이 이슈에서의 뜻 한 줄"}}]}}]}}
"""
UNMAPPED_KINDS = ("technology", "component", "material", "standard", "mechanism", "company", "other")


def term_key(term: str) -> str:
    """잔차 용어의 키 — 소문자, 영숫자·한글 밖은 _ (DB 함수 put_unmapped_terms 와 같은 규칙)."""
    return re.sub(r"[^a-zA-Z0-9가-힣]+", "_", term).strip("_").lower()


def collect_unmapped(rows: list[dict[str, Any]], node_pats, comp_pats) -> list[dict[str, Any]]:
    """선별 모델이 이슈마다 적은 잔차(unmapped)를 모아 용어별로 합친다. 어휘 사전(노드·기업 별칭)에 이미 걸리는 용어는 잔차가 아니다.
    행에서는 `_unmapped` 를 떼어 낸다 (테이블 열이 아니다)."""
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        items = row.pop("_unmapped", None) or []
        for u in items:
            term = (u.get("term") or "").strip() if isinstance(u, dict) else ""
            if not 2 <= len(term) <= 80:
                continue
            if any(p.search(term) for p, _ in node_pats) or any(p.search(term) for p, _ in comp_pats):
                continue  # 온톨로지에 이미 있는 것 (별칭·현지어 포함)
            k = term_key(term)
            if len(k) < 2:
                continue
            cur = merged.setdefault(k, {"term_key": k, "term": term, "kind_guess": None, "ecosystem": row.get("ecosystem"), "context": None, "issue_keys": []})
            kind = u.get("kind_guess")
            cur["kind_guess"] = cur["kind_guess"] or (kind if kind in UNMAPPED_KINDS else None)
            cur["context"] = cur["context"] or ((u.get("context") or "")[:300] or None)
            if row["issue_key"] not in cur["issue_keys"]:
                cur["issue_keys"].append(row["issue_key"])
    return sorted(merged.values(), key=lambda r: (-len(r["issue_keys"]), r["term_key"]))


def save_unmapped(store, terms: list[dict[str, Any]], now: datetime) -> int:
    """ideas.unmapped_terms 에 누적 — 같은 term_key 는 n_seen +1, issue_keys 합집합, first_seen 유지 (DB 함수 put_unmapped_terms 와 같은 뜻; 스토어는 RPC 가 없어 읽고 합친다)."""
    if not terms:
        return 0
    today = now.date().isoformat()
    existing = {r["term_key"]: r for r in store.select("ideas.unmapped_terms", ["term_key", "issue_keys", "first_seen", "n_seen", "status", "kind_guess", "context"],
                                                         {"term_key": [t["term_key"] for t in terms]})}
    out = []
    for t in terms:
        e = existing.get(t["term_key"])
        if e:
            keys = list(dict.fromkeys([*(e.get("issue_keys") or []), *t["issue_keys"]]))
            out.append({**t, "issue_keys": keys, "kind_guess": e.get("kind_guess") or t["kind_guess"], "context": e.get("context") or t["context"],
                        "first_seen": e["first_seen"], "last_seen": today, "n_seen": int(e.get("n_seen") or 1) + 1, "status": e.get("status") or "open",
                        "updated_at": now.isoformat()})
        else:
            out.append({**t, "first_seen": today, "last_seen": today, "n_seen": 1, "status": "open", "updated_at": now.isoformat()})
    return store.upsert("ideas.unmapped_terms", out, ["term_key"])


def llm_curate(cands: list[dict[str, Any]], graph: dict[str, Any], impact: dict[str, Any], model: str, max_issues: int, api_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from wsj.briefs.llm import LLM, resolve_model, sum_usage

    nodes = {n["id"]: n for n in graph["nodes"]}
    used_nodes = sorted({n for c in cands for n in c["nodes"]})
    node_catalog = [{"id": n, "label": nodes[n]["label"], "kind": nodes[n]["kind"], "ecosystem": nodes[n].get("ecosystem")} for n in used_nodes if n in nodes]
    # 기업 목록은 후보에 태깅된 기업 + 후보 노드에 직접 연결된 기업만 (그래프가 커져도 프롬프트가 커지지 않게)
    used_set = set(used_nodes)
    relevant = {co for c in cands for co in c["companies"]}
    for e in graph["edges"]:
        if e["from"] in used_set and nodes.get(e["to"], {}).get("kind") == "company":
            relevant.add(e["to"])
        if e["to"] in used_set and nodes.get(e["from"], {}).get("kind") == "company":
            relevant.add(e["from"])
    company_catalog = [
        {"id": n["id"], "label": n["label"], "size_band": n.get("size_band"), "ecosystem": n.get("ecosystem")}
        for n in [*graph["nodes"], *extra_company_nodes()] if n["kind"] == "company" and n["id"] in relevant
    ]
    hints = {
        n: [f"{c['company']} {c['direction']} {c['confidence']}" for c in impact.get("nodes", {}).get(n, {}).get("companies", [])[:5]]
        for n in used_nodes
    }
    payload = {
        "clusters": [
            {"cluster_id": i, "latest": c["latest"].date().isoformat(), "publishers": c["publishers"][:6], "rule_importance": c["rule_importance"],
             "nodes": c["nodes"], "companies": c["companies"],
             "items": [{"title": m.title, "publisher": m.publisher, "type": m.source_type, "date": m.published_at.date().isoformat(), "snippet": m.snippet[:300]} for m in c["members"][:5]]}
            for i, c in enumerate(cands)
        ],
        "node_catalog": node_catalog, "company_catalog": company_catalog, "impact_hints": hints,
    }
    system = LLM_SYSTEM.format(max_issues=max_issues, event_types="|".join(EVENT_TYPES))
    llm = LLM(api_key)
    out, comps = llm.complete_json(system, json.dumps(payload, ensure_ascii=False), resolve_model(model),
                                   "직전 응답을 유효한 JSON 하나로 다시 출력하라. 오류: {error}", max_tokens=9000, effort="medium")
    return out.get("issues") or [], sum_usage(comps)


# ---------------------------------------------------------------------- 실행
def collect_extra(http: HttpClient, store, now: datetime, since: datetime, indicator_points: list[Any]) -> list[Item]:
    """출처 레지스트리(sources.py)와 지표(indicators.py). 지표 점은 indicator_points 로 돌려줘 main 이 저장한다."""
    from wsj.ecosystems import indicators, sources

    out: list[Item] = []
    out += sources.collect_feeds(http, since)
    out += sources.collect_trendforce(http, now - timedelta(days=30))
    rq = sources.research_queries(DISCOVERY_QUERIES)
    out += sources.collect_arxiv(http, rq, now - timedelta(days=RESEARCH_DAYS))
    out += sources.collect_openalex(http, rq, now - timedelta(days=RESEARCH_DAYS))
    try:
        ind = indicators.run(http, store, now.date())
    except Exception as exc:  # noqa: BLE001 - 지표 실패가 이슈 피드를 막지 않게
        log.warning("indicators failed: %s", exc)
        return out
    indicator_points.extend(ind["points"])
    for n in ind["notable"]:
        # 월간 지표는 기준월 1일이 아니라 발표 시점이 사건 날짜다. 실행 시각(now)을 쓰면 같은 9월 매출이 매일 '오늘 소식'이 되므로
        # 대략의 발표일(기준월 1일 + 40일: 대만 월매출 마감 10일, 미국 PPI 중순)로 둔다
        base = datetime.combine(n["as_of"], datetime.min.time(), UTC)
        when = min(now, base + timedelta(days=40)) if n.get("monthly") else base + timedelta(hours=12)
        it = Item(n["url"], n["title"], when, n["publisher"], "data",
                  n["snippet"], n["indicator_id"], n["ecosystem"])
        it.nodes.update(n["nodes"])
        it.companies.update(n["companies"])
        out.append(it)
    return out


ADMIN_NOISE = re.compile(r"^(agency information collection|sunshine act|privacy act of 1974|notice of (public )?meeting)|information collection activities", re.I)


RESEARCH_VENUE = re.compile(
    r"arXiv|IEEE|Optica|Optics|Photonic|Lightwave|Electron Dev|Electronic Comp|Packaging|Semiconductor|Microelectronic|Solid[- ]State|"
    r"Power Electronics|Applied Physics|Nature Electronics|Nature Communications|Nature Photonics|ECTC|OFC|VLSI|IEDM|ISSCC|"
    r"Thermal Management|Electronics Packaging|Materials Science in Semiconductor|Journal of Electronic", re.I)


def phrase_in(it: Item) -> bool:
    """arXiv 는 구문 검색이 정확해 제목·초록, OpenAlex 는 검색이 느슨해 제목에 구문이 있어야 한다."""
    if not it.query:
        return False
    text = f"{it.title} {it.snippet}" if it.publisher == "arXiv" else it.title
    return it.query.lower() in text.lower() and bool(RESEARCH_VENUE.search(it.publisher))  # 반도체·광·전력전자 학회·저널만


def _research_rank(c: dict[str, Any]) -> tuple:
    m = c["members"][0]
    return (0 if "[산업체:" in m.snippet else 1, -m.published_at.timestamp())


def select_candidates(cands: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """규칙 점수 상위 + 유형별 최소치. 논문만으로 된 클러스터는 최소치로만 들어온다 (산업체 저자 우선)."""
    only_research = [c for c in cands if all(m.source_type == "research" for m in c["members"])]
    research_ids = {id(c) for c in only_research}
    ranked = sorted((c for c in cands if id(c) not in research_ids), key=lambda c: (-c["rule_importance"], -c["raw"]))
    ranked += sorted(only_research, key=_research_rank)
    chosen = ranked[: max(0, limit - sum(QUOTA.values()) // 2)]
    have = {id(c) for c in chosen}
    for st, k in QUOTA.items():
        pool = [c for c in ranked if id(c) not in have and any(m.source_type == st for m in c["members"])]
        for c in pool[:k]:
            chosen.append(c)
            have.add(id(c))
    for c in ranked:
        if len(chosen) >= limit + sum(QUOTA.values()) // 2:
            break
        if id(c) not in have and id(c) not in research_ids:
            chosen.append(c)
            have.add(id(c))
    return sorted(chosen, key=lambda c: (-c["rule_importance"], -c["raw"]))


def run(http: HttpClient, store, days: int = 14, use_llm: bool = True, model: str = "sonnet", api_key: str | None = None,
        max_candidates: int = 70, max_issues: int = 15, now: datetime | None = None,
        picks: dict[str, Any] | None = None, dump_candidates: bool = False, cache: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    since = now - timedelta(days=days)
    graph = load_graph()
    gnodes = {n["id"]: n for n in graph["nodes"]} | {n["id"]: n for n in extra_company_nodes()}
    node_pats, comp_pats = build_lexicon(graph)
    company_queries = [(f'"{COMPANY_NAMES[n["id"]][0]}"', "company") for n in graph["nodes"]
                       if n["kind"] == "company" and n.get("size_band") in ("micro", "small", "unknown", "mid") and n["id"] in COMPANY_NAMES]
    cik_to_node = {int(n["listing"]["cik"]): n["id"] for n in graph["nodes"] if n["kind"] == "company" and (n.get("listing") or {}).get("cik")}

    items: list[Item] = []
    indicator_points: list[Any] = []
    if cache and cache.exists():
        import pickle

        items = pickle.loads(cache.read_bytes())  # noqa: S301 - 이 프로그램이 만든 로컬 캐시만 읽는다
        now = max((i.published_at for i in items), default=now)
        since = now - timedelta(days=days)
    else:
        items += collect_news(http, days, company_queries)
        items += collect_trade(http, since)
        items += collect_sec(http, since.date(), now.date())
        items += collect_fedreg(http, since.date())
        items += collect_signals(store, since.date(), cik_to_node)
        items += collect_extra(http, store, now, since, indicator_points)
        if cache:
            import pickle

            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(pickle.dumps(items))
    long_window = {"regulator": 30, "research": RESEARCH_DAYS, "data": 45}  # 관보·논문·월간 지표는 빈도가 낮아 창을 넓힌다
    items = [i for i in items if (i.published_at >= since or i.published_at >= now - timedelta(days=long_window.get(i.source_type, days)))
             and i.published_at <= now + timedelta(days=1)]
    tag(items, node_pats, comp_pats)
    # 관련성: 노드·기업 태그가 있거나, 1차 출처(sec/regulator)는 질의 자체가 주제어
    relevant = [
        i for i in items
        if not NOISE.search(i.title)
        and (i.nodes or i.companies or i.source_type in ALWAYS_RELEVANT)  # 관보·정책·리서치 기관·지표는 출처 단계 필터를 이미 통과
        and not ADMIN_NOISE.search(i.title)
        and (i.source_type != "research" or phrase_in(i))  # 학술 검색은 느슨하다 — 구문이 제목·초록에 실제로 있어야
    ]
    relevant = dedupe(relevant)
    clusters = cluster(relevant)
    cands = []
    for members in clusters:
        sc = score(members, gnodes, now)
        hint = next((m.ecosystem_hint for m in members if m.ecosystem_hint), None)
        cands.append({**sc, "members": sorted(members, key=lambda m: (-SOURCE_WEIGHT.get(m.source_type, 1), m.published_at)),
                      "ecosystem": ecosystem_of(sc["nodes"], sc["companies"], hint, gnodes)})
    cands = select_candidates(cands, max_candidates)
    stats = {"items": len(items), "relevant": len(relevant), "clusters": len(clusters), "candidates": len(cands), "indicator_points": len(indicator_points),
             "by_source": dict(sorted({t: sum(1 for i in relevant if i.source_type == t) for t in SOURCE_WEIGHT}.items()))}
    log.info("issues stats %s", stats)

    impact = json.loads(IMPACT_PATH.read_text(encoding="utf-8")) if IMPACT_PATH.exists() else {}
    rows: list[dict[str, Any]] = []
    usage = None
    method = "rule"
    if picks is not None and cands:
        rows = rows_from_picks(picks.get("issues") or [], cands, gnodes, picks.get("model") or "external")
        method, usage = "llm", {"source": "picks_file", "model": picks.get("model")}
    elif use_llm and api_key and cands:
        try:
            picked, usage = llm_curate(cands, graph, impact, model, max_issues, api_key)
            rows, method = rows_from_picks(picked, cands, gnodes, model), "llm"
        except Exception as exc:  # noqa: BLE001 - LLM 실패 시 규칙 결과로
            log.warning("LLM curation failed, falling back to rules: %s", exc)
            rows, method = [], "rule"
    if not rows:
        for c in cands[:max_issues]:
            comps = [_company(gnodes[cid], "±", "기사 본문에 언급") for cid in c["companies"] if cid in gnodes]
            lead = c["members"][0]
            rows.append(_row(c["members"], lead.title, lead.snippet or None, None, "other", c["ecosystem"], c["rule_importance"],
                             f"규칙 점수: 출처 가중 {SOURCE_WEIGHT.get(lead.source_type, 1)}, 출판사 {len(c['publishers'])}곳, 노드 {len(c['nodes'])}개, 최근성 {c['recency']}",
                             c["nodes"], comps, "rule", None))
    unmapped = collect_unmapped(rows, node_pats, comp_pats)
    stats["unmapped_terms"] = len(unmapped)
    return {"as_of": now.isoformat(), "days": days, "method": method, "stats": stats, "usage": usage, "issues": rows, "indicator_points": indicator_points,
            "unmapped_terms": unmapped, "candidates": [candidate_view(i, c) for i, c in enumerate(cands)] if dump_candidates else None}


def candidate_view(i: int, c: dict[str, Any]) -> dict[str, Any]:
    """LLM 입력과 같은 모양 — 파일로 떨어뜨려 사람(또는 다른 에이전트)이 선별할 수 있게."""
    return {"cluster_id": i, "latest": c["latest"].date().isoformat(), "ecosystem": c["ecosystem"], "rule_importance": c["rule_importance"],
            "publishers": c["publishers"][:6], "nodes": c["nodes"], "companies": c["companies"],
            "items": [{"title": m.title, "publisher": m.publisher, "type": m.source_type, "url": m.url, "snippet": m.snippet[:240]} for m in c["members"][:6]]}


def rows_from_picks(picked: list[dict[str, Any]], cands: list[dict[str, Any]], gnodes: dict[str, dict], model: str) -> list[dict[str, Any]]:
    """LLM(또는 큐레이션 파일)의 선택을 행으로. 카탈로그 밖 노드·기업 id, 범위 밖 클러스터 번호는 버린다."""
    rows = []
    for p in picked:
        ids = [i for i in p.get("cluster_ids") or [] if isinstance(i, int) and 0 <= i < len(cands)]
        if not ids:
            continue
        members = [m for i in ids for m in cands[i]["members"]]
        nodes = [n for n in p.get("nodes") or [] if n in gnodes and not gnodes[n].get("_extra")]
        if not nodes:
            # 태깅 안전망: 선별 모델이 노드를 비워 두면 묶음 기사들의 어휘 태그(별칭·현지어)를 많이 나온 순으로 6개까지 쓴다.
            # 노드가 없는 이슈는 아이디어 후보 경로가 끊긴다 (10/19 광섬유 현물가 급등 이슈가 그랬다).
            freq: dict[str, int] = {}
            for m in members:
                for n in m.nodes:
                    if n in gnodes and not gnodes[n].get("_extra") and not n.startswith("eco:"):
                        freq[n] = freq.get(n, 0) + 1
            nodes = [n for n, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:6]]
        comps = []
        for c in p.get("companies") or []:
            cid = c.get("id") if isinstance(c, dict) else None
            if cid in gnodes and gnodes[cid]["kind"] == "company":
                comps.append(_company(gnodes[cid], c.get("direction") if c.get("direction") in ("+", "-", "±") else "±", c.get("basis")))
        row = _row(members, p.get("title") or members[0].title, p.get("summary"), p.get("why_it_matters"),
                   p.get("event_type") if p.get("event_type") in EVENT_TYPES else "other",
                   p.get("ecosystem") if p.get("ecosystem") in ("hbm", "optics", "power", "cross") else cands[ids[0]]["ecosystem"],
                   int(max(1, min(10, int(p.get("importance") or 1)))), p.get("importance_rationale"), nodes, comps, "llm", model)
        row["_unmapped"] = [u for u in (p.get("unmapped") or []) if isinstance(u, dict)][:4]  # 잔차 (ADR-0026) — collect_unmapped 가 떼어 간다
        rows.append(row)
    return rows


def _company(node: dict[str, Any], direction: str, basis: str | None) -> dict[str, Any]:
    return {"company_id": node["id"], "label": node["label"], "ticker": (node.get("listing") or {}).get("ticker"), "direction": direction,
            "size_band": node.get("size_band"), "in_universe": bool(node.get("in_universe")), "basis": (basis or "")[:200]}


def _row(members: list[Item], title: str, summary, why, event_type, ecosystem, importance, rationale, nodes, companies, method, model) -> dict[str, Any]:
    srcs = sorted(members, key=lambda m: (-SOURCE_WEIGHT.get(m.source_type, 1), -m.published_at.timestamp()))[:8]
    return {
        "issue_key": issue_key(members), "ecosystem": ecosystem, "event_type": event_type, "title": title[:200],
        "summary": summary, "why_it_matters": why, "importance": importance, "importance_rationale": rationale,
        "nodes": nodes, "companies": companies, "sources": [m.as_source() for m in srcs],
        "source_count": len(members), "publisher_count": len({m.publisher for m in members}),
        "latest_published_at": max(m.published_at for m in members).isoformat(), "method": method, "model": model,
    }


def save(store, rows: list[dict[str, Any]], now: datetime) -> int:
    """issue_key 로 upsert. 기존 이슈와 출처 URL 이 겹치면 그 키·first_seen 을 이어 쓴다."""
    recent = store.select("ideas.supply_chain_issues", ["issue_key", "sources", "first_seen", "status", "merged_into"],
                          {"latest_published_at": ("gte", (now - timedelta(days=30)).isoformat())})
    url_to_key = {}
    first_seen = {}
    for r in recent:
        first_seen[r["issue_key"]] = r["first_seen"]
        target = r.get("merged_into") if r.get("status") == "merged" and r.get("merged_into") else r["issue_key"]  # 병합된 이슈는 대표로
        for s in r.get("sources") or []:
            url_to_key[s.get("url")] = target
    out = []
    for row in rows:
        k = next((url_to_key[s["url"]] for s in row["sources"] if s["url"] in url_to_key), row["issue_key"])
        out.append({**row, "issue_key": k, "first_seen": first_seen.get(k, now.isoformat()), "last_seen": now.isoformat(), "status": "active"})
    # 같은 실행 안의 키 충돌 제거 (뒤의 것이 이김 → 중요도 높은 앞의 것을 남기기 위해 역순)
    uniq = {r["issue_key"]: r for r in reversed(out)}
    return store.upsert("ideas.supply_chain_issues", list(uniq.values()), ["issue_key"]) if uniq else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-issues", type=int, default=15)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--store", choices=["postgrest", "sqlite"])
    ap.add_argument("--dump-candidates", action="store_true", help="--out 에 후보 클러스터도 기록 (외부 큐레이션용)")
    ap.add_argument("--picks", type=Path, help="LLM 대신 큐레이션 파일({model, issues:[...]}) 적용. 수집 결과가 같아야 cluster_id 가 맞다 → --cache 와 함께")
    ap.add_argument("--cache", type=Path, help="수집 원자료(pickle) 저장/재사용 — 같은 후보로 picks 를 적용할 때")
    args = ap.parse_args(argv)
    from wsj.config import load_settings
    from wsj.db import make_store

    settings = load_settings()
    if args.store:
        settings.wsj_store = args.store
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = make_store(settings)
    http = HttpClient(user_agent=settings.sec_user_agent)
    from wsj.runlog import logged_run

    try:
        picks = json.loads(args.picks.read_text(encoding="utf-8")) if args.picks else None
        with logged_run(None if args.no_save else store, "issues", {"days": args.days, "model": args.model, "llm": not args.no_llm}) as rl:
            result = run(http, store, args.days, not args.no_llm, args.model, settings.anthropic_api_key or None, max_issues=args.max_issues,
                         picks=picks, dump_candidates=args.dump_candidates, cache=args.cache)
            if not args.no_save:
                n = save(store, result["issues"], datetime.fromisoformat(result["as_of"]))
                log.info("saved %d issues", n)
                rl["rows"] = n
                if result["indicator_points"]:
                    from wsj.ecosystems import indicators

                    m = indicators.save(store, result["indicator_points"])
                    log.info("saved %d indicator points", m)
                    rl["rows"] += m
                if result["unmapped_terms"]:
                    try:
                        u = save_unmapped(store, result["unmapped_terms"], datetime.fromisoformat(result["as_of"]))
                        log.info("saved %d unmapped terms", u)
                    except Exception as exc:  # noqa: BLE001 - 0029 전이거나 스토어가 모르는 테이블이면 잔차는 건너뛴다
                        log.warning("unmapped terms not saved: %s", exc)
            rl["notes"] = json.dumps({"method": result["method"], **result["stats"]}, ensure_ascii=False, default=str)[:3900]
    finally:
        http.close()
        store.close()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        dump = {**result, "indicator_points": [p.row() for p in result["indicator_points"]]}
        args.out.write_text(json.dumps(dump, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"method": result["method"], "stats": result["stats"], "usage": result["usage"], "issues": len(result["issues"])}, ensure_ascii=False))
    for r in result["issues"]:
        print(f"[{r['importance']:>2}] {r['ecosystem']:<6} {r['title'][:90]}  ({r['publisher_count']} pubs, nodes={len(r['nodes'])}, cos={[c['ticker'] for c in r['companies']][:5]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
