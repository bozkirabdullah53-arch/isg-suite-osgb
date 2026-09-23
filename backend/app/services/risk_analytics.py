"""NACE + risk değerlendirmesi analitiği.

Bu servis yalnızca mevcut kayıtları okur. NACE profilindeki başlıkları aday
tehlike kaynağı olarak, RiskAssessment kayıtlarını ise işyerinde doğrulanmış
değerlendirme olarak ayrı tutar. Böylece NACE kodu hiçbir zaman otomatik risk
kaydı üretmez veya saha değerlendirmesinin yerine geçmez.
"""
from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from math import isfinite
import re
from typing import Any, Iterable, Mapping
import unicodedata


ANALYTICS_SCHEMA_VERSION = "risk-nace-analytics-v3"

RISK_TYPE_ORDER = ("physical", "chemical", "biological", "ergonomic", "psychosocial", "other")

RISK_TYPE_META: dict[str, dict[str, str]] = {
    "physical": {
        "label": "Fiziksel",
        "description": "Gürültü, titreşim, makine, elektrik, yangın ve benzeri fiziksel kaynaklar.",
        "color": "#0f766e",
    },
    "chemical": {
        "label": "Kimyasal",
        "description": "Kimyasal madde, solvent, boya, temizlik kimyasalı ve proses kaynaklı maruziyetler.",
        "color": "#ea580c",
    },
    "biological": {
        "label": "Biyolojik",
        "description": "Biyolojik etken, enfeksiyon, kan/vücut sıvısı ve zoonotik kaynaklar.",
        "color": "#7c3aed",
    },
    "ergonomic": {
        "label": "Ergonomik",
        "description": "Elle taşıma, tekrarlı iş, uygunsuz duruş, ekranlı araçlar ve kas-iskelet yükleri.",
        "color": "#2563eb",
    },
    "psychosocial": {
        "label": "Psikososyal",
        "description": "Stres, iş yükü, mobbing, şiddet, vardiya düzeni ve diğer psikososyal etkenler.",
        "color": "#db2777",
    },
    "other": {
        "label": "İnceleme bekleyen",
        "description": "Türü belirsiz veya kaynak kategorisiyle tehlike tanımı çelişen kayıtlar; uzman incelemesi gerekir.",
        "color": "#64748b",
    },
}


# Category and hazard evidence are evaluated separately. Conflicts are visible
# review items; an incidental word must not silently override a source category.
_BIOLOGICAL_TERMS = (
    "biyolojik",
    "biolojik",
    "enfeks",
    "bloodborne",
    "infectious",
    "zoonot",
    "biyogüven",
    "bakteri",
    "virüs",
    "parazit",
    "sharps",
    "kan ve vücut",
)
_CHEMICAL_TERMS = (
    "kimyasal",
    "chemical",
    "solvent",
    "kurşun",
    "boya",
    "vernik",
    "yapıştır",
    "reaktör",
    "sds",
    "pestisit",
    "pesticide",
    "asit",
    "toxic",
    "zehir",
    "chemical",
    "refrigerant",
    "tehlikeli madde",
)
_PSYCHOSOCIAL_TERMS = (
    "psikososyal",
    "psikolojik",
    "psychosocial",
    "psychological",
    "stres",
    "stress",
    "mobbing",
    "tukenmis",
    "burnout",
    "siddet",
    "violence",
    "is yuku",
    "workload",
    "vardiya",
    "shift",
    "yalniz calisma",
    "lone work",
    "gece calisma",
    "night work",
    "catisma",
    "conflict",
)
_ERGONOMIC_TERMS = (
    "ergonom",
    "ergonomic",
    "manual handling",
    "elle tasima",
    "el ile tasima",
    "kas iskelet",
    "muskuloskeletal",
    "postur",
    "duruş",
    "durus",
    "tekrarl",
    "repetitive",
    "ekranli arac",
    "display screen",
    "agir kaldirma",
    "monoton",
    "bedensel zorlanma",
)
_PHYSICAL_TERMS = (
    "fiziksel",
    "mekanik",
    "elektrik",
    "gürült",
    "gurult",
    "titreşim",
    "titresim",
    "termal",
    "sıcak",
    "sicak",
    "soğuk",
    "soguk",
    "radyasyon",
    "makine",
    "yüksekte",
    "yuksekte",
    "trafik",
    "forklift",
    "iskele",
    "kazı",
    "kazi",
    "inşaat",
    "insaat",
    "yangın",
    "yangin",
    "patlama",
    "atex",
    "düşme",
    "dusme",
    "çarpış",
    "carpis",
    "machinery",
    "electrical",
    "noise",
    "vibration",
    "height",
    "fire",
    "explosion",
    "traffic",
    "lifting",
)

# Counts and the named roster use the same explainable matcher.
from app.services.risk_personnel import employee_scope, personnel_exposure_match as _personnel_exposure_match


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().replace("ı", "i").split())


def classify_hazard_type(*values: object) -> str:
    """Compatibility wrapper; all callers share the conflict-aware policy."""
    return classify_hazard_details(*values)["hazard_type"]


def _term_pattern(term: str) -> str:
    normalized = _fold(term)
    stems = {"enfeks", "zoonot", "biyoguven", "yapistir", "zehir", "tukenmis",
             "ergonom", "tekrarl", "gurult", "carpis"}
    suffix = r"[a-z]*" if normalized in stems else r"(?:i|in|ini|inin|a|e|da|de|dan|den|ta|te|tan|ten|li|lu|le|la|ler|lar|leri|lari|nin|nun|si|su)?"
    return r"(?<![a-z0-9])" + re.escape(normalized) + suffix + r"(?![a-z0-9])"


_TYPE_PATTERNS = {
    kind: re.compile("|".join(_term_pattern(term) for term in terms))
    for kind, terms in (
        ("biological", _BIOLOGICAL_TERMS), ("chemical", _CHEMICAL_TERMS),
        ("psychosocial", _PSYCHOSOCIAL_TERMS), ("ergonomic", _ERGONOMIC_TERMS),
        ("physical", _PHYSICAL_TERMS),
    )
}


def _text_types(value: object) -> frozenset[str]:
    return _cached_text_types(_fold(value))


@lru_cache(maxsize=4096)
def _cached_text_types(text: str) -> frozenset[str]:
    # Strip labelled consequences, including imported multiline risk definitions.
    text = re.split(r"\b(?:olasi\s+sonuc\w*|sonuc\w*|consequences?)\s*:", text, maxsplit=1)[0]
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return frozenset(kind for kind, pattern in _TYPE_PATTERNS.items() if pattern.search(text))


def classify_hazard_details(category=None, hazard=None, activity=None, definition=None) -> dict:
    category_types = _text_types(category)
    # A named hazard is more specific than the operation in which it occurs.
    # Activity/definition are fallback evidence, never a reason to override it.
    hazard_types = _text_types(hazard)
    evidence_types = hazard_types or (_text_types(activity) | _text_types(definition))
    candidates = category_types | evidence_types
    ordered = [kind for kind in RISK_TYPE_ORDER if kind in candidates]
    conflict = len(candidates) > 1
    kind = ordered[0] if len(ordered) == 1 else "other"
    status = "review_required" if conflict else ("category" if category_types else "inferred" if ordered else "unclassified")
    if conflict:
        note = f"Kaynak kategori: {category or 'Belirtilmemiş'}. Metinde birden fazla tür işareti var: {', '.join(RISK_TYPE_META[k]['label'] for k in ordered)}. Kaynak kaydı ve tehlike etkenini kontrol edin; tür kesinleştirilmedi."
    elif not ordered:
        note = "Tehlike türünü belirlemek için yeterli etken/kategori bilgisi yok; kaynak kaydı kontrol edin."
    elif category_types:
        note = "Kaynak kategorisi esas alındı; saha doğrulaması yerine geçmez."
    else:
        note = "Tehlike/faaliyet metninden tür önerisi; kaynak kategorisini doğrulayın."
    return {"hazard_type": kind, "classification_status": status,
            "classification_candidates": ordered, "classification_note": note}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _safe_count(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _unique_exposure_count(
    matched_keys: set[tuple[str, object, object]],
    reported_count: int,
    assignment_count: int,
    *,
    personnel_available: bool,
    employee_cap: int,
) -> int:
    """Estimate a de-duplicated count without ever exceeding the workforce.

    Risk rows do not store employee IDs for manually reported counts, so those
    rows cannot be perfectly de-duplicated. When personnel rows are available,
    the known employee set is preferred and an explicit count is used only as
    a conservative lower-information fallback. The visible result is always
    bounded by the active workforce.
    """

    if personnel_available:
        estimate = max(len(matched_keys), _safe_count(reported_count))
    else:
        estimate = _safe_count(assignment_count)
    if employee_cap > 0:
        estimate = min(estimate, employee_cap)
    return estimate


def _percentage(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return round((value / total) * 100, 1)


def _is_cancelled(row: Any) -> bool:
    status = _fold(getattr(row, "status", None))
    return status in {"iptal", "cancelled", "canceled"}


def _type_payload(key: str, *, risk_count: int = 0, exposed_workers: int = 0, dominance_score: float = 0.0) -> dict[str, Any]:
    meta = RISK_TYPE_META[key]
    return {
        "key": key,
        "label": meta["label"],
        "description": meta["description"],
        "color": meta["color"],
        "risk_count": int(risk_count),
        "exposed_worker_count": int(exposed_workers),
        "dominance_score": round(float(dominance_score), 2),
    }


def _iter_potential_hazards(roadmap: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_group in ("technical_risk_tags", "special_risks"):
        for item in roadmap.get(source_group) or []:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label") or item.get("key") or "").strip()
            if not label:
                continue
            category = str(item.get("category") or "").strip() or None
            hazard_type = classify_hazard_type(category, label)
            rows.append(
                {
                    "key": str(item.get("key") or label),
                    "label": label,
                    "category": category,
                    "hazard_type": hazard_type,
                    "hazard_type_label": RISK_TYPE_META[hazard_type]["label"],
                    "kind": str(item.get("kind") or "technical"),
                    "source": "NACE",
                    "description": str(item.get("description") or "").strip() or None,
                }
            )
    return rows


def build_risk_analytics(
    company: Any,
    *,
    risks: Iterable[Any] = (),
    employees: Iterable[Any] | None = None,
    hazard_map: Mapping[int, Any] | None = None,
    category_map: Mapping[int, Any] | None = None,
    nace_roadmap: Mapping[str, Any] | None = None,
    active_employee_count: int = 0,
) -> dict[str, Any]:
    """Build a read-only NACE and workplace risk analytics payload.

    ``employees`` is optional for backwards-compatible callers and tests. The
    API passes only active employees from the already scoped workplace. When a
    risk has no explicit exposed-worker count, the employee list is used for a
    conservative department/job/activity match; the company total is kept as
    context and is not copied to each risk.
    """

    hazard_map = hazard_map or {}
    category_map = category_map or {}
    roadmap = nace_roadmap or {}
    employee_rows = (
        [employee for employee in employees if getattr(employee, "is_active", True) is not False]
        if employees is not None
        else None
    )
    observed_rows: list[dict[str, Any]] = []
    prepared_people = [employee_scope(employee) for employee in employee_rows or []]
    type_buckets = {
        key: _type_payload(key)
        for key in RISK_TYPE_ORDER
    }
    type_matched_employee_keys: dict[str, set[tuple[str, object, object]]] = defaultdict(set)
    type_reported_counts: dict[str, int] = defaultdict(int)
    type_assignment_counts: dict[str, int] = defaultdict(int)
    all_matched_employee_keys: set[tuple[str, object, object]] = set()
    reported_exposure_count = 0
    assignment_exposure_count = 0
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "risk_count": 0,
            "exposed_worker_count": 0,
            "reported_exposure_count": 0,
            "assignment_exposure_count": 0,
            "matched_employee_keys": set(),
            "dominance_score": 0.0,
            "max_risk_score": 0.0,
            "risk_codes": [],
            "activity": None,
        }
    )

    for row in risks:
        if _is_cancelled(row):
            continue
        hazard = hazard_map.get(getattr(row, "hazard_id", None))
        category = category_map.get(getattr(hazard, "category_id", None)) if hazard else None
        category_name = str(getattr(category, "name", None) or "").strip() or "Kategorisiz"
        hazard_name = str(getattr(hazard, "name", None) or "").strip() or "Tehlike kaynağı"
        hazard_code = str(getattr(hazard, "code", None) or "").strip() or None
        classification = classify_hazard_details(
            category_name,
            hazard_name,
            getattr(row, "activity", None),
            getattr(row, "risk_definition", None),
        )
        hazard_type = classification["hazard_type"]
        score = max(0.0, _safe_float(getattr(row, "risk_score", None)))
        raw_exposed = getattr(row, "exposed_worker_count", None)
        matched_employee_keys: set[tuple[str, object, object]] = set()
        if raw_exposed is not None:
            exposed = _safe_count(raw_exposed)
            exposure_source = "reported"
            reported_exposure_count += exposed
        elif employee_rows is not None:
            exposed, exposure_source, matched_employee_keys = _personnel_exposure_match(row, employee_rows, prepared_employees=prepared_people)
        else:
            exposed = 0
            exposure_source = "unmatched"
        # Unverified automatic candidates must not amplify risk priority.
        # Weight 1 retains an unknown/zero-count risk; it is not a person count.
        dominance_weight = max(exposed, 1) if exposure_source == "reported" else 1
        dominance_score = max(score, 1.0) * dominance_weight
        bucket = type_buckets[hazard_type]
        bucket["risk_count"] += 1
        type_assignment_counts[hazard_type] += exposed
        assignment_exposure_count += exposed
        if exposure_source == "reported":
            type_reported_counts[hazard_type] += exposed
        else:
            type_matched_employee_keys[hazard_type].update(matched_employee_keys)
            all_matched_employee_keys.update(matched_employee_keys)
        bucket["dominance_score"] += dominance_score

        group_key = (hazard_type, category_name, hazard_name)
        group = grouped[group_key]
        group["risk_count"] += 1
        group["exposed_worker_count"] += exposed
        group["assignment_exposure_count"] += exposed
        if exposure_source == "reported":
            group["reported_exposure_count"] += exposed
        else:
            group["matched_employee_keys"].update(matched_employee_keys)
        group["dominance_score"] += dominance_score
        group["max_risk_score"] = max(group["max_risk_score"], score)
        if len(group["risk_codes"]) < 5 and getattr(row, "risk_code", None):
            group["risk_codes"].append(str(row.risk_code))
        if not group["activity"]:
            group["activity"] = str(getattr(row, "activity", None) or "").strip() or None

        observed_rows.append(
            {
                "id": getattr(row, "id", None),
                "risk_code": getattr(row, "risk_code", None),
                "category": category_name,
                "hazard_code": hazard_code,
                "hazard": hazard_name,
                "hazard_type": hazard_type,
                **classification,
                "hazard_type_label": RISK_TYPE_META[hazard_type]["label"],
                "activity": str(getattr(row, "activity", None) or "").strip() or None,
                "risk_definition": str(getattr(row, "risk_definition", None) or "").strip() or None,
                "risk_score": round(score, 2),
                "risk_level": getattr(row, "risk_level", None),
                "exposed_worker_count": exposed,
                "matched_worker_count": len(matched_employee_keys),
                "reported_worker_count": exposed if exposure_source == "reported" else 0,
                "exposure_count_reported": exposure_source == "reported",
                "exposure_count_source": exposure_source,
                "status": getattr(row, "status", None),
                "dominance_score": round(dominance_score, 2),
                "dominance_weight": dominance_weight,
            }
        )

    employee_cap = _safe_count(active_employee_count)
    if employee_cap <= 0 and employee_rows is not None:
        employee_cap = len(employee_rows)
    personnel_available = employee_rows is not None
    for key, item in type_buckets.items():
        item["matched_worker_count"] = len(type_matched_employee_keys[key])
        item["reported_worker_count"] = type_reported_counts[key]
        item["exposed_worker_count"] = _unique_exposure_count(
            type_matched_employee_keys[key],
            type_reported_counts[key],
            type_assignment_counts[key],
            personnel_available=personnel_available,
            employee_cap=employee_cap,
        )

    total_dominance = sum(float(item["dominance_score"]) for item in type_buckets.values())
    risk_types: list[dict[str, Any]] = []
    for key in RISK_TYPE_ORDER:
        item = type_buckets[key]
        item["dominance_score"] = round(float(item["dominance_score"]), 2)
        item["percentage"] = _percentage(float(item["dominance_score"]), total_dominance)
        # Beş ana tür her zaman döner; “Diğer” yalnızca gerçek kaydı varsa
        # görünür olur ve boş veride arayüz gereksiz bir ek kart göstermez.
        if key != "other" or item["risk_count"] > 0:
            risk_types.append(item)
    # Kartlar, lejant ve donut aynı sırayı kullanır: en yüksek dominant risk
    # türü her zaman ilk görünür başlıktır.
    risk_types.sort(key=lambda item: (-float(item["dominance_score"]), RISK_TYPE_ORDER.index(item["key"])))

    dominant_risks = []
    for (hazard_type, category_name, hazard_name), group in sorted(
        grouped.items(),
        key=lambda pair: (-float(pair[1]["dominance_score"]), -int(pair[1]["risk_count"]), pair[0][2]),
    ):
        dominant_risks.append(
            {
                "key": f"{hazard_type}:{category_name}:{hazard_name}",
                "label": hazard_name,
                "category": category_name,
                "hazard_type": hazard_type,
                "hazard_type_label": RISK_TYPE_META[hazard_type]["label"],
                "color": RISK_TYPE_META[hazard_type]["color"],
                "risk_count": int(group["risk_count"]),
                "matched_worker_count": len(group["matched_employee_keys"]),
                "reported_worker_count": group["reported_exposure_count"],
                "exposed_worker_count": _unique_exposure_count(
                    group["matched_employee_keys"],
                    group["reported_exposure_count"],
                    group["assignment_exposure_count"],
                    personnel_available=personnel_available,
                    employee_cap=employee_cap,
                ),
                "dominance_score": round(float(group["dominance_score"]), 2),
                "percentage": _percentage(float(group["dominance_score"]), total_dominance),
                "max_risk_score": round(float(group["max_risk_score"]), 2),
                "risk_codes": list(group["risk_codes"]),
                "activity": group["activity"],
            }
        )

    observed_rows.sort(key=lambda item: (-float(item["dominance_score"]), -float(item["risk_score"]), str(item["risk_code"] or "")))
    for row in observed_rows:
        row["percentage"] = _percentage(float(row["dominance_score"]), total_dominance)

    category_counts: dict[str, int] = defaultdict(int)
    hazard_name_counts: dict[str, int] = defaultdict(int)
    for row in observed_rows:
        category_counts[str(row["category"])] += 1
        hazard_name = _fold(row.get("hazard"))
        if hazard_name:
            hazard_name_counts[hazard_name] += 1
    potential_hazards = _iter_potential_hazards(roadmap)
    for item in potential_hazards:
        category_linked = category_counts.get(str(item.get("category") or ""), 0)
        candidate_name = _fold(item.get("label"))
        exact_linked = sum(
            count
            for observed_name, count in hazard_name_counts.items()
            if candidate_name
            and (candidate_name == observed_name or candidate_name in observed_name or observed_name in candidate_name)
        )
        item["linked_assessment_count"] = int(exact_linked)
        item["category_assessment_count"] = int(category_linked)
        if exact_linked:
            item["validation_label"] = "Risk kaydıyla eşleşti"
        elif category_linked:
            item["validation_label"] = "Aynı kategoride kayıt var"
        else:
            item["validation_label"] = "Saha doğrulaması bekliyor"
        item["validated"] = bool(exact_linked)

    dominant_type = max(
        (item for item in risk_types if int(item["risk_count"]) > 0),
        key=lambda item: float(item["dominance_score"]),
        default=None,
    )
    dominant_risk = dominant_risks[0] if dominant_risks else None
    unique_exposed_worker_count = _unique_exposure_count(
        all_matched_employee_keys,
        reported_exposure_count,
        assignment_exposure_count,
        personnel_available=personnel_available,
        employee_cap=employee_cap,
    )
    nace_identity = roadmap.get("identity") or {}
    workplace = roadmap.get("workplace") or {}
    company_id = getattr(company, "id", None)

    return {
        "schema_version": ANALYTICS_SCHEMA_VERSION,
        "company": {
            "id": company_id,
            "name": getattr(company, "name", None),
            "sgk_registry_no": getattr(company, "sgk_registry_no", None),
            "hazard_class": getattr(company, "hazard_class", None),
            "active_employee_count": _safe_count(active_employee_count),
        },
        "nace": {
            "code": workplace.get("nace_code") or roadmap.get("entered_nace_code"),
            "source": workplace.get("nace_source") or roadmap.get("nace_source"),
            "status": roadmap.get("status"),
            "status_label": roadmap.get("status_label"),
            "description": nace_identity.get("description"),
            "section_code": nace_identity.get("section_code"),
            "section_name": nace_identity.get("section_name"),
            "hazard_class": nace_identity.get("hazard_class") or getattr(company, "hazard_class", None),
            "exact_catalog_match": bool(roadmap.get("exact_catalog_match")),
        },
        "summary": {
            "risk_record_count": len(observed_rows),
            "classification_review_count": sum(row["hazard_type"] == "other" for row in observed_rows),
            "potential_hazard_count": len(potential_hazards),
            "exposed_worker_count_total": unique_exposed_worker_count,
            "unique_exposed_worker_count": unique_exposed_worker_count,
            "matched_worker_count": len(all_matched_employee_keys),
            "reported_worker_count": reported_exposure_count,
            "exposure_assignments_total": assignment_exposure_count,
            "exposure_records_reported": sum(1 for row in observed_rows if row["exposure_count_reported"]),
            "exposure_records_matched": sum(
                1 for row in observed_rows if row["exposure_count_source"] == "personnel_match"
            ),
            "exposure_records_unmatched": sum(
                1 for row in observed_rows if row["exposure_count_source"] == "unmatched"
            ),
            # Mevcut frontend sürümleri bu alanı kullanıyor; geriye dönük
            # uyumluluk için “eşleşmeyen” kayıt sayısını koruyoruz.
            "exposure_records_missing": sum(
                1 for row in observed_rows if row["exposure_count_source"] == "unmatched"
            ),
            "dominance_score_total": round(total_dominance, 2),
            "dominant_type": dominant_type["label"] if dominant_type else None,
            "dominant_type_key": dominant_type["key"] if dominant_type else None,
            "dominant_risk": dominant_risk["label"] if dominant_risk else None,
        },
        "risk_types": risk_types,
        "dominant_risks": dominant_risks[:20],
        "observed_risks": observed_rows[:50],
        "classification_reviews": [row for row in observed_rows if row["hazard_type"] == "other"],
        "potential_hazards": potential_hazards,
        "nace_warnings": list(roadmap.get("warnings") or []),
        "methodology": {
            "dominance_basis": "max(Risk skoru, 1) × max(kayıtlı kişi beyanı, 1); kişi beyanı yoksa yalnızca risk skoru kullanılır. Otomatik çalışan adayları sıralama ağırlığını artırmaz",
            "percentage_note": "Yüzdeler işyerindeki aktif risk kayıtlarının ağırlıklı baskınlık payıdır.",
            "exposure_note": "İsim listeleri bölüm ve görev bilgilerine dayalı otomatik eşleşme önerileridir; saha doğrulaması gerektirir. Eşleşme bulunmaması, maruziyet olmadığı anlamına gelmez. İşyeri toplamı ve tehlike türü özetinde aynı çalışan yalnızca bir kez sayılır; aynı kişi birden fazla risk satırında tekrar görünebilir. Açık kişi sayısı girilmiş ancak çalışan kimliği bulunmayan satırlar çalışan sayısı üst sınırıyla sınırlandırılır.",
            "nace_note": "NACE başlıkları aday tehlike kaynağıdır; saha/risk değerlendirmesi ile doğrulanmadan gerçekleşmiş risk kabul edilmez.",
        },
    }


__all__ = [
    "ANALYTICS_SCHEMA_VERSION",
    "RISK_TYPE_META",
    "RISK_TYPE_ORDER",
    "build_risk_analytics",
    "classify_hazard_type",
]
