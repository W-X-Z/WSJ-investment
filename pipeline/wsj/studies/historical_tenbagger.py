"""Historical, source-anchored event replay.

DOES NOT estimate forecast alpha or backtest a tradable strategy.
Evaluation end dates were retrospectively chosen; report upside with this limitation.
Run: python -m wsj.studies.historical_tenbagger
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path(__file__).resolve().parents[3] / "research" / "point_in_time_cases.json"


def analyze_case(case: dict[str, Any]) -> dict[str, Any]:
    event = date.fromisoformat(case["public_signal_date"])
    entry = date.fromisoformat(case["post_signal_entry_date"])
    evaluation = date.fromisoformat(case["retrospective_evaluation_date"])
    if not (event < entry < evaluation):
        raise ValueError(f"{case['ticker']}: public event must predate entry, which must predate exit")
    entry_price = float(case["split_adjusted_entry_close_usd"])
    evaluation_price = float(case["split_adjusted_evaluation_close_usd"])
    if not (0 < entry_price and 0 < evaluation_price):
        raise ValueError(f"{case['ticker']}: prices must be positive")
    for field in ("primary_source", "entry_price_source", "evaluation_price_source"):
        if not str(case.get(field, "")).startswith("https://"):
            raise ValueError(f"{case['ticker']}: source URL missing: {field}")
    multiple = evaluation_price / entry_price
    return {
        "ticker": case["ticker"],
        "pattern": case["pattern"],
        "public_signal_date": event.isoformat(),
        "entry_date": entry.isoformat(),
        "evaluation_date": evaluation.isoformat(),
        "calendar_days": (evaluation - entry).days,
        "entry_adjusted_close_usd": entry_price,
        "evaluation_adjusted_close_usd": evaluation_price,
        "ex_post_multiple": round(multiple, 3),
        "ex_post_return_pct": round((multiple - 1) * 100, 1),
        "hypothesis": case["hypothesis"],
        "primary_source": case["primary_source"],
        "price_sources": [case["entry_price_source"], case["evaluation_price_source"]],
        "important": "Retrospectively chosen evaluation date, not a tested exit rule",
    }


def analyze_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    if dataset.get("non_predictive") is not True:
        raise ValueError("Dataset must explicitly declare retrospective, non-predictive intent")
    rows = [analyze_case(c) for c in dataset["cases"]]
    if len({r["ticker"] for r in rows}) != len(rows):
        raise ValueError("Duplicate ticker case")
    return {
        "version": dataset["version"],
        "method": "Point-in-time event close to retrospectively selected evaluation close",
        "non_predictive": True,
        "survivorship_and_lookahead_warning": dataset["selection_bias_warning"],
        "count": len(rows),
        "median_ex_post_multiple": round(statistics.median(r["ex_post_multiple"] for r in rows), 3),
        "cases": rows,
        "negative_controls": dataset.get("negative_controls", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="기존 급등주 사례의 시점 고정 리플레이 (예측/백테스트 아님)")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="JSON 결과 파일, 없으면 표준 출력")
    args = parser.parse_args()
    dataset = json.loads(args.input.read_text(encoding="utf-8"))
    result = analyze_dataset(dataset)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
