"""Dijital Personel Kartı için izole ve fail-closed rollout ayarları.

OSGB profesyonel kartları işyeri şirketinden bağımsız olarak OSGB kimliğiyle açılır.
Eski şirket allowlist'i yalnız geriye uyumlu işyeri profil uçları için korunur.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PersonnelProfileSettings(BaseSettings):
    personnel_profile_card_enabled: bool = False
    personnel_profile_card_force_off: bool = False
    personnel_profile_card_pilot_company_ids: str = ""
    personnel_profile_card_pilot_osgb_ids: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


personnel_profile_settings = PersonnelProfileSettings()


def _positive_ids(raw: object) -> frozenset[int]:
    values: set[int] = set()
    for token in str(raw or "").split(","):
        clean = token.strip()
        if not clean:
            continue
        try:
            value = int(clean)
        except (TypeError, ValueError):
            continue
        if value > 0:
            values.add(value)
    return frozenset(values)


def personnel_profile_pilot_company_ids() -> frozenset[int]:
    """Geriye uyumlu işyeri pilot kimlikleri."""
    return _positive_ids(
        getattr(personnel_profile_settings, "personnel_profile_card_pilot_company_ids", "")
    )


def personnel_profile_pilot_osgb_ids() -> frozenset[int]:
    """OSGB profesyonel kartı için açık OSGB kimlikleri."""
    return _positive_ids(
        getattr(personnel_profile_settings, "personnel_profile_card_pilot_osgb_ids", "")
    )


def _global_open() -> bool:
    return bool(
        getattr(personnel_profile_settings, "personnel_profile_card_enabled", False)
    ) and not bool(
        getattr(personnel_profile_settings, "personnel_profile_card_force_off", False)
    )


def personnel_profile_card_active(company_id: int | None = None) -> bool:
    """Eski işyeri kapsamlı uçlar için geriye uyumlu kapı."""
    if not _global_open() or company_id is None:
        return False
    try:
        normalized = int(company_id)
    except (TypeError, ValueError):
        return False
    return normalized in personnel_profile_pilot_company_ids()


def personnel_profile_osgb_card_active(osgb_id: int | None = None) -> bool:
    """OSGB'nin kendi profesyonel kartları için fail-closed kapı."""
    if not _global_open() or osgb_id is None:
        return False
    try:
        normalized = int(osgb_id)
    except (TypeError, ValueError):
        return False
    return normalized in personnel_profile_pilot_osgb_ids()


def personnel_profile_rollout(company_id: int | None) -> dict[str, bool]:
    pilots = personnel_profile_pilot_company_ids()
    try:
        normalized = int(company_id) if company_id is not None else None
    except (TypeError, ValueError):
        normalized = None
    pilot = bool(normalized and normalized in pilots)
    return {
        "global_enabled": bool(personnel_profile_settings.personnel_profile_card_enabled),
        "force_off": bool(personnel_profile_settings.personnel_profile_card_force_off),
        "allowlist_configured": bool(pilots),
        "pilot_company": pilot,
        "active": bool(_global_open() and pilot),
    }


def personnel_profile_osgb_rollout(osgb_id: int | None) -> dict[str, bool]:
    pilots = personnel_profile_pilot_osgb_ids()
    try:
        normalized = int(osgb_id) if osgb_id is not None else None
    except (TypeError, ValueError):
        normalized = None
    pilot = bool(normalized and normalized in pilots)
    return {
        "global_enabled": bool(personnel_profile_settings.personnel_profile_card_enabled),
        "force_off": bool(personnel_profile_settings.personnel_profile_card_force_off),
        "allowlist_configured": bool(pilots),
        "pilot_osgb": pilot,
        "active": bool(_global_open() and pilot),
    }
