"""Regression coverage for the requested remote-training sector categories."""
from __future__ import annotations


REQUESTED_SECTORS = {
    "emergency_teams": "Acil Durum Ekiplerinin Eğitimleri",
    "health": "Hastaneler ve Sağlık Hizmetleri",
    "education_universities": "Eğitim Kurumları ve Üniversiteler",
    "public_municipalities": "Kamu Kurumları ve Belediyeler",
    "agriculture_livestock_forestry": "Tarım, Hayvancılık ve Ormancılık",
    "hospitality_tourism_restaurants": "Konaklama, Turizm ve Restoran",
    "trade_retail_markets": "Ticaret, Perakende ve Marketler",
    "energy_electricity_gas": "Enerji, Elektrik ve Doğalgaz",
    "water_sewerage_waste": "Su, Kanalizasyon ve Atık Yönetimi",
    "textile_clothing_leather": "Tekstil, Giyim ve Deri",
    "plastic_rubber": "Plastik ve Kauçuk",
    "wood_furniture": "Ağaç ve Mobilya",
    "ceramic_glass_marble": "Seramik, Cam ve Mermer",
    "building_cleaning_security": "Bina, Temizlik ve Güvenlik Hizmetleri",
    "automotive_vehicle_services": "Otomotiv ve Araç Servisleri",
    "battery": "Akü, Pil ve Enerji Depolama",
}


def test_all_requested_remote_sector_categories_are_selectable_and_mapped():
    from app.models.remote_training import REMOTE_SECTOR_CODES, REMOTE_SECTOR_LABELS
    from app.services.remote_training_custom_packages import (
        custom_package_base_code,
        custom_package_sector_code,
    )

    assert set(REQUESTED_SECTORS).issubset(REMOTE_SECTOR_CODES)
    for sector_code, label in REQUESTED_SECTORS.items():
        assert REMOTE_SECTOR_LABELS[sector_code] == label
        custom_code = f"custom--{sector_code}--abc123"
        assert custom_package_sector_code(custom_code) == sector_code
        expected_base = (
            "health-services-ohs"
            if sector_code == "health"
            else "battery-production-ohs"
            if sector_code == "battery"
            else "emergency-teams-ohs"
            if sector_code == "emergency_teams"
            else "common-basic-ohs"
        )
        assert custom_package_base_code(custom_code) == expected_base
