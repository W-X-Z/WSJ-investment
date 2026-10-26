from datetime import date

from wsj.signals import rules


def _filing(adsh, cik, owner, officer=True, director=False, title="CFO"):
    return {
        "accession_no": adsh,
        "issuer_cik": cik,
        "owner_cik": owner,
        "owner_name": f"Owner {owner}",
        "is_officer": officer,
        "is_director": director,
        "officer_title": title,
        "file_url": "u",
    }


def _tx(adsh, d, code, shares, price, ad="A"):
    return {
        "accession_no": adsh,
        "row_type": "transaction",
        "table_type": "nonDerivative",
        "transaction_date": d,
        "transaction_code": code,
        "shares": shares,
        "price_per_share": price,
        "acquired_disposed": ad,
    }


def test_cluster_buy_requires_two_owners_within_window():
    filings = [_filing("a1", 100, 1), _filing("a2", 100, 2), _filing("a3", 100, 1)]
    txs = [
        _tx("a1", "2026-10-01", "P", 1000, 10),
        _tx("a2", "2026-10-05", "P", 2000, 10),
        _tx("a3", "2026-11-20", "P", 500, 10),  # 창 밖
    ]
    sigs = rules.insider_signals(filings, txs)
    kinds = sorted(s["kind"] for s in sigs)
    assert kinds == ["cluster_buy", "open_market_buy", "open_market_buy", "open_market_buy"]
    cluster = next(s for s in sigs if s["kind"] == "cluster_buy")
    assert cluster["payload"]["owners"] == 2
    assert cluster["payload"]["value"] == 30000
    assert cluster["signal_date"] == date(2026, 10, 5)
    assert cluster["source_key"] == "100:2026-10-01"


def test_single_owner_is_not_a_cluster_and_holder_buy_is_weaker():
    filings = [_filing("h1", 7, 9, officer=False, director=False, title=None)]
    txs = [_tx("h1", "2026-10-01", "P", 100000, 10)]
    sigs = rules.insider_signals(filings, txs)
    assert [s["kind"] for s in sigs] == ["holder_buy"]
    off = rules.insider_signals([_filing("o1", 7, 9)], [_tx("o1", "2026-10-01", "P", 100000, 10)])
    assert off[0]["strength"] > sigs[0]["strength"]


def test_sales_and_derivative_rows_ignored_for_buys():
    filings = [_filing("s1", 5, 1)]
    txs = [
        _tx("s1", "2026-10-01", "S", 1000, 10, ad="D"),
        {**_tx("s1", "2026-10-01", "P", 1, 1), "table_type": "derivative"},
    ]
    assert rules.insider_signals(filings, txs) == []


def test_filing_rules_map_items_and_forms():
    fl = [
        {
            "accession_no": "x1",
            "cik": 1,
            "form": "8-K",
            "items": ["1.01", "9.01"],
            "file_date": "2026-10-02",
            "display_names": ["A"],
        },
        {
            "accession_no": "x2",
            "cik": 1,
            "form": "424B5",
            "items": [],
            "file_date": "2026-10-03",
            "display_names": ["A"],
        },
        {
            "accession_no": "x3",
            "cik": 1,
            "form": "SCHEDULE 13D",
            "items": [],
            "file_date": "2026-10-04",
            "display_names": ["A"],
        },
        {
            "accession_no": "x4",
            "cik": 1,
            "form": "10-Q",
            "items": [],
            "file_date": "2026-10-05",
            "display_names": ["A"],
        },
    ]
    sigs = rules.filing_signals(fl)
    got = {(s["family"], s["kind"], s["direction"]) for s in sigs}
    assert got == {
        ("contract", "material_agreement", 1),
        ("dilution", "offering_424b5", -1),
        ("activist", "schedule_13d", 1),
    }


def test_score_candidates_needs_two_families_or_cluster():
    base = {"direction": 1, "strength": 3.0, "summary": "s", "url": None}
    sigs = [
        {**base, "cik": 1, "family": "insider", "kind": "open_market_buy", "signal_date": date(2026, 10, 1)},
        {
            **base,
            "cik": 1,
            "family": "contract",
            "kind": "material_agreement",
            "signal_date": date(2026, 10, 2),
        },
        {**base, "cik": 2, "family": "insider", "kind": "open_market_buy", "signal_date": date(2026, 10, 1)},
        {
            **base,
            "cik": 3,
            "family": "insider",
            "kind": "cluster_buy",
            "strength": 8.0,
            "signal_date": date(2026, 10, 1),
        },
        {
            **base,
            "cik": 3,
            "family": "dilution",
            "kind": "shelf_s3",
            "direction": -1,
            "signal_date": date(2026, 10, 3),
        },
        {
            **base,
            "cik": 4,
            "family": "insider",
            "kind": "open_market_buy",
            "signal_date": date(2026, 1, 1),
        },  # 창 밖
        {**base, "cik": 4, "family": "gov", "kind": "new_award", "signal_date": date(2026, 1, 2)},
    ]
    cands = rules.score_candidates(sigs, as_of=date(2026, 10, 26), window_days=90)
    by = {c["cik"]: c for c in cands}
    assert set(by) == {1, 3}
    assert by[1]["family_count"] == 2 and by[1]["score"] == 3.0 + 3.0 + 2.0
    assert by[3]["family_count"] == 1 and by[3]["risk_count_90d"] == 1 and by[3]["score"] == 8.0 - 0.5
    assert cands[0]["cik"] == 1  # 점수순
