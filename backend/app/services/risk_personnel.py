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
    "alan", "bolum", "risk", "tehlike", "kaynak", "maruziyet", "maruz",
    "uretim", "imalat", "eleman", "operator", "destek", "sorumlu", "teknisyen",
    "teknik", "genel", "tesis", "hat", "calisma", "gorev", "yardimci",
})


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().replace("ı", "i").split())


def words(value: object) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", fold(value)))


def specific_tokens(value: object) -> set[str]:
    # Turkish suffixes must not make generic titles informative again.
    return {w for w in words(value) if len(w) >= 3 and not any(
        w == generic or (len(generic) >= 4 and w.startswith(generic))
        for generic in _GENERIC
    )}


def overlap(left: set[str], right: set[str]) -> list[str]:
    return sorted({a for a in left for b in right if a == b or (
        min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))
    )})


def same_department(left: object, right: object) -> bool:
    a, b = words(left), words(right)
    if not a or not b:
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
        "job_tokens": specific_tokens(getattr(employee, "job_title", None)),
    }


def risk_scope(row: Any) -> dict:
    return {
        "row": row,
        "department": getattr(row, "department_name", None),
        "department_tokens": specific_tokens(getattr(row, "department_name", None)),
        "activity_tokens": specific_tokens(getattr(row, "activity", None)),
        "scope_tokens": specific_tokens(" ".join(str(getattr(row, field, None) or "") for field in (
            "risk_source", "hazard_detail", "risk_definition",
        ))),
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
    else:
        tokens = overlap(scope["department_tokens"], person["department_tokens"])
        if tokens:
            reasons.append("Bölüm terimi eşleşiyor: " + ", ".join(tokens))
    for key, label in (("activity_tokens", "Görev–faaliyet"), ("scope_tokens", "Görev–risk açıklaması")):
        tokens = overlap(person["job_tokens"], scope[key])
        if tokens:
            reasons.append(label + " eşleşmesi: " + ", ".join(tokens))
    return reasons


def personnel_exposure_match(row: Any, employees: Iterable[Any]) -> tuple[int, str, set]:
    scope = risk_scope(row)
    matched = {employee_key(e) for e in employees if match_reasons(scope, employee_scope(e))}
    return len(matched), "personnel_match" if matched else "unmatched", matched
