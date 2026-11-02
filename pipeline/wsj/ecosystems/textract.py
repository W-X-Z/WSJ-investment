"""웹 문서 → 본문 텍스트 (외부 라이브러리 없이). 단서 본문 저장과 페이지 변화 감지가 쓴다.

해석 작업이 원문을 다시 열지 않고 DB 에서 읽게 하려는 것이라, 완벽한 본문 추출보다 '사람이 읽을 문단'을 빠짐없이 모으는 데 둔다:
문단·목록·표·제목 블록의 글자만 모으고, 메뉴·머리말·꼬리말·스크립트는 버린다. 짧은 조각(메뉴 글자)은 버리되 숫자가 든 표 칸은 남긴다.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "iframe", "select", "template", "head"}
BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "td", "th", "blockquote", "pre", "dd", "dt", "figcaption", "caption", "article", "section", "div"}
LEAF = BLOCK - {"article", "section", "div"}
VOID = {"br", "hr", "img", "meta", "link", "input", "source", "wbr"}


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.cur: list[str] = []
        self.blocks: list[tuple[str, str]] = []
        self.tags: list[str] = []
        self.meta: dict[str, str] = {}
        self.title: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            a = dict(attrs)
            key = (a.get("property") or a.get("name") or "").lower()
            if key in ("og:description", "description", "og:title") and a.get("content"):
                self.meta.setdefault(key, a["content"] or "")
            return
        if tag == "title":
            self.in_title = True
        if tag in VOID:
            if tag == "br":
                self.cur.append(" ")
            return
        if tag in SKIP:
            self.skip += 1
            return
        if tag in BLOCK:
            self._flush()
            self.tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if tag in BLOCK:
            self._flush()
            if self.tags and self.tags[-1] == tag:
                self.tags.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        if not self.skip:
            self.cur.append(data)

    def _flush(self) -> None:
        t = " ".join("".join(self.cur).split())
        self.cur = []
        if t:
            self.blocks.append((self.tags[-1] if self.tags else "", t))


def _keep(tag: str, text: str) -> bool:
    if tag in ("h1", "h2", "h3", "h4", "h5"):
        return len(text) >= 4
    if tag in ("td", "th", "dd", "dt"):
        return len(text) >= 2 and (bool(re.search(r"\d", text)) or len(text) >= 20)
    if tag in LEAF:
        return len(text) >= 25
    return len(text) >= 80             # 문단 태그 밖의 글자 (div 에 바로 쓴 본문)


def extract_text(html: str, max_chars: int = 20_000) -> tuple[str, str]:
    """(제목, 본문). 본문은 블록을 빈 줄로 잇는다. 같은 블록이 되풀이되면 한 번만."""
    p = _Collect()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - 깨진 HTML 이라도 모은 데까지는 쓴다
        pass
    seen: set[str] = set()
    out: list[str] = []
    for tag, text in p.blocks:
        if not _keep(tag, text) or text in seen:
            continue
        seen.add(text)
        out.append(text)
    body = "\n\n".join(out)
    if len(body) < 200 and p.meta.get("og:description", p.meta.get("description")):
        body = (body + "\n\n" + p.meta.get("og:description", p.meta.get("description", ""))).strip()
    title = " ".join("".join(p.title).split()) or p.meta.get("og:title", "")
    return title[:400], body[:max_chars]
