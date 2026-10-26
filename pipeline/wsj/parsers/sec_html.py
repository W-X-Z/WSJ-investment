"""EDGAR HTML → 본문 텍스트, 10-K 섹션(Item 1 / 1A / 7) 추출. ADR-0009 §2.

전략 (검증: RAPP 10-K 2026-03, accession 0001193125-26-099360):
1. 목차의 `<a href="#id">Item 1. Business</a>` 를 모아 항목 → 앵커 id 를 얻고, 본문의 `id="..."` 위치로
   섹션 경계를 잡는다. 같은 href 를 가진 앵커가 여러 개면 ("Item 1." 과 "Business" 가 따로) 텍스트를 합친다.
2. 앵커가 없는 옛 문서는 텍스트 정규식 폴백: 각 항목 제목의 출현 중 "다음 항목까지의 거리가 가장 긴" 것을 본문으로 본다
   (목차 출현은 서로 붙어 있어 짧다).
3. HTML → 텍스트 변환은 블록 태그에서만 줄을 바꾸고 인라인 태그(span/b/font)는 공백 없이 잇는다 —
   그래야 "It</span><span>em 1" 같은 분할이 "Item 1" 로 복원된다.
"""

from __future__ import annotations

import html as htmlmod
import re
from dataclasses import dataclass

BLOCK_TAGS = "p|div|br|tr|li|h1|h2|h3|h4|h5|h6|table|thead|tbody|ul|ol|section|article|blockquote|hr|title"
_RE_SCRIPT = re.compile(r"<(script|style|head)\b.*?</\1\s*>", re.I | re.S)
_RE_XBRL_HIDDEN = re.compile(r"<ix:header\b.*?</ix:header\s*>", re.I | re.S)
_RE_COMMENT = re.compile(r"<!--.*?-->", re.S)
_RE_BLOCK = re.compile(rf"</?(?:{BLOCK_TAGS})\b[^>]*>", re.I)
_RE_CELL = re.compile(r"</?(?:td|th)\b[^>]*>", re.I)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"[ \t ​]+")
_RE_NL = re.compile(r"\n\s*\n\s*\n+")
_RE_PAGE_NOISE = re.compile(r"^(table of contents|\d{1,3}|[ivxlc]{1,5}|f-\d{1,3})$", re.I)

SECTION_PATTERNS: dict[str, str] = {
    # key: regex on normalized anchor text (lowercase, single spaces)
    "item_1": r"^item\s*1\b(?!\s*[abc]\b)",
    "item_1a": r"^item\s*1a\b",
    "item_1b": r"^item\s*1b\b",
    "item_1c": r"^item\s*1c\b",
    "item_2": r"^item\s*2\b",
    "item_3": r"^item\s*3\b",
    "item_5": r"^item\s*5\b",
    "item_7": r"^item\s*7\b(?!\s*a\b)",
    "item_7a": r"^item\s*7a\b",
    "item_8": r"^item\s*8\b",
}
# 추출 대상 → 끝 경계 후보 (문서 순서대로 가장 먼저 나오는 것)
SECTION_END: dict[str, tuple[str, ...]] = {
    "item_1": ("item_1a", "item_1b", "item_1c", "item_2", "item_3"),
    "item_1a": ("item_1b", "item_1c", "item_2", "item_3"),
    "item_7": ("item_7a", "item_8"),
}
# 텍스트 폴백용 제목 패턴 (앵커 없을 때)
TEXT_HEADINGS: dict[str, str] = {
    "item_1": r"item\s*1\.?\s*[\-–—:]?\s*business\b",
    "item_1a": r"item\s*1a\.?\s*[\-–—:]?\s*risk\s*factors\b",
    "item_1b": r"item\s*1b\.?\s*[\-–—:]?\s*unresolved\s*staff\s*comments\b",
    "item_1c": r"item\s*1c\.?\s*[\-–—:]?\s*cybersecurity\b",
    "item_2": r"item\s*2\.?\s*[\-–—:]?\s*properties\b",
    "item_3": r"item\s*3\.?\s*[\-–—:]?\s*legal\s*proceedings\b",
    "item_7": r"item\s*7\.?\s*[\-–—:]?\s*management['’]?s\s*discussion\b",
    "item_7a": r"item\s*7a\.?\s*[\-–—:]?\s*quantitative\s*and\s*qualitative\b",
    "item_8": r"item\s*8\.?\s*[\-–—:]?\s*financial\s*statements\b",
}


def html_to_text(raw: str) -> str:
    """HTML(iXBRL 포함) → 읽을 수 있는 텍스트. 표 셀은 탭, 블록은 줄바꿈."""
    s = _RE_SCRIPT.sub(" ", raw)
    s = _RE_XBRL_HIDDEN.sub(" ", s)
    s = _RE_COMMENT.sub(" ", s)
    s = _RE_CELL.sub("\t", s)
    s = _RE_BLOCK.sub("\n", s)
    s = _RE_TAG.sub("", s)
    s = htmlmod.unescape(s)
    s = s.replace("\r", "")
    s = _RE_WS.sub(" ", s)
    lines = [ln.strip(" \t") for ln in s.split("\n")]
    # 페이지 머리말·쪽번호 ('Table of Contents', '104') 제거
    lines = [ln for ln in lines if not _RE_PAGE_NOISE.match(ln)]
    s = "\n".join(lines)
    s = _RE_NL.sub("\n\n", s)
    return s.strip()


def _norm_label(text: str) -> str:
    t = htmlmod.unescape(_RE_TAG.sub("", text))
    t = t.replace(" ", " ")
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = t.replace("item 1 a", "item 1a").replace("item 1 b", "item 1b").replace("item 1 c", "item 1c")
    t = t.replace("item 7 a", "item 7a")
    return t


@dataclass
class Section:
    key: str
    text: str
    method: str  # anchor | regex
    start: int
    end: int
    truncated: bool = False


_RE_ANCHOR = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']#([^\"'#>]+)[\"'][^>]*>(.*?)</a\s*>", re.I | re.S)


TITLE_ONLY_PATTERNS: dict[str, str] = {
    # 앵커 텍스트에 'Item N' 없이 제목만 있을 때 (RAPP: <td>Item 1.</td><td><a>Business</a></td>)
    "item_1": r"^business\.?$",
    "item_1a": r"^risk\s*factors\.?$",
    "item_1b": r"^unresolved\s*staff\s*comments\.?$",
    "item_1c": r"^cybersecurity\.?$",
    "item_2": r"^properties\.?$",
    "item_3": r"^legal\s*proceedings\.?$",
    "item_7": r"^management['’]?s\s*discussion\s*and\s*analysis",
    "item_7a": r"^quantitative\s*and\s*qualitative\s*disclosures",
    "item_8": r"^financial\s*statements\s*and\s*supplementary\s*data\.?$",
}


def _match_key(label: str, patterns: dict[str, str]) -> str | None:
    for key, pat in patterns.items():
        if re.match(pat, label):
            return key
    return None


def _row_label(raw: str, pos: int) -> str:
    """앵커를 감싼 <tr> (없으면 앞 300자) 의 텍스트 — 'item 1. business 3' 꼴."""
    tr = raw.rfind("<tr", 0, pos)
    if tr != -1 and pos - tr < 4000:
        end = raw.find("</tr", pos)
        if end != -1 and end - tr < 8000:
            return _norm_label(raw[tr:end])
    return _norm_label(raw[max(0, pos - 300) : pos])


def toc_anchor_ids(raw: str) -> dict[str, str]:
    """섹션 키 → 앵커 id.

    매칭 순서: (1) 앵커 텍스트(같은 href 의 앵커는 이어 붙임) 에 'item 1a ...' (2) id 자체 ('item_1a_risk_factors')
    (3) 앵커 텍스트가 제목만 ('Risk Factors') (4) 앵커를 감싼 표 행 텍스트. 목차가 여러 개면 먼저 매칭된 id.
    """
    by_href: dict[str, list[str]] = {}
    first_pos: dict[str, int] = {}
    order: list[str] = []
    for m in _RE_ANCHOR.finditer(raw):
        href, inner = m.group(1), m.group(2)
        label = _norm_label(inner)
        if not label:
            continue
        if href not in by_href:
            by_href[href] = []
            order.append(href)
            first_pos[href] = m.start()
        by_href[href].append(label)
    found: dict[str, str] = {}
    for href in order:
        label = " ".join(by_href[href])
        id_label = _norm_label(re.sub(r"[_\-]+", " ", href))
        key = (
            _match_key(label, SECTION_PATTERNS)
            or _match_key(id_label, SECTION_PATTERNS)
            or _match_key(label, TITLE_ONLY_PATTERNS)
        )
        if key is None:
            row = _row_label(raw, first_pos[href])
            m = re.search(r"item\s*\d+[abc]?\b.*", row)
            key = _match_key(m.group(0), SECTION_PATTERNS) if m else None
        if key and key not in found:
            found[key] = href
    return found


def _id_position(raw: str, anchor_id: str) -> int | None:
    pat = re.compile(r"<[^>]+\b(?:id|name)\s*=\s*[\"']" + re.escape(anchor_id) + r"[\"'][^>]*>", re.I)
    m = pat.search(raw)
    return m.start() if m else None


def extract_sections_by_anchor(
    raw: str, wanted: tuple[str, ...] = ("item_1", "item_1a", "item_7")
) -> dict[str, Section]:
    ids = toc_anchor_ids(raw)
    if not ids:
        return {}
    pos: dict[str, int] = {}
    for key, aid in ids.items():
        p = _id_position(raw, aid)
        if p is not None:
            pos[key] = p
    out: dict[str, Section] = {}
    for key in wanted:
        if key not in pos:
            continue
        start = pos[key]
        end = len(raw)
        for end_key in SECTION_END.get(key, ()):
            if end_key in pos and pos[end_key] > start:
                end = pos[end_key]
                break
        else:
            # 끝 경계 후보가 전부 없으면 start 이후 가장 가까운 다른 앵커
            later = [p for k, p in pos.items() if p > start and k != key]
            if later:
                end = min(later)
        text = html_to_text(raw[start:end])
        if len(text) < 500:
            # 앵커가 목차 자체를 가리킨 경우 등 — 폴백에 맡긴다
            continue
        out[key] = Section(key=key, text=text, method="anchor", start=start, end=end)
    return out


def extract_sections_by_text(
    text: str, wanted: tuple[str, ...] = ("item_1", "item_1a", "item_7")
) -> dict[str, Section]:
    """앵커 없는 문서용 폴백. 모든 제목 출현 위치를 모은 뒤, 각 항목의 출현 중
    다음 '다른 항목' 출현까지의 거리가 가장 긴 것을 본문 시작으로 본다."""
    hits: list[tuple[int, str]] = []
    for key, pat in TEXT_HEADINGS.items():
        for m in re.finditer(pat, text, re.I):
            # 줄 시작 근처의 제목만 (문장 중간의 'Item 1A' 참조 배제)
            ls = text.rfind("\n", 0, m.start()) + 1
            if m.start() - ls > 12:
                continue
            hits.append((m.start(), key))
    hits.sort()
    out: dict[str, Section] = {}
    for key in wanted:
        best: tuple[int, int] | None = None  # (start, end)
        for i, (p, k) in enumerate(hits):
            if k != key:
                continue
            nxt = next((q for q, kk in hits[i + 1 :] if kk != key), len(text))
            if best is None or (nxt - p) > (best[1] - best[0]):
                best = (p, nxt)
        if best and best[1] - best[0] > 500:
            out[key] = Section(
                key=key, text=text[best[0] : best[1]].strip(), method="regex", start=best[0], end=best[1]
            )
    return out


def extract_10k_sections(raw: str, caps: dict[str, int] | None = None) -> dict[str, Section]:
    """Item 1 / 1A / 7 을 앵커 → 정규식 순으로 추출하고 길이 상한을 적용한다."""
    caps = caps or {"item_1": 25_000, "item_1a": 15_000, "item_7": 25_000}
    wanted = tuple(caps.keys())
    got = extract_sections_by_anchor(raw, wanted)
    missing = tuple(k for k in wanted if k not in got)
    if missing:
        text = html_to_text(raw)
        got.update(extract_sections_by_text(text, missing))
    for key, sec in got.items():
        cap = caps.get(key)
        if cap and len(sec.text) > cap:
            sec.text = truncate_text(sec.text, cap)
            sec.truncated = True
    return got


_RE_MDNA_TITLE = re.compile(r"management['’]?s\s*discussion\s*and\s*analysis", re.I)
_RE_10Q_NEXT = re.compile(r"item\s*[34]\.?\s*[\-–—:]?\s*(quantitative|controls)|part\s*ii\b", re.I)


def extract_10q_mdna(raw: str, cap: int = 12_000) -> Section | None:
    """10-Q Part I Item 2 (MD&A). 앵커: 'Management's Discussion' 을 가리키는 첫 TOC 앵커 → 다음 앵커 id 까지.
    폴백: 텍스트에서 제목 출현 중 다음 'Item 3/4' 까지 가장 긴 구간."""
    anchors: list[tuple[int, str]] = []  # (anchor pos, id)
    for m in _RE_ANCHOR.finditer(raw):
        anchors.append((m.start(), m.group(1)))
    ids_in_order: list[str] = []
    seen: set[str] = set()
    target: str | None = None
    for pos, aid in anchors:
        if aid not in seen:
            seen.add(aid)
            ids_in_order.append(aid)
        if target is None:
            label = _norm_label(raw[pos : raw.find("</a", pos) if raw.find("</a", pos) != -1 else pos + 400])
            if _RE_MDNA_TITLE.search(label) or _RE_MDNA_TITLE.search(_row_label(raw, pos)):
                target = aid
    if target:
        start = _id_position(raw, target)
        if start is not None:
            later = [
                p
                for p in (_id_position(raw, i) for i in ids_in_order if i != target)
                if p is not None and p > start
            ]
            end = min(later) if later else len(raw)
            text = html_to_text(raw[start:end])
            if len(text) > 500:
                truncated = len(text) > cap
                return Section("mdna", truncate_text(text, cap), "anchor", start, end, truncated)
    text = html_to_text(raw)
    best: tuple[int, int] | None = None
    for m in re.finditer(r"item\s*2\.?\s*[\-–—:]?\s*management['’]?s\s*discussion", text, re.I):
        ls = text.rfind("\n", 0, m.start()) + 1
        if m.start() - ls > 12:
            continue
        nxt = _RE_10Q_NEXT.search(text, m.end())
        end = nxt.start() if nxt else len(text)
        if best is None or end - m.start() > best[1] - best[0]:
            best = (m.start(), end)
    if best and best[1] - best[0] > 500:
        body = text[best[0] : best[1]].strip()
        return Section("mdna", truncate_text(body, cap), "regex", best[0], best[1], len(body) > cap)
    return None


def truncate_text(text: str, cap: int, tail_ratio: float = 0.0) -> str:
    """문단 경계에서 자른다. tail_ratio>0 이면 끝부분도 일부 남긴다 (MD&A 유동성 절 등)."""
    if len(text) <= cap:
        return text
    head_n = int(cap * (1 - tail_ratio))
    head = text[:head_n]
    cut = head.rfind("\n\n")
    if cut > head_n * 0.7:
        head = head[:cut]
    if tail_ratio <= 0:
        return head + f"\n\n[... 이하 생략 (원문 {len(text)}자) ...]"
    tail_n = cap - len(head)
    tail = text[-tail_n:]
    cut = tail.find("\n\n")
    if 0 <= cut < tail_n * 0.3:
        tail = tail[cut + 2 :]
    return head + f"\n\n[... 중간 생략 (원문 {len(text)}자) ...]\n\n" + tail
