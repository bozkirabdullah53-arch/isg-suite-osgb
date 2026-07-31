"""RLS oturum değişkeni — boş allowed_company_ids sentinel."""

from app.core.rls import _allowed_csv


def test_allowed_csv_empty_uses_sentinel():
    assert _allowed_csv(None) == "-1"
    assert _allowed_csv([]) == "-1"


def test_allowed_csv_joins_ids():
    assert _allowed_csv([3, 7, 11]) == "3,7,11"
