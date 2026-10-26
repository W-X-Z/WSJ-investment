"""Network-free unit tests for research monitor and time-preserving evidence states."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from wsj.ecosystems import monitor


def evidence(**changes):
    data = dict(origin="openalex", origin_id="https://openalex.org/W123", ecosystem="hbm",
                kind="paper", published_at="2026-10-20", url="https://api.openalex.org/works/W123",
                title="New HBM hybrid bonding reliability paper", excerpt="Bond yield improves under standard condition")
    data.update(changes)
    return monitor.public_event(**data)


def test_stable_source_fingerprint_and_url_allowlist():
    a = evidence()
    assert a["id"] == evidence()["id"]
    assert a["published_at"] == "2026-10-20"
    assert monitor.allowed_url("https://www.sec.gov/Archives/example")
    assert not monitor.allowed_url("https://attacker.example/steal")
    with pytest.raises(ValueError, match="Untrusted URL"):
        evidence(url="https://attacker.example")


def test_empty_state_dedupe_and_baseline():
    state = {"version": 1, "seen": {}, "initialized_at": None, "page_snapshots": {}, "run_history": []}
    now = "2026-10-26T09:00:00+00:00"
    events = [evidence()]
    first, updated = monitor.apply_observations(state, events, now, initial_run=True)
    assert first == []
    second, _ = monitor.apply_observations(updated, events, now, initial_run=False)
    assert second == []
    extra, _ = monitor.apply_observations(updated, [evidence(origin_id="other-id")], now)
    assert len(extra) == 1
    assert extra[0]["review_state"] == "unverified"


def test_abstract_reconstruction_respects_positions_and_limit():
    assert monitor.rebuild_abstract({"HyBrId": [0], "bonding": [1], "yield": [2]}) == "HyBrId bonding yield"
    assert monitor.rebuild_abstract({"ignored": [-1, 2001]}) == ""


def test_federal_extraction_never_claims_independent_supplier(monkeypatch):
    def response(url):
        assert "semiconductor" in url
        return {"results": [{
            "document_number": "2026-12345", "title": "Semiconductor advanced packaging funding",
            "publication_date": "2026-10-25", "abstract": "manufacturing of HBM memory chips",
            "html_url": "https://www.federalregister.gov/documents/2026/10/25/2026-12345/demo",
            "agencies": [{"name": "Department of Commerce"}],
        }]}
    monkeypatch.setattr(monitor, "fetch_url", response)
    out = monitor.harvest_federal("hbm", "2026-10-01")
    assert out[0]["kind"] == "regulatory"
    assert out[0]["source_group"] == "federal_register"
    assert "not verified" not in out[0]["title"].lower()


def test_openalex_filters_older_and_irrelevant(monkeypatch):
    def response(url):
        assert "abstract_inverted_index" in url
        return {"results": [{
            "id": "https://openalex.org/W111", "display_name": "HBM hybrid bonding study",
            "publication_date": "2026-10-23", "doi": "https://doi.org/example",
            "abstract_inverted_index": {"This": [0], "improves": [1], "yield": [2]},
        }, {
            "id": "https://openalex.org/W222", "display_name": "1980s HBM historical paper",
            "publication_date": "2025-01-01", "doi": None,
        }, {
            "id": "https://openalex.org/W333", "display_name": "A poem about the sky",
            "publication_date": "2026-10-23", "doi": None,
        }]}
    monkeypatch.setattr(monitor, "fetch_url", response)
    out = monitor.harvest_openalex("hbm", "2026-10-01")
    assert len(out) == 1
    assert "improves yield" in out[0]["excerpt"]
    assert out[0]["url"].endswith("/W111")


def test_official_website_snapshot_requires_a_previous_known_good_snapshot(monkeypatch):
    monkeypatch.setattr(monitor, "fetch_url", lambda *a, **k: "<html><nav>ignore</nav><main>IEEE 802.3dj 1.6 draft active</main></html>")
    page = monitor.SPEC_PAGES[0]
    events, baseline = monitor.harvest_page(page, None, "2026-10-26T00:00:00Z")
    assert events == []
    events, unchanged = monitor.harvest_page(page, baseline, "2026-10-26T00:01:00Z")
    assert events == []
    monkeypatch.setattr(monitor, "fetch_url", lambda *a, **k: "<html>IEEE 802.3dj 1.6 approved standard</html>")
    events, changed = monitor.harvest_page(page, baseline, "2026-10-26T00:02:00Z")
    assert len(events) == 1
    assert events[0]["published_at"] is None
    assert changed["digest"] != baseline["digest"]


def test_html_strip_and_highlights_have_bounds():
    raw = "<html><script>bad</script><nav>Ads</nav><p>HBM microbump sensitivity 0.1 micron</p></html>"
    text = monitor.strip_html(raw)
    assert "bad" not in text and "Ads" not in text
    assert "sensitivity" in text
    assert monitor.page_highlights(text, ("microbump",)) 


def test_hypotheses_are_unverified_not_picks():
    graph = json.loads(monitor.DEFAULT_GRAPH.read_text(encoding="utf-8"))
    events = [dict(evidence(), research_priority=3)]
    result = monitor.hypotheses_from_events(graph, events)
    assert len(result) == 1
    h = result[0]
    assert h["status"] == "discovery_not_verified"
    assert all("NOT verified" in x["basis"] for x in h["affected_company_candidates"])
    assert h["confirmed_evidence"] == [events[0]["url"]]
    assert "검증" in h["next_checks"][1]


def test_financing_forms_are_risk_events(monkeypatch):
    monkeypatch.setattr(monitor, "fetch_url", lambda url: {"filings": {"recent": {
        "form": ["S-3", "6-K", "8-K", "10-Q"],
        "filingDate": ["2026-10-24", "2026-10-23", "2026-05-01", "2026-10-21"],
        "accessionNumber": ["000123-26-000001", "000123-26-000002", "000123-26-000003", "000123-26-000004"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"],
    }}})
    result = monitor.harvest_sec("AEHR", "power", "2026-10-01", 123)
    assert len(result) == 3
    assert result[0]["kind"] == "financing"
    assert result[1]["kind"] == "company_filing"
    assert result[0]["url"].endswith("/00012326000001/a.htm")


def test_llm_never_required_for_rule_based_run(tmp_path, monkeypatch):
    graph = monitor.DEFAULT_GRAPH
    # All sources return empty data; first run initializes, second run continues with no fabricated signals.
    monkeypatch.setattr(monitor, "harvest_openalex", lambda *a: [])
    monkeypatch.setattr(monitor, "harvest_federal", lambda *a: [])
    monkeypatch.setattr(monitor, "sec_ticker_index", lambda: {})
    monkeypatch.setattr(monitor, "harvest_page", lambda page, old, at: ([], {"digest": "stable", "last_observed_at": at}))
    state = tmp_path / "state.json"
    first = monitor.run("watch", state_path=state, graph_path=graph, data_dir=tmp_path, no_ai=True)
    assert first["baseline_created"]
    second = monitor.run("daily", state_path=state, graph_path=graph, data_dir=tmp_path, no_ai=True)
    assert not second["baseline_created"]
    assert second["hypotheses_proposed"] == 0
    assert (tmp_path / "reports" / second["run_at"][:10]).with_suffix(".md").exists()
    assert "신규 투자 논제" in (tmp_path / "run-summary.md").read_text(encoding="utf-8")


def test_source_failure_is_visible_but_not_fabricated(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "harvest_openalex", lambda *a: [])
    monkeypatch.setattr(monitor, "harvest_federal", lambda *a: [])
    monkeypatch.setattr(monitor, "sec_ticker_index", lambda: {})
    def broken(page, old, when):
        if page["source_id"] == "ieee_802_3dj":
            raise RuntimeError("429 rate-limit")
        return [], {"digest": "safe", "last_observed_at": when}
    monkeypatch.setattr(monitor, "harvest_page", broken)
    report = monitor.run("watch", state_path=tmp_path / "s.json",
                         graph_path=monitor.DEFAULT_GRAPH, data_dir=tmp_path, no_ai=True)
    assert any(x["source"] == "official_ieee_802_3dj" for x in report["failures"])
    assert report["top_events"] == []
