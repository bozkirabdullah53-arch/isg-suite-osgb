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
        resolve_training_curriculum,
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

    yuksek_cur = resolve_training_curriculum(
        SimpleNamespace(training_type="Yüksekte Çalışma Güvenliği Eğitimi", title="", notes="")
    )
    assert yuksek_cur["is_special"] is True
    assert yuksek_cur["duration_hours"] == 8
    assert any("Yüksekte çalışma" in t[1] for t in yuksek_cur["sol"] + yuksek_cur["sag"] if not t[0])
    assert "GENEL KONULAR" not in " ".join(t[1] for t in yuksek_cur["sol"] + yuksek_cur["sag"])

    hijyen_cur = resolve_training_curriculum(
        SimpleNamespace(training_type="İşyeri İçi Hijyen ve Sanitasyon Bilgilendirme Eğitimi", title="", notes="")
    )
    assert hijyen_cur["duration_hours"] == 4
    assert any("hijyen" in t[1].casefold() for t in hijyen_cur["sol"] + hijyen_cur["sag"])


def test_special_hours_override_hazard_rules():
    from app.schemas.training import resolve_training_hours

    assert (
        resolve_training_hours(
            training_type="Yüksekte Çalışma Güvenliği Eğitimi",
            title="Yüksekte Çalışma Güvenliği Eğitimi",
            notes="",
            hazard_class="Çok Tehlikeli",
        )
        == 8
    )
    assert (
        resolve_training_hours(
            training_type="İşyeri İçi Hijyen ve Sanitasyon Bilgilendirme Eğitimi",
            title="Hijyen",
            notes="",
            hazard_class="Çok Tehlikeli",
        )
        == 4
    )
    assert (
        resolve_training_hours(
            training_type="Temel İSG Eğitimi",
            title="Temel",
            notes="",
            hazard_class="Çok Tehlikeli",
        )
        == 16
    )