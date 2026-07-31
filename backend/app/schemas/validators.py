from datetime import datetime
import re


def parse_optional_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise TypeError("Geçersiz tarih değeri.")
    s = value.strip()
    if not s or s in {"—", "-", "null", "undefined"}:
        return None
    if len(s) == 16 and "T" in s:
        s = f"{s}:00"
    if s.endswith("Z"):
        s = f"{s[:-1]}+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    tr = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$", s)
    if tr:
        day, month, year, hour, minute, second = tr.groups()
        return datetime(
            int(year),
            int(month),
            int(day),
            int(hour or 0),
            int(minute or 0),
            int(second or 0),
        )
    raise ValueError("Geçersiz tarih formatı. YYYY-MM-DD veya GG.AA.YYYY kullanın.")
