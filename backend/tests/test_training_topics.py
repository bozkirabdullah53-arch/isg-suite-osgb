from app.services.training_topics import (
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
    assert sektor_kodu_cozumle("İnşaat / Şantiye") == "insaat"
    assert sektor_kodu_cozumle(None) == "genel_uretim"


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
