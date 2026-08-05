"""Reviewed technical-risk taxonomy for training content profiles.

Every entry is explicitly tied to the five canonical training topics of that
profile. This module never derives risks from free-text activity names or broad
NACE sections.
"""
from __future__ import annotations

from typing import Final

RISK_CATALOG_VERSION: Final = "training-risk-profile-v1"

REVIEWED_PROFILE_RISK_TAGS: Final[dict[str, tuple[str, ...]]] = {
    "perakende": ("slips_trips", "storage_racking", "manual_handling", "cutting_equipment", "crowd_evacuation"),
    "bakim_onarim_teknik_servis": ("machinery", "energy_isolation", "vehicle_traffic", "manual_handling", "fire"),
    "tekstil": ("machinery_entanglement", "textile_dust", "chemical_exposure", "hot_surfaces", "repetitive_work"),
    "genel_uretim": ("machinery", "vehicle_traffic", "manual_handling", "fire", "maintenance"),
    "elektronik": ("solder_fume", "electrical", "static_electricity", "robotics", "battery_fire"),
    "demir_celik_hadde": ("molten_metal", "lifting", "metal_fume", "heat_stress", "crushing"),
    "cam_seramik": ("sharp_edges", "hot_furnace", "silica_dust", "grinding", "lifting"),
    "egitim_kurumu": ("public_safety", "laboratory_workshop", "emergency_evacuation", "slips_trips", "violence"),
    "belediye_kamu_hizmetleri": ("road_traffic", "biological_agents", "sharps", "excavation", "confined_space"),
    "otomotiv": ("robotics", "vehicle_lift", "welding_fume", "solvents", "high_voltage_vehicle"),
    "ahsap_mobilya": ("woodworking_machinery", "wood_dust", "solvents", "nail_gun", "combustible_dust"),
    "plastik_kaucuk": ("injection_moulding", "hot_polymer", "chemical_exposure", "conveyors", "fire_smoke"),
    "banka_finans": ("display_screen", "ergonomics", "psychosocial", "violence", "fire"),
    "elektrik_elektronik_uretim": ("solder_fume", "electrical", "static_electricity", "robotics", "battery_fire"),
    "restoran_cafe_mutfak": ("cutting_equipment", "hot_oil", "lpg_natural_gas", "slips_trips", "food_hygiene"),
    "basin_yayin_medya": ("display_screen", "ergonomics", "electrical", "slips_trips", "psychosocial"),
    "hirdavat_yapi_market": ("slips_trips", "storage_racking", "manual_handling", "cutting_equipment", "crowd_evacuation"),
    "spor_tesisi_fitness": ("fitness_equipment", "slips_trips", "pool_chemicals", "biological_agents", "first_aid"),
    "kagit_karton_uretimi": ("machinery_entanglement", "printing_chemicals", "paper_dust", "heavy_rolls", "static_fire"),
    "ayakkabi_deri_uretimi": ("cutting_machinery", "leather_dust", "adhesives", "hot_surfaces", "repetitive_work"),
    "ekipman_kiralama": ("equipment_inspection", "loading_unloading", "lifting", "energy_isolation", "fuel_battery_fire"),
    "muhendislik_proje_ofisi": ("display_screen", "ergonomics", "electrical", "slips_trips", "psychosocial"),
    "boyahaneler_boya_uretimi": ("solvents", "isocyanates", "toxic_vapour", "atex", "chemical_storage"),
    "dijital_baski_matbaa": ("machinery_entanglement", "printing_chemicals", "paper_dust", "heavy_rolls", "static_fire"),
    "is_makinesi_agir_ekipman": ("working_at_height", "excavation", "lifting", "mobile_plant", "temporary_electricity"),
    "beton_cimento_hazir_beton": ("silica_dust", "conveyors", "rotating_equipment", "concrete_pump", "mobile_plant"),
    "laboratuvar_analiz": ("chemical_exposure", "fume_hood", "compressed_gases", "cryogenic_liquids", "biological_agents"),
    "organizasyon_etkinlik": ("working_at_height", "temporary_electricity", "manual_handling", "crowd_management", "weather"),
    "konaklama_otel_pansiyon": ("hot_surfaces", "pool_chemicals", "biological_agents", "slips_trips", "night_work"),
    "hayvancilik": ("animal_contact", "zoonoses", "manure_gases", "agricultural_machinery", "slips_trips"),
    "otomotiv_servis_bakim": ("vehicle_lift", "maintenance_pit", "welding_fume", "solvents", "high_voltage_vehicle"),
    "telekom": ("working_at_height", "electrical", "rf_fields", "roadside_work", "lone_work"),
    "temizlik_facility_management": ("cleaning_chemicals", "slips_trips", "biological_agents", "ladder_work", "sharps"),
    "avukatlik_hukuk_burosu": ("display_screen", "ergonomics", "storage_racking", "electrical", "psychosocial"),
    "demiryolu": ("rail_traffic", "high_voltage", "machinery", "tunnel_work", "night_work"),
    "guzellik_kuafor_spa": ("cosmetic_chemicals", "skin_exposure", "sharps", "hot_surfaces", "sterilization"),
    "kozmetik_temizlik_urunleri": ("chemical_exposure", "powder_exposure", "mixing_machinery", "clean_room", "sterilization"),
    "bilisim_yazilim_it": ("display_screen", "ergonomics", "server_room", "electrical", "psychosocial"),
    "firin_unlu_mamuller": ("food_machinery", "hot_surfaces", "steam", "refrigerants", "cleaning_chemicals"),
    "kuyumculuk_mucevher": ("machinery", "fine_dust", "chemical_exposure", "hot_work", "security"),
    "seramik_fayans": ("sharp_edges", "hot_furnace", "silica_dust", "grinding", "lifting"),
    "petrol_dogalgaz": ("flammable_gases", "atex", "toxic_gases", "confined_space", "static_electricity"),
    "aku_uretimi": ("lead_exposure", "sulfuric_acid", "hydrogen_gas", "chemical_spill", "health_surveillance"),
    "atik_geri_donusum": ("sharps", "waste_sorting", "baling_machinery", "biological_agents", "battery_fire"),
    "camasirhane_kuru_temizleme": ("dry_cleaning_solvents", "steam", "hot_surfaces", "laundry_machinery", "biological_agents"),
    "ilac_farmasotik_uretim": ("active_pharmaceutical_dust", "solvents", "mixing_machinery", "clean_room", "sterilization"),
    "reklam_tabela_baski": ("machinery_entanglement", "printing_chemicals", "paper_dust", "heavy_materials", "static_fire"),
    "sut_sut_urunleri": ("food_machinery", "hot_process", "refrigerants", "cleaning_in_place", "biological_agents"),
    "aricilik": ("bee_stings", "anaphylaxis", "manual_handling", "smoker_fire", "outdoor_weather"),
    "eczane_medikal_satis": ("storage_racking", "cold_chain", "biological_agents", "night_work", "violence"),
    "guvenlik_hizmetleri": ("violence", "lone_work", "night_work", "crowd_management", "suspicious_package"),
    "sigorta_broker": ("display_screen", "ergonomics", "psychosocial", "violence", "fire"),
    "turizm_seyahat": ("travel_safety", "display_screen", "psychosocial", "public_contact", "emergency"),
    "kablo_tel_uretimi": ("wire_drawing_machinery", "electrical", "chemical_exposure", "repetitive_work", "fire"),
    "kurye": ("road_traffic", "weather", "manual_handling", "violence", "lone_work"),
    "laboratuvar": ("chemical_exposure", "fume_hood", "compressed_gases", "cryogenic_liquids", "biological_agents"),
    "temizlik": ("cleaning_chemicals", "slips_trips", "biological_agents", "ladder_work", "sharps"),
    "veterinerlik": ("animal_attack", "zoonoses", "sharps", "anesthetic_gases", "ionizing_radiation"),
    "akaryakit_lpg_dolum_istasyonu": ("flammable_liquids", "lpg", "atex", "static_electricity", "vehicle_traffic"),
    "cenaze_hizmetleri": ("biological_agents", "manual_handling", "disinfectants", "sharps", "psychosocial"),
    "dagitim_kargo_kurye": ("road_traffic", "weather", "manual_handling", "violence", "lone_work"),
    "elektrik_tesisat_pano_montaj": ("electrical", "arc_flash", "energy_isolation", "electrical_panels", "permit_to_work"),
    "universite_yuksekogretim": ("public_safety", "laboratory_workshop", "emergency_evacuation", "slips_trips", "violence"),
    "hayvanat_bahcesi": ("wild_animal_attack", "zoonoses", "animal_escape", "crowd_management", "emergency_capture"),
    "tutun_urunleri_uretimi": ("tobacco_dust", "nicotine_exposure", "machinery", "combustible_dust", "ergonomics"),
}

REVIEWED_SPECIAL_RISKS: Final[dict[str, tuple[str, ...]]] = {
    "tekstil": ("machinery_entanglement", "dust_fire", "chemical_overexposure"),
    "demir_celik_hadde": ("molten_metal_release", "dropped_load", "severe_heat_stress"),
    "belediye_kamu_hizmetleri": ("confined_space_fatality", "traffic_strike", "biological_exposure"),
    "otomotiv": ("vehicle_fall", "high_voltage_electrocution", "paint_fire"),
    "ahsap_mobilya": ("dust_explosion", "machine_amputation", "solvent_fire"),
    "plastik_kaucuk": ("molten_polymer_burn", "machine_entanglement", "toxic_fire_smoke"),
    "boyahaneler_boya_uretimi": ("flash_fire", "toxic_release", "isocyanate_overexposure"),
    "is_makinesi_agir_ekipman": ("fall_from_height", "collapse", "dropped_load"),
    "beton_cimento_hazir_beton": ("silica_overexposure", "concrete_hose_whip", "machine_entanglement"),
    "laboratuvar_analiz": ("toxic_release", "gas_cylinder_rupture", "cryogenic_burn"),
    "organizasyon_etkinlik": ("structural_collapse", "crowd_crush", "temporary_electrical_fatality"),
    "hayvancilik": ("toxic_manure_atmosphere", "animal_crush", "zoonotic_exposure"),
    "otomotiv_servis_bakim": ("vehicle_fall", "high_voltage_electrocution", "paint_fire"),
    "telekom": ("fall_from_height", "electrocution", "lone_worker_emergency"),
    "demiryolu": ("train_strike", "high_voltage_electrocution", "tunnel_emergency"),
    "petrol_dogalgaz": ("vapour_cloud_explosion", "toxic_release", "confined_space_fatality"),
    "aku_uretimi": ("lead_poisoning", "acid_burn", "hydrogen_explosion"),
    "atik_geri_donusum": ("battery_thermal_runaway", "waste_fire", "machine_entanglement"),
    "ilac_farmasotik_uretim": ("potent_compound_overexposure", "solvent_fire", "pressure_release"),
    "aricilik": ("anaphylaxis", "wildfire", "remote_area_emergency"),
    "veterinerlik": ("animal_attack", "zoonotic_outbreak", "anesthetic_gas_overexposure"),
    "akaryakit_lpg_dolum_istasyonu": ("vapour_cloud_explosion", "vehicle_fire", "toxic_release"),
    "elektrik_tesisat_pano_montaj": ("arc_flash_fatality", "electrocution", "energized_work"),
    "hayvanat_bahcesi": ("wild_animal_attack", "animal_escape", "zoonotic_outbreak"),
    "tutun_urunleri_uretimi": ("combustible_dust_explosion", "nicotine_overexposure", "machine_entanglement"),
}


def apply_reviewed_risk_profiles() -> int:
    """Install the reviewed mappings into the classification service."""
    from app.services import training_nace_classification as classification

    changed = 0
    for profile, tags in REVIEWED_PROFILE_RISK_TAGS.items():
        if classification._PROFILE_RISK_TAGS.get(profile) != tags:
            classification._PROFILE_RISK_TAGS[profile] = tags
            changed += 1
    for profile, risks in REVIEWED_SPECIAL_RISKS.items():
        classification._SPECIAL_RISKS[profile] = risks
    return changed
