"""Helpers for safely writing user-controlled values to spreadsheets."""

from typing import Any


def safe_excel_value(value: Any) -> Any:
    """Prevent spreadsheet formula execution while preserving typed values."""
    if value is None or isinstance(value, (int, float, bool)):
        return value if value is not None else ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text
