"""아이디어 판단 — 10점 근거 점수, 노출 순도, 가격 맥락, 확인 일정(watch) 정리·채점. ADR-0017.

점수는 '근거가 얼마나 강한가'이지 주가 전망이 아니다. 가격은 점수에 넣지 않고 '이미 움직인 폭'으로 따로 보여 준다.

  기업 직접 근거   0~4  주 기업 자신의 공시·실적·수주 날짜 (7일 4 · 14일 3 · 30일 2 · 60일 1)
  숫자 확인        0~1  기업 직접 근거에 원문에서 확인한 숫자가 있다
  병목·전환 구조   0~3  주 기업이 그래프의 병목/전환 경로 위에 있다 · 최근 30일 독립 이슈 2건+ · 병목 상태 관측치 또는 공급사 3곳 이하
  노출 순도        0~2  그 사업이 매출의 50%+ (2) · 20%+ (1) · 모름/그 밖 (0)
  반대 근거       −2~0  최근 30일 근거가 붙은 반대 근거 1건당 −1
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

STAR3_MIN_SCORE = 7
STAR1_MAX_SCORE = 2
WATCH_MAX_DAYS = 180     # 확인 일정은 6개월 안
WATCH_EXPIRE_DAYS = 14   # 기한을 넘기고 이만큼 지나도 채점이 없으면 '기한 지남'
WATCH_STATUS = {"pending", "hit", "miss", "void", "expired"}


def _d(s: Any) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


# ------------------------------------------------------------------ 그래프 구조
class Structure:
    """그래프에서 기업 → (공급하는 노드) → (그 노드로 완화되는 병목) 을 미리 계산한다."""

    def __init__(self, graph: dict[str, Any]) -> None:
        self.nodes = {n["id"]: n for n in graph["nodes"]}
        self.supplies: dict[str, set[str]] = defaultdict(set)      # company → 노드
        self.suppliers: dict[str, set[str]] = defaultdict(set)     # 노드 → 상장 공급사
        self.bottlenecks_of_node: dict[str, set[str]] = defaultdict(set)
        self.edge_confs: dict[tuple[str, str], float] = {}      # (a, b) 양방향 → 가장 높은 간선 확신도 (근거 등급 기준)
        onto = None
        try:
            from wsj.ecosystems.ontology import edge_confidence, load_ontology

            onto = load_ontology()
        except Exception:  # noqa: BLE001 - 온톨로지 파일이 없으면 등급 없이 0.5
            edge_confidence = None  # type: ignore[assignment]
        for e in graph["edges"]:
            rel = e.get("relation")
            c = float(e.get("confidence") or (edge_confidence(e, onto) if onto else 0.5))
            for k in ((e["from"], e["to"]), (e["to"], e["from"])):
                if c > self.edge_confs.get(k, 0.0):
                    self.edge_confs[k] = c
            if rel == "offered_by" and self.nodes.get(e["to"], {}).get("kind") == "company":
                self.supplies[e["to"]].add(e["from"])
                if (self.nodes[e["to"]].get("listing") or {}).get("ticker"):
                    self.suppliers[e["from"]].add(e["to"])
            elif rel in ("develops", "holds_ip") and self.nodes.get(e["from"], {}).get("kind") == "company":
                self.supplies[e["from"]].add(e["to"])
            elif rel == "mitigated_by" and self.nodes.get(e["from"], {}).get("kind") == "bottleneck":
                self.bottlenecks_of_node[e["to"]].add(e["from"])

    def bottlenecks(self, company: str) -> list[str]:
        out: set[str] = set()
        for n in self.supplies.get(company, ()):
            out |= self.bottlenecks_of_node.get(n, set())
            if self.nodes.get(n, {}).get("kind") == "bottleneck":
                out.add(n)
        return sorted(out)

    def min_suppliers(self, company: str) -> int | None:
        counts = [len(self.suppliers.get(n, ())) for n in self.supplies.get(company, ()) if self.suppliers.get(n)]
        return min(counts) if counts else None

    def label(self, nid: str) -> str:
        return re.split(r"\s+\(", (self.nodes.get(nid) or {}).get("label", nid))[0]

    def edge_conf(self, a: str, b: str) -> float | None:
        """두 노드가 간선(어느 방향이든)으로 이어져 있으면 그 확신도."""
        return self.edge_confs.get((a, b))


# ------------------------------------------------------------------ 가격 맥락
def price_key(node: dict[str, Any] | None) -> str | None:
    from wsj.ecosystems.prices import px_key

    lst = (node or {}).get("listing") or {}
    return px_key(lst.get("exchange"), lst.get("ticker"))


# 텐배거 후보의 출발 조건 (ADR-0017 개정 1): 아직 작은가 · 아직 안 갔는가. 숫자는 임시값 — 사용자가 정하면 바꾼다.
TENBAGGER_MCAP_USD = 3e9
TENBAGGER_MAX_FROM_LOW = 200.0   # 1년 저점 대비 +200% (= 3배) 미만
MIN_POINTS_FOR_RANGE = 120        # 고점·저점 대비를 믿으려면 최소 거래일 수


def tenbagger_check(mcap_usd: float | None, from_low: float | None) -> dict[str, Any]:
    """{candidate: True|False|None, reason}. 시총을 모르면 None (판단 보류)."""
    if mcap_usd is None:
        return {"candidate": None, "reason": "시가총액 미확인"}
    if mcap_usd > TENBAGGER_MCAP_USD:
        return {"candidate": False, "reason": f"시총 ${mcap_usd / 1e9:.1f}B > ${TENBAGGER_MCAP_USD / 1e9:.0f}B"}
    if from_low is not None and from_low >= TENBAGGER_MAX_FROM_LOW:
        return {"candidate": False, "reason": f"1년 저점 대비 {from_low:+.0f}% — 이미 {1 + from_low / 100:.1f}배"}
    return {"candidate": True, "reason": f"시총 ${mcap_usd / 1e9:.2f}B" + (f" · 저점 대비 {from_low:+.0f}%" if from_low is not None else " · 저점 대비 미확인")}


def price_context(prices: dict[str, dict[str, Any]], node: dict[str, Any] | None) -> dict[str, Any] | None:
    key = price_key(node)
    p = prices.get(key) if key else None
    if not p or p.get("close") is None:
        return None
    out = {k: (float(p[k]) if p.get(k) is not None else None)
           for k in ("close", "r1m", "r3m", "r12m", "from_high", "from_low", "vol_ratio", "market_cap_usd")}
    pts = int(p.get("points") or 0)
    if pts and pts < MIN_POINTS_FOR_RANGE:  # 이력이 몇 날뿐이면 고점·저점 대비는 뜻이 없다
        out["from_high"] = out["from_low"] = None
    out |= {"key": key, "as_of": str(p.get("as_of"))[:10], "points": pts or None}
    flags = []
    if out["from_low"] is not None and out["from_low"] >= TENBAGGER_MAX_FROM_LOW:
        flags.append(f"1년 저점 대비 {out['from_low']:+.0f}% — 이미 {1 + out['from_low'] / 100:.1f}배")
    elif out["r12m"] is not None and out["r12m"] >= 200:
        flags.append(f"12개월 {out['r12m']:+.0f}% — 이미 크게 오른 상태")
    if out["r1m"] is not None and out["r1m"] <= -25:
        flags.append(f"1개월 {out['r1m']:+.0f}% 급락")
    if out["r3m"] is not None and out["r3m"] <= -35:
        flags.append(f"3개월 {out['r3m']:+.0f}% — 근거와 어긋나면 설명이 필요")
    if out["vol_ratio"] is not None and out["vol_ratio"] >= 3:
        flags.append(f"거래량 평소의 {out['vol_ratio']:.1f}배")
    out["flags"] = flags
    out["tenbagger"] = tenbagger_check(out["market_cap_usd"], out["from_low"])
    return out


# ------------------------------------------------------------------ 관측치
def observations_for(nodes: set[str], indicators: list[dict[str, Any]], now: datetime, days: int = 120) -> list[dict[str, Any]]:
    cut = (now - timedelta(days=days)).date()
    out = []
    for i in indicators:
        if i.get("category") != "observation" or not set(i.get("nodes") or []) & nodes:
            continue
        d = _d(i.get("as_of"))
        if d and d >= cut:
            out.append({"indicator_id": i["indicator_id"], "label": i.get("label"), "unit": i.get("unit"), "as_of": d.isoformat(),
                        "value": float(i["value"]) if i.get("value") is not None else None, "source_url": i.get("source_url")})
    return sorted(out, key=lambda x: x["as_of"], reverse=True)


# ------------------------------------------------------------------ 점수
def company_names(st: Structure, cid: str | None) -> list[str]:
    """근거 제목에서 주 기업을 알아볼 이름들 — 영문 이름·첫 단어·티커·현지어 (층 표시가 없던 예전 근거용)."""
    if not cid:
        return []
    n = st.nodes.get(cid) or {}
    label = n.get("label") or ""
    base = re.split(r"\s+\(", label)[0]
    names = {base, base.split(" ")[0], str((n.get("listing") or {}).get("ticker") or "")}
    names |= set(re.findall(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]{2,}", label))
    try:
        from wsj.ecosystems.company_feed import native_names

        if native_names().get(cid):
            names.add(native_names()[cid])
    except Exception:  # noqa: BLE001
        pass
    return [x.lower() for x in names if x and (len(x) >= 3 or re.search(r"[\u3040-\u9fff\uac00-\ud7af]", x))]


def _is_direct(e: dict[str, Any], names: list[str]) -> bool:
    if e.get("rel"):
        return e["rel"] == "direct"
    return str(e.get("id", "")).startswith("S") and any(nm in str(e.get("title") or "").lower() for nm in names)


def _direct_dates(idea: dict[str, Any], names: list[str] | None = None) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for st in idea.get("chain") or []:
        for e in st.get("evidence") or []:
            if _is_direct(e, names or []) and e.get("date"):
                out.append((str(e["date"])[:10], e))
    return sorted(out, key=lambda x: x[0])


def exposure_of(idea: dict[str, Any]) -> dict[str, Any] | None:
    pc = next((c for c in idea.get("companies") or [] if c.get("id") == idea.get("primary_company")), None)
    ex = (pc or {}).get("exposure")
    if not isinstance(ex, dict):
        return None
    try:
        share = float(ex.get("share_pct"))
    except (TypeError, ValueError):
        return None
    if not 0 <= share <= 100:
        return None
    return {"share_pct": round(share, 1), "segment": (ex.get("segment") or "")[:60], "basis": (ex.get("basis") or "")[:160],
            "url": ex.get("url"), "as_of": ex.get("as_of")}


def assess(idea: dict[str, Any], st: Structure, issues: list[dict[str, Any]], indicators: list[dict[str, Any]],
           prices: dict[str, dict[str, Any]], now: datetime, fallback_direct: str | None = None) -> dict[str, Any]:
    today = now.date()
    primary = idea.get("primary_company")
    parts: dict[str, dict[str, Any]] = {}

    # 1) 기업 직접 근거
    names = company_names(st, primary)
    dd = _direct_dates(idea, names)
    last = dd[-1][0] if dd else fallback_direct
    age = (today - _d(last)).days if _d(last) else None
    pts = 4 if age is not None and age <= 7 else 3 if age is not None and age <= 14 else 2 if age is not None and age <= 30 else 1 if age is not None and age <= 60 else 0
    parts["company"] = {"pts": pts, "max": 4, "note": f"기업 직접 근거 {last} ({age}일 전)" if last else "주 기업 자신의 공시·실적·수주 근거 없음"}

    # 2) 숫자 확인 — 원문 확인 요약(note)이나 공시 제목에 숫자가 있는 기업 직접 근거
    nums = [e for _, e in dd if re.search(r"\d", str(e.get("note") or "")) or (e.get("tier") == "official_issuer" and re.search(r"\d{2,}", str(e.get("title") or "")))]
    parts["confirm"] = {"pts": 1 if nums else 0, "max": 1, "note": "원문에서 확인한 숫자 있음" if nums else "기업 근거의 숫자를 원문으로 확인하지 못함"}

    # 3) 병목·전환 구조
    bns = st.bottlenecks(primary) if primary else []
    idea_nodes = set(idea.get("nodes") or [])
    on_path = bool(bns) or any(st.nodes.get(n, {}).get("kind") in ("bottleneck", "technology") for n in idea_nodes)
    watch_nodes = set(bns) | idea_nodes | (st.supplies.get(primary, set()) if primary else set())
    cut = (today - timedelta(days=30)).isoformat()
    recent = [i for i in issues if str(i.get("latest_published_at") or i.get("last_seen") or "")[:10] >= cut and set(i.get("nodes") or []) & watch_nodes]
    pubs = {p for i in recent for p in (i.get("publishers") or [s.get("publisher") for s in i.get("sources") or []] or [i.get("issue_key")]) if p}
    obs = observations_for(set(bns) | idea_nodes, indicators, now)
    n_sup = st.min_suppliers(primary) if primary else None
    s_pts = int(on_path) + int(len(recent) >= 2 and len(pubs) >= 2) + int(bool(obs) or (n_sup is not None and n_sup <= 3))
    bits = []
    if bns:
        bits.append("병목: " + ", ".join(st.label(b) for b in bns[:2]))
    bits.append(f"최근 30일 관련 이슈 {len(recent)}건")
    if obs:
        bits.append(f"상태 관측치 {len(obs)}개")
    if n_sup is not None:
        bits.append(f"공급사 {n_sup}곳")
    parts["structure"] = {"pts": s_pts, "max": 3, "note": " · ".join(bits)}

    # 4) 노출 순도
    ex = exposure_of(idea)
    e_pts = 0 if not ex else 2 if ex["share_pct"] >= 50 else 1 if ex["share_pct"] >= 20 else 0
    parts["exposure"] = {"pts": e_pts, "max": 2,
                         "note": f"{ex['segment'] or '관련 사업'} 매출 비중 {ex['share_pct']:g}%" if ex else "관련 사업의 매출 비중 미확인"}

    # 5) 반대 근거 — 주 기업 자신에 관한 최근 반대 사실(가이던스 하향·수주 취소 등)만 깎는다. 업계 일반 위험을 성실히 적은 것은 깎지 않는다
    own_risks = sum(1 for r in idea.get("risks") or []
                    if any(str(e.get("date") or "")[:10] >= cut and _is_direct(e, names) for e in r.get("evidence") or []))
    parts["counter"] = {"pts": -min(2, own_risks), "max": 0,
                        "note": f"주 기업 자신의 최근 반대 사실 {own_risks}건" if own_risks else "주 기업 자신의 최근 반대 사실 없음"}

    score = max(0, min(10, sum(p["pts"] for p in parts.values())))
    node = st.nodes.get(primary) if primary else None
    return {"score": score, "parts": parts, "exposure": ex, "price": price_context(prices, node),
            "bottlenecks": [{"id": b, "label": st.label(b)} for b in bns[:4]], "observations": obs[:3],
            "anticipation": anticipation(idea, st, prices, now, last, fallback_direct),
            "computed_at": now.isoformat(timespec="seconds"), "version": 2}


# ------------------------------------------------------------------ 선행 추론 점수 (ADR-0017 개정 2)
# 온톨로지의 목적: 기술·산업의 변화가 생겼을 때 영향 관계를 따라가 '다음에 바뀔 기업'을 시장보다 먼저 찾는 것.
# 수주·계약은 주가에 즉시 반영된다 — 그래서 근거 점수(확신)와 별개로 '아직 반영되지 않았나·룸이 큰가'를 따로 센다.
#   경로 0–3: 변화 → … → 기업 경로가 그래프에 있고(근거 등급), 몇 단계 떨어져 있나
#   미반영 0–3: 기업 직접 근거가 아직 없고 주가·거래량이 움직이지 않았나
#   룸 0–2: 변화의 규모가 이 회사 매출에 비해 큰가 (LLM 이 근거 id 와 함께 추정, 시총이 크면 깎는다)
#   발현 0–2: 몇 분기 안에 숫자로 나타나나
ANTICIPATION_MAX_HOPS = 6


def path_confidence(st: Structure, path: list[str]) -> tuple[float | None, list[str]]:
    """노드 id 경로가 그래프 간선으로 이어지는지 — (최약 간선 확신도, 끊긴 구간)."""
    if not path or len(path) < 2:
        return None, []
    confs, broken = [], []
    for a, b in zip(path, path[1:]):
        c = st.edge_conf(a, b)
        if c is None:
            broken.append(f"{st.label(a)} → {st.label(b)}")
        else:
            confs.append(c)
    return (min(confs) if confs and not broken else None), broken


def anticipation(idea: dict[str, Any], st: Structure, prices: dict[str, dict[str, Any]], now: datetime,
                 direct_last: str | None, fallback_direct: str | None = None) -> dict[str, Any] | None:
    """LLM 이 적은 anticipation{trigger, path, mechanism, lead_quarters, effect{pct_of_revenue, basis, evidence}, priced_in} 을 검증·채점."""
    a = idea.get("anticipation") or ((idea.get("assessment") or {}).get("anticipation") if isinstance(idea.get("assessment"), dict) else None)
    if not isinstance(a, dict):
        return None
    primary = idea.get("primary_company")
    node = st.nodes.get(primary) if primary else None
    px = price_context(prices, node) or {}
    parts: dict[str, dict[str, Any]] = {}
    # 경로
    path = [p for p in (a.get("path") or []) if isinstance(p, str) and p in st.nodes]
    if path and path[-1] != primary and primary in st.nodes:
        path = path + [primary] if st.edge_conf(path[-1], primary) is not None else path
    conf, broken = path_confidence(st, path)
    hops = max(0, len(path) - 1)
    if conf is None or hops == 0:
        p_pts, p_note = 0, ("경로가 그래프 간선으로 이어지지 않음: " + "; ".join(broken[:2])) if broken else "변화 → 기업 경로 없음"
    else:
        p_pts = 3 if conf >= 0.8 else 2 if conf >= 0.6 else 1
        p_note = f"{hops}단계 경로, 최약 간선 확신도 {conf:.2f}"
    parts["path"] = {"pts": p_pts, "max": 3, "note": p_note}
    # 미반영
    last = direct_last or fallback_direct
    age = (now.date() - _d(last)).days if _d(last) else None
    r1m, vol, from_low = px.get("r1m"), px.get("vol_ratio"), px.get("from_low")
    moved = (r1m is not None and r1m >= 30) or (vol is not None and vol >= 3)
    if from_low is not None and from_low >= TENBAGGER_MAX_FROM_LOW:
        u_pts, u_note = 0, f"1년 저점 대비 {from_low:+.0f}% — 이미 반영"
    elif age is not None and age <= 30 and moved:
        u_pts, u_note = 0, f"기업 직접 근거 {age}일 전 + 주가 반응(1개월 {r1m:+.0f}%)" if r1m is not None else "기업 직접 근거 + 거래량 급증"
    elif age is not None and age <= 30:
        u_pts, u_note = 2, f"기업 직접 근거 {age}일 전이지만 주가는 아직 (1개월 {r1m:+.0f}%)" if r1m is not None else "기업 직접 근거 있음, 주가 미확인"
    elif moved:
        u_pts, u_note = 1, f"기업 근거는 없는데 주가가 움직임 (1개월 {r1m:+.0f}%)" if r1m is not None else "거래량 급증"
    elif px:
        u_pts, u_note = 3, f"기업 직접 근거 없음 · 1개월 {r1m:+.0f}%" if r1m is not None else "기업 직접 근거 없음 · 주가 조용"
    else:
        u_pts, u_note = 2, "기업 직접 근거 없음 · 주가 미수집"
    parts["unpriced"] = {"pts": u_pts, "max": 3, "note": u_note}
    # 룸
    eff = a.get("effect") if isinstance(a.get("effect"), dict) else {}
    try:
        pct = float(eff.get("pct_of_revenue")) if eff.get("pct_of_revenue") is not None else None
    except (TypeError, ValueError):
        pct = None
    mcap = px.get("market_cap_usd")
    if pct is None or not eff.get("basis"):
        r_pts, r_note = 0, "변화의 규모 대비 매출 비중 미추정"
    else:
        r_pts = 2 if pct >= 30 else 1 if pct >= 10 else 0
        if mcap is not None and mcap > 1e10 and r_pts:
            r_pts = min(r_pts, 1)
        r_note = f"변화 규모 ≈ 매출의 {pct:g}% ({str(eff.get('basis'))[:80]})" + (f" · 시총 ${mcap / 1e9:.1f}B" if mcap else "")
    parts["room"] = {"pts": r_pts, "max": 2, "note": r_note}
    # 발현 시점
    try:
        lq = int(a.get("lead_quarters")) if a.get("lead_quarters") is not None else None
    except (TypeError, ValueError):
        lq = None
    l_pts = 0 if lq is None else 2 if lq <= 2 else 1 if lq <= 4 else 0
    parts["lead"] = {"pts": l_pts, "max": 2, "note": f"숫자로 나타나기까지 약 {lq}분기" if lq is not None else "발현 시점 미추정"}
    score = max(0, min(10, sum(p["pts"] for p in parts.values())))
    return {"score": score, "parts": parts, "trigger": a.get("trigger"), "path": path, "path_labels": [st.label(n) for n in path],
            "hops": hops, "mechanism": str(a.get("mechanism") or "")[:300], "lead_quarters": lq,
            "effect": {"pct_of_revenue": pct, "basis": str(eff.get("basis") or "")[:160], "url": eff.get("url"), "as_of": eff.get("as_of")} if pct is not None else None,
            "priced_in": a.get("priced_in") if a.get("priced_in") in ("none", "partial", "full") else None}


def apply_star_rule(stars: int, score: int) -> tuple[int, str]:
    """★ 와 점수가 어긋나면 고친다: ★3 은 7점 이상, 2점 이하는 ★1."""
    if stars == 3 and score < STAR3_MIN_SCORE:
        return 2, f" (근거 점수 {score}/10 < {STAR3_MIN_SCORE} → ★2)"
    if stars >= 2 and score <= STAR1_MAX_SCORE:
        return 1, f" (근거 점수 {score}/10 → ★1)"
    return stars, ""


# ------------------------------------------------------------------ 확인 일정
def normalize_watch(items: list[Any], now: datetime, prev: list[Any] | None = None) -> list[dict[str, Any]]:
    """LLM 의 watch (문자열 또는 {what, due, metric, threshold, direction}) → 객체 목록. 같은 문구의 이전 채점은 이어받는다."""
    today = now.date()
    before = {str(w.get("what") if isinstance(w, dict) else w).strip(): w for w in prev or []}
    out = []
    for w in items or []:
        if isinstance(w, str):
            w = {"what": w}
        if not isinstance(w, dict) or not str(w.get("what") or "").strip():
            continue
        what = str(w["what"]).strip()[:200]
        due = _d(w.get("due"))
        if due and not (today - timedelta(days=WATCH_EXPIRE_DAYS) <= due <= today + timedelta(days=WATCH_MAX_DAYS)):
            due = None
        row = {"what": what, "due": due.isoformat() if due else None, "metric": (w.get("metric") or None), "threshold": (w.get("threshold") or None),
               "direction": w.get("direction") if w.get("direction") in ("strengthen", "weaken") else None, "status": "pending"}
        old = before.get(what)
        if isinstance(old, dict) and old.get("status") in WATCH_STATUS - {"pending"}:
            row |= {k: old.get(k) for k in ("status", "graded_at", "evidence_url", "grade_note") if old.get(k) is not None}
        out.append({k: v for k, v in row.items() if v is not None})
    return out[:4]


def expire_watch(items: list[Any], now: datetime) -> tuple[list[Any], bool]:
    """기한이 지나고 WATCH_EXPIRE_DAYS 동안 채점이 없으면 'expired'."""
    changed = False
    out = []
    for w in items or []:
        if isinstance(w, dict) and w.get("status", "pending") == "pending" and _d(w.get("due")) and _d(w["due"]) < now.date() - timedelta(days=WATCH_EXPIRE_DAYS):
            w = {**w, "status": "expired", "graded_at": now.date().isoformat(), "grade_note": "기한이 지나도록 확인되지 않음"}
            changed = True
        out.append(w)
    return out, changed


def apply_grades(existing: dict[str, dict[str, Any]], grades: list[dict[str, Any]], reg, now: datetime) -> dict[str, list[Any]]:
    """LLM 의 채점 [{idea_key, index|what, status: hit|miss|void, evidence: 'S12', note}] → idea_key 별 새 watch 목록."""
    out: dict[str, list[Any]] = {}
    for g in grades or []:
        key, status = g.get("idea_key"), g.get("status")
        if key not in existing or status not in ("hit", "miss", "void"):
            continue
        items = [dict(w) if isinstance(w, dict) else {"what": str(w), "status": "pending"} for w in out.get(key, existing[key].get("watch") or [])]
        idx = g.get("index")
        if not isinstance(idx, int):
            idx = next((i for i, w in enumerate(items) if w.get("what") == g.get("what")), None)
        if idx is None or not 0 <= idx < len(items):
            continue
        ev = reg.items.get(g.get("evidence")) if reg is not None and g.get("evidence") else None
        if status in ("hit", "miss") and ev is None:
            continue  # 적중·빗나감은 근거가 있어야 한다
        items[idx] |= {"status": status, "graded_at": now.date().isoformat(), "grade_note": str(g.get("note") or "")[:200]}
        if ev is not None:
            items[idx]["evidence_url"] = ev.url
        out[key] = items
    return out


def track_record(ideas: list[dict[str, Any]]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for x in ideas:
        for w in x.get("watch") or []:
            c[(w.get("status") if isinstance(w, dict) else None) or "pending"] += 1
    return dict(c)
