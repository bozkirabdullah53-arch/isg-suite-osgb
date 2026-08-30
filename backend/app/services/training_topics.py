"""İSG temel eğitim — 6331 kapsamı sektör kataloğu ve belge konuları.

Belgede basılan müfredat: genel + teknik + sağlık + işyerine özgü (sektör) konular.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from app.services.training_sector_catalog import (
    SEKTOR_ADLARI as PROFIL_ADLARI,
    SEKTOREL_EGITIM_KONULARI as PROFIL_KONULARI,
    SEKTOREL_KONU_AGIRLIKLARI,
    nace_profil_kodu_getir,
)

TEHLIKE_EGITIM_KURALLARI = {
    "Az Tehlikeli": {
        "saat": 8,
        "dakika": 8 * 45,
        "ilk_uc_dakika": 6 * 45,
        "dorduncu_bolum_dakika": 2 * 45,
        "dorduncu_bolum_ders_saati": 2,
        "dorduncu_bolum_yontem": "Uzaktan, yüz yüze veya karma",
        "sure": "8 DERS SAAT",
        "yenileme": "3 yılda bir yenilenir",
        "yenileme_yil": 3,
    },
    "Tehlikeli": {
        "saat": 12,
        "dakika": 12 * 45,
        "ilk_uc_dakika": 9 * 45,
        "dorduncu_bolum_dakika": 3 * 45,
        "dorduncu_bolum_ders_saati": 3,
        "dorduncu_bolum_yontem": "Yüz yüze",
        "sure": "12 DERS SAAT",
        "yenileme": "2 yılda bir yenilenir",
        "yenileme_yil": 2,
    },
    "Çok Tehlikeli": {
        "saat": 16,
        "dakika": 16 * 45,
        "ilk_uc_dakika": 12 * 45,
        "dorduncu_bolum_dakika": 4 * 45,
        "dorduncu_bolum_ders_saati": 4,
        "dorduncu_bolum_yontem": "Yüz yüze",
        "sure": "16 DERS SAAT",
        "yenileme": "Her yıl yenilenir",
        "yenileme_yil": 1,
    },
}

# (kod, ad, tehlike_sinifi, 5 sektörel konu) — ISG Pro 2026 tam katalog aktarımı
# Kaynak: training_sector_catalog.py / Pro egitim/sector_catalog.py
def _load_sector_raw() -> list[tuple[str, str, str, list[str]]]:
    path = Path(__file__).resolve().parent / "data" / "nace_sectors.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str, list[str]]] = []
    for row in rows:
        out.append(
            (
                str(row["code"]),
                str(row["name"]),
                str(row["hazard_class"]),
                list(row.get("topics") or []),
            )
        )
    if not out:
        raise RuntimeError(f"NACE sektör kataloğu boş: {path}")
    return out


# NACE 2026 resmi tehlike sınıfları (CSV → nace_sectors.json)
_SECTOR_RAW: list[tuple[str, str, str, list[str]]] = _load_sector_raw()


# Katalog aktarımında satırların büyük kısmı varsayılan "Tehlikeli" ile gelmişti.
# Sınıflar, İş Sağlığı ve Güvenliğine İlişkin İşyeri Tehlike Sınıfları Tebliği
# (NACE Rev.2) karşılıklarına göre düzeltilir.
TEHLIKE_SINIFI_DUZELTMELERI: dict[str, str] = {
    # Yapı işleri (NACE 41-43)
    "insaat": "Çok Tehlikeli",
    "insaat_santiye": "Çok Tehlikeli",
    "muteahhitlik_taahhut": "Çok Tehlikeli",
    "yol_altyapi_insaati": "Çok Tehlikeli",
    "iskele_kalip_yapi_ekipmani": "Çok Tehlikeli",
    "yuksekte_calisma_cephe": "Çok Tehlikeli",
    "celik_yapi_metal_konstruksiyon": "Çok Tehlikeli",
    "asansor_montaj_ve_bakim": "Çok Tehlikeli",
    "is_makinesi_agir_ekipman": "Çok Tehlikeli",
    # Madencilik ve taş ocakçılığı (NACE 05-09)
    "madencilik_maden_ocagi": "Çok Tehlikeli",
    "tas_ocagi_maden_ocagi": "Çok Tehlikeli",
    "kapali_maden": "Çok Tehlikeli",
    # Tersane, liman, demiryolu (NACE 30.11, 52.24, 42.12)
    "gemi_insa_tersane": "Çok Tehlikeli",
    "tersane": "Çok Tehlikeli",
    "tersane_liman_hizmetleri": "Çok Tehlikeli",
    "liman": "Çok Tehlikeli",
    "demiryolu": "Çok Tehlikeli",
    # Metal ana sanayi (NACE 24)
    "demir_celik_hadde": "Çok Tehlikeli",
    # Kimya, patlayıcı, petrol, gaz (NACE 19-20, 35.22)
    "kimya_kimyasal_uretim": "Çok Tehlikeli",
    "boyahaneler_boya_uretimi": "Çok Tehlikeli",
    "patlayici": "Çok Tehlikeli",
    "petrol_rafineri_depolama": "Çok Tehlikeli",
    "akaryakit_lpg_dolum_istasyonu": "Çok Tehlikeli",
    "dogalgaz_enerji_dagitim": "Çok Tehlikeli",
    # Enerji üretim/iletim (NACE 35.11, 33.14)
    "enerji_jenerator_trafo": "Çok Tehlikeli",
    "yenilenebilir_enerji": "Çok Tehlikeli",
    "yenilenebilir_enerji_gunes_ruzgar": "Çok Tehlikeli",
    "telekomunikasyon_altyapi": "Çok Tehlikeli",
    # Kauçuk, cam, çimento, yapı malzemesi (NACE 22.1, 23)
    "plastik_kaucuk": "Çok Tehlikeli",
    "cam_seramik_porselen": "Çok Tehlikeli",
    "cam_seramik": "Çok Tehlikeli",
    "cimento_klinker": "Çok Tehlikeli",
    "beton_cimento_hazir_beton": "Çok Tehlikeli",
    "yapi_malzemeleri_uretimi": "Çok Tehlikeli",
    "kagit_karton_uretimi": "Çok Tehlikeli",
    "tekstil_dokuma_boyama": "Çok Tehlikeli",
    "otomotiv": "Çok Tehlikeli",
    # Ormancılık, balıkçılık, atık, atıksu (NACE 02.20, 03.11, 37-38)
    "ormancilik": "Çok Tehlikeli",
    "ormancilik_kereste": "Çok Tehlikeli",
    "balikcilik_su_urunleri": "Çok Tehlikeli",
    "atik_yonetimi_geri_donusum": "Çok Tehlikeli",
    "atik_geri_donusum": "Çok Tehlikeli",
    "elektronik_atik_bertaraf": "Çok Tehlikeli",
    "su_atiksu": "Çok Tehlikeli",
    # Hastane hizmetleri (NACE 86.10)
    "saglik": "Çok Tehlikeli",
    "saglik_hastane_klinik": "Çok Tehlikeli",
    # Büro, finans, bilişim, eğitim, kamu idaresi (NACE 62, 64-66, 69, 82, 84-85)
    "avukatlik_hukuk_burosu": "Az Tehlikeli",
    "banka_finans": "Az Tehlikeli",
    "banka_finans_2": "Az Tehlikeli",
    "sigorta_broker": "Az Tehlikeli",
    "cagri_merkezi_contact_center": "Az Tehlikeli",
    "bilisim_yazilim_it": "Az Tehlikeli",
    "muhendislik_proje_ofisi": "Az Tehlikeli",
    "ofis_idari_hizmetler": "Az Tehlikeli",
    "basin_yayin_medya": "Az Tehlikeli",
    "organizasyon_etkinlik": "Az Tehlikeli",
    "egitim_okul_kurs": "Az Tehlikeli",
    "egitim_kurumu": "Az Tehlikeli",
    "universite_yuksekogretim": "Az Tehlikeli",
    "kamu_kurumu_idare": "Az Tehlikeli",
    # Perakende, konaklama, yeme-içme, kişisel hizmet (NACE 47, 55-56, 93, 96)
    "market_perakende": "Az Tehlikeli",
    "perakende": "Az Tehlikeli",
    "alisveris_merkezi_avm": "Az Tehlikeli",
    "hirdavat_yapi_market": "Az Tehlikeli",
    "eczane_medikal_satis": "Az Tehlikeli",
    "konaklama_otel_pansiyon": "Az Tehlikeli",
    "turizm": "Az Tehlikeli",
    "restoran_cafe_mutfak": "Az Tehlikeli",
    "restoran": "Az Tehlikeli",
    "guzellik_kuafor_spa": "Az Tehlikeli",
    "spor_tesisi_fitness": "Az Tehlikeli",
}

# Aktarımda bazı sektörlere başka bir sektörün konu seti eşlenmişti
# (ör. hukuk bürosuna kanalizasyon gazı). Bu sektörlerin konuları yeniden yazıldı.
SEKTOREL_KONU_DUZELTMELERI: dict[str, list[str]] = {
    "avukatlik_hukuk_burosu": [
        "Ekranlı araçlarla çalışma, oturma düzeni ve ergonomi",
        "Arşiv, dosya taşıma ve raf-istif düzeni",
        "Elektrikli büro ekipmanları ve kablo düzeni",
        "Yangın, tahliye ve toplanma alanı uygulamaları",
        "Duruşma-saha ziyaretlerinde yol güvenliği ve psikososyal riskler",
    ],
    "bilisim_yazilim_it": [
        "Ekranlı araçlarla çalışma, göz sağlığı ve mola düzeni",
        "Oturma düzeni, ergonomi ve tekrarlayan zorlanmalar",
        "Sistem odası: elektrik, sıcaklık ve yangın riskleri",
        "Kablo düzeni, kayma-takılma ve düzenli çalışma alanı",
        "Uzun çalışma saatleri, iş yükü ve psikososyal riskler",
    ],
    "kamu_kurumu_idare": [
        "Ekranlı araçlarla çalışma, oturma düzeni ve ergonomi",
        "Arşiv, evrak taşıma ve raf-istif güvenliği",
        "Elektrikli büro ekipmanları ve kayma-takılma riskleri",
        "Yangın, deprem, tahliye ve toplanma alanları",
        "Halka açık hizmet alanlarında şiddet ve psikososyal riskler",
    ],
    "organizasyon_etkinlik": [
        "Sahne, truss, ışık-ses kurulumunda yüksekte çalışma",
        "Geçici elektrik tesisatı, jeneratör ve kablo güvenliği",
        "Ağır ekipman taşıma, elle kaldırma ve ergonomi",
        "Kalabalık yönetimi, acil çıkış ve tahliye planı",
        "Yangın, hava koşulları ve açık alan riskleri",
    ],
    "eczane_medikal_satis": [
        "İlaç ve medikal ürün istifleme, raf ve depo düzeni",
        "Soğuk zincir, buzdolabı ve ürün taşıma güvenliği",
        "Hijyen, bulaşıcı hastalık ve kişisel korunma",
        "Nöbet, gece çalışması, şiddet ve psikososyal riskler",
        "Yangın, elektrikli cihazlar ve acil durum uygulamaları",
    ],
    "guzellik_kuafor_spa": [
        "Boya, oksidan, keratin ve kozmetik kimyasallara maruziyet",
        "Havalandırma, solunum koruma ve cilt koruma",
        "Makas, jilet, elektrikli cihaz ve sıcak yüzey riskleri",
        "Ayakta çalışma, ergonomi ve tekrarlayan hareketler",
        "Hijyen, sterilizasyon, kayma-düşme ve yangın güvenliği",
    ],
    "spor_tesisi_fitness": [
        "Ağırlık, kondisyon aleti ve ekipman bakımı güvenliği",
        "Üye ve çalışan için kayma-düşme, çarpma riskleri",
        "Havuz/sauna alanlarında kimyasal, biyolojik ve termal riskler",
        "Elle taşıma, ergonomi ve tekrarlayan zorlanmalar",
        "İlk yardım, acil durum, yangın ve tahliye uygulamaları",
    ],
    "balikcilik_su_urunleri": [
        "Güvertede kayma-düşme, denize düşme ve kurtarma",
        "Ağ, halat, vinç ve makara ile çalışmada sıkışma riskleri",
        "Soğuk, ıslak ortam, ısı stresi ve uzun vardiyalar",
        "Kesici aletler, biyolojik etkenler ve hijyen",
        "Soğutma tesisatı, amonyak/gaz kaçağı ve acil durumlar",
    ],
}


def _topics_with_dk(topics: list[str]) -> list[str]:
    return [t if " DK" in t else f"{t} - 30 DK" for t in topics]


# Build maps. Resmî tehlike sınıfı doğrudan NACE kaydından, konu profili ise
# NACE bölüm/alt kod hiyerarşisinden gelir; faaliyet metninde rastlantısal
# kelime eşleştirmesi yapılmaz.
SEKTOR_SECENEKLERI: list[tuple[str, str]] = [(c, n) for c, n, _, _ in _SECTOR_RAW]


def _nace_kodu(code: str) -> str:
    return code.removeprefix("nace_").replace("_", ".") if code.startswith("nace_") else ""


SEKTOR_PROFIL: dict[str, str] = {
    code: nace_profil_kodu_getir(_nace_kodu(code)) if code.startswith("nace_") else code
    for code, _name, _hazard, _topics in _SECTOR_RAW
}
SEKTOREL_EGITIM_KONULARI: dict[str, list[str]] = {
    code: _topics_with_dk(PROFIL_KONULARI.get(SEKTOR_PROFIL[code], topics))
    for code, _name, _hazard, topics in _SECTOR_RAW
}
SEKTOR_TEHLIKE: dict[str, str] = {code: hazard for code, _name, hazard, _topics in _SECTOR_RAW}
# Eski OSGB eğitim kayıtları profil kodu saklamış olabilir. Bu kodlar API
# listesini kalabalıklaştırmadan PDF ve kayıt açma akışında geriye uyumlu kalır.
SEKTOREL_EGITIM_KONULARI.update({
    code: _topics_with_dk(SEKTOREL_KONU_DUZELTMELERI.get(code, topics))
    for code, topics in PROFIL_KONULARI.items()
})
SEKTOR_TEHLIKE.update({
    code: TEHLIKE_SINIFI_DUZELTMELERI.get(code, "Tehlikeli")
    for code in PROFIL_KONULARI
})

# Eski NACE yayımlarında kullanılan kodlar. Güncel katalogdaki 41.00.xx
# satırlarını değiştirmeden, eski işyeri kayıtlarının da aynı faaliyet ve
# tehlike sınıfına çözümlenmesini sağlar. Bu harita tek bir kod için özel
# davranış eklemez; bilinen eski yapı kodlarının tamamı için geriye uyumluluk
# katmanıdır.
LEGACY_NACE_ALIASES: dict[str, dict[str, str]] = {
    "41.20.01": {
        "current_nace": "41.00.02",
        "name": "İkamet amaçlı olmayan binaların inşaatı (fabrika, atölye, hastane, okul, otel, işyeri ve benzeri binaların inşaatı)",
        "hazard_class": "Çok Tehlikeli",
    },
    "41.20.02": {
        "current_nace": "41.00.01",
        "name": "İkamet amaçlı binaların inşaatı (müstakil konutlar, birden çok ailenin oturduğu binalar, gökdelenler vb.nin inşaatı) (ahşap binaların inşaatı hariç)",
        "hazard_class": "Çok Tehlikeli",
    },
    "41.20.03": {
        "current_nace": "41.00.05",
        "name": "Prefabrik binalar için bileşenlerin alanda birleştirilmesi ve kurulması",
        "hazard_class": "Çok Tehlikeli",
    },
    "41.20.04": {
        "current_nace": "41.00.04",
        "name": "İkamet amaçlı ahşap binaların inşaatı",
        "hazard_class": "Çok Tehlikeli",
    },
    "41.20.05": {
        "current_nace": "41.00.03",
        "name": "Mevcut ikamet amaçlı olan veya ikamet amaçlı olmayan binaların yeniden düzenlenmesi veya yenilenmesi",
        "hazard_class": "Çok Tehlikeli",
    },
}
LEGACY_NACE_ALIAS_BY_KEY: dict[str, dict[str, str]] = {
    f"nace_{nace.replace('.', '_')}": {"nace": nace, **meta}
    for nace, meta in LEGACY_NACE_ALIASES.items()
}

for _legacy_nace, _legacy_meta in LEGACY_NACE_ALIASES.items():
    _legacy_key = f"nace_{_legacy_nace.replace('.', '_')}"
    _current_key = f"nace_{_legacy_meta['current_nace'].replace('.', '_')}"
    _current_profile = SEKTOR_PROFIL.get(_current_key)
    if _current_profile:
        SEKTOR_PROFIL[_legacy_key] = _current_profile
    _current_topics = SEKTOREL_EGITIM_KONULARI.get(_current_key, [])
    if _current_topics:
        SEKTOREL_EGITIM_KONULARI[_legacy_key] = list(_current_topics)
    SEKTOR_TEHLIKE[_legacy_key] = _legacy_meta["hazard_class"]


def tehlike_kurali(tehlike_sinifi: str) -> dict:
    return TEHLIKE_EGITIM_KURALLARI.get(
        (tehlike_sinifi or "").strip(), TEHLIKE_EGITIM_KURALLARI["Çok Tehlikeli"]
    )


def sektor_adi(sektor_kodu: str | None) -> str:
    code = sektor_kodu or ""
    return dict(SEKTOR_SECENEKLERI).get(
        code,
        PROFIL_ADLARI.get(code, LEGACY_NACE_ALIAS_BY_KEY.get(code, {}).get("name", "")),
    )


def sektor_kodu_cozumle(sektor: str | None) -> str:
    if not sektor:
        return "genel_uretim"
    raw = sektor.strip()
    if raw in SEKTOREL_EGITIM_KONULARI:
        return raw
    nace_code = "nace_" + raw.replace(".", "_")
    if nace_code in SEKTOREL_EGITIM_KONULARI:
        return nace_code
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return kod
    for kod, ad in PROFIL_ADLARI.items():
        if ad.casefold() == raw.casefold():
            return kod
    if raw in ("01", "02", "03", "04", "05"):
        return "genel_uretim"
    return "genel_uretim"


def sektorel_konular(sektor_kodu: str | None) -> list[str]:
    kod = sektor_kodu_cozumle(sektor_kodu)
    return list(SEKTOREL_EGITIM_KONULARI.get(kod, []))


def sektor_tehlike_sinifi(sektor_kodu: str | None) -> str:
    return SEKTOR_TEHLIKE.get(sektor_kodu_cozumle(sektor_kodu), "")


def sure_ekini_temizle(konu: str) -> str:
    return re.sub(r"\s*-\s*\d+\s*DK\s*$", "", str(konu or "")).strip()


def _bes_dakikaya_yuvarla(value: float) -> int:
    return max(5, int(round(float(value) / 5.0) * 5))


def agirlikli_dakika_dagitimi(
    konular: list[str], hedef_dakika: int, agirliklar
) -> list[tuple[str, int]]:
    if not konular:
        return []
    agirliklar = [max(0.1, float(x)) for x in list(agirliklar)[:len(konular)]]
    if len(agirliklar) < len(konular):
        agirliklar.extend([1.0] * (len(konular) - len(agirliklar)))
    toplam_agirlik = sum(agirliklar) or 1.0
    dagitim = [
        _bes_dakikaya_yuvarla(int(hedef_dakika) * weight / toplam_agirlik)
        for weight in agirliklar
    ]
    fark = int(hedef_dakika) - sum(dagitim)
    siralama = sorted(range(len(konular)), key=lambda i: (-agirliklar[i], i))
    while fark >= 5:
        for i in siralama:
            if fark < 5:
                break
            dagitim[i] += 5
            fark -= 5
    while fark <= -5:
        degisti = False
        for i in reversed(siralama):
            if fark > -5:
                break
            if dagitim[i] > 5:
                dagitim[i] -= 5
                fark += 5
                degisti = True
        if not degisti:
            break
    if fark:
        dagitim[siralama[0]] += fark
    return list(zip(konular, dagitim))


def _temel_konu_tanimlari():
    return [
        ("sol", 1, "1. GENEL KONULAR", 0),
        ("sol", 0, "a) Çalışma mevzuatı ve temel kavramlar", 1.10),
        ("sol", 0, "b) Çalışanların yasal hak ve sorumlulukları", 1.05),
        ("sol", 0, "c) İşyeri temizliği ve düzeni", 0.80),
        ("sol", 0, "ç) İş kazası ve meslek hastalığından doğan hukuki sonuçlar", 1.05),
        ("sol", 1, "2. SAĞLIK KONULARI", 0),
        ("sol", 0, "a) Meslek hastalıklarının sebepleri", 1.10),
        ("sol", 0, "b) Hastalıktan korunma prensipleri ve korunma tekniklerinin uygulanması", 1.10),
        ("sol", 0, "c) Biyolojik ve psikososyal risk etmenleri", 0.95),
        ("sol", 0, "ç) İlk yardım", 0.85),
        ("sol", 0, "d) Bağımlılık yapıcı maddelerin zararları ve teknoloji bağımlılığı", 0.60),
        ("sol", 1, "3. TEKNİK KONULAR", 0),
        ("sol", 0, "a) Kimyasal, fiziksel ve ergonomik risk etmenleri", 1.20),
        ("sol", 0, "b) Elle kaldırma ve taşıma", 0.85),
        ("sol", 0, "c) Parlama ve patlama", 1.05),
        ("sol", 0, "ç) Yangın ve yangından korunma", 1.15),
        ("sag", 1, "3. TEKNİK KONULAR (DEVAM)", 0),
        ("sag", 0, "d) İş ekipmanlarının güvenli kullanımı", 1.20),
        ("sag", 0, "e) Ekranlı araçlarla çalışma", 0.60),
        ("sag", 0, "f) Elektrik tehlikeleri, riskleri ve önlemleri", 1.05),
        ("sag", 0, "g) İş kazalarının sebepleri ve korunma prensipleri ile tekniklerinin uygulanması", 1.00),
        ("sag", 0, "ğ) Sağlık ve güvenlik işaretleri", 0.55),
        ("sag", 0, "h) Kişisel koruyucu donanım kullanımı", 0.85),
        ("sag", 0, "ı) İş sağlığı ve güvenliği genel kuralları ve güvenlik kültürü", 0.75),
        ("sag", 0, "i) Acil durumlar, tahliye ve kurtarma", 1.05),
    ]


def dorduncu_bolum_basligi(tehlike_sinifi: str, buyuk_harf: bool = False) -> str:
    if (tehlike_sinifi or "").strip() == "Az Tehlikeli":
        baslik = "4. Faaliyetin Genel Tehlike ve Riskleri"
    else:
        baslik = "4. İşe ve İşyerine Özgü Riskler ve Risk Değerlendirmesine Dayalı Konular"
    return baslik.upper() if buyuk_harf else baslik


def egitim_konularini_hazirla(tehlike_sinifi: str, sektor: str | None = None):
    kural = tehlike_kurali(tehlike_sinifi)
    sektorel = sektorel_konular(sektor)
    if len(sektorel) != 5:
        raise ValueError("Geçerli bir NACE faaliyeti seçilmeli ve beş sektörel konu bulunmalıdır.")

    tanimlar = _temel_konu_tanimlari()
    temel_metinler = [metin for _taraf, baslik, metin, _w in tanimlar if not baslik]
    temel_agirliklar = [w for _taraf, baslik, _metin, w in tanimlar if not baslik]
    temel_dagitim = iter(
        agirlikli_dakika_dagitimi(temel_metinler, kural["ilk_uc_dakika"], temel_agirliklar)
    )
    sol, sag = [], []
    for taraf, baslik, metin, _weight in tanimlar:
        if baslik:
            satir = (1, metin)
        else:
            konu, dakika = next(temel_dagitim)
            satir = (0, f"{konu} - {dakika} DK")
        (sol if taraf == "sol" else sag).append(satir)

    sektorel_metinler = [
        f"{index}) {sure_ekini_temizle(konu)}"
        for index, konu in enumerate(sektorel, start=1)
    ]
    sektorel_dagitim = agirlikli_dakika_dagitimi(
        sektorel_metinler,
        kural["dorduncu_bolum_dakika"],
        SEKTOREL_KONU_AGIRLIKLARI,
    )
    aciklama = (
        "Faaliyetin genel tehlike ve riskleri"
        if (tehlike_sinifi or "").strip() == "Az Tehlikeli"
        else "Risk değerlendirmesine dayalı"
    )
    sag.extend([
        (1, dorduncu_bolum_basligi(tehlike_sinifi, buyuk_harf=True)),
        (1, f"{aciklama} · {kural['dorduncu_bolum_ders_saati']} ders saati · {kural['dorduncu_bolum_yontem']}"),
    ])
    sag.extend((0, f"{metin} - {dakika} DK") for metin, dakika in sektorel_dagitim)
    return sol, sag, int(kural["dakika"]), int(kural["saat"])


def katilim_formu_konu_ozeti(tehlike_sinifi: str, sektor: str | None = None) -> str:
    sektorel = [sure_ekini_temizle(k) for k in sektorel_konular(sektor)[:5]]
    if len(sektorel) != 5:
        raise ValueError("Katılım formu için geçerli sektör konuları bulunamadı.")
    kural = tehlike_kurali(tehlike_sinifi)
    return (
        "1. Genel Konular / 2. Sağlık Konuları / 3. Teknik Konular | "
        f"{dorduncu_bolum_basligi(tehlike_sinifi)} "
        f"({kural['dorduncu_bolum_ders_saati']} ders saati, "
        f"{kural['dorduncu_bolum_yontem']}) | "
        f"{sektor_adi(sektor)}: {'; '.join(sektorel)}"
    )


def sectors_list_for_api(*, include_legacy_nace_aliases: bool = False) -> list[dict]:
    path = Path(__file__).resolve().parent / "data" / "nace_sectors.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for row in sorted(rows, key=lambda x: str(x.get("label") or x.get("name") or "").casefold()):
        code = str(row["code"])
        topics = [sure_ekini_temizle(t) for t in SEKTOREL_EGITIM_KONULARI.get(code, [])]
        hazard = SEKTOR_TEHLIKE.get(code, str(row["hazard_class"]))
        items.append({
            "code": code,
            "name": row["name"],
            "label": (
                f"{row.get('nace')} / {row['name']} / {hazard}"
                if row.get("nace")
                else row.get("label") or f"{row['name']} / {hazard}"
            ),
            "hazard_class": hazard,
            "nace": row.get("nace"),
            "topics": topics,
        })
    if include_legacy_nace_aliases:
        by_nace = {
            str(item.get("nace") or "").strip(): item
            for item in items
            if item.get("nace")
        }
        for legacy_nace, legacy_meta in LEGACY_NACE_ALIASES.items():
            if legacy_nace in by_nace:
                continue
            current = by_nace.get(legacy_meta["current_nace"])
            if not current:
                continue
            alias_key = f"nace_{legacy_nace.replace('.', '_')}"
            hazard = legacy_meta["hazard_class"]
            items.append({
                "code": alias_key,
                "name": legacy_meta["name"],
                "label": f"{legacy_nace} / {legacy_meta['name']} / {hazard}",
                "hazard_class": hazard,
                "nace": legacy_nace,
                "topics": list(current.get("topics") or []),
                "section": current.get("section") or "F",
                "is_legacy_alias": True,
                "source_nace": legacy_meta["current_nace"],
            })
        items.sort(key=lambda x: str(x.get("label") or x.get("name") or "").casefold())
    return items


def meta_payload() -> dict:
    return {
        "hazard_rules": TEHLIKE_EGITIM_KURALLARI,
        "sectors": sectors_list_for_api(include_legacy_nace_aliases=True),
    }
