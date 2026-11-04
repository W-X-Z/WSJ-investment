"""원본 페이지 변화 감지 (ADR-0030, 백로그 I-3) — 피드가 없는 원본(표준 위원회 문서 목록·규칙 개정 페이지·회의 자료·사양 페이지)을
하루 한 번 읽고, 지난번과 달라진 것만 단서로 만든다.

    python -m wsj.ecosystems.pages probe [--id jedec_jc45]      # 저장 없이 출처마다 링크·문단 수와 새 항목 예시

출처는 `research/sources/registry.json` 의 type `html_diff`(목록·문서 페이지)와 `html_list`(피드 없는 기사 목록). 단서 수집기(clues.run)가 부른다.
- 새로 생긴 링크는 하나씩 단서가 된다 (주소 = 그 링크, 제목 = 링크 글자). 문서 목록·기사 목록의 새 항목이 여기서 나온다.
- 링크가 아닌 본문 변화(조치 이력 한 줄, 사양 문단)는 페이지마다 '페이지 변경' 단서 하나로 모으고, 새로 생긴 줄을 본문으로 남긴다.
- 상태는 `ops.collector_state` 의 `page:<출처 id>` 에 줄 해시와 링크 목록만 둔다. 원문 전체는 저장하지 않는다 (공개 저장소에도 올리지 않는다).
- 처음 보는 페이지는 기준선만 저장하고 단서를 내지 않는다. 한 번에 새 링크가 너무 많으면(사이트 개편) 링크 단서 대신 페이지 변경 하나로 알린다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

log = logging.getLogger("wsj.ecosystems.pages")
PAGE_TYPES = {"html_diff", "html_list"}
MAX_NEW_LINKS = 30            # 페이지 하나에서 링크 단서로 내는 상한 — 넘으면 개편으로 보고 페이지 변경 하나로
MIN_LINK_TEXT = 6
OLD_ITEM_DAYS = 14            # 링크 글자에 적힌 날짜가 이보다 오래면 '새 항목'이 아니다 (목록이 밀려 다시 보인 옛 글)
SKIP_LINK = re.compile(r"^(?:mailto:|javascript:|tel:|#)|/(?:login|signin|register|cart|search|tag|category|author|page/\d+)(?:/|$)|\?(?:share|replytocom)=", re.I)
NAV_TEXT = re.compile(r"^(?:home|about|contact|privacy|terms|cookie|login|sign in|subscribe|read more|learn more|more|view all|see all|"
                      r"next|previous|prev|first|last|older|newer|older posts|newer posts|back|menu|search|"
                      r"english|español|한국어|日本語|中文|facebook|twitter|linkedin|youtube|rss|share|print|download|더 ?보기|다음|이전|"
                      r"첫 ?페이지|마지막 ?페이지|이전 ?페이지|다음 ?페이지|처음|맨 ?앞|맨 ?뒤|목록|전체 ?보기|상세 ?보기)$", re.I)
ARROWS = re.compile(r"[«»‹›<>→←↑↓…|]+")
# 링크 안 블록 요소 경계 — 카드형 목록(<a><div>분류</div><div>제목</div><div>날짜</div><span>Read More</span></a>)을 조각으로 나눈다
BLOCK_IN_LINK = {"div", "p", "span", "time", "small", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6"}
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_TEXT = re.compile(r"^(?:(?P<mon>[A-Za-z]{3,9})\.? (?P<d>\d{1,2}),? (?P<y>\d{4})|(?P<d2>\d{1,2}) (?P<mon2>[A-Za-z]{3,9})\.? (?P<y2>\d{4})|"
                       r"(?P<y3>\d{4})[-./](?P<m3>\d{1,2})[-./](?P<d3>\d{1,2})\.?)$")


def nav_text(text: str) -> bool:
    return bool(NAV_TEXT.match(" ".join(ARROWS.sub(" ", text or "").split())))


def parse_date_text(text: str) -> datetime | None:
    m = DATE_TEXT.match(" ".join((text or "").split()))
    if not m:
        return None
    try:
        if m["y3"]:
            return datetime(int(m["y3"]), int(m["m3"]), int(m["d3"]), tzinfo=UTC)
        mon = MONTHS.get((m["mon"] or m["mon2"] or "")[:3].lower())
        return datetime(int(m["y"] or m["y2"]), mon, int(m["d"] or m["d2"]), tzinfo=UTC) if mon else None
    except ValueError:
        return None


def link_parts(parts: list[str]) -> tuple[str, datetime | None]:
    """링크 안 조각들 → (제목, 날짜). 날짜·'Read More' 같은 조각을 떼고, 여러 조각이 남으면 네 단어 이상인 가장 긴 조각이 제목
    (카드의 분류 꼬리표 'Financial' 같은 것이 빠진다). 그런 조각이 없으면 제목 안의 강조(<span>HBM4</span> update)로 보고 잇는다."""
    segs = [" ".join(x.split()) for x in parts]
    segs = [x for x in segs if x]
    date = next((d for d in map(parse_date_text, segs) if d), None)
    rest = [x for x in segs if not parse_date_text(x) and not nav_text(x)]
    if not rest:
        return (" ".join(segs) if not date else ""), date
    longest = max(rest, key=len)
    return (longest if len(rest) == 1 or len(longest.split()) >= 4 else " ".join(rest)), date


@dataclass
class Snapshot:
    title: str = ""
    lines: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    dates: dict[str, datetime] = field(default_factory=dict)      # 링크 글자에 적혀 있던 날짜 (있을 때만)


class _Links(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.out: list[tuple[str, list[str]]] = []
        self._href: str | None = None
        self._parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("nav", "header", "footer", "script", "style", "noscript"):
            self.skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            self._href, self._parts = (href, [""]) if href and not self.skip else (None, [])
        elif self._href is not None and tag in BLOCK_IN_LINK:
            self._parts.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("nav", "header", "footer", "script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        if tag == "a" and self._href:
            self.out.append((self._href, self._parts))
            self._href = None
        elif self._href is not None and tag in BLOCK_IN_LINK:
            self._parts.append("")

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts[-1] += data


def norm_link(href: str, base: str) -> str | None:
    href = href.strip()
    if not href or SKIP_LINK.search(href):
        return None
    u = urlsplit(urljoin(base, href))
    if u.scheme not in ("http", "https"):
        return None
    return urlunsplit((u.scheme, u.netloc.lower(), u.path or "/", u.query, ""))


def snapshot(html: str, base: str) -> Snapshot:
    from wsj.ecosystems.textract import extract_text

    title, body = extract_text(html, max_chars=200_000)
    p = _Links(base)
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - 깨진 HTML 이라도 모은 데까지
        pass
    links: dict[str, str] = {}
    dates: dict[str, datetime] = {}
    for href, parts in p.out:
        u = norm_link(href, base)
        if not u or u.rstrip("/") == base.rstrip("/"):
            continue
        text, d = link_parts(parts)
        if len(text) < MIN_LINK_TEXT and not re.search(r"\.(?:pdf|docx?|xlsx?|zip|pptx?)$", u, re.I):
            continue
        if nav_text(text):
            continue
        if u not in links or len(text) > len(links[u]):
            links[u] = text
        if d:
            dates[u] = d
    lines = [ln.strip() for ln in body.split("\n\n") if ln.strip()]
    return Snapshot(title, lines, sorted(links.items()), dates)


def _h(s: str) -> str:
    return hashlib.sha1(" ".join(s.split()).lower().encode()).hexdigest()[:12]


def state_of(s: Snapshot) -> dict[str, Any]:
    return {"lines": sorted({_h(x) for x in s.lines}), "links": [u for u, _ in s.links], "n_lines": len(s.lines),
            "checked": datetime.now(UTC).isoformat()}


def diff(prev: dict[str, Any] | None, cur: Snapshot) -> tuple[list[str], list[tuple[str, str]]]:
    """(새 줄, 새 링크). 처음이면 둘 다 빈 목록 — 기준선만."""
    if not prev:
        return [], []
    old_lines, old_links = set(prev.get("lines") or []), set(prev.get("links") or [])
    new_links = [(u, t) for u, t in cur.links if u not in old_links]
    link_texts = [t for _, t in new_links if len(t) >= 8]
    new_lines = [x for x in cur.lines if _h(x) not in old_lines and not any(t in x for t in link_texts)]
    return new_lines, new_links


def to_clues(src: Any, page_url: str, cur: Snapshot, new_lines: list[str], new_links: list[tuple[str, str]], now: datetime | None = None):
    """새 링크 → 링크마다 단서, 새 줄 → 페이지 변경 단서 하나. (단서들, 본문 행들)"""
    from wsj.ecosystems.clues import Clue

    now = now or datetime.now(UTC)
    clues, bodies = [], []
    redesign = len(new_links) > MAX_NEW_LINKS
    if not redesign:
        for u, t in new_links:
            d = cur.dates.get(u)
            if d and d < now - timedelta(days=OLD_ITEM_DAYS):
                continue                      # 목록이 밀려 다시 보인 옛 글 — 새 소식이 아니다
            c = Clue(u, (t or u)[:400], f"{src.name} — 새 항목", d or now, src.id, src.name, src.kind, src.lang, src.region,
                     broad=src.broad, layer=src.layer)
            c.extra = {"page": page_url, "change": "new_link"} | ({"date_in_link": d.date().isoformat()} if d else {})
            clues.append(c)
    text = [x for x in new_lines if len(x) >= 20]
    if redesign:
        text = [f"(새 링크 {len(new_links)}개 — 개편이거나 대량 게시)"] + [t for _, t in new_links[:40]] + text
    if sum(len(x) for x in text) >= 60:
        key = hashlib.sha1("\n".join(text).encode()).hexdigest()[:10]
        url = f"{page_url}#changed-{now:%Y%m%d}-{key}"
        head = re.sub(r"\s+", " ", text[0])[:90]
        c = Clue(url, f"{src.name} 페이지 변경: {head}", "\n".join(text)[:500], now, src.id, src.name, src.kind, src.lang, src.region,
                 broad=src.broad, layer=src.layer)
        c.extra = {"page": page_url, "change": "text", "new_lines": len(text), "new_links": len(new_links)}
        clues.append(c)
        body = "\n\n".join(text)[:20_000]
        bodies.append({"url": url, "body": body, "chars": len(body), "status": "ok", "http_status": 200, "fetched_at": now.isoformat()})
    return clues, bodies


def collect_pages(http: Any, store: Any | None, sources: list[Any]) -> tuple[list[Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """페이지형 출처를 읽어 (단서, 본문 행, 저장할 상태 {collector: state}, 통계). 상태는 단서를 저장한 뒤에 쓴다 (commit_states)."""
    from wsj.ecosystems.sources import BROWSER_UA

    headers = {**BROWSER_UA, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"}
    clues, bodies, states = [], [], {}
    stats: dict[str, Any] = {"pages": {}, "failed": [], "baseline": []}
    for s in sources:
        if s.type not in PAGE_TYPES or not s.enabled:
            continue
        key = f"page:{s.id}"
        try:
            html = http.get_text(s.url, headers=headers)
            cur = snapshot(html, s.url)
        except Exception as exc:  # noqa: BLE001 - 페이지 하나가 죽어도 나머지는 계속
            stats["failed"].append({"id": s.id, "error": str(exc)[:160]})
            continue
        if not cur.lines and not cur.links:
            stats["failed"].append({"id": s.id, "error": "빈 페이지 (스크립트로 그리는 페이지?)"})
            continue
        prev = None
        if store is not None:
            try:
                prev = store.get_watermark(key) or None
            except Exception as exc:  # noqa: BLE001
                log.warning("state %s: %s", key, exc)
        new_lines, new_links = diff(prev, cur)
        got, b = to_clues(s, s.url, cur, new_lines, new_links)
        clues += got
        bodies += b
        states[key] = state_of(cur)
        if prev is None:
            stats["baseline"].append(s.id)
        stats["pages"][s.id] = {"links": len(cur.links), "lines": len(cur.lines), "new_links": len(new_links), "new_lines": len(new_lines), "clues": len(got)}
    return clues, bodies, states, stats


def commit_states(store: Any, states: dict[str, Any]) -> int:
    n = 0
    for key, st in states.items():
        try:
            store.set_watermark(key, st)
            n += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("state %s 저장 실패: %s", key, exc)
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe", help="저장 없이 출처마다 링크·문단 수와 예시")
    p.add_argument("--id", action="append")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from wsj.ecosystems.clues import load_registry
    from wsj.ecosystems.sources import BROWSER_UA
    from wsj.http import HttpClient

    http = HttpClient(BROWSER_UA["User-Agent"], timeout=25, max_retries=1)
    out = {}
    try:
        for s in load_registry():
            if s.type not in PAGE_TYPES or (args.id and s.id not in args.id):
                continue
            try:
                cur = snapshot(http.get_text(s.url, headers=BROWSER_UA), s.url)
                out[s.id] = {"enabled": s.enabled, "layer": s.layer, "links": len(cur.links), "lines": len(cur.lines),
                             "link_examples": [t for _, t in cur.links[:5]], "line_examples": [x[:80] for x in cur.lines[:3]]}
            except Exception as exc:  # noqa: BLE001
                out[s.id] = {"enabled": s.enabled, "error": str(exc)[:160]}
    finally:
        http.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 1 if any("error" in v or not v.get("lines") for v in out.values() if v.get("enabled")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
