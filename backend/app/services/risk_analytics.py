"""NACE + risk değerlendirmesi analitiği.

Bu servis yalnızca mevcut kayıtları okur. NACE profilindeki başlıkları aday
tehlike kaynağı olarak, RiskAssessment kayıtlarını ise işyerinde doğrulanmış
değerlendirme olarak ayrı tutar. Böylece NACE kodu hiçbir zaman otomatik risk
kaydı üretmez veya saha değerlendirmesinin yerine geçmez.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
import re
from typing import Any, Iterable, Mapping
import unicodedata


ANALYTICS_SCHEMA_VERSION = "risk-nace-analytics-v1"

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
        "description": "Biyolojik etken, enfeksiyon, kan/vücut sıvısı, hijyen ve zoonotik kaynaklar.",
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
        "label": "Diğer",
        "description": "Ana risk türlerine güvenli biçimde sınıflandırılamayan diğer tehlike kayıtları.",
        "color": "#64748b",
    },
}


# Sınıflandırma yalnızca açıklanabilir katalog metni ve risk kaydı alanlarıyla
# yapılır. Öncelik sırası, örneğin "kimyasal ve biyolojik" gibi birleşik
# kategori adlarında daha özel biyolojik/kimyasal/psikososyal/ergonomik
# anlamı korur.
_BIOLOGICAL_TERMS = (
    "biyolojik",
    "biolojik",
    "enfeks",
    "bloodborne",
    "infectious",
    "zoonot",
    "biyogüven",
    "hijyen",
    "hayvan",
    "sharps",
    "kan ve vücut",
)
_CHEMICAL_TERMS = (
    "kimyasal",
    "chemical",
    "solvent",
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
    "toz",
    "makine",
    "yüksekte",
    "yuksekte",
    "kaldır",
    "kaldir",
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

# Personel–risk eşleştirmesinde tek başına anlam taşımayan bağlaç ve rapor
# kelimeleri. Eşleştirme isim üzerinden değil; bölüm, görev ve faaliyet
# kapsamındaki anlamlı kelimeler üzerinden yapılır.
_PERSONNEL_MATCH_STOP_WORDS = frozenset(
    {
        "ve",
        "veya",
        "ile",
        "icin",
        "olan",
        "olarak",
        "calisan",
        "calisanlar",
        "personel",
        "ekip",
        "is",
        "isi",
        "islem",
        "faaliyet",
        "proses",
        "alan",
        "bolum",
        "risk",
        "tehlike",
        "kaynak",
        "maruziyet",
        "maruz",
    }
)


def _meaningful_tokens(value: object) -> set[str]:
    """Return normalized words suitable for conservative personnel matching."""

    return {
        token
        for token in re.findall(r"[a-z0-9]+", _fold(value))
        if len(token) >= 3 and token not in _PERSONNEL_MATCH_STOP_WORDS
    }


def _token_overlap(left: set[str], right: set[str]) -> bool:
    """Allow simple Turkish suffix variations without fuzzy overmatching."""

    return any(
        first == second
        or (len(first) >= 4 and len(second) >= 4 and (first.startswith(second) or second.startswith(first)))
        for first in left
        for second in right
    )


def _same_scope_text(left: object, right: object) -> bool:
    left_text = _fold(left)
    right_text = _fold(right)
    return bool(left_text and right_text and (left_text == right_text or left_text in right_text or right_text in left_text))


def _personnel_exposure_match(row: Any, employees: Iterable[Any]) -> tuple[int, str]:
    """Count active employees whose stored scope matches one risk.

    The application has two structured personnel fields today: ``department``
    and ``job_title``. Risk rows provide ``department_name`` and ``activity``;
    imported rows additionally carry the source risk/hazard text. A match is
    deliberately conservative: an exact/contained department match or a
    meaningful job-to-activity match is required. The company-wide employee
    count is never copied to every risk.
    """

    risk_department = str(getattr(row, "department_name", None) or "").strip()
    risk_activity = str(getattr(row, "activity", None) or "").strip()
    risk_scope_values = (
        risk_activity,
        getattr(row, "risk_source", None),
        getattr(row, "hazard_detail", None),
        getattr(row, "risk_definition", None),
    )
    activity_tokens = _meaningful_tokens(risk_activity)
    scope_tokens = _meaningful_tokens(" ".join(str(value or "") for value in risk_scope_values))
    if not risk_department and not activity_tokens and not scope_tokens:
        return 0, "unmatched"

    risk_branch_id = getattr(row, "branch_id", None)
    matched = 0
    for employee in employees:
        employee_branch_id = getattr(employee, "branch_id", None)
        if risk_branch_id and employee_branch_id and risk_branch_id != employee_branch_id:
            continue

        employee_department = str(getattr(employee, "department", None) or "").strip()
        employee_job = str(getattr(employee, "job_title", None) or "").strip()
        department_tokens = _meaningful_tokens(employee_department)
        job_tokens = _meaningful_tokens(employee_job)

        department_match = _same_scope_text(risk_department, employee_department)
        department_token_match = bool(
            risk_department
            and department_tokens
            and _token_overlap(_meaningful_tokens(risk_department), department_tokens)
        )
        job_activity_match = bool(activity_tokens and job_tokens and _token_overlap(job_tokens, activity_tokens))
        job_scope_match = bool(scope_tokens and job_tokens and _token_overlap(job_tokens, scope_tokens))

        # Bölüm eşleşmesi önceliklidir. Bölüm adı farklı tutulmuşsa görev ile
        # faaliyet veya tehlike metninin anlamlı bir kesişimi de yeterlidir;
        # böylece “Elektrik Trafosu” alanındaki elektrik teknisyeni gibi
        # kayıtlar yalnızca bölüm adı birebir aynı değil diye kaybolmaz.
        if department_match or department_token_match or job_activity_match or job_scope_match:
            matched += 1

    return matched, "personnel_match" if matched else "unmatched"


def _fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.casefold().replace("ı", "i").split())


def classify_hazard_type(*values: object) -> str:
    """Map a controlled category/label to a displayable hazard type."""

    text = _fold(" ".join(str(value or "") for value in values if value))
    if any(term in text for term in _BIOLOGICAL_TERMS):
        return "biological"
    if any(term in text for term in _CHEMICAL_TERMS):
        return "chemical"
    if any(term in text for term in _PSYCHOSOCIAL_TERMS):
        return "psychosocial"
    if any(term in text for term in _ERGONOMIC_TERMS):
        return "ergonomic"
    if any(term in text for term in _PHYSICAL_TERMS):
        return "physical"
    return "other"


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
    type_buckets = {
        key: _type_payload(key)
        for key in RISK_TYPE_ORDER
    }
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "risk_count": 0,
            "exposed_worker_count": 0,
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
        hazard_type = classify_hazard_type(
            category_name,
            hazard_name,
            getattr(row, "activity", None),
            getattr(row, "risk_definition", None),
        )
        score = max(0.0, _safe_float(getattr(row, "risk_score", None)))
        raw_exposed = getattr(row, "exposed_worker_count", None)
        if raw_exposed is not None:
            exposed = _safe_count(raw_exposed)
            exposure_source = "reported"
        elif employee_rows is not None:
            exposed, exposure_source = _personnel_exposure_match(row, employee_rows)
        else:
            exposed = 0
            exposure_source = "unmatched"
        # Çalışan sayısı bulunamayan riskler sıralamada kaybolmasın. Bu
        # durumda tek risk ağırlığı kullanılır; açık sayı veya güvenilir
        # personel eşleşmesi varsa etkisi doğrudan ağırlığa yansır.
        dominance_score = max(score, 1.0) * max(exposed, 1)
        bucket = type_buckets[hazard_type]
        bucket["risk_count"] += 1
        bucket["exposed_worker_count"] += exposed
        bucket["dominance_score"] += dominance_score

        group_key = (hazard_type, category_name, hazard_name)
        group = grouped[group_key]
        group["risk_count"] += 1
        group["exposed_worker_count"] += exposed
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
                "hazard_type_label": RISK_TYPE_META[hazard_type]["label"],
                "activity": str(getattr(row, "activity", None) or "").strip() or None,
                "risk_definition": str(getattr(row, "risk_definition", None) or "").strip() or None,
                "risk_score": round(score, 2),
                "risk_level": getattr(row, "risk_level", None),
                "exposed_worker_count": exposed,
                "exposure_count_reported": exposure_source == "reported",
                "exposure_count_source": exposure_source,
                "status": getattr(row, "status", None),
                "dominance_score": round(dominance_score, 2),
            }
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
                "exposed_worker_count": int(group["exposed_worker_count"]),
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
            "potential_hazard_count": len(potential_hazards),
            "exposed_worker_count_total": sum(int(row["exposed_worker_count"]) for row in observed_rows),
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
        "potential_hazards": potential_hazards,
        "nace_warnings": list(roadmap.get("warnings") or []),
        "methodology": {
            "dominance_basis": "Risk skoru × max(açık kişi sayısı veya personel eşleşmesi, 1)",
            "percentage_note": "Yüzdeler işyerindeki aktif risk kayıtlarının ağırlıklı baskınlık payıdır.",
            "exposure_note": "Maruz kişi hesabında önce risk kaydındaki açık sayı, sonra aktif personelin bölüm/görev-faaliyet eşleşmesi kullanılır. Eşleşmeyen kayıtta firma toplamı varsayılmaz; aynı çalışan birden fazla riskte tekrar sayılabilir.",
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
