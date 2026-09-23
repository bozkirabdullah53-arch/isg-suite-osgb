"""Explainable personnel suggestions, shared by counts and the named roster.

Suggestions are not a measurement or a confirmed exposure record. No names,
national IDs or clinical data participate in matching.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


_GENERIC = frozenset({
    "ve", "veya", "ile", "icin", "olan", "olarak", "calisan", "calisanlar",
    "personel", "ekip", "is", "isi", "isci", "islem", "faaliyet", "proses",
    "alan", "bolum", "risk", "tehlike", "maruziyet", "maruz",
    "uretim", "imalat", "eleman", "operator", "destek", "sorumlu", "teknisyen",
    "teknik", "genel", "tesis", "hat", "calisma", "gorev", "yardimci",
    "ortak", "tum", "her", "diger", "uzman", "kontrol", "bakim", "hijyen",
    "hatti", "hatlar", "isletme", "fabrika", "saha", "tumu", "tamami",
})

# Explicit occupational variants, not arbitrary shared prefixes (halk/halkla).
# These aliases only produce candidates; they never confirm an exposure.
_TOKEN_ALIASES = {
    "kaynakci": "kaynak", "kaynakcilik": "kaynak",
    "elektrikci": "elektrik", "elektrikcilik": "elektrik",
    "temizlikci": "temizlik", "supurme": "temizlik",
    "sarjhane": "sarj", "desarjhane": "desarj",
}
_TASK_PHRASES = {("zemin", "yikama"): "temizlik", ("zemin", "temizligi"): "temizlik"}


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().replace("ı", "i").split())


def words(value: object) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", fold(value)))


def specific_tokens(value: object) -> set[str]:
    # Turkish suffixes must not make generic titles informative again.
    return {_TOKEN_ALIASES.get(w, w) for w in words(value) if len(w) >= 3 and not any(
        w == generic or (len(generic) >= 4 and w.startswith(generic))
        for generic in _GENERIC
    )}


def overlap(left: set[str], right: set[str]) -> list[str]:
    return sorted(left & right)


def task_tokens(value: object) -> set[str]:
    tokens = specific_tokens(value)
    parts = words(value)
    for phrase, token in _TASK_PHRASES.items():
        if any(parts[i:i + len(phrase)] == phrase for i in range(len(parts) - len(phrase) + 1)):
            tokens.add(token)
    return tokens


def same_department(left: object, right: object) -> bool:
    a = tuple(_TOKEN_ALIASES.get(w, w) for w in words(left))
    b = tuple(_TOKEN_ALIASES.get(w, w) for w in words(right))
    if not specific_tokens(left) or not specific_tokens(right):
        return False
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    # Whole words: Şarj must never match Deşarj by substring.
    return any(large[i:i + len(small)] == small for i in range(len(large) - len(small) + 1))


def employee_key(employee: Any) -> tuple[str, object, object]:
    eid = getattr(employee, "id", None)
    return ("employee", getattr(employee, "branch_id", None), eid) if eid is not None else ("object", None, id(employee))


def employee_scope(employee: Any) -> dict:
    return {
        "employee": employee,
        "department": getattr(employee, "department", None),
        "department_tokens": specific_tokens(getattr(employee, "department", None)),
        "job_tokens": task_tokens(getattr(employee, "job_title", None)),
    }


def risk_scope(row: Any) -> dict:
    return {
        "row": row,
        "department": getattr(row, "department_name", None),
        "department_tokens": specific_tokens(getattr(row, "department_name", None)),
        # Sources, hazards and consequences do not establish who performs a task.
        "activity_tokens": task_tokens(getattr(row, "activity", None)),
    }


def match_reasons(scope: dict, person: dict) -> list[str]:
    row, employee = scope["row"], person["employee"]
    if getattr(employee, "is_active", True) is False:
        return []
    company_id = getattr(row, "company_id", None)
    employee_company = getattr(employee, "company_id", None)
    if company_id is not None and employee_company is not None and company_id != employee_company:
        return []
    branch_id = getattr(row, "branch_id", None)
    if branch_id is not None and branch_id != getattr(employee, "branch_id", None):
        return []
    reasons = []
    if same_department(scope["department"], person["department"]):
        reasons.append("Bölüm bilgisi eşleşiyor: " + str(scope["department"]))
    tokens = overlap(person["job_tokens"], scope["activity_tokens"])
    if tokens:
        reasons.append("Görev–faaliyet adayı: " + ", ".join(tokens))
    return reasons


def personnel_exposure_match(row: Any, employees: Iterable[Any], *, prepared_employees=None) -> tuple[int, str, set]:
    scope = risk_scope(row)
    people = prepared_employees if prepared_employees is not None else (employee_scope(e) for e in employees)
    matched = {employee_key(person["employee"]) for person in people if match_reasons(scope, person)}
    return len(matched), "personnel_match" if matched else "unmatched", matched
