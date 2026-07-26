from app.services.special_training_profiles import special_meta_for_api, special_profiles_for_api
from app.services.training_topics import sectors_list_for_api


def test_pro_sector_catalog_size():
    sectors = sectors_list_for_api()
    assert len(sectors) >= 150
    codes = {s["code"] for s in sectors}
    assert "genel_uretim" in codes
    assert "insaat" in codes
    assert "acik_maden" in codes
    # legacy Suite kodları korunur
    assert "yuksekte_calisma" in codes


def test_special_training_profiles_ported():
    profiles = special_profiles_for_api()
    assert {p["code"] for p in profiles} >= {"yuksekte_calisma", "hijyen_sanitasyon"}
    meta = special_meta_for_api()
    assert len(meta["profiles"]) == 2
    assert meta["instructor_roles"]
    assert meta["verification_methods"]
