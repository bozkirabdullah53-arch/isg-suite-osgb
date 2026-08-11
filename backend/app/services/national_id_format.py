"""Small, non-destructive formatting helpers for national identity values.

Excel can expose an 11-digit Turkish national identity number as a numeric
cell with a ``.0`` suffix.  The suffix is a serialization artefact, not part
of the identity value.  This module deliberately normalizes only that exact
shape and leaves masked or otherwise formatted values untouched.
"""
from __future__ import annotations

import re


_EXCEL_NUMERIC_TCKN = re.compile(r"^(?P<digits>\d{11})\.0+$")


def normalize_national_id(value: object | None) -> str:
    """Remove an Excel float suffix from an 11-digit identity value.

    Existing masked values (for example ``123******89``), dotted values, and
    all other strings are preserved as-is apart from surrounding whitespace.
    No database value is changed by this helper.
    """

    if value is None:
        return ""
    text = str(value).strip()
    match = _EXCEL_NUMERIC_TCKN.fullmatch(text)
    return match.group("digits") if match else text
