from copy import deepcopy
from urllib.error import HTTPError

import pytest

from wsj.studies import technology_evidence as study


def test_bounded_registry_and_unique_ids():
    ids = [q["id"] for q in study.QUERIES]
    assert len(ids) >= 10
    assert len(ids) == len(set(ids))
    assert {q["ticker"] for q in study.QUERIES} >= {"TMDX", "ASTS", "RKLB", "IONQ"}


def test_rejects_future_dated_publications():
    data = {"results": [
        {"id": "old", "publication_date": "2022-06-20", "display_name": "Before"},
        {"id": "new", "publication_date": "2022-07-20", "display_name": "After"},
    ]}
    rows, limitation = study.parse_records("openalex", data, "2022-06-30")
    assert len(rows) == 1 and rows[0]["id"] == "old"
    assert "Current" in limitation


def test_fda_supplement_filters_by_decision_date():
    payload = {"results": [
        {"pma_number": "P180051", "decision_date": "2021-09-03", "device_name": "OCS Heart"},
        {"pma_number": "P180051S001", "decision_date": "2022-04-27", "device_name": "OCS Heart DCD"},
        {"pma_number": "P180051S999", "decision_date": "2025-02-01", "device_name": "Future"},
    ]}
    rows, _ = study.parse_records("fda", payload, "2022-06-30")
    assert len(rows) == 2


def test_github_ignores_current_stars_and_future_created():
    payload = {"items": [
        {"full_name": "a/b", "created_at": "2023-01-01T00:00:00Z", "stargazers_count": 9999, "html_url": "https://github.com/a/b"},
        {"full_name": "a/c", "created_at": "2024-01-01T00:00:00Z"},
    ]}
    rows, _ = study.parse_records("github", payload, "2023-12-31")
    assert len(rows) == 1 and "stargazers_count" not in rows[0]


def test_usaspending_does_not_claim_award_date_was_public():
    rows, note = study.parse_records("usaspending", {"results": [{"Award ID": "A1", "Base Obligation Date": "2023-12-21"}]}, "2023-12-22")
    assert len(rows) == 1
    assert "not public availability" in note


def test_empty_is_not_technological_failure(monkeypatch):
    monkeypatch.setattr(study, "_request", lambda query: {"results": []})
    q = next(q for q in study.QUERIES if q["source"] == "openalex")
    result = study.run_probe(q)
    assert result["status"] == "empty" and result["count"] == 0
    assert result["availability_class"].startswith("retrospective")


def test_failure_is_reported_not_swallowed(monkeypatch):
    def fake(query):
        raise HTTPError(query["url"], 429, "too many requests", None, None)
    monkeypatch.setattr(study, "_request", fake)
    result = study.run_probe(study.QUERIES[0])
    assert result["status"] == "blocked_or_error"
    assert result["http_status"] == 429
    assert study.build_report([result])["statuses"]["blocked_or_error"] == 1


def test_all_sources_have_allowlisted_https_hosts():
    from urllib.parse import urlsplit
    for q in study.QUERIES:
        parts = urlsplit(q["url"])
        assert parts.scheme == "https"
        assert parts.hostname in study.ALLOWED_HOSTS
