"""Deterministic NACE classification and legacy training audit foundation.

This module is intentionally fail-closed. It never infers an exact NACE code
from a broad legacy profile and never marks an unmapped profile as compliant.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.training_topics import PROFIL_ADLARI, sectors_list_for_api

CATALOG_SCHEMA_VERSION = "nace-training-registry-v1"
VALID_HAZARD_CLASSES = {"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"}

# A lesson hour consists of 45 minutes instruction and 15 minutes break.
DURATION_RULES: dict[str, dict[str, int]] = {
    "Az Tehlikeli": {
        "lesson_hours": 8,
        "instruction_minutes": 360,
        "scheduled_minutes": 480,
        "sector_lesson_hours": 2,
        "sector_instruction_minutes": 90,
        "sector_scheduled_minutes": 120,
    },
    "Tehlikeli": {
        "lesson_hours": 12,
        "instruction_minutes": 540,
        "scheduled_minutes": 720,
        "sector_lesson_hours": 3,
        "sector_instruction_minutes": 135,
        "sector_scheduled_minutes": 180,
    },
    "Çok Tehlikeli": {
        "lesson_hours": 16,
        "instruction_minutes": 720,
        "scheduled_minutes": 960,
        "sector_lesson_hours": 4,
        "sector_instruction_minutes": 180,
        "sector_scheduled_minutes": 240,
    },
}

# NACE Rev.2 section ranges. The exact six-digit activity remains the primary
# identifier; these ranges are only a deterministic hierarchy layer.
NACE_SECTIONS: tuple[tuple[int, int, str, str], ...] = (
    (1, 3, "A", "Tarım, ormancılık ve balıkçılık"),
    (5, 9, "B", "Madencilik ve taş ocakçılığı"),
    (10, 33, "C", "İmalat"),
    (35, 35, "D", "Elektrik, gaz, buhar ve iklimlendirme üretimi ve dağıtımı"),
    (36, 39, "E", "Su temini; kanalizasyon, atık yönetimi ve iyileştirme"),
    (41, 43, "F", "İnşaat"),
    (45, 47, "G", "Toptan ve perakende ticaret; motorlu taşıt onarımı"),
    (49, 53, "H", "Ulaştırma ve depolama"),
    (55, 56, "I", "Konaklama ve yiyecek hizmeti faaliyetleri"),
    (58, 63, "J", "Bilgi ve iletişim"),
    (64, 66, "K", "Finans ve sigorta faaliyetleri"),
    (68, 68, "L", "Gayrimenkul faaliyetleri"),
    (69, 75, "M", "Mesleki, bilimsel ve teknik faaliyetler"),
    (77, 82, "N", "İdari ve destek hizmet faaliyetleri"),
    (84, 84, "O", "Kamu yönetimi ve savunma; zorunlu sosyal güvenlik"),
    (85, 85, "P", "Eğitim"),
    (86, 88, "Q", "İnsan sağlığı ve sosyal hizmet faaliyetleri"),
    (90, 93, "R", "Kültür, sanat, eğlence, dinlence ve spor"),
    (94, 96, "S", "Diğer hizmet faaliyetleri"),
    (97, 98, "T", "Hanehalklarının işveren olarak faaliyetleri"),
    (99, 99, "U", "Uluslararası örgütler ve temsilciliklerinin faaliyetleri"),
)

# Explicit profile-to-risk mapping. Missing profiles remain review_required;
# risk tags are never fabricated from free-text similarity.
PROFILE_RISK_TAGS: dict[str, tuple[str, ...]] = {
    "tarim": ("mobile_equipment", "outdoor_work", "biological", "manual_handling"),
    "tarim_ziraat": ("tractor", "agricultural_machinery", "pesticide", "outdoor_work"),
    "hayvancilik": ("animal_handling", "biological", "manual_handling", "outdoor_work"),
    "hayvancilik_ciftlik": ("animal_handling", "biological", "agricultural_machinery", "manual_handling"),
    "balikcilik_su_urunleri": ("marine_work", "drowning", "slip_trip", "cold_weather", "manual_handling"),
    "ormancilik": ("chainsaw", "falling_objects", "mobile_equipment", "outdoor_work", "fire"),
    "madencilik_maden_ocagi": ("ground_control", "explosive", "dust", "mobile_equipment", "confined_space"),
    "petrol_dogalgaz": ("flammable", "explosive_atmosphere", "pressure", "chemical", "confined_space"),
    "gida_uretim": ("machinery", "food_hygiene", "chemical_cleaning", "cold_storage", "ergonomics"),
    "restoran_gida_hizmeti": ("hot_surface", "knife", "food_hygiene", "slip_trip", "fire"),
    "firin_unlu_mamuller": ("flour_dust", "machinery", "hot_surface", "manual_handling", "fire"),
    "sut_sut_urunleri": ("biological", "chemical_cleaning", "machinery", "cold_storage", "slip_trip"),
    "tekstil": ("textile_machinery", "dust", "noise", "ergonomics", "fire"),
    "ayakkabi_deri_uretimi": ("solvent", "cutting", "machinery", "ergonomics", "fire"),
    "kimya_kimyasal_uretim": ("chemical", "explosive_atmosphere", "flammable", "toxic_exposure", "process_safety"),
    "kimyasal_boya": ("solvent", "chemical", "explosive_atmosphere", "local_exhaust", "fire"),
    "boyahaneler_boya_uretimi": ("solvent", "chemical", "spray", "local_exhaust", "fire"),
    "kozmetik_temizlik_urunleri": ("chemical", "mixing", "labeling", "ergonomics", "fire"),
    "aku_uretimi": ("lead", "sulfuric_acid", "hydrogen", "electrical", "machinery"),
    "metal_imalat": ("machinery", "cutting", "noise", "metal_fume", "lifting"),
    "kaynakli_imalat": ("welding_fume", "hot_work", "fire", "electrical", "compressed_gas"),
    "makine_imalat": ("machinery", "lockout_tagout", "lifting", "cutting", "noise"),
    "otomotiv": ("vehicle_lift", "machinery", "chemical", "battery", "ergonomics"),
    "insaat_yapi": ("work_at_height", "scaffold", "excavation", "lifting", "temporary_electrical"),
    "yapi_yol_insaati": ("mobile_equipment", "excavation", "traffic", "lifting", "temporary_electrical"),
    "kazi_hafriyat": ("excavation", "ground_collapse", "mobile_equipment", "underground_utilities", "traffic"),
    "yikim_sokum": ("structural_collapse", "asbestos", "falling_objects", "work_at_height", "dust"),
    "cati_kaplama": ("work_at_height", "fall_protection", "weather", "hot_work", "manual_handling"),
    "enerji_jenerator_trafo": ("electrical", "arc_flash", "lockout_tagout", "fire", "lifting"),
    "elektrik_tesisat_pano_montaj": ("electrical", "arc_flash", "work_at_height", "lockout_tagout", "temporary_electrical"),
    "depo_lojistik": ("forklift", "racking", "manual_handling", "loading_dock", "traffic"),
    "karayolu_tasimacilik": ("road_traffic", "driver_fatigue", "loading", "vehicle_maintenance", "manual_handling"),
    "havalimani_yer_hizmetleri": ("airside_traffic", "ground_support_equipment", "noise", "fuel", "manual_handling"),
    "havacilik": ("airside_traffic", "aircraft_maintenance", "work_at_height", "noise", "fuel"),
    "saglik": ("biological", "sharps", "patient_handling", "chemical", "radiation"),
    "veterinerlik": ("animal_handling", "biological", "sharps", "chemical", "ergonomics"),
    "guzellik_kuafor_spa": ("cosmetic_chemical", "sharps", "ergonomics", "electrical", "slip_trip"),
    "cenaze_hizmetleri": ("biological", "chemical", "manual_handling", "psychosocial", "vehicle"),
    "egitim_okul": ("emergency", "ergonomics", "psychosocial", "laboratory", "child_safety"),
    "ofis": ("ergonomics", "electrical", "fire", "psychosocial", "slip_trip"),
    "perakende_magaza": ("manual_handling", "slip_trip", "racking", "cash_security", "fire"),
    "otel_konaklama": ("housekeeping", "chemical_cleaning", "food_hygiene", "fire", "ergonomics"),
    "temizlik": ("chemical_cleaning", "slip_trip", "biological", "ergonomics", "work_at_height"),
    "atik_geri_donusum": ("waste", "biological", "machinery", "fire", "sharps"),
    "spor_tesisi_fitness": ("ergonomics", "equipment", "slip_trip", "emergency", "biological"),
    "plastik_kaucuk": ("machinery", "chemical", "hot_surface", "fire", "fume"),
    "ahsap_mobilya": ("wood_dust", "machinery", "fire", "noise", "chemical"),
    "cam_seramik": ("silica_dust", "hot_surface", "machinery", "cutting", "manual_handling"),
    "seramik_fayans": ("silica_dust", "machinery", "hot_surface", "manual_handling", "noise"),
}

BROAD_PROFILE_CODES = {
    "genel_uretim",
    "ofis",
    "depo_lojistik",
    "saglik",
    "tarim",
}

SPECIAL_RISK_TAGS = {
    "asbestos",
    "biological",
    "chemical",
    "confined_space",
    "drowning",
    "explosive",
    "explosive_atmosphere",
    "lead",
    "radiation",
    "silica_dust",
    "sulfuric_acid",
    "work_at_height",
}


@dataclass(frozen=True)
class NaceClassification:
    nace_code: str
    nace_key: str
    description: str
    division_code: str
    activity_group_code: str
    main_sector_code: str
    main_sector_name: str
    profile_code: str
    profile_name: str
    hazard_class: str
    risk_tags: tuple[str, ...]
    special_risks: tuple[str, ...]
    topics: tuple[str, ...]
    lesson_hours: int
    instruction_minutes: int
    scheduled_minutes: int
    sector_lesson_hours: int
    sector_instruction_minutes: int
    sector_scheduled_minutes: int
    mapping_status: str
    validation_errors: tuple[str, ...]

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def normalize_nace_code(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if raw.startswith("nace_"):
        raw = raw[5:].replace("_", ".")
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 6:
        return None
    return f"{digits[:2]}.{digits[2:4]}.{digits[4:]}"


def nace_key(nace_code: str) -> str:
    return "nace_" + nace_code.replace(".", "_")


def _section_for(nace_code: str) -> tuple[str, str]:
    division = int(nace_code[:2])
    for start, end, code, name in NACE_SECTIONS:
        if start <= division <= end:
            return code, name
    return "", ""


def _topic_titles(raw_topics: Any) -> tuple[str, ...]:
    titles: list[str] = []
    for item in raw_topics or []:
        if isinstance(item, str):
            title = item.strip()
        elif isinstance(item, dict):
            title = str(item.get("title") or item.get("name") or "").strip()
        else:
            title = ""
        if title and title.casefold() not in {x.casefold() for x in titles}:
            titles.append(title)
    return tuple(titles)


def classify_catalog_row(row: dict[str, Any]) -> NaceClassification:
    exact = normalize_nace_code(row.get("nace") or row.get("nace_code") or row.get("code"))
    errors: list[str] = []
    if exact is None:
        exact = "00.00.00"
        errors.append("invalid_exact_nace")

    hazard = str(row.get("hazard_class") or "").strip()
    if hazard not in VALID_HAZARD_CLASSES:
        errors.append("invalid_hazard_class")
    duration = DURATION_RULES.get(hazard, {
        "lesson_hours": 0,
        "instruction_minutes": 0,
        "scheduled_minutes": 0,
        "sector_lesson_hours": 0,
        "sector_instruction_minutes": 0,
        "sector_scheduled_minutes": 0,
    })

    profile = str(row.get("profile") or "").strip()
    if not profile:
        errors.append("missing_profile")
    topics = _topic_titles(row.get("topics"))
    if not topics:
        errors.append("missing_topics")
    risks = tuple(sorted(set(PROFILE_RISK_TAGS.get(profile, ()))))
    if not risks:
        errors.append("risk_mapping_review_required")

    section_code, section_name = _section_for(exact)
    if not section_code:
        errors.append("missing_main_sector")

    if any(error for error in errors if error != "risk_mapping_review_required"):
        status = "blocked"
    elif "risk_mapping_review_required" in errors or profile in BROAD_PROFILE_CODES:
        status = "review_required"
    else:
        status = "mapped"

    return NaceClassification(
        nace_code=exact,
        nace_key=nace_key(exact),
        description=str(row.get("name") or row.get("description") or "").strip(),
        division_code=exact[:2],
        activity_group_code=exact[:5],
        main_sector_code=section_code,
        main_sector_name=section_name,
        profile_code=profile,
        profile_name=str(PROFIL_ADLARI.get(profile) or profile).strip(),
        hazard_class=hazard,
        risk_tags=risks,
        special_risks=tuple(tag for tag in risks if tag in SPECIAL_RISK_TAGS),
        topics=topics,
        lesson_hours=duration["lesson_hours"],
        instruction_minutes=duration["instruction_minutes"],
        scheduled_minutes=duration["scheduled_minutes"],
        sector_lesson_hours=duration["sector_lesson_hours"],
        sector_instruction_minutes=duration["sector_instruction_minutes"],
        sector_scheduled_minutes=duration["sector_scheduled_minutes"],
        mapping_status=status,
        validation_errors=tuple(errors),
    )


def build_registry() -> list[NaceClassification]:
    registry: list[NaceClassification] = []
    seen: set[str] = set()
    for row in sectors_list_for_api():
        classification = classify_catalog_row(row)
        if classification.nace_code == "00.00.00":
            continue
        if classification.nace_code in seen:
            raise ValueError(f"Duplicate NACE catalog row: {classification.nace_code}")
        seen.add(classification.nace_code)
        registry.append(classification)
    return sorted(registry, key=lambda item: item.nace_code)


def registry_content_hash(registry: list[NaceClassification] | None = None) -> str:
    rows = registry if registry is not None else build_registry()
    canonical = json.dumps(
        [row.payload() for row in rows],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def registry_report(*, include_entries: bool = False) -> dict[str, Any]:
    rows = build_registry()
    status_counts = {"mapped": 0, "review_required": 0, "blocked": 0}
    hazard_counts = {hazard: 0 for hazard in sorted(VALID_HAZARD_CLASSES)}
    for row in rows:
        status_counts[row.mapping_status] += 1
        if row.hazard_class in hazard_counts:
            hazard_counts[row.hazard_class] += 1
    report: dict[str, Any] = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "content_hash": registry_content_hash(rows),
        "entry_count": len(rows),
        "status_counts": status_counts,
        "hazard_counts": hazard_counts,
        "all_compliant": False,
    }
    if include_entries:
        report["entries"] = [row.payload() for row in rows]
    return report


def materialize_registry(db: Session, *, created_by_id: int) -> dict[str, Any]:
    rows = build_registry()
    content_hash = registry_content_hash(rows)
    existing = db.execute(
        text("SELECT id, version_code, status, entry_count FROM training_nace_catalog_versions WHERE content_hash=:hash"),
        {"hash": content_hash},
    ).mappings().first()
    if existing:
        return {"created": False, **dict(existing), "content_hash": content_hash}

    version_id = db.execute(
        text("""
            INSERT INTO training_nace_catalog_versions
                (version_code, content_hash, source_label, source_url, status,
                 entry_count, created_by_id, created_at)
            VALUES
                (:version_code, :content_hash, :source_label, :source_url, 'candidate',
                 :entry_count, :created_by_id, CURRENT_TIMESTAMP)
            RETURNING id
        """),
        {
            "version_code": CATALOG_SCHEMA_VERSION,
            "content_hash": content_hash,
            "source_label": "Repository NACE catalog + explicit risk classifier",
            "source_url": "https://www.csgb.gov.tr/sikca-sorulan-sorular/is-sagligi-ve-guvenligi-genel-mudurlugu/",
            "entry_count": len(rows),
            "created_by_id": created_by_id,
        },
    ).scalar_one()

    params = []
    for row in rows:
        payload = row.payload()
        params.append({
            "version_id": version_id,
            "nace_code": row.nace_code,
            "nace_key": row.nace_key,
            "description": row.description,
            "division_code": row.division_code,
            "activity_group_code": row.activity_group_code,
            "main_sector_code": row.main_sector_code,
            "main_sector_name": row.main_sector_name,
            "profile_code": row.profile_code,
            "profile_name": row.profile_name,
            "hazard_class": row.hazard_class,
            "risk_tags_json": json.dumps(payload["risk_tags"], ensure_ascii=False),
            "special_risks_json": json.dumps(payload["special_risks"], ensure_ascii=False),
            "topics_json": json.dumps(payload["topics"], ensure_ascii=False),
            "lesson_hours": row.lesson_hours,
            "instruction_minutes": row.instruction_minutes,
            "scheduled_minutes": row.scheduled_minutes,
            "sector_lesson_hours": row.sector_lesson_hours,
            "sector_instruction_minutes": row.sector_instruction_minutes,
            "sector_scheduled_minutes": row.sector_scheduled_minutes,
            "mapping_status": row.mapping_status,
            "validation_errors_json": json.dumps(payload["validation_errors"], ensure_ascii=False),
        })
    db.execute(
        text("""
            INSERT INTO training_nace_catalog_entries
                (version_id, nace_code, nace_key, description, division_code,
                 activity_group_code, main_sector_code, main_sector_name,
                 profile_code, profile_name, hazard_class, risk_tags_json,
                 special_risks_json, topics_json, lesson_hours,
                 instruction_minutes, scheduled_minutes, sector_lesson_hours,
                 sector_instruction_minutes, sector_scheduled_minutes,
                 mapping_status, validation_errors_json)
            VALUES
                (:version_id, :nace_code, :nace_key, :description, :division_code,
                 :activity_group_code, :main_sector_code, :main_sector_name,
                 :profile_code, :profile_name, :hazard_class, :risk_tags_json,
                 :special_risks_json, :topics_json, :lesson_hours,
                 :instruction_minutes, :scheduled_minutes, :sector_lesson_hours,
                 :sector_instruction_minutes, :sector_scheduled_minutes,
                 :mapping_status, :validation_errors_json)
        """),
        params,
    )
    return {
        "created": True,
        "id": version_id,
        "version_code": CATALOG_SCHEMA_VERSION,
        "status": "candidate",
        "entry_count": len(rows),
        "content_hash": content_hash,
    }


def legacy_training_report(db: Session) -> dict[str, Any]:
    registry = build_registry()
    exact_index = {row.nace_code: row for row in registry}
    profile_index: dict[str, list[NaceClassification]] = {}
    for row in registry:
        profile_index.setdefault(row.profile_code, []).append(row)

    trainings = db.execute(
        text("""
            SELECT id, company_id, branch_id, sector, hazard_class,
                   duration_hours, status, created_at
            FROM training_sessions
            ORDER BY id
        """)
    ).mappings().all()

    items: list[dict[str, Any]] = []
    status_counts = {"exact": 0, "review_required": 0, "blocked": 0}
    for training in trainings:
        stored = str(training["sector"] or "").strip()
        exact = normalize_nace_code(stored)
        errors: list[str] = []
        candidates: list[NaceClassification] = []
        resolved: NaceClassification | None = None

        if exact and exact in exact_index:
            resolved = exact_index[exact]
        elif stored:
            candidates = profile_index.get(stored, [])
            errors.append("legacy_exact_nace_missing")
            if len(candidates) > 1:
                errors.append("legacy_profile_ambiguous")
            elif len(candidates) == 0:
                errors.append("legacy_profile_unknown")
        else:
            errors.append("missing_sector")

        expected = DURATION_RULES.get(str(training["hazard_class"] or ""), {}).get("lesson_hours")
        if expected is None:
            errors.append("invalid_hazard_class")
        elif int(training["duration_hours"] or 0) != expected:
            errors.append("duration_mismatch")
        if training["branch_id"] is None:
            errors.append("workplace_missing")

        if resolved and not errors:
            status = "exact"
        elif any(code in errors for code in ("missing_sector", "legacy_profile_unknown", "invalid_hazard_class", "duration_mismatch")):
            status = "blocked"
        else:
            status = "review_required"
        status_counts[status] += 1

        items.append({
            "training_id": training["id"],
            "company_id": training["company_id"],
            "branch_id": training["branch_id"],
            "stored_sector": stored,
            "stored_hazard_class": training["hazard_class"],
            "stored_duration_hours": training["duration_hours"],
            "status": status,
            "resolved_nace_code": resolved.nace_code if resolved else None,
            "candidate_nace_count": len(candidates),
            "errors": errors,
        })

    return {
        "total": len(items),
        "status_counts": status_counts,
        "items": items,
        "note": "Broad legacy profile keys are never converted to an exact NACE code automatically.",
    }
