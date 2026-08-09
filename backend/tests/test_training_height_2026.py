from types import SimpleNamespace

from app.services.special_training_profiles import (
    SPECIAL_INSTRUCTOR_ROLES,
    SPECIAL_TRAINING_PROFILES,
)
from app.services.training_height_2026 import (
    HEIGHT_LEGAL_BASIS,
    apply_height_training_profile_2026,
    height_instructor_is_authorized,
    is_height_training,
)


def test_height_profile_2026_only_restricts_height_instructor_roles():
    apply_height_training_profile_2026()

    height = SPECIAL_TRAINING_PROFILES["yuksekte_calisma"]
    assert height["allowed_roles"] == [
        "isg_a",
        "isg_b",
        "isg_c",
        "isyeri_hekimi",
        "yonetmelik_m10_kurum_egiticisi",
    ]
    assert "02.04.2026" in HEIGHT_LEGAL_BASIS
    assert "m.10" in height["legal_basis"]
    assert "yuksekte_calisma" in SPECIAL_INSTRUCTOR_ROLES["isyeri_hekimi"]["profiles"]
    assert "yuksekte_calisma" not in SPECIAL_INSTRUCTOR_ROLES["yuksekte_egitmen"]["profiles"]


def test_height_profile_detection_does_not_match_other_trainings():
    assert is_height_training(
        SimpleNamespace(
            training_type="Yüksekte Çalışma Güvenliği Eğitimi",
            title="Yüksekte Çalışma Güvenliği Eğitimi",
            notes="",
        )
    )
    assert not is_height_training(
        SimpleNamespace(
            training_type="Temel İSG Eğitimi",
            title="Temel İş Sağlığı ve Güvenliği Eğitimi",
            notes="",
        )
    )
    assert not is_height_training(
        SimpleNamespace(
            training_type="Hijyen",
            title="İşyeri İçi Hijyen ve Sanitasyon Bilgilendirme Eğitimi",
            notes="",
        )
    )


def test_standalone_height_trainer_certificate_is_not_treated_as_legal_authority():
    assert height_instructor_is_authorized("A Sınıfı İş Güvenliği Uzmanı")
    assert height_instructor_is_authorized("İşyeri Hekimi")
    assert height_instructor_is_authorized(
        "Yönetmelik m.10 Kapsamında Yetkili Kurum/Kuruluş Eğiticisi"
    )
    assert not height_instructor_is_authorized("Belgeli Yüksekte Çalışma Eğitmeni")
