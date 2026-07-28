"""İSG temel eğitim — 6331 kapsamı sektör kataloğu ve belge konuları.

Belgede basılan müfredat: genel + teknik + sağlık + işyerine özgü (sektör) konular.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

TEHLIKE_EGITIM_KURALLARI = {
    "Az Tehlikeli": {
        "saat": 8,
        "dakika": 8 * 60,
        "sure": "8 DERS SAAT",
        "yenileme": "3 yılda bir yenilenir",
        "yenileme_yil": 3,
    },
    "Tehlikeli": {
        "saat": 12,
        "dakika": 12 * 60,
        "sure": "12 DERS SAAT",
        "yenileme": "2 yılda bir yenilenir",
        "yenileme_yil": 2,
    },
    "Çok Tehlikeli": {
        "saat": 16,
        "dakika": 16 * 60,
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


# Build maps
SEKTOR_SECENEKLERI: list[tuple[str, str]] = [(c, n) for c, n, _, _ in _SECTOR_RAW]
SEKTOREL_EGITIM_KONULARI: dict[str, list[str]] = {
    c: _topics_with_dk(SEKTOREL_KONU_DUZELTMELERI.get(c, topics)) for c, _, _, topics in _SECTOR_RAW
}
SEKTOR_TEHLIKE: dict[str, str] = {
    c: TEHLIKE_SINIFI_DUZELTMELERI.get(c, h) for c, _, h, _ in _SECTOR_RAW
}


def tehlike_kurali(tehlike_sinifi: str) -> dict:
    return TEHLIKE_EGITIM_KURALLARI.get(
        (tehlike_sinifi or "").strip(), TEHLIKE_EGITIM_KURALLARI["Çok Tehlikeli"]
    )


def sektor_adi(sektor_kodu: str | None) -> str:
    return dict(SEKTOR_SECENEKLERI).get(sektor_kodu or "", "Genel Fabrika / Üretim")


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
    if raw in ("01", "02", "03", "04", "05"):
        return "genel_uretim"
    return "genel_uretim"


def sektorel_konular(sektor_kodu: str | None) -> list[str]:
    kod = sektor_kodu_cozumle(sektor_kodu)
    return list(SEKTOREL_EGITIM_KONULARI.get(kod, SEKTOREL_EGITIM_KONULARI["genel_uretim"]))


def sure_ekini_temizle(konu: str) -> str:
    return re.sub(r"\s*-\s*\d+\s*DK\s*$", "", str(konu or "")).strip()


def konu_dakikalarini_hedefe_esitle(konular: list[tuple[int, str]], hedef_dakika: int) -> list[tuple[int, str]]:
    n = len(konular)
    if n == 0:
        return []
    taban = max(5, (hedef_dakika // n // 5) * 5)
    dagitim = [taban] * n
    kalan = hedef_dakika - sum(dagitim)
    i = 0
    while kalan >= 5:
        dagitim[i % n] += 5
        kalan -= 5
        i += 1
    if kalan:
        dagitim[-1] += kalan
    return [(b, f"{sure_ekini_temizle(m)} - {dk} DK") for (b, m), dk in zip(konular, dagitim)]


def egitim_konularini_hazirla(tehlike_sinifi: str, sektor: str | None = None):
    kural = tehlike_kurali(tehlike_sinifi)
    hedef_dakika = int(kural["dakika"])
    hedef_saat = int(kural["saat"])
    sektorel = sektorel_konular(sektor)

    sabit_sol = [
        (1, "1. GENEL KONULAR"),
        (0, "a) Çalışma mevzuatı"),
        (0, "b) Yasal hak ve sorumluluklar"),
        (0, "c) İşyeri temizliği ve düzeni"),
        (0, "d) İş kazası hukuki sonuçlar"),
        (1, "2. TEKNİK KONULAR"),
        (0, "a) Kimyasal/fiziksel/ergonomik risk"),
        (0, "b) Elle kaldırma ve taşıma"),
        (0, "c) Parlama, patlama, yangın"),
        (0, "d) İş ekipman güvenli kullanım"),
        (0, "e) Ekranlı araçlar"),
        (0, "f) Elektrik tehlikeleri/önlem"),
        (0, "g) İş kazası sebepleri/korunma"),
        (0, "h) Sağlık ve güvenlik işaretleri"),
        (0, "ı) Kişisel koruyucu donanım"),
        (0, "i) İSG kuralları ve güvenlik kültürü"),
        (0, "j) Acil durum, tahliye, kurtarma"),
    ]
    sabit_sag = [
        (1, "3. SAĞLIK KONULARI"),
        (0, "a) Meslek hastalıkları sebepleri"),
        (0, "b) Korunma prensipleri/teknikleri"),
        (0, "c) Biyolojik/psikososyal risk"),
        (0, "d) İlk yardım"),
        (0, "e) Bağımlılık/teknoloji bağımlılığı"),
        (1, "4. İŞ VE İŞYERİNE ÖZGÜ RİSKLER"),
        (1, "Risk Değerlendirmesine Dayalı"),
        (0, "1) Risk değerlendirme durumları"),
        (0, "2) Acil durum eylem planı"),
    ]
    for sira, konu in enumerate(sektorel[:5], start=3):
        sabit_sag.append((0, f"{sira}) {sure_ekini_temizle(konu)}"))

    tum = [("sol", i, b, m) for i, (b, m) in enumerate(sabit_sol)] + [
        ("sag", i, b, m) for i, (b, m) in enumerate(sabit_sag)
    ]
    dakika_girdiler = [(b, m) for _, _, b, m in tum if not b]
    dakika_ciktilar = konu_dakikalarini_hedefe_esitle(dakika_girdiler, hedef_dakika)

    sol, sag = [], []
    di = 0
    for taraf, _, baslik_mi, metin in tum:
        if baslik_mi:
            satir = (baslik_mi, metin)
        else:
            satir = dakika_ciktilar[di]
            di += 1
        (sol if taraf == "sol" else sag).append(satir)
    return sol, sag, hedef_dakika, hedef_saat


def katilim_formu_konu_ozeti(tehlike_sinifi: str, sektor: str | None = None) -> str:
    """PRO imza formu konu özeti formatı."""
    sektorel = [sure_ekini_temizle(k) for k in sektorel_konular(sektor)[:5]]
    ana = (
        "1. Genel Konular / 2. Teknik Konular / 3. Sağlık Konuları / "
        "4. İş ve İşyerine Özgü Riskler"
    )
    if sektorel:
        return ana + " | Sektöre Özgü Başlıklar: " + "; ".join(sektorel)
    return ana


def sectors_list_for_api() -> list[dict]:
    path = Path(__file__).resolve().parent / "data" / "nace_sectors.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for row in sorted(rows, key=lambda x: str(x.get("label") or x.get("name") or "").casefold()):
        topics = [sure_ekini_temizle(t) for t in (row.get("topics") or [])]
        items.append({
            "code": row["code"],
            "name": row["name"],
            "label": row.get("label") or f"{row.get('nace','')} / {row['name']} / {row['hazard_class']}",
            "hazard_class": row["hazard_class"],
            "nace": row.get("nace"),
            "topics": topics,
        })
    return items


def meta_payload() -> dict:
    return {
        "hazard_rules": TEHLIKE_EGITIM_KURALLARI,
        "sectors": sectors_list_for_api(),
    }
