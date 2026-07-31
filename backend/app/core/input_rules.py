"""Uygulama geneli tarih / metin giriş kuralları — saçma veya tutarsız veri engeli."""
from __future__ import annotations

import re
from datetime import date, timedelta

# Tipik anlamsız / test girdileri (küçük harf, TR karakter yok sayılır)
_PLACEHOLDER = frozenset({
    "test", "asdf", "qwerty", "xxx", "xxxx", "aaaa", "bbbb", "dddd",
    "yok", "yok.", "bilmiyorum", "bilmiyorum.", "---", "...", "n/a", "na",
    "deneme", "ornek", "örnek", "placeholder", "string", "null", "none",
})

_REPEAT = re.compile(r"^(.)\1{4,}$")  # aaaaa, 11111
_ONLY_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)
_HAS_LETTER = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĞğÜüŞşİıÇçÖö]", re.UNICODE)
_PERSON_OK = re.compile(
    r"^[A-Za-zÀ-ÖØ-öø-ÿĞğÜüŞşİıÇçÖö][A-Za-zÀ-ÖØ-öø-ÿĞğÜüŞşİıÇçÖö\s.'-]{1,158}$"
)


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def assert_meaningful_text(
    value: str | None,
    *,
    label: str,
    min_len: int = 2,
    required: bool = True,
    allow_digits_only: bool = False,
) -> str | None:
    text = clean_text(value)
    if not text:
        if required:
            raise ValueError(f"{label} zorunludur.")
        return None
    if len(text) < min_len:
        raise ValueError(f"{label} en az {min_len} karakter olmalıdır.")
    low = text.casefold()
    if low in _PLACEHOLDER:
        raise ValueError(f"{label} için anlamlı bir metin giriniz (test/saçma ifade kabul edilmez).")
    if _REPEAT.match(text) or _ONLY_PUNCT.match(text):
        raise ValueError(f"{label} için anlamlı bir metin giriniz.")
    if not allow_digits_only and text.isdigit():
        raise ValueError(f"{label} yalnızca rakamlardan oluşamaz.")
    if not allow_digits_only and not _HAS_LETTER.search(text) and not any(ch.isdigit() for ch in text):
        raise ValueError(f"{label} için anlamlı bir metin giriniz.")
    return text


def low_placeholder(text: str) -> bool:
    return text.casefold() in _PLACEHOLDER


def assert_person_name(value: str | None, *, label: str, required: bool = False) -> str | None:
    text = clean_text(value)
    if not text:
        if required:
            raise ValueError(f"{label} zorunludur.")
        return None
    if len(text) < 2:
        raise ValueError(f"{label} en az 2 karakter olmalıdır.")
    if text.isdigit() or low_placeholder(text):
        raise ValueError(f"{label} geçerli bir ad soyad olmalıdır.")
    if not _PERSON_OK.match(text):
        raise ValueError(f"{label} geçerli bir ad soyad olmalıdır (yalnızca harf ve boşluk).")
    return text


def assert_event_date(
    value: date | None,
    *,
    label: str = "Tarih",
    required: bool = True,
    earliest: date | None = None,
    allow_future_days: int = 0,
) -> date | None:
    if value is None:
        if required:
            raise ValueError(f"{label} zorunludur.")
        return None
    from datetime import datetime, timezone

    floor = earliest or date(2000, 1, 1)
    # Sunucu UTC ise TR “bugün” gelecek sayılmasın
    today = datetime.now(timezone.utc).date()
    ceiling = today + timedelta(days=max(0, allow_future_days))
    if value < floor:
        raise ValueError(f"{label} {floor.isoformat()} tarihinden önce olamaz.")
    if value > ceiling:
        if allow_future_days == 0:
            raise ValueError(f"{label} gelecekte olamaz.")
        raise ValueError(f"{label} en fazla {allow_future_days} gün ileri olabilir.")
    return value


def assert_date_order(
    earlier: date | None,
    later: date | None,
    *,
    earlier_label: str,
    later_label: str,
) -> None:
    if earlier and later and later < earlier:
        raise ValueError(f"{later_label}, {earlier_label} tarihinden önce olamaz.")
