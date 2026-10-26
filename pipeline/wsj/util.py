"""작은 공용 함수. 외부 의존성 없음."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from datetime import date, datetime, timedelta
from typing import TypeVar

T = TypeVar("T")


def chunked(items: Iterable[T], size: int) -> Iterator[list[T]]:
    buf: list[T] = []
    for it in items:
        buf.append(it)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def dedupe(rows: list[dict], keys: Sequence[str]) -> list[dict]:
    """자연키가 같은 행은 마지막 것만 남긴다. 한 배치 안의 중복은 Postgres upsert 가 21000 으로 거부한다."""
    seen: dict[tuple, dict] = {}
    for r in rows:
        seen[tuple(r.get(k) for k in keys)] = r
    return list(seen.values())


def parse_date(value: str | None) -> date | None:
    """'2026-10-23', '20261023', '2026-10-23 11:56:37' → date. 실패하면 None."""
    if not value:
        return None
    v = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(v[: len(fmt) + 4] if "T" in fmt else v, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(v).date()
    except ValueError:
        return None


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def daterange(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def to_bool(value: str | int | None) -> bool | None:
    if value is None or value == "":
        return None
    return str(value).strip().lower() in ("1", "true", "yes")


def to_num(value: str | float | int | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


_SUFFIXES = (
    "INCORPORATED",
    "INC",
    "CORPORATION",
    "CORP",
    "COMPANY",
    "CO",
    "LIMITED",
    "LTD",
    "LLC",
    "LP",
    "PLC",
    "HOLDINGS",
    "HOLDING",
    "GROUP",
    "THE",
    "SA",
    "NV",
    "AG",
    "PHARMACEUTICALS",
    "PHARMACEUTICAL",
    "THERAPEUTICS",
    "BIOSCIENCES",
    "BIOSCIENCE",
    "TECHNOLOGIES",
    "TECHNOLOGY",
)
_PUNCT = re.compile(r"[^A-Z0-9 ]+")
_WS = re.compile(r"\s+")


def normalize_name(name: str | None, strip_industry_words: bool = False) -> str:
    """법인명 정규화 — 대문자, 구두점 제거, 법적 접미사 제거.

    strip_industry_words=True 면 PHARMACEUTICALS/THERAPEUTICS 같은 업종어까지 제거한다 (후보 탐색용).
    정확 매칭에는 False 를 쓴다.
    """
    if not name:
        return ""
    s = _PUNCT.sub(" ", name.upper().replace("&", " AND "))
    tokens = [t for t in _WS.split(s) if t]
    legal = set(_SUFFIXES[:16]) if not strip_industry_words else set(_SUFFIXES)
    while tokens and tokens[-1] in legal:
        tokens.pop()
    if tokens and tokens[0] == "THE":
        tokens.pop(0)
    return " ".join(tokens)
