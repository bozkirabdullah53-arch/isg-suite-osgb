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
_DOMAIN_TOKENS = frozenset({
    "aku", "akumulator", "batarya", "sarj", "sarjhane", "kursun", "lead",
    "oksit", "elektrolit", "asit", "hidrojen", "plaka", "pres",
})


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
        "department_id": getattr(employee, "department_id", None),
    }


def risk_scope(row: Any) -> dict:
    return {
        "row": row,
        "department": getattr(row, "department_name", None),
        "department_tokens": specific_tokens(getattr(row, "department_name", None)),
        # Sources, hazards and consequences do not establish who performs a task.
        "activity_tokens": task_tokens(getattr(row, "activity", None)),
        "scope_tokens": specific_tokens(" ".join(str(getattr(row, field, None) or "") for field in (
            "risk_source", "hazard_detail", "risk_definition", "affected_people", "affected_group",
        ))),
        "department_id": getattr(row, "department_id", None),
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
    if scope["department_id"] is not None and scope["department_id"] == person["department_id"]:
        reasons.append("Bölüm kaydı eşleşiyor")
    if same_department(scope["department"], person["department"]):
        reasons.append("Bölüm bilgisi eşleşiyor: " + str(scope["department"]))
    tokens = overlap(person["job_tokens"], scope["activity_tokens"])
    if tokens:
        reasons.append("Görev–faaliyet adayı: " + ", ".join(tokens))
    return reasons


def match_detail(row: Any, employee: Any) -> dict:
    """Return a conservative, explainable match without changing legacy counts."""
    scope = risk_scope(row)
    person = employee_scope(employee)
    company_id = getattr(row, "company_id", None)
    employee_company = getattr(employee, "company_id", None)
    if company_id is not None and employee_company is not None and company_id != employee_company:
        return {"matched": False, "level": "unmatched", "score": 0, "reasons": []}
    branch_id = getattr(row, "branch_id", None)
    if branch_id is not None and branch_id != getattr(employee, "branch_id", None):
        return {"matched": False, "level": "unmatched", "score": 0, "reasons": []}
    reasons = match_reasons(scope, person)
    score = 0
    activity_tokens = scope["activity_tokens"] | scope["scope_tokens"]
    person_domain = set(words(person["employee"].job_title)) | set(words(person["employee"].department))
    risk_domain = set(words(getattr(row, "activity", None))) | set(words(getattr(row, "risk_definition", None))) | set(words(getattr(row, "hazard_detail", None)))
    domain_overlap = sorted((person_domain & _DOMAIN_TOKENS) & (risk_domain & _DOMAIN_TOKENS))
    if not domain_overlap and (person_domain & {"aku", "batarya", "sarj", "sarjhane"}) and (risk_domain & {"kursun", "lead", "oksit", "elektrolit"}):
        domain_overlap = ["akü/kurşun görev ilişkisi"]
        score = 70
        reasons.append("Özel görev/tehlike terimi eşleşmesi: akü/kurşun görev ilişkisi")
    if not reasons and not domain_overlap:
        return {"matched": False, "level": "unmatched", "score": 0, "reasons": []}
    if domain_overlap and not reasons:
        reasons.append("Özel görev/tehlike terimi eşleşmesi: " + ", ".join(domain_overlap))
    if scope["department_id"] is not None and scope["department_id"] == person["department_id"]:
        score += 55
    elif same_department(scope["department"], person["department"]):
        score += 50
    elif overlap(scope["department_tokens"], person["department_tokens"]):
        score += 40
    job_overlap = overlap(person["job_tokens"], activity_tokens)
    if job_overlap:
        score += 55
    if domain_overlap:
        score += 20
        reasons.append("Özel görev/tehlike terimi eşleşmesi: " + ", ".join(domain_overlap))
    if not domain_overlap and any(
        min(len(left), len(right)) >= 4 and (left.startswith(right) or right.startswith(left))
        for left in person["department_tokens"]
        for right in scope["department_tokens"] | scope["activity_tokens"]
    ):
        score += 15
        reasons.append("Sektör/bölüm kök terimi eşleşmesi")
    level = "exact" if score >= 90 else "strong" if score >= 70 else "probable" if score >= 50 else "weak"
    return {"matched": level in {"exact", "strong", "probable"}, "level": level, "score": min(score, 100), "reasons": reasons}


def personnel_exposure_match(row: Any, employees: Iterable[Any], *, prepared_employees=None) -> tuple[int, str, set]:
    people = prepared_employees if prepared_employees is not None else [employee_scope(e) for e in employees]
    matched = {employee_key(person["employee"]) for person in people if match_detail(row, person["employee"])["matched"]}
    return len(matched), "personnel_match" if matched else "unmatched", matched
