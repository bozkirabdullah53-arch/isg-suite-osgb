from app.services.special_training_profiles import special_meta_for_api, special_profiles_for_api
import re

from app.services.training_topics import (
    SEKTOR_PROFIL,
    TEHLIKE_EGITIM_KURALLARI,
    egitim_konularini_hazirla,
    sectors_list_for_api,
)


def test_pro_sector_catalog_size():
    sectors = sectors_list_for_api()
    assert len(sectors) == 2142
    codes = {s["code"] for s in sectors}
    assert "genel_uretim" in codes
    assert "nace_01_48_01" in codes
    assert "nace_20_59_17" in codes
    for sector in sectors:
        assert len(sector["topics"]) == 5
        assert len(set(sector["topics"])) == 5


def test_nace_profiles_are_activity_compatible():
    expected = {
        "nace_01_48_01": "aricilik",
        "nace_08_93_02": "madencilik_maden_ocagi",
        "nace_20_59_17": "patlayici",
        "nace_30_11_02": "gemi_insa_tersane",
        "nace_47_30_01": "akaryakit_lpg_dolum_istasyonu",
        "nace_75_00_04": "veterinerlik",
        "nace_91_41_00": "hayvanat_bahcesi",
        "nace_96_10_03": "camasirhane_kuru_temizleme",
        "nace_96_30_01": "cenaze_hizmetleri",
    }
    for code, profile in expected.items():
        assert SEKTOR_PROFIL[code] == profile

    bee = next(item for item in sectors_list_for_api() if item["code"] == "nace_01_48_01")
    joined = " ".join(bee["topics"]).casefold()
    assert "arı sokmaları" in joined
    assert "anafilaksi" in joined
    assert "kovan" in joined
    assert "körük" in joined
    assert "sağım" not in joined
    assert "gübre gaz" not in joined


def test_every_nace_activity_has_exact_mandatory_topic_minutes():
    for sector in sectors_list_for_api():
        hazard = sector["hazard_class"]
        sol, sag, total, _hours = egitim_konularini_hazirla(hazard, sector["code"])
        all_minutes = [
            int(match.group(1))
            for _bold, text in sol + sag
            if (match := re.search(r"-\s*(\d+)\s*DK$", text))
        ]
        section_index = next(
            index for index, (_bold, text) in enumerate(sag) if text.startswith("4. ")
        )
        section_minutes = [
            int(match.group(1))
            for _bold, text in sag[section_index + 2:]
            if (match := re.search(r"-\s*(\d+)\s*DK$", text))
        ]
        rule = TEHLIKE_EGITIM_KURALLARI[hazard]
        assert total == sum(all_minutes) == rule["dakika"]
        assert sum(section_minutes) == rule["dorduncu_bolum_dakika"]
        assert len(section_minutes) == 5
        assert all(value > 0 and value % 5 == 0 for value in all_minutes)


def test_special_training_profiles_ported():
    profiles = special_profiles_for_api()
    expected_profiles = {
        "yuksekte_calisma",
        "hijyen_sanitasyon",
        "gida_su_hijyeni",
    }
    assert {p["code"] for p in profiles} == expected_profiles
    meta = special_meta_for_api()
    assert {p["code"] for p in meta["profiles"]} == expected_profiles
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


def test_height_training_replaces_oversized_hidden_stamp_with_profile_legal_basis():
    from datetime import date

    from app.schemas.training import TrainingCreate
    from app.services.special_training_profiles import SPECIAL_TRAINING_PROFILES

    payload = TrainingCreate(
        company_id=1,
        title="Yüksekte Çalışma Güvenliği Eğitimi",
        training_type="Yüksekte Çalışma Güvenliği Eğitimi",
        delivery_method="Yüz yüze ve uygulamalı",
        location="İşyeri Eğitim Salonu",
        start_date=date(2026, 8, 8),
        end_date=date(2026, 8, 10),
        hazard_class="Tehlikeli",
        sector="genel_uretim",
        instructor_name="Abdullah Bozkır",
        instructor_qualification="A Sınıfı İş Güvenliği Uzmanı",
        stamp_text="x" * 1000,
        evaluation_method="Yazılı ve uygulamalı değerlendirme",
        participant_ids=[1],
    )

    assert payload.stamp_text == SPECIAL_TRAINING_PROFILES["yuksekte_calisma"]["legal_basis"]
    assert len(payload.stamp_text) <= 400
