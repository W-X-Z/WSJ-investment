from datetime import date

from wsj.util import chunked, normalize_name, parse_date, to_bool, to_num


def test_parse_date_formats():
    assert parse_date("2026-10-23") == date(2026, 10, 23)
    assert parse_date("20261023") == date(2026, 10, 23)
    assert parse_date("2026-10-16 11:56:37") == date(2026, 10, 16)
    assert parse_date("2026-10-16T11:56:37") == date(2026, 10, 16)
    assert parse_date("") is None
    assert parse_date("not a date") is None


def test_normalize_name():
    assert normalize_name("Ardelyx, Inc.") == "ARDELYX"
    assert normalize_name("ARDELYX INC") == "ARDELYX"
    assert normalize_name("The Kraft Heinz Company") == "KRAFT HEINZ"
    assert normalize_name("Kratos S2, Inc") == "KRATOS S2"
    assert normalize_name("Ocugen, Inc.") == normalize_name("OCUGEN INC")
    # 업종어는 기본적으로 남긴다 (정확 매칭용)
    assert normalize_name("Immunovant Therapeutics Inc") == "IMMUNOVANT THERAPEUTICS"
    assert normalize_name("Immunovant Therapeutics Inc", strip_industry_words=True) == "IMMUNOVANT"
    assert normalize_name(None) == ""


def test_small_helpers():
    assert to_bool("1") is True and to_bool("0") is False and to_bool(None) is None
    assert to_num("1,000.5") == 1000.5 and to_num("") is None
    assert list(chunked(range(5), 2)) == [[0, 1], [2, 3], [4]]
