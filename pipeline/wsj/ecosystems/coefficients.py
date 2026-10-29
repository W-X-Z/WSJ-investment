"""워크로드 → 하드웨어 계수표 계산 (ADR-0026 T-4). 자료는 research/coefficients/workload_hardware.json.

    python -m wsj.ecosystems.coefficients            # 요약: 토큰당 KV, 사용량 증가율, 압축 속도, 희소성 지수
    python -m wsj.ecosystems.coefficients --json

메모리 테제가 묻는 것은 "사용량 증가 × 토큰당 강도" 의 곱이 어디로 가느냐다. 사용량(토큰/월)은 연 수 배로 늘지만
토큰당 KV 바이트는 구조(GQA → MLA → 교차층 공유) 와 정밀도(BF16 → FP8 → FP4) 로 줄어든다. 둘을 같은 표에 놓아야
'에이전트가 메모리를 더 쓴다' 가 숫자가 된다. 한 랩의 압축을 시장 전체로 일반화하지 않는다 — 행마다 모델을 적는다.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parents[3] / "research" / "coefficients" / "workload_hardware.json"
SCARCITY_WEIGHT = {"rationing": 2, "price_up": 1, "time_of_day": 1, "priority_tier": 1, "retire_capacity": 1, "price_down": -1, "free_expand": -1}


def load(path: Path = PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def kv_bytes_per_token(row: dict[str, Any]) -> float | None:
    """GQA/MHA: 2·L·H_kv·d·b, MLA: L·(r + d_rope)·b, 그 밖은 보고값."""
    if row.get("bytes_per_token_reported") is not None:
        return float(row["bytes_per_token_reported"])
    b = row.get("bytes_per_elem")
    if row.get("attention") == "gqa" and all(row.get(k) for k in ("layers", "kv_heads", "head_dim")) and b:
        return 2.0 * row["layers"] * row["kv_heads"] * row["head_dim"] * b
    if row.get("attention") == "mla" and all(row.get(k) for k in ("layers", "kv_lora_rank", "qk_rope_head_dim")) and b:
        return float(row["layers"] * (row["kv_lora_rank"] + row["qk_rope_head_dim"]) * b)
    return None


def _d(s: str) -> date:
    parts = [int(x) for x in s.split("-")]
    return date(parts[0], parts[1], parts[2] if len(parts) > 2 else 1)


def annual_growth(series: list[dict[str, Any]], metric: str, start: str | None = None, end: str | None = None) -> dict[str, Any] | None:
    """metric 의 두 점(기본: 처음·마지막) 사이 연율 배수."""
    pts = sorted((r for r in series if r["metric"] == metric), key=lambda r: _d(r["date"]))
    if start:
        pts = [p for p in pts if _d(p["date"]) >= _d(start)]
    if end:
        pts = [p for p in pts if _d(p["date"]) <= _d(end)]
    if len(pts) < 2:
        return None
    a, z = pts[0], pts[-1]
    years = (_d(z["date"]) - _d(a["date"])).days / 365.25
    if years <= 0 or a["value"] <= 0:
        return None
    mult = z["value"] / a["value"]
    return {"metric": metric, "from": a["date"], "to": z["date"], "multiple": round(mult, 2), "per_year": round(mult ** (1 / years), 2)}


def compression(rows: list[dict[str, Any]], models: list[str]) -> dict[str, Any] | None:
    """같은 계보의 모델들(시간순)의 토큰당 KV 감소 — 연율 배수(<1 이면 감소)."""
    pts = [(r, kv_bytes_per_token(r)) for r in rows if r["model"] in models]
    pts = sorted(((r, b) for r, b in pts if b), key=lambda x: _d(x[0]["date"]))
    if len(pts) < 2:
        return None
    (a, ba), (z, bz) = pts[0], pts[-1]
    years = (_d(z["date"]) - _d(a["date"])).days / 365.25
    return {"from": f"{a['model']} {a['date']} {ba:,.0f}B", "to": f"{z['model']} {z['date']} {bz:,.0f}B", "multiple": round(bz / ba, 4),
            "per_year": round((bz / ba) ** (1 / years), 3) if years > 0 else None}


def scarcity_index(events: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for e in events:
        out[e["date"][:7]] += SCARCITY_WEIGHT.get(e.get("kind", ""), 0)
    return dict(sorted(out.items()))


def summary(data: dict[str, Any]) -> dict[str, Any]:
    kv = [{"model": r["model"], "date": r["date"], "kv_bytes_per_token": kv_bytes_per_token(r), "verification": r.get("verification")} for r in data["arch_kv"]]
    usage = annual_growth(data["usage_series"], "google_tokens_per_month", "2025-05")
    comp = compression(data["arch_kv"], ["DeepSeek-V3 (FP8 KV)", "DeepSeek-V4-Flash", "DeepSeek-V4.1-Flash"])
    net = None
    if usage and comp and comp.get("per_year"):
        # 토큰당 KV 가 이 속도로 줄고 처리 토큰이 이 속도로 늘면, '처리 토큰에 비례하는 KV 트래픽' 의 연율 배수.
        # 상주 KV 는 동시 세션 × 컨텍스트에 비례하므로 이 값은 하한·상한이 아니라 방향 지표다.
        net = round(usage["per_year"] * comp["per_year"], 2)
    return {"kv_per_token": kv, "usage_growth": usage, "kv_compression_deepseek_line": comp,
            "kv_traffic_net_per_year": net, "scarcity_index_by_month": scarcity_index(data["scarcity_events"]["events"]),
            "caveats": ["압축 계보는 DeepSeek 한 랩 — 시장 전체가 아니다", "Google 토큰/월은 서버 측 처리량 — 추론 모델·긴 컨텍스트가 사용자 수요 없이도 키운다",
                        "agent_reported 행은 원문 재확인 전"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    s = summary(load())
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0
    print("토큰당 KV (bytes):")
    for r in s["kv_per_token"]:
        v = r["kv_bytes_per_token"]
        shown = f"{v:,.0f}" if v else "?"
        print(f"  {r['date']}  {r['model']:<28} {shown:>10}  [{r['verification']}]")
    u, c = s["usage_growth"], s["kv_compression_deepseek_line"]
    if u:
        print(f"사용량: Google 토큰/월 {u['from']}→{u['to']} {u['multiple']}배 (연 {u['per_year']}배)")
    if c:
        print(f"압축: {c['from']} → {c['to']} = {c['multiple']}배 (연 {c['per_year']}배)")
    if s["kv_traffic_net_per_year"] is not None:
        print(f"순 KV 트래픽 방향 (사용량 × 압축, 연): {s['kv_traffic_net_per_year']}배  ← 1 보다 작으면 사용량 증가가 압축에 먹힌다")
    print("희소성 지수 (월):", s["scarcity_index_by_month"])
    for cv in s["caveats"]:
        print("  주의:", cv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
