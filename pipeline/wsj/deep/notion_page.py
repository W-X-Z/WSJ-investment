"""N24 — 리포트 JSON(deep.store 형식)을 노션 '리서치 리포트' 페이지 본문·속성으로 바꾼다.

게시는 노션 MCP 로 한다(오케스트레이터 예약작업). 여기서는 문자열만 만든다.
- 노션 마크다운에서 `$` 는 수식, `~` 는 취소선이 되므로 본문에서는 이스케이프한다.
- 주가 이슈 절 위에 차트 이미지를 둔다(`image` 에 file-upload:// 또는 https 주소).
- 끝에 '사용자 메모' 제목만 비워 둔다.
"""
from __future__ import annotations

import re
from typing import Any

HEADS: tuple[tuple[str, str], ...] = (
    ("profile", "종목 프로필"),
    ("price_story", "주가 이슈"),
    ("fundamentals", "펀더멘탈"),
    ("industry_peers", "산업 및 피어"),
    ("valuation", "밸류에이션"),
    ("future_value", "향후 밸류"),
    ("risks", "리스크"),
    ("estimates", "추정 (원문 아님)"),
)
MARKET_KO = {"us": "미국", "kr": "한국"}
_TAG = re.compile(r"<(?![bius]>|/[bius]>)")


def esc(text: str) -> str:
    t = (text or "").replace("\\", "\\\\").replace("$", "\\$").replace("~", "\\~")
    return _TAG.sub("&lt;", t)


def _link_title(title: str) -> str:
    return esc(title).replace("[", "(").replace("]", ")")[:110]


def markdown(spec: dict[str, Any], image: str | None = None, chart_caption: str = "1년 주가와 번호별 이슈") -> str:
    sec = spec.get("sections") or {}
    head, _, rest = esc(sec.get("summary", "")).partition("\n")
    out = [f'<callout icon="📌" color="gray_bg">\n<b>{head.strip()}</b>\n\n{rest.strip()}\n</callout>']
    if sec.get("conclusion"):
        out += ["## 결론", esc(sec["conclusion"])]
    for key, title in HEADS:
        if not sec.get(key):
            continue
        out.append(f"## {title}")
        if key == "price_story" and image:
            out.append(f'<image source="{image}">{esc(chart_caption)}</image>')
        out.append(esc(sec[key]))
    srcs = spec.get("sources") or []
    if srcs:
        lines = []
        for s in srcs:
            line = f"- [{_link_title(s.get('title') or s['url'])}]({s['url']})"
            if s.get("published_at"):
                line += f" · {s['published_at']}"
            lines.append(line)
        out.append(f'<toggle heading="h2">\n출처 ({len(srcs)})\n\n' + "\n".join(lines) + "\n</toggle>")
    out += ["---", "## 사용자 메모"]
    return "\n\n".join(out)


def properties(spec: dict[str, Any], report_id: str, market_cap_usd: float | None = None,
               candidate_page: str | None = None) -> dict[str, Any]:
    cand = spec.get("candidate") or {}
    props: dict[str, Any] = {
        "제목": spec["title"],
        "★": f"★{int(spec['stars'])}",
        "종목": spec["symbol"],
        "시장": MARKET_KO.get(spec.get("market", "us"), "미국"),
        "판단": spec.get("verdict", ""),
        "date:기준일:start": spec["as_of"],
        "date:기준일:is_datetime": 0,
        "리포트 ID": report_id,
    }
    if cand.get("id"):
        props["후보 ID"] = cand["id"]
    if market_cap_usd:
        props["시총(USD)"] = round(float(market_cap_usd))
    if candidate_page:
        props["후보"] = [candidate_page]
    return props


def page(spec: dict[str, Any], image: str | None = None, market_cap_usd: float | None = None,
         candidate_page: str | None = None) -> dict[str, Any]:
    from wsj.deep.store import report_id

    rid = report_id(spec.get("market", "us"), spec["symbol"], spec["as_of"])
    return {"report_id": rid,
            "properties": properties(spec, rid, market_cap_usd, candidate_page),
            "content": markdown(spec, image)}
