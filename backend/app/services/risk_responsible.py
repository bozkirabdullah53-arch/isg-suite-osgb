"""Deterministic risk-control responsible suggestions.

Suggestions are only an aid for the İSG specialist. When a person is chosen,
the API validates the company-scoped employee id and the specialist confirms
the final selection.
The heuristic intentionally uses transparent workplace facts (branch,
department, job title and risk text); it never invents a person or treats an
OSGB professional as the default implementer.
"""
from __future__ import annotations

from collections.abc import Iterable


def normalize_text(value: str | None) -> str:
    text = (value or "").strip().casefold()
    for source, target in (
        ("ı", "i"),
        ("ş", "s"),
        ("ğ", "g"),
        ("ü", "u"),
        ("ö", "o"),
        ("ç", "c"),
    ):
        text = text.replace(source, target)
    return " ".join(text.split())


_LEADERSHIP_TERMS = (
    "isveren",
    "isveren vekili",
    "genel mudur",
    "fabrika mudur",
    "isletme mudur",
    "tesis mudur",
    "saha mudur",
    "bolum mudur",
    "departman mudur",
    "teknik mudur",
    "bakim mudur",
    "santiye sef",
    "vardiya sef",
    "ekip basi",
    "ustabasi",
    "sorumlu",
    "amir",
    "sef",
    "supervizor",
    "yonetici",
)

_RISK_ROLE_TERMS = {
    "elektr": ("elektr", "enerji", "elektrik"),
    "makine": ("makine", "mekanik", "bakim", "teknik", "uretim"),
    "bakim": ("bakim", "mekanik", "elektr", "teknik", "makine"),
    "kimya": ("kimya", "laboratuvar", "boya", "solvent", "sds"),
    "yangin": ("yangin", "acil", "itfaiye", "tesis", "bakim"),
    "yuksek": ("santiye", "insaat", "saha", "iskele", "bakim", "teknik"),
    "insaat": ("santiye", "insaat", "saha", "iskele", "kalip", "teknik"),
    "depo": ("depo", "lojistik", "sevk", "stok", "ambar"),
    "forklift": ("forklift", "depo", "lojistik", "sevk", "ambar"),
    "ergonomi": ("insan kaynak", "ofis", "uretim", "ergonomi", "depo"),
    "gürült": ("uretim", "makine", "bakim", "teknik"),
    "gurult": ("uretim", "makine", "bakim", "teknik"),
    "toz": ("uretim", "boya", "kimya", "bakim", "cevre"),
}


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if term in text]


def _risk_terms(*values: str | None) -> list[str]:
    text = normalize_text(" ".join(value or "" for value in values))
    matched: list[str] = []
    for marker, terms in _RISK_ROLE_TERMS.items():
        if marker in text:
            matched.extend(terms)
    return list(dict.fromkeys(matched))


def score_responsible_candidate(
    employee,
    *,
    branch_id: int | None = None,
    department_name: str | None = None,
    activity: str | None = None,
    risk_definition: str | None = None,
    hazard_name: str | None = None,
    category_name: str | None = None,
) -> tuple[int, list[str]]:
    """Return a transparent suitability score and human-readable reasons."""
    title = normalize_text(getattr(employee, "job_title", None))
    department = normalize_text(getattr(employee, "department", None))
    requested_department = normalize_text(department_name)
    context = normalize_text(
        " ".join(
            value or ""
            for value in (activity, risk_definition, hazard_name, category_name)
        )
    )
    score = 0
    reasons: list[str] = []

    if branch_id is not None:
        employee_branch = getattr(employee, "branch_id", None)
        if employee_branch == branch_id:
            score += 35
            reasons.append("Seçilen şubede görevli")
        elif employee_branch is None:
            score += 5
            reasons.append("Firma genelinde görevli")

    if requested_department:
        if department and (
            department == requested_department
            or department in requested_department
            or requested_department in department
        ):
            score += 35
            reasons.append("Risk bölümüyle eşleşen departman")
        elif requested_department in title:
            score += 20
            reasons.append("Görev unvanında risk bölümü geçiyor")

    leadership = _contains_any(title, _LEADERSHIP_TERMS)
    if leadership:
        score += 28
        reasons.append("Uygulama yetkisi bulunan yönetici/sorumlu unvanı")

    matched_roles = _contains_any(context, _risk_terms(activity, risk_definition, hazard_name, category_name))
    if matched_roles and _contains_any(title, matched_roles):
        score += 25
        reasons.append("Görev alanı tespit edilen riskle ilişkili")
    elif matched_roles and _contains_any(department, matched_roles):
        score += 15
        reasons.append("Departmanı tespit edilen riskle ilişkili")

    if score == 0:
        score = 1
        reasons.append("Aynı işyerindeki aktif personel")
    return score, reasons


def rank_responsible_candidates(
    employees: Iterable,
    **context,
) -> list[tuple[object, int, list[str]]]:
    ranked = [
        (employee, *score_responsible_candidate(employee, **context))
        for employee in employees
    ]
    return sorted(
        ranked,
        key=lambda item: (
            -item[1],
            normalize_text(getattr(item[0], "full_name", None)),
            int(getattr(item[0], "id", 0) or 0),
        ),
    )
