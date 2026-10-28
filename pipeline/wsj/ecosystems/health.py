"""시스템 점검 — 데이터가 제대로 들어오고 판단이 쌓이는지. 개선 예약작업이 이 보고서에서 고칠 일을 고른다 (ADR-0017).

    python -m wsj.ecosystems.health --out health.json      # 공개 뷰(publishable 키)만 읽는다

항목: 수집기 실행 상태 · 지표 신선도(빈 지표 포함) · 가격 커버리지 · 그래프(끊긴 병목·가격 없는 거래소) · 노드 없는 이슈 ·
아이디어 점수 분포와 확인 일정 성적.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DAILY = {"issues", "company_feed", "prices", "ideas"}           # 매일 돌아야 하는 수집기
STALE_DAYS = {"daily": 5, "weekly": 14, "monthly": 75, "irregular": 120}  # 월간은 기준월 1일 + 발표(~40일) + 여유


def _d(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def report(graph: dict[str, Any], inputs: dict[str, list[dict[str, Any]]], now: datetime) -> dict[str, Any]:
    from wsj.ecosystems.assess import track_record
    from wsj.ecosystems.ontology import dead_end_bottlenecks
    from wsj.ecosystems.prices import listings

    today = now.date()
    problems: list[dict[str, Any]] = []

    # 1) 수집기
    runs = inputs.get("runs") or []
    by: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        by[r["collector"]].append(r)
    collectors = {}
    for name, rs in by.items():
        rs.sort(key=lambda r: str(r.get("started_at")), reverse=True)
        ok = [r for r in rs if r.get("status") == "succeeded"]
        fails = [r for r in rs if r.get("status") == "failed" and str(r.get("started_at"))[:10] >= (today - timedelta(days=7)).isoformat()]
        last_ok = str(ok[0]["started_at"])[:10] if ok else None
        collectors[name] = {"last_ok": last_ok, "fails_7d": len(fails), "last_error": (fails[0].get("error") or "")[:160] if fails else None}
        if name in DAILY and (not last_ok or _d(last_ok) < today - timedelta(days=2)):
            problems.append({"area": "data", "severity": 3, "what": f"수집기 {name} 이 2일 넘게 성공하지 못함", "detail": collectors[name]})
        elif fails and (not last_ok or str(fails[0]["started_at"]) > str(ok[0]["started_at"])):
            problems.append({"area": "data", "severity": 2, "what": f"수집기 {name} 최근 실행 실패", "detail": collectors[name]})
    for name in DAILY - set(by):
        problems.append({"area": "data", "severity": 2 if inputs.get("runs") else 1, "what": f"수집기 {name} 실행 기록 없음 (45일)"})

    # 2) 지표
    inds = inputs.get("indicators") or []
    stale, by_cat = [], Counter()
    for i in inds:
        by_cat[i.get("category")] += 1
        d = _d(i.get("as_of"))
        lim = STALE_DAYS.get(i.get("frequency") or "irregular", 60)
        if d and (today - d).days > lim:
            stale.append({"indicator_id": i["indicator_id"], "as_of": d.isoformat(), "frequency": i.get("frequency")})
    registered = inputs.get("indicator_registry") or []
    empty = sorted({r["indicator_id"] for r in registered} - {i["indicator_id"] for i in inds})
    if empty:
        problems.append({"area": "data", "severity": 2, "what": f"값이 하나도 없는 지표 {len(empty)}개", "detail": empty[:10]})
    if stale:
        problems.append({"area": "data", "severity": 1, "what": f"갱신이 늦은 지표 {len(stale)}개", "detail": stale[:10]})
    if not by_cat.get("observation"):
        problems.append({"area": "ontology", "severity": 2, "what": "병목 상태 관측치(observation)가 없다 — 병목이 조여지는지 숫자로 볼 수 없다"})

    # 3) 가격
    items, uncovered = listings(graph)
    prices = {p["ticker"]: p for p in inputs.get("prices") or []}
    fresh = {k for k, p in prices.items() if _d(p.get("as_of")) and (today - _d(p["as_of"])).days <= 7}
    by_market = defaultdict(lambda: [0, 0])
    for x in items:
        by_market[x.market][1] += 1
        if x.key in fresh:
            by_market[x.market][0] += 1
    price_cov = {m: f"{a}/{b}" for m, (a, b) in sorted(by_market.items())}
    if items and len(fresh) < 0.6 * len(items):
        problems.append({"area": "data", "severity": 2, "what": f"최근 7일 가격이 있는 상장사 {len(fresh)}/{len(items)}", "detail": price_cov})
    if uncovered:
        problems.append({"area": "data", "severity": 1, "what": "가격 출처가 없는 거래소", "detail": uncovered})

    # 4) 그래프·이슈
    dead = dead_end_bottlenecks(graph)
    if dead:
        problems.append({"area": "ontology", "severity": 3, "what": f"상장사로 이어지지 않는 병목 {len(dead)}개", "detail": dead})
    untagged = [i.get("title") for i in inputs.get("issues") or [] if not (i.get("nodes") or [])]
    if untagged:
        problems.append({"area": "ontology", "severity": 2, "what": f"노드가 없는 활성 이슈 {len(untagged)}건 — 별칭·노드 보강 필요", "detail": untagged[:8]})

    # 5) 아이디어 판단
    ideas = inputs.get("existing") or []
    scores = [((x.get("assessment") or {}).get("score")) for x in ideas]
    unscored = sum(1 for s in scores if s is None)
    tr = track_record(ideas)
    undated = sum(1 for x in ideas for w in x.get("watch") or [] if not (isinstance(w, dict) and w.get("due")))
    if unscored:
        problems.append({"area": "judgment", "severity": 1, "what": f"점수 없는 아이디어 {unscored}건 (0021 적용·다음 실행 후 채워짐)"})
    if undated:
        problems.append({"area": "judgment", "severity": 1, "what": f"날짜 없는 확인 일정 {undated}개 — 채점할 수 없다"})
    star3_low = [x["title"] for x in ideas if x.get("stars") == 3 and (x.get("assessment") or {}).get("score") is not None
                 and x["assessment"]["score"] < 7]
    if star3_low:
        problems.append({"area": "judgment", "severity": 2, "what": "점수 7 미만인 ★3", "detail": star3_low})

    problems.sort(key=lambda p: -p["severity"])
    return {"as_of": now.isoformat(timespec="seconds"), "problems": problems, "collectors": collectors,
            "indicators": {"by_category": dict(by_cat), "stale": len(stale), "empty": len(empty)},
            "prices": {"listed": len(items), "fresh_7d": len(fresh), "by_market": price_cov, "uncovered_exchanges": uncovered},
            "graph": {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "dead_end_bottlenecks": dead},
            "ideas": {"active": len(ideas), "scores": sorted(s for s in scores if s is not None), "track_record": tr},
            "issues": {"active": len(inputs.get("issues") or []), "untagged": len(untagged)}}


def load_inputs() -> dict[str, list[dict[str, Any]]]:
    from wsj.ecosystems.ideas import load_public_inputs, public_credentials
    from wsj.http import HttpClient

    url, key = public_credentials()
    inputs = load_public_inputs(url, key)
    http = HttpClient("WSJ-investment health", timeout=30, max_retries=1)
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    for name, view, sel in (("runs", "v_collector_runs", "*"), ("indicator_registry", "v_indicator_registry", "indicator_id")):
        try:
            inputs[name] = http.get_json(f"{url.rstrip('/')}/rest/v1/{view}", params={"select": sel, "limit": "5000"}, headers=headers)
        except Exception:  # noqa: BLE001 - 0021 전에는 없다
            inputs[name] = []
    http.close()
    return inputs


def markdown(rep: dict[str, Any]) -> str:
    sev = {3: "🔴", 2: "🟠", 1: "🟡"}
    lines = [f"# 시스템 점검 {rep['as_of'][:10]}", ""]
    for p in rep["problems"]:
        lines.append(f"- {sev.get(p['severity'], '·')} [{p['area']}] {p['what']}")
    lines += ["", f"가격: {rep['prices']['fresh_7d']}/{rep['prices']['listed']} · 그래프 {rep['graph']['nodes']} 노드 / {rep['graph']['edges']} 관계 · "
              f"아이디어 {rep['ideas']['active']}건, 확인 일정 {rep['ideas']['track_record']}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--md", type=Path)
    args = ap.parse_args(argv)
    from wsj.ecosystems.ontology import load_graph

    rep = report(load_graph(), load_inputs(), datetime.now(UTC))
    if args.out:
        args.out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if args.md:
        args.md.write_text(markdown(rep), encoding="utf-8")
    print(markdown(rep))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
