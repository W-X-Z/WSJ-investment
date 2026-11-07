"""증분 수요 엔진 — '이 사건이 부품별 지출을 얼마나 바꾸고, 그게 회사별 순이익·시총 대비 몇 %인가'.

숫자는 전부 입력 JSON 에서 온다 (도메인 숫자를 코드에 두지 않는다). 형식:

{
  "units": "USD bn; unit costs per GW",           # 표시용 라벨 (선택)
  "scenarios": {"base": {"TX": 11}, "event": {"DEST": 8, "evap_to_dry": 0.6}},   # 드라이버(또는 mix) → 수량
  "mixes": {                                        # (선택) 가중 묶음. 다른 mix 를 품을 수 있다 (순환 금지)
    "TX":   {"bldg": 1, "cool_evap": 0.30, "pwr_grid": 0.45, ...},
    "DEST": {"OK": 0.25, "LA": 0.15, ...}
  },
  "unit_costs": {"mv_swgr": {"bldg": 0.60}, "turbine": {"pwr_turb": 1.60}, ...},  # 부품 → {기초 드라이버: 단위당 금액}
  "suppliers": {"mv_swgr": {"ETN": 0.25, "FPS": 0.08}, ...},                     # 부품 → {회사: 점유율}
  "companies": {"ETN": {"margin": 0.25, "mcap": 129.9}, ...},                     # 증분 영업이익률, 시총(같은 금액 단위)
  "tax": 0.22,
  "sensitivities": {"low_reloc": {"scenarios.event.DEST": 5}, ...}               # (선택) 점 경로 → 값 '교체'
}

계산:
  수량(시나리오) → mix 를 풀어 기초 드라이버 수량 q_d
  지출[부품] = Σ_d q_d × unit_costs[부품][d];   Δ[부품] = 지출(event) − 지출(base)
  Δ매출[회사] = Σ_부품 Δ[부품] × 점유율;   Δ순이익 = Δ매출 × margin × (1 − tax);   Δ순이익 ÷ 시총
민감도: sensitivities 의 각 항목은 {'점.경로': 새 값} — 그 노드를 통째로 바꾼 사본으로 다시 계산한다.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from wsj.tools.context import ToolError


# ---------------------------------------------------------------- 입력 처리
def load_spec(path: str | Path) -> dict[str, Any]:
    import sys

    text = sys.stdin.read() if str(path) == "-" else Path(path).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError(f"JSON 을 읽을 수 없습니다: {exc}") from exc


def apply_overrides(spec: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """{'scenarios.event.DEST': 5, 'mixes.TX': {...}} → 해당 노드를 교체한 깊은 사본. 중간 노드가 없으면 만든다."""
    out = copy.deepcopy(spec)
    for path, value in overrides.items():
        keys = [k for k in str(path).split(".") if k]
        if not keys:
            raise ToolError(f"빈 경로: {path!r}")
        node = out
        for k in keys[:-1]:
            if not isinstance(node.get(k), dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = copy.deepcopy(value)
    return out


def resolve(quantities: dict[str, float], mixes: dict[str, dict[str, float]]) -> dict[str, float]:
    """mix 를 재귀로 풀어 기초 드라이버 수량으로. 순환이면 ToolError."""
    out: dict[str, float] = {}

    def walk(name: str, qty: float, stack: tuple[str, ...]) -> None:
        if name in stack:
            raise ToolError(f"mix 순환: {' → '.join(stack + (name,))}")
        if name in mixes:
            for child, w in mixes[name].items():
                walk(child, qty * float(w), stack + (name,))
        else:
            out[name] = out.get(name, 0.0) + qty

    for name, q in quantities.items():
        walk(name, float(q), ())
    return out


def spend(drivers: dict[str, float], unit_costs: dict[str, dict[str, float]]) -> dict[str, float]:
    return {comp: sum(drivers.get(d, 0.0) * float(c) for d, c in costs.items()) for comp, costs in unit_costs.items()}


def validate(spec: dict[str, Any]) -> list[str]:
    """치명적이면 ToolError, 아니면 경고 목록."""
    for k in ("scenarios", "unit_costs", "suppliers", "companies"):
        if not isinstance(spec.get(k), dict):
            raise ToolError(f"'{k}' 가 없습니다 (객체여야 합니다)")
    sc = spec["scenarios"]
    if "base" not in sc or "event" not in sc:
        raise ToolError("scenarios 에 base 와 event 가 둘 다 있어야 합니다")
    if not 0 <= float(spec.get("tax", 0.0)) < 1:
        raise ToolError("tax 는 0 이상 1 미만")
    warns = []
    mixes = spec.get("mixes") or {}
    prims = {d for costs in spec["unit_costs"].values() for d in costs}
    for name in ("base", "event"):
        for d in resolve(sc[name], mixes):
            if d not in prims:
                warns.append(f"scenario '{name}': driver '{d}' has no unit cost in any component (contributes 0)")
    for comp, shares in spec["suppliers"].items():
        if comp not in spec["unit_costs"]:
            warns.append(f"suppliers: component '{comp}' not in unit_costs (ignored)")
        tot = sum(float(v) for v in shares.values())
        if tot > 1 + 1e-9:
            warns.append(f"suppliers: shares for '{comp}' sum to {tot:.3f} > 1")
        for co in shares:
            if co not in spec["companies"]:
                warns.append(f"companies: '{co}' (supplier of {comp}) has no margin/mcap → net income null")
    for co, c in spec["companies"].items():
        if c.get("mcap") is not None and float(c["mcap"]) <= 0:
            warns.append(f"companies: '{co}' mcap ≤ 0 → ratio null")
    return sorted(set(warns))


# ---------------------------------------------------------------- 계산
def evaluate(spec: dict[str, Any]) -> dict[str, Any]:
    warns = validate(spec)
    mixes = spec.get("mixes") or {}
    uc = spec["unit_costs"]
    tax = float(spec.get("tax", 0.0))
    q_base = resolve(spec["scenarios"]["base"], mixes)
    q_event = resolve(spec["scenarios"]["event"], mixes)
    s_base, s_event = spend(q_base, uc), spend(q_event, uc)
    comps = []
    for comp in uc:
        d = s_event[comp] - s_base[comp]
        comps.append({"component": comp, "base": s_base[comp], "event": s_event[comp], "delta": d})
    comps.sort(key=lambda r: (-abs(r["delta"]), r["component"]))
    delta = {r["component"]: r["delta"] for r in comps}

    acc: dict[str, dict[str, Any]] = {}
    for comp, shares in spec["suppliers"].items():
        if comp not in delta:
            continue
        for co, sh in shares.items():
            a = acc.setdefault(co, {"rev": 0.0, "by": {}})
            v = delta[comp] * float(sh)
            a["rev"] += v
            a["by"][comp] = a["by"].get(comp, 0.0) + v
    rows = []
    for co, a in acc.items():
        info = spec["companies"].get(co) or {}
        m, cap = info.get("margin"), info.get("mcap")
        t = float(info.get("tax", tax))
        dni = a["rev"] * float(m) * (1 - t) if m is not None else None
        ratio = dni / float(cap) if dni is not None and cap is not None and float(cap) > 0 else None
        rows.append({"company": co, "d_revenue": a["rev"], "margin": m, "d_net_income": dni, "mcap": cap,
                     "d_ni_over_mcap": ratio, "d_ni_over_mcap_pct": ratio * 100 if ratio is not None else None,
                     "by_component": dict(sorted(a["by"].items(), key=lambda kv: -abs(kv[1])))})
    rows.sort(key=lambda r: (r["d_ni_over_mcap"] is None, -(r["d_ni_over_mcap"] or 0.0), r["company"]))
    return {"drivers": {"base": q_base, "event": q_event},
            "totals": {"base": sum(s_base.values()), "event": sum(s_event.values()),
                       "delta": sum(s_event.values()) - sum(s_base.values())},
            "components": comps, "companies": rows, "warnings": warns}


def run(spec: dict[str, Any], cases: list[str] | None = None, sensitivity: bool = True, top: int | None = None,
        include_drivers: bool = False) -> dict[str, Any]:
    """central(입력 그대로) + 민감도 케이스. cases 를 주면 그 케이스만."""
    sens = spec.get("sensitivities") or {}
    names = ["central"] + (list(sens) if sensitivity else [])
    if cases:
        unknown = [c for c in cases if c != "central" and c not in sens]
        if unknown:
            raise ToolError(f"없는 케이스: {', '.join(unknown)} (가능: central, {', '.join(sens)})")
        names = [n for n in names if n in cases] or cases
    base_spec = {k: v for k, v in spec.items() if k != "sensitivities"}
    results: dict[str, Any] = {}
    for n in names:
        s = base_spec if n == "central" else apply_overrides(base_spec, sens[n])
        r = evaluate(s)
        if not include_drivers:
            r.pop("drivers")
        results[n] = r
    table = []
    all_cos = {row["company"] for r in results.values() for row in r["companies"]}
    first = names[0]
    for co in all_cos:
        vals = {n: next((row["d_ni_over_mcap_pct"] for row in results[n]["companies"] if row["company"] == co), None)
                for n in names}
        table.append({"company": co, **vals})
    table.sort(key=lambda r: (r[first] is None, -(r[first] or 0.0), r["company"]))
    if top:  # 표를 다 만든 뒤에 자른다 (케이스마다 상위가 달라도 표는 완전하게)
        for r in results.values():
            r["companies"] = r["companies"][:top]
            r["components"] = r["components"][:top]
        table = table[:top]
    return {"units": spec.get("units"), "tax": spec.get("tax", 0.0), "cases": results,
            "sensitivity_table": {"metric": "d_net_income / mcap, %", "columns": names, "rows": table}}
