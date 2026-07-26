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


def test_document_titles_follow_training_type():
    from types import SimpleNamespace

    from app.services.special_training_profiles import (
        DEFAULT_CERTIFICATE_TITLE,
        resolve_training_document_titles,
    )

    yuksek = resolve_training_document_titles(
        SimpleNamespace(training_type="Yüksekte Çalışma Güvenliği Eğitimi", title="", notes="")
    )
    assert "YÜKSEKTE" in yuksek["certificate_title"]
    assert yuksek["profile_key"] == "yuksekte_calisma"

    hijyen = resolve_training_document_titles(
        SimpleNamespace(training_type="İşyeri İçi Hijyen ve Sanitasyon Bilgilendirme Eğitimi", title="", notes="")
    )
    assert "HİJYEN" in hijyen["certificate_title"]
    assert hijyen["profile_key"] == "hijyen_sanitasyon"

    temel = resolve_training_document_titles(
        SimpleNamespace(training_type="Temel İSG Eğitimi", title="İlk Defa", notes="")
    )
    assert temel["certificate_title"] == DEFAULT_CERTIFICATE_TITLE
    assert temel["profile_key"] is None
