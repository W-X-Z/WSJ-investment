"""기업별 최신 소식 — 그래프의 상장 기업마다 최근 며칠의 공시·실적·뉴스를 모아 아이디어 엔진의 신호로 쓴다. ADR-0016 개정 1.

    python -m wsj.ecosystems.company_feed [--days 10] [--no-news] [--only company:a,company:b] [--out events.json]

출처 (모두 무료. 키가 필요한 곳은 키가 있을 때만)
- 미국 SEC EDGAR submissions: 8-K·6-K·10-Q·10-K·20-F·40-F·SC 13D. 8-K item 번호를 한국어로 풀고, 계약·실적·Reg FD
  공시는 EX-99 보도자료의 첫 헤드라인을 제목으로 쓴다.
- 대만 TWSE·TPEx OpenAPI: 일일 중대공시(重大訊息)와 월매출(지표 모듈이 이미 보는 17곳 밖의 그래프 기업, 눈에 띄는 달만).
  개명·액면·주총 일정 같은 행정 공시는 버린다.
- 일본 TDnet 적시공시 목록(適時開示): 그래프의 도쿄 상장 기업. 실적·업적 수정·수주·설비투자는 중요도를 올리고
  자사주·주식보상·지배구조 보고서 같은 정형 공시는 버린다.
- 중국 巨潮资讯(cninfo) 공시: 그래프의 상하이·선전 상장 기업. 실적 예고·중대 계약·경영 현황·IR 기록은 올리고
  법률 의견서·이사회 결의 같은 절차 공시는 버린다.
- 한국 DART OpenAPI (DART_API_KEY 가 있을 때): 그래프의 한국 기업. 공급계약·잠정실적·시설투자·증자는 중요도를 올린다.
- Google News: 기업명 검색 (+ 현지어 이름이 있으면 현지 뉴스). 소형·중형 상장사는 매 실행, 대형·초대형은 기존 아이디어에
  든 기업일 때만 — 대형사는 기사가 너무 많고 공시로 충분하다. 제목에 기업명이 없으면 버린다.

이 모듈은 사실(제목·날짜·URL·공시 종류)만 모은다. 해석은 아이디어 엔진의 LLM 이 근거 id 로 인용하며 한다.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import logging
import math
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from wsj.ecosystems.ontology import RESEARCH_DIR, clean_name, load_graph

log = logging.getLogger("wsj.ecosystems.company_feed")

NATIVE_PATH = RESEARCH_DIR / "native_names.json"
GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TWSE_MATERIAL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_MATERIAL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
TWSE_REV = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_REV = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"
TDNET_LIST = "https://www.release.tdnet.info/inbs/I_list_{page:03d}_{day}.html"
TDNET_DOC = "https://www.release.tdnet.info/inbs/{href}"
CNINFO_SEARCH = "https://www.cninfo.com.cn/new/information/topSearch/query"
CNINFO_QUERY = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_DOC = "https://static.cninfo.com.cn/{path}"
DART_CORPCODE = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_LIST = "https://opendart.fss.or.kr/api/list.json"
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

KR_EX = ("KRX", "KOSDAQ", "KOSPI")
TW_EX = ("TWSE", "TPEX")
CN_EX = ("SSE", "SZSE")

# ---- SEC
SEC_FORMS = {"8-K", "8-K/A", "6-K", "10-Q", "10-K", "20-F", "40-F", "SC 13D", "SC 13D/A"}
ITEM_KO = {
    "1.01": "중요 계약 체결", "1.02": "중요 계약 종료", "2.01": "인수·매각 완료", "2.02": "실적 발표", "2.03": "채무 발생",
    "2.05": "구조조정", "2.06": "자산 손상", "3.01": "상장 유지 요건 통지", "3.02": "주식 발행(사모)", "5.01": "지배권 변동", "5.02": "임원 변동",
    "7.01": "공정공시(Reg FD)", "8.01": "기타 중요 사항",
}
FORM_KO = {"10-Q": "분기 보고서", "10-K": "연차 보고서", "20-F": "연차 보고서", "40-F": "연차 보고서", "6-K": "해외 발행인 수시 공시",
           "SC 13D": "5% 이상 지분 취득(경영 참여 목적)", "SC 13D/A": "5% 이상 지분 변동(경영 참여 목적)"}
SEC_HEADLINE_ITEMS = {"1.01", "2.01", "2.02", "7.01", "8.01"}
SEC_SKIP_ONLY = {"5.07", "9.01", "5.03", "5.08", "3.03"}  # 주총 결과·정관 등만 있는 8-K

_EX_PREFIX = re.compile(r"^(?:EX-99(?:\.\d+)?|Exhibit(?: 99(?:\.\d+)?)?|Exhibit Description|Description|\d+(?:\.\d+)?|\S+\.html?|Document|"
                        r"(?:FOR )?(?:IMMEDIATE )?RELEASE|News Release|Press Release|NEWS|www\.\S+|EdgarFiling|Announcement|[-–—]+|"
                        r"(?:on )?\d{4}/\d{1,2}/\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? 20\d\d)\s*[:\-–—]?\s*", re.I)
_TRAIL_CITY = re.compile(r"(?:\s+[A-Z][A-Z.\-]{2,}(?: [A-Z][A-Z.\-]+)*,?)+\s*…?$")

# ---- Taiwan
TW_SKIP = ("更名", "面額", "股東常會", "股東臨時會", "召開日期", "除權", "除息", "停止過戶", "簽證會計師", "代理發言人", "發言人", "董事會決議日期",
           "取得或處分資產處理程序", "背書保證", "資金貸與", "庫藏股", "買回", "註銷", "獨立董事", "審計委員會", "薪資報酬委員會")
TW_UP = ("營收", "營業收入", "訂單", "合約", "簽訂", "擴產", "擴建", "資本支出", "取得機器設備", "取得使用權資產", "法說會", "財務報告", "獲利",
         "合併", "策略聯盟", "增資", "私募", "新廠")
REV_YOY_UP, REV_YOY_DOWN, REV_MOM = 30.0, -20.0, 25.0

# ---- Japan
JP_SKIP = ("自己株式", "株式報酬", "譲渡制限付株式", "コーポレート・ガバナンス", "独立役員", "定款", "招集", "役員の異動", "人事異動", "株主優待",
           "ストックオプション", "新株予約権の発行", "行使状況", "上場廃止", "ETF", "基準価額", "代表者の異動", "臨時報告書", "剰余金の配当", "主要株主",
           "市場区分", "訂正")
JP_UP3 = ("業績予想の修正", "上方修正", "受注", "契約締結", "資本業務提携", "業務提携", "設備投資", "増産", "生産能力", "新工場", "買収", "株式取得")
JP_UP2 = ("月次", "中期経営計画", "業績予想", "合併", "共同運営", "合弁")  # 決算短信 제목엔 숫자가 없다 → 1

# ---- China
CN_SKIP = ("法律意见书", "决议", "股东大会", "股东会", "独立董事", "章程", "制度", "核查意见", "保荐", "摘要", "英文版", "提示性公告",
           "关联交易", "担保", "募集资金", "会计师事务所", "限售", "质押", "回购", "激励", "资金占用", "内部控制", "可转换公司债券", "中签", "H股公告",
           "说明会", "权益分派", "授信", "风险评估", "风险处置", "债券", "受托管理", "募集说明书", "问询函", "股本变动", "上市公告书", "发行结果",
           "减持", "增持计划", "一致行动", "证券事务代表", "董事会秘书", "会议日期", "报废", "私募基金", "投资基金", "超额配售", "稳定价格")
CN_UP3 = ("业绩预告", "业绩快报", "业绩预增", "预增", "重大合同", "签订", "中标", "扩产", "投资建设", "项目投资", "收购")
CN_UP2 = ("生产经营情况", "投资者关系活动记录", "调研活动", "经营数据")  # 정기 보고서 제목엔 숫자가 없다 → 1

# ---- Korea
DART_UP3 = ("단일판매", "공급계약")
DART_UP2 = ("잠정", "영업(잠정)실적", "시설투자", "신규시설", "유상증자", "전환사채", "신주인수권", "타법인주식", "분기보고서", "반기보고서", "사업보고서")
DART_SKIP = ("임원ㆍ주요주주", "최대주주등소유주식", "주식등의대량보유", "자기주식", "의결권대리행사", "주주총회", "정정신고")

# ---- news: 제목에 이 말이 있으면 사건성 기사로 본다 (중요도 2)
NEWS_UP = re.compile(
    r"\b(order|orders|contract|wins|won|awarded|supply agreement|qualif\w*|design win|capacity|expan\w+|new (?:plant|fab|factory)|"
    r"record (?:revenue|sales|quarter)|guidance|raises|beats|acquir\w+|merger|partnership|mass production|ramp\w*|shortage|price hike)\b"
    r"|수주|공급계약|증설|최대 실적|사상 최대|양산|흑자전환|단가 인상|품귀|공급 부족|생산능력|캐파|受注|増産|最高益|上方修正|量産|品薄|供給不足|"
    r"订单|扩产|签订|中标|创新高|量产|涨价|短缺|缺货|供不应求|产能|訂單|擴產|創新高|量產|漲價|缺貨|缺口|供不應求|產能",
    re.I)
# 주가 등락·목표가·수급표 같은 시세 기사 — 사건(수주·증설·실적)이 같이 없으면 버린다
PRICE_CHATTER = re.compile(
    r"특징주|강보합|약보합|상승률|하락률|급등|급락|주가|목표가|목표주가|신고가|\[MK시그널\]|株価|日経平均|値上がり|値下がり|信用売買|ストップ高|"
    r"盤中|漲停|跌停|停板|目標價|股價|股价|涨停|跌停|焦點股|熱門股|"
    r"\bshares? (?:of|rose|fell|jumped|surged|plunged|climb\w*|slid)|\bstock (?:price|rises|falls|jumps|surges)|Estimates –|is on the rise|price target|"
    r"Price Today|\btarget (?:€|\$|£|¥)|keeps .{0,40} at '|\b(?:upgrade|downgrade)s?\b|voting rights|shareholder (?:notice|alert)|class action|"
    r"investors? (?:with|who) (?:substantial )?losses|個股概覽|主力资金|净卖出|净买入|認購|權證|股市爆料|ETF|今天買進|格上げ|格下げ|목표가|매수세",
    re.I)
# 기관 보유 지분 변동·공매도 기사 — 사건어가 있어도 버린다 ('Acquires 882,739 Shares of …')
HOLDINGS_NOISE = re.compile(
    r"\b(?:acquires|buys|purchases|sells|sold|trims|boosts|cuts|raises|lowers|reduces|grows|increases|decreases|expands|lifts)\s+"
    r"(?:[\d,.]+\s+(?:million\s+)?shares|(?:a\s+)?new\s+(?:stake|position)|(?:its\s+|their\s+)?(?:stake|position|holdings)\s+in)"
    r"|\bstake with [\d.,]+ (?:million )?share|short (?:bet|interest|position)|\$[A-Z]{2,5}\b|\b13F\b", re.I)
# 시세 집계 사이트 — 주가 해설·종목 요약이 대부분이다 (2026-10-30: 기업 소식 2,550건 중 781건). clues.py 도 이 목록을 쓴다.
NOISE_PUBLISHERS = {
    "tradingview", "simply wall st", "simply wall street", "marketbeat", "gurufocus", "moomoo", "ad-hoc-news.de", "www.ad-hoc-news.de",
    "zacks", "zacks investment research", "the motley fool", "motley fool", "investorplace", "24/7 wall st.", "stocktitan", "stock titan",
    "marketscreener", "www.marketscreener.com", "marketscreener.com", "investing.com", "finviz", "tipranks", "insidermonkey", "insider monkey",
    "stockstory", "yahoo!ファイナンス", "kabutan", "株探", "證券之星", "证券之星", "东方财富", "東方財富", "新浪财经",
}
COMMON_WORDS = {"zeus", "protec", "comet", "flex", "gates", "nova", "dover", "eaton", "carrier", "meta", "oracle", "apple", "amazon", "corning",
                "danfoss", "lumentum", "screen", "canon", "nikon", "rohm", "disco", "resonac", "hitachi", "panasonic", "vertiv", "legrand",
                "agc", "ase", "tel", "mks", "onto", "form", "coherent", "credo", "astera", "fabrinet"}
_NATIVE = re.compile(r"[぀-ヿ㐀-鿿가-힯][぀-ヿ㐀-鿿가-힯A-Za-z·]*")


@dataclass
class CompanyEvent:
    company_id: str
    kind: str                 # filing | disclosure | revenue | news
    published_at: datetime
    title: str
    url: str
    publisher: str
    tier: str                 # official_issuer | third_party_report
    importance: int = 1       # 1~3
    text: str = ""
    lang: str = "en"
    extra: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, Any]:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat()
        return d

    @classmethod
    def from_public(cls, d: dict[str, Any]) -> CompanyEvent:
        keep = {k: d.get(k) for k in ("company_id", "kind", "title", "url", "publisher", "tier", "importance", "text", "lang", "extra")}
        extra = dict(d.get("extra") or {})
        if d.get("event_id"):  # DB 에서 읽은 행은 저장된 id 를 그대로 (Claude 가 더한 소식은 id 규칙이 다르다)
            extra["event_id"] = d["event_id"]
        return cls(**{**keep, "published_at": datetime.fromisoformat(str(d["published_at"]).replace("Z", "+00:00")),
                      "text": d.get("text") or "", "lang": d.get("lang") or "en", "extra": extra})

    @property
    def event_id(self) -> str:
        return (self.extra or {}).get("event_id") or hashlib.sha1(f"{self.company_id}|{self.url}|{self.title[:120]}".encode()).hexdigest()[:20]

    def row(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self.public(), "text": self.text or None, "extra": self.extra or None}


def _names_file() -> dict[str, Any]:
    try:
        return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def native_names() -> dict[str, str]:
    return {k: v for k, v in (_names_file().get("names") or {}).items() if not k.startswith("_")}


def node_terms() -> list[tuple[str, str]]:
    """(용어, 노드 id) — 한·중·일 기사 제목을 그래프 노드에 잇는다. 긴 용어부터."""
    terms = [(t, nid) for nid, ts in (_names_file().get("node_terms") or {}).items() if not nid.startswith("_") for t in ts]
    return sorted(terms, key=lambda x: -len(x[0]))


def listed_companies(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nf = _names_file()
    natives, context = nf.get("names") or {}, nf.get("news_context") or {}
    out = []
    for n in graph["nodes"]:
        if n["kind"] != "company":
            continue
        lst = n.get("listing") or {}
        if lst.get("filer_type") == "private" or n.get("size_band") == "private" or not lst.get("exchange"):
            continue
        name = clean_name(n["label"])
        m = _NATIVE.search(name)
        native = natives.get(n["id"])
        if m:  # 'Henan Shijia Photons 仕佳光子' → 이름과 현지어를 나눈다
            native = native or m.group(0).strip()
            name = (name[: m.start()] + name[m.end():]).strip(" /·-") or name
        out.append({"id": n["id"], "name": re.sub(r"\s*/.*$", "", name).strip(), "native": native, "ticker": str(lst.get("ticker") or "") or None,
                    "exchange": str(lst.get("exchange") or "").upper(), "cik": lst.get("cik"), "size": n.get("size_band") or "unknown",
                    "ecosystem": n.get("ecosystem"), "context": context.get(n["id"])})
    return out


def _roc(d: Any) -> date | None:
    """'1151026' → 2026-10-26 (민국 연도)."""
    d = re.sub(r"\D", "", str(d or ""))
    if len(d) != 7:
        return None
    try:
        return date(int(d[:3]) + 1911, int(d[3:5]), int(d[5:7]))
    except ValueError:
        return None


def _utc(d: date, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=UTC)


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", str(s or "")))).strip()


def _num(s: Any) -> float | None:
    try:
        return float(str(s).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- US: SEC EDGAR
INSIDER_MIN_USD = 100_000  # 장내 매수(코드 P) 합계가 이 이상이면 소식으로


def form4_purchase(xml_text: str) -> dict[str, Any] | None:
    """Form 4 XML → 장내 매수(P) 요약 {owner, title, shares, usd, avg}. 매수가 없거나 10b5-1 계획이면 None."""
    from wsj.parsers.form4_xml import parse_form4

    f = parse_form4(xml_text)
    buys = [r for r in f.rows if r.get("table_type") == "nonDerivative" and r.get("transaction_code") == "P" and (r.get("shares") or 0) > 0]
    if not buys or f.header.get("aff10b5one"):
        return None
    shares = sum(r["shares"] for r in buys)
    usd = sum(r["shares"] * (r.get("price_per_share") or 0) for r in buys)
    title = f.header.get("officer_title") or ("이사" if f.header.get("is_director") else "10% 주주" if f.header.get("is_ten_percent_owner") else "내부자")
    return {"owner": f.header.get("owner_name"), "title": title, "shares": shares, "usd": usd, "avg": usd / shares if shares else None}


def sec_events(http, cos: list[dict[str, Any]], since: date, headline_limit: int = 40, form4_limit: int = 80) -> list[CompanyEvent]:
    out: list[CompanyEvent] = []
    heads = 0
    f4 = 0
    for c in cos:
        if not c.get("cik"):
            continue
        cik = int(c["cik"])
        try:
            sub = http.get_json(SEC_SUBMISSIONS.format(cik=cik))
        except Exception as exc:  # noqa: BLE001
            log.warning("sec submissions %s failed: %s", c["id"], exc)
            continue
        rec = sub.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        items_all = rec.get("items") or [""] * len(forms)
        for i, form in enumerate(forms):
            fdate = date.fromisoformat(rec["filingDate"][i])
            if fdate < since:
                break  # 최신순
            if form == "4" and f4 < form4_limit:
                # 내부자 장내 매수 — 경영진이 자기 돈으로 산다는 공식 신호 (매도는 보상·세금 목적이 많아 쓰지 않는다)
                f4 += 1
                acc4 = rec["accessionNumber"][i].replace("-", "")
                doc = re.sub(r"^xsl[^/]+/", "", rec["primaryDocument"][i])
                url4 = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc4}/{doc}"
                try:
                    buy = form4_purchase(http.get_text(url4))
                except Exception as exc:  # noqa: BLE001
                    log.warning("form4 %s failed: %s", url4, exc)
                    buy = None
                if buy and buy["usd"] >= INSIDER_MIN_USD:
                    imp = 3 if buy["usd"] >= 1_000_000 else 2
                    avg = f" (평균 ${buy['avg']:,.2f})" if buy.get("avg") else ""
                    out.append(CompanyEvent(c["id"], "filing", _utc(fdate),
                                            f"{c['name']} 내부자 장내 매수: {buy['owner']} ({buy['title']}) {buy['shares']:,.0f}주, 약 ${buy['usd']:,.0f}{avg}",
                                            f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc4}/{rec['primaryDocument'][i]}",
                                            f"SEC EDGAR ({c['name']})", "official_issuer", imp, extra={"form": "4", "insider_buy_usd": round(buy["usd"])}))
                continue
            if form not in SEC_FORMS:
                continue
            items = [x.strip() for x in str(items_all[i] or "").split(",") if x.strip()]
            if form.startswith("8-K") and items and set(items) <= SEC_SKIP_ONLY:
                continue
            acc = rec["accessionNumber"][i].replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"
            what = ", ".join(ITEM_KO.get(x, x) for x in items if x not in SEC_SKIP_ONLY) or FORM_KO.get(form, form)
            # 10-Q·10-K 는 실적 8-K 뒤에 오는 정형 보고서 — 새 사실은 8-K 쪽에 있다
            imp = 3 if "1.01" in items or form.startswith("SC 13D") else 2 if {"2.01", "2.02", "7.01", "8.01"} & set(items) else 1
            ev = CompanyEvent(c["id"], "filing", _utc(fdate), f"{c['name']} {form}: {what}", f"{base}/{rec['primaryDocument'][i]}",
                              f"SEC EDGAR ({c['name']})", "official_issuer", imp, extra={"form": form, "items": items})
            if heads < headline_limit and (set(items) & SEC_HEADLINE_ITEMS or form == "6-K"):
                heads += 1
                try:
                    idx = http.get_json(f"{base}/index.json")
                    ex = next((f["name"] for f in idx.get("directory", {}).get("item", [])
                               if re.search(r"ex-?99|ex99|press|pr\d", f["name"], re.I) and f["name"].lower().endswith((".htm", ".html", ".txt"))), None)
                    if ex:
                        head = exhibit_headline(http.get_text(f"{base}/{ex}"), c["name"])
                        ev.url = f"{base}/{ex}"
                        if head:
                            ev.text = ev.title
                            ev.title = f"{c['name']}: {head}"
                except Exception as exc:  # noqa: BLE001 - 헤드라인 실패는 메타데이터 제목으로
                    log.warning("sec headline %s failed: %s", base, exc)
            out.append(ev)
    log.info("sec events: %d", len(out))
    return out


def exhibit_headline(text: str, company: str = "") -> str | None:
    """EX-99 보도자료 → 첫 헤드라인. SGML 머리말·'Exhibit 99.1'·'FOR IMMEDIATE RELEASE' 를 걷어내고, 기호·표 조각이면 None."""
    from wsj.ecosystems.issues import sec_headline

    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
    for _ in range(16):
        t2 = _EX_PREFIX.sub("", t, count=1)
        if t2 == t:
            break
        t = t2
    m = re.search(r"\s[A-Z][A-Z.\-]{2,}(?: [A-Z][A-Z.\-]+)*,\s", t[:400])  # 'SAN JOSE, Calif.' 같은 대문자 데이트라인 앞에서 자른다
    if m and m.start() > 20:
        t = t[: m.start()]
    head, _ = sec_headline(t, "", company)
    head = _TRAIL_CITY.sub("", head or "").strip(" ,-–—")
    if not head:
        return None
    letters = sum(ch.isalpha() for ch in head)
    if len(head.split()) < 5 or letters < 0.6 * len(head.replace(" ", "")) or re.search(r"[•➜■□▪]", head):
        return None
    return head


# ---------------------------------------------------------------- Taiwan
def _tw_rows(http, url: str) -> list[dict[str, Any]]:
    raw = http.get_text(url, headers=BROWSER_UA)
    return [{str(k).strip(): v for k, v in r.items()} for r in json.loads(raw.lstrip("﻿"))]


def tw_events(http, cos: list[dict[str, Any]], since: date) -> list[CompanyEvent]:
    by_code = {c["ticker"].lstrip("0"): c for c in cos if c["exchange"] in TW_EX and c.get("ticker")}
    out: list[CompanyEvent] = []
    for url, market in ((TWSE_MATERIAL, "TWSE"), (TPEX_MATERIAL, "TPEx")):
        try:
            rows = _tw_rows(http, url)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s material info failed: %s", market, exc)
            continue
        for r in rows:
            code = str(r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip().lstrip("0")
            c = by_code.get(code)
            if not c:
                continue
            subject = _clean(r.get("主旨"))
            if not subject or any(w in subject for w in TW_SKIP):
                continue
            d = _roc(r.get("發言日期")) or _roc(r.get("出表日期")) or _roc(r.get("Date"))
            if not d or d < since:
                continue
            body = _clean(r.get("說明"))[:500]
            imp = 2 if any(w in subject + body[:160] for w in TW_UP) else 1
            out.append(CompanyEvent(c["id"], "disclosure", _utc(d), f"{c['name']} 중대공시: {subject}",
                                    f"https://mops.twse.com.tw/mops/#/web/t05st01?companyId={code}&date={d:%Y%m%d}", f"{market} 중대공시",
                                    "official_issuer", imp, body, "zh"))
    log.info("tw material events: %d", len(out))
    return out


def tw_revenue_events(http, cos: list[dict[str, Any]], since: date) -> list[CompanyEvent]:
    """지표 모듈(TW_ENTITIES 17곳) 밖의 그래프 대만 기업 월매출 — 눈에 띄는 달만 사건으로."""
    from wsj.ecosystems.indicators import TW_ENTITIES

    covered = {str(e["local_code"]) for e in TW_ENTITIES.values()}
    by_code = {c["ticker"].lstrip("0"): c for c in cos if c["exchange"] in TW_EX and c.get("ticker") and c["ticker"] not in covered}
    out: list[CompanyEvent] = []
    for url, market in ((TWSE_REV, "TWSE"), (TPEX_REV, "TPEx")):
        try:
            rows = _tw_rows(http, url)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s revenue failed: %s", market, exc)
            continue
        for r in rows:
            code = str(r.get("公司代號", "")).strip().lstrip("0")
            c = by_code.get(code)
            if not c:
                continue
            ym = str(r.get("資料年月", "")).strip()
            try:
                month = date(int(ym[:-2]) + 1911, int(ym[-2:]), 1)
            except ValueError:
                continue
            yoy, mom = _num(r.get("營業收入-去年同月增減(%)")), _num(r.get("營業收入-上月比較增減(%)"))
            reasons = []
            if yoy is not None and (yoy >= REV_YOY_UP or yoy <= REV_YOY_DOWN):
                reasons.append(f"전년 대비 {yoy:+.0f}%")
            if mom is not None and abs(mom) >= REV_MOM:
                reasons.append(f"전월 대비 {mom:+.0f}%")
            if not reasons:
                continue
            published = _roc(r.get("出表日期")) or (month.replace(day=28) + timedelta(days=14))
            if published < since:
                continue
            imp = 3 if (yoy or 0) >= 80 else 2
            out.append(CompanyEvent(c["id"], "revenue", _utc(published), f"{c['name']} {month:%Y-%m} 월매출 {', '.join(reasons)}",
                                    f"https://mops.twse.com.tw/mops/#/web/t146sb05?companyId={code}&ym={month:%Y%m}", f"{market} 월매출",
                                    "official_issuer", imp, _clean(r.get("備註"))[:200], "zh", {"yoy": yoy, "mom": mom, "month": f"{month:%Y-%m}"}))
    log.info("tw revenue events: %d", len(out))
    return out


# ---------------------------------------------------------------- Japan: TDnet
_TD_ROW = re.compile(r'kjTime"[^>]*>([^<]*)</td>\s*<td[^>]*kjCode"[^>]*>([^<]*)</td>\s*<td[^>]*kjName"[^>]*>([^<]*)</td>\s*'
                     r'<td[^>]*kjTitle"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def parse_tdnet(page: str) -> tuple[int | None, list[tuple[str, str, str, str]]]:
    """TDnet 목록 페이지 → (전체 건수, [(HH:MM, 4자리 코드, 문서 href, 제목)])."""
    m = re.search(r"全\s*(\d+)\s*件", page)
    rows = [(tm.strip(), code.strip()[:4], href.strip(), _clean(title)) for tm, code, _n, href, title in _TD_ROW.findall(page)]
    return (int(m.group(1)) if m else None), rows


def jp_events(http, cos: list[dict[str, Any]], since: date, today: date) -> list[CompanyEvent]:
    by_code = {c["ticker"]: c for c in cos if c["exchange"] == "TSE" and c.get("ticker")}
    if not by_code:
        return []
    out: list[CompanyEvent] = []
    d = since
    while d <= today:
        if d.weekday() < 5:
            page, pages = 1, 1
            while page <= pages:
                try:
                    total, rows = parse_tdnet(http.get_text(TDNET_LIST.format(page=page, day=f"{d:%Y%m%d}"), headers=BROWSER_UA))
                except Exception as exc:  # noqa: BLE001 - 공시 없는 날·보관 기간(약 1개월) 밖
                    log.info("tdnet %s p%d: %s", d, page, exc)
                    break
                if page == 1 and total:
                    pages = min(30, math.ceil(total / 100))
                for tm, code, href, title in rows:
                    c = by_code.get(code)
                    if not c or any(w in title for w in JP_SKIP):
                        continue
                    hh, mm = (int(x) for x in tm.split(":")) if re.fullmatch(r"\d{1,2}:\d{2}", tm) else (0, 0)
                    imp = 3 if any(w in title for w in JP_UP3) else 2 if any(w in title for w in JP_UP2) else 1
                    if "簡易吸収合併" in title or "完全子会社" in title and "合併" in title:
                        imp = 1  # 자회사 흡수합병은 그룹 내부 정리
                    # TDnet 시각은 JST — UTC 로 9시간 당긴다
                    out.append(CompanyEvent(c["id"], "disclosure", _utc(d, hh, mm) - timedelta(hours=9), f"{c['name']} 적시공시: {title}",
                                            TDNET_DOC.format(href=href), "TDnet 적시공시", "official_issuer", imp, "", "ja"))
                page += 1
        d += timedelta(days=1)
    log.info("jp events: %d", len(out))
    return out


# ---------------------------------------------------------------- China: cninfo
def cn_events(http, cos: list[dict[str, Any]], since: date, today: date) -> list[CompanyEvent]:
    out: list[CompanyEvent] = []
    for c in cos:
        if c["exchange"] not in CN_EX or not c.get("ticker"):
            continue
        try:
            hits = http.request("POST", CNINFO_SEARCH, params={"keyWord": c["ticker"], "maxNum": 5}, headers=BROWSER_UA).json()
            org = next((h["orgId"] for h in hits if h.get("code") == c["ticker"]), None)
            if not org:
                continue
            resp = http.request("POST", CNINFO_QUERY, headers=BROWSER_UA, data={
                "pageNum": 1, "pageSize": 30, "column": "sse" if c["exchange"] == "SSE" else "szse", "tabName": "fulltext",
                "stock": f"{c['ticker']},{org}", "seDate": f"{since}~{today}", "isHLtitle": "true"})
            anns = resp.json().get("announcements") or []
        except Exception as exc:  # noqa: BLE001
            log.warning("cninfo %s failed: %s", c["id"], exc)
            continue
        for a in anns:
            title = _clean(a.get("announcementTitle"))
            if not title or not a.get("adjunctUrl") or any(w in title for w in CN_SKIP):
                continue
            ts = datetime.fromtimestamp(int(a.get("announcementTime") or 0) / 1000, tz=UTC)
            imp = 3 if any(w in title for w in CN_UP3) else 2 if any(w in title for w in CN_UP2) else 1
            out.append(CompanyEvent(c["id"], "disclosure", ts, f"{c['native'] or c['name']} 공시: {title}",
                                    CNINFO_DOC.format(path=a["adjunctUrl"]), "巨潮资讯 공시", "official_issuer", imp, "", "zh"))
    log.info("cn events: %d", len(out))
    return out


# ---------------------------------------------------------------- Korea: DART
def dart_events(http, cos: list[dict[str, Any]], since: date, key: str | None) -> list[CompanyEvent]:
    kr = {c["ticker"].zfill(6): c for c in cos if c["exchange"] in KR_EX and c.get("ticker")}
    if not key:
        log.info("DART_API_KEY 없음 — 한국 공시 건너뜀 (뉴스로만 본다)")
        return []
    try:
        resp = http.request("GET", DART_CORPCODE, params={"crtfc_key": key})
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        root = ET.fromstring(zf.read(zf.namelist()[0]))
        corp = {(e.findtext("stock_code") or "").strip(): e.findtext("corp_code") for e in root.iter("list")}
    except Exception as exc:  # noqa: BLE001
        log.warning("dart corpCode failed: %s", exc)
        return []
    out: list[CompanyEvent] = []
    for code, c in kr.items():
        cc = corp.get(code)
        if not cc:
            continue
        try:
            data = http.get_json(DART_LIST, params={"crtfc_key": key, "corp_code": cc, "bgn_de": f"{since:%Y%m%d}", "page_count": "50"})
        except Exception as exc:  # noqa: BLE001
            log.warning("dart list %s failed: %s", c["id"], exc)
            continue
        for r in data.get("list") or []:
            name = re.sub(r"\s+", " ", r.get("report_nm", "")).strip()
            if not name or any(w in name for w in DART_SKIP):
                continue
            imp = 3 if any(w in name for w in DART_UP3) else 2 if any(w in name for w in DART_UP2) else 1
            out.append(CompanyEvent(c["id"], "disclosure", datetime.strptime(r["rcept_dt"], "%Y%m%d").replace(tzinfo=UTC),
                                    f"{c['native'] or c['name']} 공시: {name}", f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}",
                                    "DART 전자공시", "official_issuer", imp, "", "ko"))
    log.info("dart events: %d", len(out))
    return out


# ---------------------------------------------------------------- news
def _news_queries(c: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    name = c["name"]
    nat = c.get("native")
    qs = []
    common = name.lower() in COMMON_WORDS or len(name) <= 5
    us = c["exchange"] in ("NASDAQ", "NYSE", "NYSE AMERICAN")
    if not (common and nat and not us):  # 흔한 이름의 해외 기업은 영어 기사 대신 현지 기사만
        q = f'"{name}"' + (' (semiconductor OR chip OR AI OR optical OR power OR "data center")' if common else "")
        qs.append((q, "en-US", "US", "en", "en"))
    if nat:
        ctx = c.get("context")
        if not ctx and len(nat) <= 2 and c["exchange"] not in KR_EX:  # '高力'·'聯亞' 같은 두 글자 이름은 종목코드·업종어로 좁힌다
            ctx = f"({c['ticker']} OR AI OR 半導體 OR 半导体)" if c.get("ticker") else "(AI OR 半導體 OR 半导体)"
        nq = f'"{nat}"' + (f" {ctx}" if ctx else "")
        if c["exchange"] in KR_EX:
            qs.append((nq, "ko", "KR", "ko", "ko"))
        elif c["exchange"] == "TSE":
            qs.append((nq, "ja", "JP", "ja", "ja"))
        elif c["exchange"] in TW_EX:
            qs.append((nq, "zh-TW", "TW", "zh-Hant", "zh"))
        elif c["exchange"] in (*CN_EX, "HKEX"):
            qs.append((nq, "zh-CN", "CN", "zh-Hans", "zh"))
    return qs


def mentions(title: str, c: dict[str, Any]) -> bool:
    """기사 제목이 이 기업을 직접 말하는가 — 본문에만 스친 기사는 버린다."""
    t = title.lower()
    name = c["name"].lower()
    if name in t or (c.get("native") and c["native"] in title):
        return True
    if c.get("ticker") and not c["ticker"].isdigit() and re.search(rf"\b{re.escape(c['ticker'])}\b", title):
        return True
    first = re.split(r"[\s,]+", name)[0]
    return len(first) >= 5 and first not in COMMON_WORDS and re.search(rf"\b{re.escape(first)}\b", t) is not None


def news_events(http, cos: list[dict[str, Any]], days: int, focus: set[str], per_query: int = 8) -> list[CompanyEvent]:
    out: list[CompanyEvent] = []
    seen: set[str] = set()
    n_q = 0
    for c in cos:
        if c["size"] in ("large", "mega") and c["id"] not in focus:
            continue
        for q, hl, gl, lang, code in _news_queries(c):
            n_q += 1
            url = GOOGLE_NEWS.format(q=quote_plus(f"{q} when:{days}d"), hl=hl, gl=gl, lang=lang)
            try:
                root = ET.fromstring(http.get_text(url, headers=BROWSER_UA))
            except Exception as exc:  # noqa: BLE001
                log.warning("news %s failed: %s", c["id"], exc)
                continue
            for it in root.findall(".//item")[:per_query]:
                title = _clean(it.findtext("title"))
                publisher = _clean(it.findtext("source")) or "news"
                if title.endswith(" - " + publisher):
                    title = title[: -len(publisher) - 3]
                key = re.sub(r"\W+", "", title.lower())[:80]
                if not title or key in seen or not mentions(title, c):
                    continue
                up = NEWS_UP.search(title)
                if HOLDINGS_NOISE.search(title) or (PRICE_CHATTER.search(title) and not up):
                    continue
                if publisher.strip().lower() in NOISE_PUBLISHERS:  # 시세 집계 사이트 (ADR-0028: 시세 기사는 버린다)
                    continue
                try:
                    d = datetime.strptime(it.findtext("pubDate") or "", "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
                except ValueError:
                    continue
                seen.add(key)
                out.append(CompanyEvent(c["id"], "news", d, title, it.findtext("link") or "", publisher, "third_party_report",
                                        2 if up else 1, "", code, {"query": q}))
    log.info("news events: %d (%d queries)", len(out), n_q)
    return out


# ---------------------------------------------------------------- orchestration
def collect(http, graph: dict[str, Any], days: int = 10, focus: set[str] | None = None, dart_key: str | None = None,
            with_news: bool = True, today: date | None = None) -> tuple[list[CompanyEvent], dict[str, Any]]:
    cos = listed_companies(graph)
    today = today or datetime.now(UTC).date()
    since = today - timedelta(days=days)
    stats: dict[str, Any] = {"companies": len(cos)}
    events: list[CompanyEvent] = []
    steps = [("sec", lambda: sec_events(http, cos, since)), ("tw", lambda: tw_events(http, cos, since)),
             ("tw_revenue", lambda: tw_revenue_events(http, cos, since)), ("jp", lambda: jp_events(http, cos, since, today)),
             ("cn", lambda: cn_events(http, cos, since, today)), ("kr", lambda: dart_events(http, cos, since, dart_key))]
    if with_news:
        steps.append(("news", lambda: news_events(http, cos, min(days, 7), focus or set())))
    for name, fn in steps:
        t0 = time.monotonic()
        try:
            got = fn()
        except Exception as exc:  # noqa: BLE001 - 한 출처가 죽어도 나머지는 쓴다
            log.warning("%s feed failed: %s", name, exc)
            got = []
        stats[name] = {"events": len(got), "sec": round(time.monotonic() - t0, 1)}
        events += got
    # 같은 기업·같은 제목은 하나로 (뉴스 재게재, 공시 정정본)
    uniq: dict[tuple[str, str], CompanyEvent] = {}
    for e in sorted(events, key=lambda e: (-e.importance, e.published_at)):
        uniq.setdefault((e.company_id, re.sub(r"\W+", "", e.title.lower())[:90]), e)
    events = sorted(uniq.values(), key=lambda e: e.published_at, reverse=True)
    stats["events"] = len(events)
    stats["with_events"] = len({e.company_id for e in events})
    return events, stats


def save_events(store, events: list[CompanyEvent]) -> int:
    """ideas.company_events 에 쌓는다 (0019 전이면 저장하지 않고 0 을 돌려준다)."""
    rows = list({e.event_id: e.row() for e in events}.values())
    if not rows:
        return 0
    try:
        return store.upsert("ideas.company_events", rows, ["event_id"])
    except Exception as exc:  # noqa: BLE001
        log.warning("ideas.company_events 에 쓸 수 없음 (0019 적용 전?): %s", exc)
        return 0


def load_events(store, days: int) -> list[CompanyEvent]:
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    try:
        rows = store.select("ideas.company_events", ["*"], {"published_at": ("gte", since)})
    except Exception as exc:  # noqa: BLE001
        log.warning("ideas.company_events 를 읽을 수 없음 (0019 적용 전?): %s", exc)
        return []
    return [CompanyEvent.from_public(r) for r in rows]


def merge_events(*groups: list[CompanyEvent]) -> list[CompanyEvent]:
    out: dict[str, CompanyEvent] = {}
    for g in groups:
        for e in g:
            out.setdefault(e.event_id, e)
    return sorted(out.values(), key=lambda e: e.published_at, reverse=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--only", help="쉼표로 구분한 기업 id 만 (점검용)")
    ap.add_argument("--out")
    ap.add_argument("--save", action="store_true", help="ideas.company_events 에 쌓는다 (LLM 없이 수집만 하는 실행용)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.config import load_settings
    from wsj.http import HttpClient

    settings = load_settings()
    graph = load_graph()
    if args.only:
        keep = set(args.only.split(","))
        graph = {**graph, "nodes": [n for n in graph["nodes"] if n["kind"] != "company" or n["id"] in keep]}
    store, focus = None, set()
    if args.save:
        from wsj.db import make_store

        store = make_store(settings)
        try:  # 대형사 뉴스는 기존 아이디어에 든 기업만 본다
            for x in store.select("ideas.investment_ideas", ["primary_company", "companies"], {"status": "active"}):
                focus |= {x.get("primary_company")} | {c.get("id") for c in x.get("companies") or []}
        except Exception as exc:  # noqa: BLE001
            log.warning("기존 아이디어를 읽을 수 없음: %s", exc)
        try:  # 투자 아이디어(ADR-0028)의 기업도
            for x in store.select("ideas.opportunities", ["companies"], {"status": "active"}):
                focus |= {c.get("company") for c in x.get("companies") or [] if c.get("company")}
        except Exception as exc:  # noqa: BLE001 - 0031 전
            log.warning("투자 아이디어를 읽을 수 없음: %s", exc)
    http = HttpClient(settings.sec_user_agent, timeout=25, max_retries=2)
    try:
        if store is not None:  # 실행 기록 → 아이디어 예약작업이 "오늘 수집이 끝났나" 를 ops.collector_runs 로 확인한다
            from wsj.runlog import logged_run

            with logged_run(store, "company_feed", {"days": args.days, "news": not args.no_news}) as run:
                events, stats = collect(http, graph, args.days, {f for f in focus if f}, settings.dart_api_key or None, not args.no_news)
                stats["saved"] = save_events(store, events)
                run["rows"] = stats["saved"]
                run["notes"] = json.dumps({k: v for k, v in stats.items() if k in ("events", "with_events", "saved")})
        else:
            events, stats = collect(http, graph, args.days, {f for f in focus if f}, settings.dart_api_key or None, not args.no_news)
    finally:
        http.close()
        if store is not None:
            store.close()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump([e.public() for e in events], f, ensure_ascii=False, indent=1)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
