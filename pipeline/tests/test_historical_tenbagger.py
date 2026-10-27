import json
from copy import deepcopy
from pathlib import Path

import pytest

from wsj.studies.historical_tenbagger import DEFAULT_INPUT, analyze_case, analyze_dataset


def _data():
    return json.loads(DEFAULT_INPUT.read_text(encoding="utf-8"))


def test_replay_all_public_signal_entries_have_sources():
    result = analyze_dataset(_data())
    assert result["count"] == 5
    assert result["non_predictive"] is True
    assert len(result["negative_controls"]) == 2
    assert {row["ticker"] for row in result["cases"]} == {"CELH", "SMCI", "CVNA", "APP", "ASTS"}
    assert result["median_ex_post_multiple"] == 8.385


@pytest.mark.parametrize(
    ("ticker", "expected"),
    [("CELH", 8.385), ("SMCI", 18.194), ("CVNA", 5.916), ("APP", 8.705), ("ASTS", 7.206)],
)
def test_retrospective_event_multiples(ticker, expected):
    data = _data()
    row = next(item for item in data["cases"] if item["ticker"] == ticker)
    assert analyze_case(row)["ex_post_multiple"] == expected


def test_no_information_time_travel():
    data = _data()
    sample = deepcopy(data["cases"][0])
    sample["post_signal_entry_date"] = sample["public_signal_date"]
    with pytest.raises(ValueError, match="event must predate"):
        analyze_case(sample)
    sample = deepcopy(data["cases"][0])
    sample["retrospective_evaluation_date"] = sample["public_signal_date"]
    with pytest.raises(ValueError, match="event must predate"):
        analyze_case(sample)


def test_reject_missing_source_and_predictive_claim():
    data = _data()
    sample = deepcopy(data["cases"][0])
    sample["entry_price_source"] = ""
    with pytest.raises(ValueError, match="source URL"):
        analyze_case(sample)
    data["non_predictive"] = False
    with pytest.raises(ValueError, match="retrospective"):
        analyze_dataset(data)


def test_no_duplicate_ticker():
    data = _data()
    data["cases"].append(deepcopy(data["cases"][0]))
    with pytest.raises(ValueError, match="Duplicate ticker"):
        analyze_dataset(data)
