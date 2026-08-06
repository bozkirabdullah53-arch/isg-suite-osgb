"""Dijital Personel Kartı için izole ve fail-closed rollout ayarları.

Bu modül mevcut ana Settings sınıfını veya çalışan personel akışlarını değiştirmez.
Feature varsayılan olarak kapalıdır; şirket allowlist'i boşsa hiçbir şirket aktif olmaz.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class PersonnelProfileSettings(BaseSettings):
    personnel_profile_card_enabled: bool = False
    personnel_profile_card_force_off: bool = False
    personnel_profile_card_pilot_company_ids: str = ""
    personnel_profile_restricted_data_enabled: bool = False
    personnel_profile_external_sharing_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


personnel_profile_settings = PersonnelProfileSettings()


def personnel_profile_pilot_company_ids() -> frozenset[int]:
    """Virgülle ayrılmış pilot şirketleri güvenli biçimde ayrıştırır.

    Hatalı, sıfır veya negatif değerler yok sayılır. Dönen kimlikler API yanıtlarında
    açıklanmaz; yalnız sunucu tarafı erişim kararında kullanılır.
    """

    raw = str(
        getattr(personnel_profile_settings, "personnel_profile_card_pilot_company_ids", "")
        or ""
    )
    company_ids: set[int] = set()
    for token in raw.split(","):
        clean = token.strip()
        if not clean:
            continue
        try:
            company_id = int(clean)
        except (TypeError, ValueError):
            continue
        if company_id > 0:
            company_ids.add(company_id)
    return frozenset(company_ids)


def personnel_profile_card_active(company_id: int | None = None) -> bool:
    """Global flag + force-off + fail-closed şirket allowlist kapısı."""

    if bool(getattr(personnel_profile_settings, "personnel_profile_card_force_off", False)):
        return False
    if not bool(getattr(personnel_profile_settings, "personnel_profile_card_enabled", False)):
        return False
    if company_id is None:
        return False
    try:
        normalized_company_id = int(company_id)
    except (TypeError, ValueError):
        return False
    return normalized_company_id in personnel_profile_pilot_company_ids()


def personnel_profile_rollout(company_id: int | None) -> dict[str, bool]:
    """Allowlist üyelerini açıklamayan, hassas olmayan rollout teşhisi."""

    pilots = personnel_profile_pilot_company_ids()
    global_enabled = bool(
        getattr(personnel_profile_settings, "personnel_profile_card_enabled", False)
    )
    force_off = bool(
        getattr(personnel_profile_settings, "personnel_profile_card_force_off", False)
    )
    try:
        normalized_company_id = int(company_id) if company_id is not None else None
    except (TypeError, ValueError):
        normalized_company_id = None
    pilot_company = bool(normalized_company_id and normalized_company_id in pilots)
    return {
        "global_enabled": global_enabled,
        "force_off": force_off,
        "allowlist_configured": bool(pilots),
        "pilot_company": pilot_company,
        "active": bool(global_enabled and not force_off and pilot_company),
    }


def personnel_profile_restricted_data_active(company_id: int | None) -> bool:
    """Restricted veri şirket kapısı ve ayrı hukuki flag olmadan aktif değildir."""

    return bool(
        personnel_profile_card_active(company_id)
        and getattr(personnel_profile_settings, "personnel_profile_restricted_data_enabled", False)
    )


def personnel_profile_external_sharing_active(company_id: int | None) -> bool:
    """Dış paylaşım şirket kapısı ve ayrı onay flag'i olmadan aktif değildir."""

    return bool(
        personnel_profile_card_active(company_id)
        and getattr(personnel_profile_settings, "personnel_profile_external_sharing_enabled", False)
    )
