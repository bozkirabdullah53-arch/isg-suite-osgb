"""Personel cinsiyet alanının eski Excel değerleriyle uyumluluğu."""
from types import SimpleNamespace

import pytest

from app.api.exports import _gender_summary
from app.schemas.employee import normalize_gender


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Kadın", "Kadın"),
        ("KADIN", "Kadın"),
        ("KADİN", "Kadın"),
        ("K", "Kadın"),
        ("Bayan", "Kadın"),
        ("female", "Kadın"),
        ("Erkek", "Erkek"),
        ("ERKEK", "Erkek"),
        ("E", "Erkek"),
        ("Bay", "Erkek"),
        ("male", "Erkek"),
    ],
)
def test_normalize_gender_accepts_explicit_legacy_labels(value, expected):
    assert normalize_gender(value) == expected


def test_gender_summary_does_not_mark_explicit_legacy_values_as_missing():
    rows = [
        SimpleNamespace(gender=value)
        for value in ("Kadın", "K", "Bayan", "Erkek", "E", "Bay")
    ]

    assert _gender_summary(rows) == (3, 3, 0)


def test_normalize_gender_keeps_unknown_values_unknown():
    assert normalize_gender("Belirlenmedi") == "Belirlenmedi"
    assert normalize_gender("") is None
