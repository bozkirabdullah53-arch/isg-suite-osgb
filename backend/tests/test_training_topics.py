import pytest

from app.services.training_topics import (
    SEKTOR_TEHLIKE,
    SEKTOREL_EGITIM_KONULARI,
    egitim_konularini_hazirla,
    sektor_kodu_cozumle,
    tehlike_kurali,
)


def test_tehlike_rules():
    assert tehlike_kurali("Az Tehlikeli")["saat"] == 8
    assert tehlike_kurali("Tehlikeli")["dakika"] == 720
    assert tehlike_kurali("Çok Tehlikeli")["yenileme_yil"] == 1


def test_sektor_resolve():
    assert sektor_kodu_cozumle("insaat") == "insaat"
    # Pro katalogunda "İnşaat / Şantiye" kodu insaat_santiye
    assert sektor_kodu_cozumle("İnşaat / Şantiye") == "insaat_santiye"
    assert sektor_kodu_cozumle("İnşaat ve Şantiye") == "insaat"
    assert sektor_kodu_cozumle(None) == "genel_uretim"


@pytest.mark.parametrize(
    "kod,beklenen",
    [
        # Tehlike Sınıfları Tebliği — yapı, maden, tersane, kimya çok tehlikeli
        ("insaat_santiye", "Çok Tehlikeli"),
        ("insaat", "Çok Tehlikeli"),
        ("muteahhitlik_taahhut", "Çok Tehlikeli"),
        ("yuksekte_calisma_cephe", "Çok Tehlikeli"),
        ("madencilik_maden_ocagi", "Çok Tehlikeli"),
        ("tersane", "Çok Tehlikeli"),
        ("kimya_kimyasal_uretim", "Çok Tehlikeli"),
        ("patlayici", "Çok Tehlikeli"),
        ("saglik_hastane_klinik", "Çok Tehlikeli"),
        # Büro ve perakende hizmetleri az tehlikeli
        ("avukatlik_hukuk_burosu", "Az Tehlikeli"),
        ("bilisim_yazilim_it", "Az Tehlikeli"),
        ("banka_finans", "Az Tehlikeli"),
        ("egitim_okul_kurs", "Az Tehlikeli"),
        ("market_perakende", "Az Tehlikeli"),
        ("eczane_medikal_satis", "Az Tehlikeli"),
        # Orta grup değişmedi
        ("metal_isleme_torna_freze", "Tehlikeli"),
        ("gida_uretim", "Tehlikeli"),
    ],
)
def test_sektor_tehlike_sinifi_mevzuata_uygun(kod, beklenen):
    assert SEKTOR_TEHLIKE[kod] == beklenen


def test_buro_sektorlerine_alakasiz_konu_atanmaz():
    """Aktarım hatası: hukuk bürosuna kanalizasyon/havuz konuları eşlenmişti."""
    for kod in ("avukatlik_hukuk_burosu", "bilisim_yazilim_it", "kamu_kurumu_idare"):
        konular = " ".join(SEKTOREL_EGITIM_KONULARI[kod])
        assert "Kanalizasyon" not in konular
        assert "Havuz" not in konular
        assert "ergonomi" in konular.casefold()


def test_katilim_belgesinde_tehlike_sinifi_yazar():
    from types import SimpleNamespace

    from app.services.training_pdfs import certificate_meta_parts

    training = SimpleNamespace(
        hazard_class="Çok Tehlikeli",
        duration_hours=16,
        training_type="İlk Defa",
        delivery_method="Yüz yüze",
        verification_code="ABC123",
    )
    parts = certificate_meta_parts(training, kural=tehlike_kurali("Çok Tehlikeli"))
    assert "Tehlike Sınıfı: Çok Tehlikeli" in parts
    assert parts.index("Tehlike Sınıfı: Çok Tehlikeli") == 1


def test_konular_have_minutes_and_sections():
    sol, sag, toplam_dk, saat = egitim_konularini_hazirla("Çok Tehlikeli", "insaat")
    assert saat == 16
    assert toplam_dk == 960
    assert any(t.startswith("1. GENEL") for _, t in sol)
    assert any("Yüksekte çalışma" in t or "Yüksekte" in t for b, t in sag if not b)
    # dakika etiketli satırlar toplamı ~ hedef
    minutes = []
    for items in (sol, sag):
        for is_h, text in items:
            if is_h:
                continue
            if " DK" in text:
                minutes.append(int(text.rsplit("-", 1)[-1].replace("DK", "").strip()))
    assert sum(minutes) == 960
