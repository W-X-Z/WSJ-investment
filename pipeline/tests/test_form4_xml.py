from datetime import date
from pathlib import Path

from wsj.parsers.form4_xml import parse_form4

FIX = Path(__file__).parent / "fixtures"


def test_nmhi_ten_percent_owner_purchases():
    p = parse_form4((FIX / "form4_nmhi_2026-10-23.xml").read_text())
    h = p.header
    assert h["document_type"] == "4"
    assert h["issuer_cik"] == 1947861
    assert h["issuer_ticker"] == "NMHI"
    assert h["owner_cik"] == 2160363
    assert h["is_ten_percent_owner"] is True and h["is_director"] is False
    assert h["period_of_report"] == date(2026, 8, 18)
    assert h["aff10b5one"] is False
    assert h["owner_count"] == 1
    assert "F1" in h["payload"]["footnotes"]

    assert len(p.rows) == 22
    first = p.rows[0]
    assert first["seq"] == 1 and first["table_type"] == "nonDerivative" and first["row_type"] == "transaction"
    assert first["transaction_code"] == "P"
    assert first["transaction_date"] == date(2026, 10, 6)
    assert first["shares"] == 1_000_000
    assert first["price_per_share"] == 0.0006
    assert first["acquired_disposed"] == "A"
    assert first["shares_owned_following"] == 103_000_000
    assert first["ownership_nature"] == "D"
    assert first["footnote_ids"] == ["F1", "F2"]
    assert all(r["transaction_code"] == "P" for r in p.rows)


def test_kodiak_officer_with_derivative_exercise():
    p = parse_form4((FIX / "form4_kod_2026-10-23.xml").read_text())
    h = p.header
    assert h["issuer_cik"] == 1468748
    assert h["is_officer"] is True
    assert h["officer_title"]
    deriv = [r for r in p.rows if r["table_type"] == "derivative"]
    assert len(deriv) == 1
    d = deriv[0]
    assert d["transaction_code"] == "M"
    assert d["conversion_or_exercise_price"] == 2.49
    assert d["expiration_date"] == date(2034, 8, 4)
    assert d["underlying_title"] == "Common Stock"
    assert d["underlying_shares"] == 30000
    assert d["footnote_ids"] == ["F9"]
    # seq 는 nonDerivative 다음에 이어진다
    assert d["seq"] == len(p.rows)
    nonderiv = [r for r in p.rows if r["table_type"] == "nonDerivative"]
    assert len(nonderiv) == 9


def test_rejects_non_ownership_document():
    import pytest

    with pytest.raises(ValueError):
        parse_form4("<html></html>")
