"""Strict, auditable NACE classification for training records.

New training writes must resolve to an exact official catalog row. Legacy profile
codes remain readable, but are explicitly marked ``legacy_unverified`` and are
never promoted to an exact NACE code by guessing.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import event

from app.models.entities import TrainingSession
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_sector_catalog import SEKTOR_ADLARI
from app.services.training_topics import (
    SEKTOR_PROFIL,
    TEHLIKE_EGITIM_KURALLARI,
    sectors_list_for_api,
    sektorel_konular,
    sektor_adi,
)

CLASSIFICATION_SCHEMA_VERSION = "nace-training-v3"
VALID_HAZARD_CLASSES = frozenset(TEHLIKE_EGITIM_KURALLARI)
_EXACT_NACE_RE = re.compile(r"^\d{2}(?:\.\d{2}){1,2}$")

# NACE Rev.2 sections. Division ranges are stable classification structure,
# not free-text similarity.
_SECTION_RANGES: tuple[tuple[str, str, int, int], ...] = (
    ("A", "Tarım, Ormancılık ve Balıkçılık", 1, 3),
    ("B", "Madencilik ve Taş Ocakçılığı", 5, 9),
    ("C", "İmalat", 10, 33),
    ("D", "Elektrik, Gaz, Buhar ve İklimlendirme", 35, 35),
    ("E", "Su Temini, Kanalizasyon, Atık Yönetimi ve İyileştirme", 36, 39),
    ("F", "İnşaat", 41, 43),
    ("G", "Toptan ve Perakende Ticaret; Motorlu Taşıt Onarımı", 45, 47),
    ("H", "Ulaştırma ve Depolama", 49, 53),
    ("I", "Konaklama ve Yiyecek Hizmeti Faaliyetleri", 55, 56),
    ("J", "Bilgi ve İletişim", 58, 63),
    ("K", "Finans ve Sigorta Faaliyetleri", 64, 66),
    ("L", "Gayrimenkul Faaliyetleri", 68, 68),
    ("M", "Mesleki, Bilimsel ve Teknik Faaliyetler", 69, 75),
    ("N", "İdari ve Destek Hizmet Faaliyetleri", 77, 82),
    ("O", "Kamu Yönetimi ve Savunma; Zorunlu Sosyal Güvenlik", 84, 84),
    ("P", "Eğitim", 85, 85),
    ("Q", "İnsan Sağlığı ve Sosyal Hizmet Faaliyetleri", 86, 88),
    ("R", "Kültür, Sanat, Eğlence, Dinlence ve Spor", 90, 93),
    ("S", "Diğer Hizmet Faaliyetleri", 94, 96),
    ("T", "Hanehalklarının İşveren Olarak Faaliyetleri", 97, 98),
    ("U", "Uluslararası Örgütler ve Temsilciliklerinin Faaliyetleri", 99, 99),
)

# Controlled profile mappings. No main-section fallback is allowed: where an
# exact profile has not been reviewed, the snapshot remains ``review_required``
# instead of receiving broad or potentially unrelated risk tags.
_PROFILE_RISK_TAGS: dict[str, tuple[str, ...]] = {
    "insaat": ("working_at_height", "scaffolding", "excavation", "lifting", "temporary_electricity", "site_traffic"),
    "insaat_santiye": ("working_at_height", "scaffolding", "excavation", "lifting", "temporary_electricity", "site_traffic"),
    "yol_altyapi_insaati": ("excavation", "mobile_plant", "road_traffic", "lifting", "temporary_electricity"),
    "iskele_kalip_yapi_ekipmani": ("working_at_height", "scaffolding", "formwork", "falling_objects"),
    "yuksekte_calisma_cephe": ("working_at_height", "fall_protection", "scaffolding", "weather", "pressure_washing"),
    "madencilik_maden_ocagi": ("ground_control", "explosives", "mobile_plant", "dust", "confined_space"),
    "kapali_maden": ("ground_control", "mine_ventilation", "explosives", "dust", "confined_space"),
    "tas_ocagi_maden_ocagi": ("blasting", "mobile_plant", "silica_dust", "crushing", "traffic"),
    "kimya_kimyasal_uretim": ("chemical_exposure", "process_safety", "atex", "spill_response", "fire"),
    "petrol_rafineri_depolama": ("process_safety", "atex", "flammable_liquids", "confined_space", "fire"),
    "patlayici": ("explosives", "atex", "static_electricity", "segregated_storage", "emergency"),
    "gida_uretim": ("machinery", "food_hygiene", "chemical_cleaning", "cold_environment", "ergonomics"),
    "gida_uretimi_isleme": ("machinery", "food_hygiene", "chemical_cleaning", "cold_environment", "ergonomics"),
    "saglik_hastane_klinik": ("biological_agents", "sharps", "patient_handling", "chemical_disinfectants", "violence"),
    "saglik": ("biological_agents", "sharps", "patient_handling", "chemical_disinfectants", "violence"),
    "tip_dis_klinigi": ("biological_agents", "sharps", "sterilization", "radiation", "ergonomics"),
    "tarim": ("agricultural_machinery", "pesticides", "animal_contact", "weather", "manual_handling"),
    "tarim_ziraat": ("agricultural_machinery", "pesticides", "weather", "manual_handling", "fire"),
    "balikcilik_su_urunleri": ("man_overboard", "winches", "cold_environment", "biological_agents", "refrigerants"),
    "ormancilik": ("chainsaw", "falling_trees", "mobile_plant", "terrain", "weather"),
    "depo_lojistik": ("forklifts", "storage_racking", "loading_docks", "traffic", "manual_handling"),
    "karayolu_tasimacilik": ("road_traffic", "driver_fatigue", "loading", "vehicle_maintenance", "manual_handling"),
    "liman": ("lifting", "container_handling", "traffic", "working_over_water", "dangerous_goods"),
    "gemi_insa_tersane": ("hot_work", "confined_space", "working_at_height", "lifting", "coatings"),
    "havacilik": ("airside_traffic", "ground_support_equipment", "noise", "fuel", "weather"),
    "havalimani_yer_hizmetleri": ("airside_traffic", "ground_support_equipment", "noise", "fuel", "manual_handling"),
    "metal_isleme_torna_freze": ("machinery", "metalworking_fluids", "hot_work", "lifting", "noise"),
    "metal_yapi_elemanlari_toptan": ("lifting", "load_securing", "storage_stability", "vehicle_traffic", "sharp_edges"),
    "ticaret_aracilik_ofis": ("road_traffic", "lone_work", "display_screen", "ergonomics", "psychosocial"),
    "tarimsal_urun_toptan": ("organic_dust", "storage_stability", "forklifts", "manual_handling", "fire"),
    "canli_hayvan_toptan": ("animal_handling", "biological_agents", "loading", "vehicle_traffic", "manual_handling"),
    "gida_toptan_depo": ("food_hygiene", "cold_environment", "forklifts", "storage_racking", "loading_docks"),
    "tekstil_deri_toptan": ("fire", "storage_racking", "forklifts", "manual_handling", "sharp_tools"),
    "elektrik_elektronik_toptan": ("electrical", "battery_fire", "storage_racking", "forklifts", "manual_handling"),
    "kimyasal_toptan_depo": ("chemical_exposure", "segregated_storage", "flammable_liquids", "spill_response", "forklifts"),
    "ecza_medikal_toptan": ("cold_chain", "storage_racking", "forklifts", "sharps", "fire"),
    "mobilya_ev_esyasi_toptan": ("storage_stability", "lifting", "sharp_edges", "forklifts", "fire"),
    "makine_ekipman_toptan": ("lifting", "storage_stability", "energy_isolation", "sharp_edges", "vehicle_traffic"),
    "otomotiv_toptan": ("vehicle_traffic", "loading", "battery_fire", "flammable_liquids", "manual_handling"),
    "yakit_toptan_depo": ("flammable_liquids", "atex", "static_electricity", "tanker_loading", "spill_response"),
    "yapi_malzemeleri_toptan": ("lifting", "storage_stability", "mineral_dust", "sharp_edges", "vehicle_traffic"),
    "atik_hurda_toptan": ("hazardous_waste", "sharps", "storage_stability", "mobile_plant", "fire"),
    "genel_toptan_depo": ("forklifts", "storage_racking", "loading_docks", "manual_handling", "fire"),
    "kimyasal_perakende": ("chemical_exposure", "segregated_storage", "flammable_liquids", "spill_response", "fire"),
    "kaynakli_imalat": ("hot_work", "welding_fume", "gas_cylinders", "fire", "lifting"),
    "makine_imalat": ("machinery", "energy_isolation", "lifting", "noise", "metalworking_fluids"),
    "elektrik_bakim": ("electrical", "arc_flash", "energy_isolation", "working_at_height", "fire"),
    "enerji_uretim": ("electrical", "high_voltage", "energy_isolation", "confined_space", "fire"),
    "atik_yonetimi_geri_donusum": ("biological_agents", "sharps", "machinery", "vehicle_traffic", "hazardous_waste"),
    "su_atiksu": ("biological_agents", "confined_space", "toxic_gases", "chemical_treatment", "drowning"),
    "ofis": ("display_screen", "ergonomics", "fire", "electrical", "psychosocial"),
    "ofis_idari_hizmetler": ("display_screen", "ergonomics", "fire", "electrical", "psychosocial"),
}

_SPECIAL_RISKS: dict[str, tuple[str, ...]] = {
    "insaat": ("fall_from_height", "collapse", "buried_services"),
    "insaat_santiye": ("fall_from_height", "collapse", "buried_services"),
    "madencilik_maden_ocagi": ("ground_collapse", "explosion", "toxic_atmosphere"),
    "kapali_maden": ("ground_collapse", "explosion", "toxic_atmosphere"),
    "patlayici": ("mass_explosion", "fireball", "fragmentation"),
    "kimya_kimyasal_uretim": ("major_accident", "toxic_release", "runaway_reaction"),
    "petrol_rafineri_depolama": ("major_accident", "vapour_cloud_explosion", "toxic_release"),
    "gemi_insa_tersane": ("confined_space_fatality", "fall_from_height", "dropped_load"),
    "balikcilik_su_urunleri": ("man_overboard", "hypothermia", "refrigerant_release"),
    "saglik_hastane_klinik": ("bloodborne_exposure", "infectious_disease", "violence"),
    "su_atiksu": ("toxic_atmosphere", "oxygen_deficiency", "drowning"),
    "metal_yapi_elemanlari_toptan": ("dropped_load", "load_collapse", "vehicle_collision"),
    "canli_hayvan_toptan": ("animal_escape", "crushing", "zoonotic_exposure"),
    "kimyasal_toptan_depo": ("toxic_release", "warehouse_fire", "incompatible_reaction"),
    "yakit_toptan_depo": ("vapour_cloud_explosion", "major_fire", "tanker_release"),
    "atik_hurda_toptan": ("unknown_hazardous_material", "pile_collapse", "battery_fire"),
}


@dataclass(frozen=True)
class NaceClassification:
    catalog_key: str | None
    nace_code: str | None
    nace_description: str | None
    nace_section_code: str | None
    nace_section_name: str | None
    subsector_code: str | None
    activity_group_code: str | None
    content_profile_code: str | None
    content_profile_name: str | None
    hazard_class: str | None
    training_topics: tuple[str, ...]
    technical_risk_tags: tuple[str, ...]
    special_risks: tuple[str, ...]
    required_duration_minutes: int | None
    required_duration_hours: int | None
    classification_status: str
    catalog_version: str
    catalog_hash: str
    source_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["training_topics"] = list(self.training_topics)
        data["technical_risk_tags"] = list(self.technical_risk_tags)
        data["special_risks"] = list(self.special_risks)
        return data

    def database_values(
        self, *, training_id: int, company_id: int, branch_id: int | None
    ) -> dict[str, Any]:
        return {
            "training_id": training_id,
            "company_id": company_id,
            "branch_id": branch_id,
            "catalog_key": self.catalog_key,
            "nace_code": self.nace_code,
            "nace_description": self.nace_description,
            "nace_section_code": self.nace_section_code,
            "nace_section_name": self.nace_section_name,
            "subsector_code": self.subsector_code,
            "activity_group_code": self.activity_group_code,
            "content_profile_code": self.content_profile_code,
            "content_profile_name": self.content_profile_name,
            "hazard_class": self.hazard_class,
            "training_topics_json": _json(list(self.training_topics)),
            "technical_risk_tags_json": _json(list(self.technical_risk_tags)),
            "special_risks_json": _json(list(self.special_risks)),
            "required_duration_minutes": self.required_duration_minutes,
            "required_duration_hours": self.required_duration_hours,
            "classification_status": self.classification_status,
            "catalog_version": self.catalog_version,
            "catalog_hash": self.catalog_hash,
            "source_snapshot_json": _json(self.source_snapshot),
        }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=1)
def _catalog_indexes() -> tuple[dict[str, dict], dict[str, dict]]:
    by_key: dict[str, dict] = {}
    by_nace: dict[str, dict] = {}
    for raw in sectors_list_for_api(include_legacy_nace_aliases=True):
        row = dict(raw)
        key = str(row.get("code") or "").strip()
        nace = str(row.get("nace") or "").strip()
        if key:
            by_key[key] = row
        if nace:
            by_nace[nace] = row
    return by_key, by_nace


def _section(nace_code: str) -> tuple[str | None, str | None]:
    try:
        division = int(nace_code.split(".", 1)[0])
    except (TypeError, ValueError):
        return None, None
    for code, name, start, end in _SECTION_RANGES:
        if start <= division <= end:
            return code, name
    return None, None


def _codes(nace_code: str) -> tuple[str | None, str | None]:
    parts = nace_code.split(".")
    subsector = ".".join(parts[:2]) if len(parts) >= 2 else None
    activity = ".".join(parts[:3]) if len(parts) >= 3 else subsector
    return subsector, activity


def _catalog_hash(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest()


def resolve_exact_nace(value: str | None) -> NaceClassification:
    """Resolve only an exact catalog key or exact catalog NACE code.

    Raises ``ValueError`` instead of falling back to a different sector.
    """
    raw = str(value or "").strip()
    by_key, by_nace = _catalog_indexes()
    row = by_key.get(raw)
    if row is None and _EXACT_NACE_RE.fullmatch(raw):
        row = by_nace.get(raw)
    if row is None:
        raise ValueError(
            "Geçerli ve tam bir NACE faaliyeti seçilmelidir; genel sektör veya "
            "ilgili olmayan yedek profil kabul edilmez."
        )

    catalog_key = str(row.get("code") or "").strip()
    nace_code = str(row.get("nace") or "").strip()
    description = str(row.get("name") or "").strip()
    hazard = str(row.get("hazard_class") or "").strip()
    profile = str(SEKTOR_PROFIL.get(catalog_key) or "").strip()
    catalog_topics = tuple(
        str(item).strip() for item in (row.get("topics") or []) if str(item).strip()
    )
    topics = tuple(
        str(item).strip()
        for item in sektorel_konular(catalog_key)
        if str(item).strip()
    )

    errors: list[str] = []
    if not catalog_key.startswith("nace_"):
        errors.append("resmî katalog anahtarı")
    if not _EXACT_NACE_RE.fullmatch(nace_code):
        errors.append("tam NACE kodu")
    if not description:
        errors.append("NACE açıklaması")
    if hazard not in VALID_HAZARD_CLASSES:
        errors.append("tehlike sınıfı")
    if not profile:
        errors.append("içerik profili")
    if len(topics) != 5:
        errors.append("beş onaylı sektörel eğitim konusu")
    if errors:
        raise ValueError(
            "NACE sınıflandırması eksik veya geçersiz: " + ", ".join(errors) + "."
        )

    section_code, section_name = _section(nace_code)
    if not section_code:
        raise ValueError("NACE bölüm sınıflandırması çözümlenemedi.")
    subsector, activity_group = _codes(nace_code)
    risk_tags = tuple(_PROFILE_RISK_TAGS.get(profile, ()))
    risk_mapping_status = "verified" if risk_tags else "review_required"
    special_risks = tuple(_SPECIAL_RISKS.get(profile, ())) if risk_tags else ()

    duration = TEHLIKE_EGITIM_KURALLARI[hazard]
    source_snapshot = {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "catalog_row": row,
        "catalog_key": catalog_key,
        "nace_code": nace_code,
        "content_profile_code": profile,
        "content_profile_name": SEKTOR_ADLARI.get(profile) or sektor_adi(profile),
        "section": {"code": section_code, "name": section_name},
        "topic_mapping": {
            "source": "canonical_training_topics_v1",
            "catalog_topics_overridden": catalog_topics != topics,
        },
        "catalog_topics": list(catalog_topics),
        "training_topics": list(topics),
        "risk_mapping": {
            "status": risk_mapping_status,
            "source": "controlled_profile_map_v1" if risk_tags else None,
            "review_reasons": [] if risk_tags else ["technical_risk_tags_missing"],
        },
        "technical_risk_tags": list(risk_tags),
        "special_risks": list(special_risks),
        "duration_rule": {
            "hazard_class": hazard,
            "minutes": int(duration["dakika"]),
            "hours": int(duration["saat"]),
        },
    }
    return NaceClassification(
        catalog_key=catalog_key,
        nace_code=nace_code,
        nace_description=description,
        nace_section_code=section_code,
        nace_section_name=section_name,
        subsector_code=subsector,
        activity_group_code=activity_group,
        content_profile_code=profile,
        content_profile_name=SEKTOR_ADLARI.get(profile) or sektor_adi(profile),
        hazard_class=hazard,
        training_topics=topics,
        technical_risk_tags=risk_tags,
        special_risks=special_risks,
        required_duration_minutes=int(duration["dakika"]),
        required_duration_hours=int(duration["saat"]),
        classification_status=risk_mapping_status,
        catalog_version=CLASSIFICATION_SCHEMA_VERSION,
        catalog_hash=_catalog_hash(source_snapshot),
        source_snapshot=source_snapshot,
    )


def classify_legacy(value: str | None, hazard_class: str | None = None) -> NaceClassification:
    """Represent a legacy profile without inventing an exact NACE code."""
    raw = str(value or "").strip() or None
    profile_name = (SEKTOR_ADLARI.get(raw or "") or sektor_adi(raw)) if raw else None
    topics = tuple(str(item).strip() for item in sektorel_konular(raw) if str(item).strip())
    source_snapshot = {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "legacy_value": raw,
        "reason": "Exact official NACE identity is not present in the historical training record.",
        "profile_name": profile_name,
        "hazard_class": hazard_class,
        "training_topics": list(topics),
    }
    duration = TEHLIKE_EGITIM_KURALLARI.get(str(hazard_class or "").strip())
    return NaceClassification(
        catalog_key=raw,
        nace_code=None,
        nace_description=None,
        nace_section_code=None,
        nace_section_name=None,
        subsector_code=None,
        activity_group_code=None,
        content_profile_code=raw,
        content_profile_name=profile_name,
        hazard_class=str(hazard_class or "").strip() or None,
        training_topics=topics,
        technical_risk_tags=(),
        special_risks=(),
        required_duration_minutes=int(duration["dakika"]) if duration else None,
        required_duration_hours=int(duration["saat"]) if duration else None,
        classification_status="legacy_unverified",
        catalog_version=CLASSIFICATION_SCHEMA_VERSION,
        catalog_hash=_catalog_hash(source_snapshot),
        source_snapshot=source_snapshot,
    )


def classify_training_value(
    value: str | None, *, hazard_class: str | None = None
) -> NaceClassification:
    try:
        return resolve_exact_nace(value)
    except ValueError:
        return classify_legacy(value, hazard_class)


_snapshot_hook_installed = False


def install_training_nace_snapshot_hooks() -> str:
    """Freeze the classification when a training row is inserted.

    The hook is installed during application bootstrap, before development
    ``create_all`` and after Alembic in production. Existing records are not
    rewritten and no exact NACE code is inferred for legacy profile values.
    """
    global _snapshot_hook_installed
    if _snapshot_hook_installed:
        return "already-active"

    @event.listens_for(TrainingSession, "after_insert")
    def _freeze_training_nace(_mapper, connection, target: TrainingSession) -> None:
        classification = classify_training_value(
            target.sector, hazard_class=target.hazard_class
        )
        connection.execute(
            TrainingNaceSnapshot.__table__.insert().values(
                **classification.database_values(
                    training_id=int(target.id),
                    company_id=int(target.company_id),
                    branch_id=target.branch_id,
                )
            )
        )

    _snapshot_hook_installed = True
    return "active"
