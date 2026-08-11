from app.services.national_id_format import normalize_national_id


def test_normalize_excel_numeric_tckn_suffix():
    assert normalize_national_id("26230266894.0") == "26230266894"
    assert normalize_national_id("26230266894.00") == "26230266894"


def test_normalize_national_id_preserves_masked_and_formatted_values():
    assert normalize_national_id("262******94") == "262******94"
    assert normalize_national_id("262.302.668.94") == "262.302.668.94"
    assert normalize_national_id(None) == ""
