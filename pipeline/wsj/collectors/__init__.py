"""수집기 레지스트리. 순서 = `--all` 실행 순서 (유니버스가 먼저)."""

from __future__ import annotations

from wsj.collectors.base import Collector


def all_collectors() -> list[Collector]:
    # 지연 import: 한 모듈의 import 에러가 전체를 막지 않도록
    from wsj.collectors.clinicaltrials import ClinicalTrialsCollector
    from wsj.collectors.finra import FinraCollector
    from wsj.collectors.openfda import OpenFdaCollector
    from wsj.collectors.sec_filings import SecFilingsCollector
    from wsj.collectors.sec_form4 import SecForm4Collector
    from wsj.collectors.sec_universe import SecUniverseCollector
    from wsj.collectors.usaspending import UsaSpendingCollector

    return [
        SecUniverseCollector(),
        SecForm4Collector(),
        SecFilingsCollector(),
        FinraCollector(),
        ClinicalTrialsCollector(),
        OpenFdaCollector(),
        UsaSpendingCollector(),
    ]


def get_collector(name: str) -> Collector:
    for c in all_collectors():
        if c.name == name:
            return c
    raise KeyError(name)
