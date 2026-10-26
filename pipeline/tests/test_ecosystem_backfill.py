"""Regression tests: six-year backfill, provenance, dedupe, safe limits."""
import json
from datetime import date
from unittest.mock import patch

import pytest

from wsj.ecosystems import backfill


def test_doi_normalization_and_dedupe_are_not_independent_confirmation():
    day="2021-06-01T12:00:00+00:00"
    a=backfill.record(source="crossref",source_id="10.1234/ABC",ecosystem="hbm",
                      kind="paper",day="2020-01-01",title="HBM package",
                      url="https://api.crossref.org/works/10.1234/ABC",excerpt="abstract",
                      observed_at=day,doi="https://doi.org/10.1234/ABC")
    b=backfill.record(source="openalex",source_id="W1",ecosystem="hbm",
                      kind="paper",day="2020-01-01",title="HBM package",
                      url="https://api.openalex.org/works/W1",excerpt="long technical abstract",
                      observed_at=day,doi="10.1234/abc")
    assert backfill.normalize_doi(a["doi"])=="10.1234/abc"
    result=backfill.reconcile([a,b])
    assert len(result)==1
    assert result[0]["source"]=="openalex"
    assert result[0]["also_indexed_by"]==["crossref","openalex"]
    assert result[0]["not_a_live_trigger"]
    assert result[0]["historical_investor_observation_unverified"]


def test_crossref_pub_date_precision_conservative():
    assert backfill.pub_date({"issued":{"date-parts":[[2022]]}})=="2022-12-28"
    assert backfill.pub_date({"issued":{"date-parts":[[2022,1,4]]}})=="2022-01-04"
    assert backfill.pub_date({}) is None


def test_backfill_boundaries_reject_unbounded_queries(tmp_path):
    with pytest.raises(ValueError):
        backfill.run(out=tmp_path,since=2010,until=2026)
    with pytest.raises(ValueError):
        backfill.run(out=tmp_path,since=2020,until=2024,pages=100)


def test_historical_sec_archive_retrieval_includes_2020():
    root={"filings":{"recent":{"form":["10-Q"],"filingDate":["2024-05-01"],
       "accessionNumber":["0000123456-24-000001"],"primaryDocument":["p.htm"]},
       "files":[{"name":"CIK0000123456-submissions-001.json","filingFrom":"2019-01-01","filingTo":"2021-12-01"}]}}
    archive={"form":["10-K"],"filingDate":["2020-03-20"],
             "accessionNumber":["0000123456-20-000001"],"primaryDocument":["report.htm"]}
    with patch.object(backfill,"fetch_json",side_effect=[root,archive]) as get:
        rows,err=backfill.sec_filings("hbm","CAMT",123456,2020,2024,"2026-10-26T12:00:00+00:00",35)
    assert not err
    assert [x["published_at"] for x in rows]==["2024-05-01","2020-03-20"]
    assert any(x["source_id"].endswith("-20-000001") for x in rows)
    assert get.call_count==2


def test_backfill_persists_yearly_records_without_polluting_live_monitor(tmp_path):
    one=backfill.record(source="crossref",source_id="10.1234/test",ecosystem="hbm",
        kind="paper",day="2020-06-03",title="Wafer inspection",
        url="https://api.crossref.org/works/10.1234/test",excerpt="",
        observed_at="2026-10-26T12:00:00+00:00",doi="10.1234/test")
    with patch.object(backfill,"openalex",return_value=[]),patch.object(backfill,"crossref",return_value=[one]),patch.object(backfill,"federal",return_value=[]),patch.object(backfill.time,"sleep"):
        report=backfill.run(out=tmp_path,since=2020,until=2020,pages=1,per_page=1,sources=("openalex","crossref","federal"))
    assert report["records"]==1
    result=[json.loads(line) for line in (tmp_path/"hbm.jsonl").read_text().splitlines()]
    assert result[0]["published_at"]=="2020-06-03"
    assert result[0]["first_seen_at"]=="2026-10-26T12:00:00+00:00"
    assert result[0]["not_a_live_trigger"]
    assert (tmp_path/"summary.json").exists()
    assert (tmp_path/"optics.jsonl").exists()


def test_crossref_results_are_title_filtered():
    with patch.object(backfill,"fetch_json",return_value={
        "message":{"items":[{"DOI":"10.5555/hbm", "title":["HBM wafer packaging inspection"],
                            "published":{"date-parts":[[2021,4,2]]},"type":"journal-article"}]}
    }):
        rows=backfill.crossref("hbm",2021,"2026-10-26T12:00:00+00:00",35,1)
    assert len(rows)==1
    assert rows[0]["published_at"]=="2021-04-02"


def test_no_false_full_coverage_claim():
    report=backfill.create_summary([], [{"source":"openalex","error":"403"}],2020,2026,"today")
    assert report["status"]=="partial_with_errors"
    assert report["historical_period"]==[2020,2026]
