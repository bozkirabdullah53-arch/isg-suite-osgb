"""İSG temel eğitim konu motoru — Çalışma Bakanlığı belgesinde basılacak müfredat.

Kaynak: İSG PRO 2026 egitim modülü (tehlike sınıfı süreleri + sektörel konular).
"""
from __future__ import annotations

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

SEKTOR_SECENEKLERI = [
    ("aku_uretimi", "Akü Üretimi"),
    ("insaat", "İnşaat / Şantiye"),
    ("yol_asfalt", "Yol / Asfalt"),
    ("acik_maden", "Açık Maden / Taş Ocağı / Agrega"),
    ("kimyasal_boya", "Kimyasal / Boya"),
    ("dokum_metal", "Döküm / Metal"),
    ("makine_imalat", "Makine İmalat / Montaj"),
    ("kaynakli_imalat", "Kaynaklı İmalat"),
    ("ahsap_mobilya", "Ahşap / Mobilya"),
    ("gida_uretim", "Gıda Üretim"),
    ("depo_lojistik", "Depo / Lojistik"),
    ("elektrik_bakim", "Elektrik Bakım"),
    ("ofis", "Ofis / İdari İşler"),
    ("saglik", "Sağlık Sektörü"),
    ("temizlik", "Temizlik İşleri"),
    ("genel_uretim", "Genel Fabrika / Üretim"),
]

SEKTOREL_EGITIM_KONULARI = {
    "aku_uretimi": [
        "Kurşun ve bileşikleriyle çalışma - 30 DK",
        "Sülfürik asit ve sıçrama riski - 30 DK",
        "Hidrojen gazı ve patlama riski - 30 DK",
        "Kimyasal dökülme/acil müdahale - 30 DK",
        "Havalandırma, hijyen ve KKD kullanımı - 30 DK",
    ],
    "insaat": [
        "Yüksekte çalışma ve düşme riski - 30 DK",
        "İskele, merdiven ve platform güvenliği - 30 DK",
        "Kazı, göçük ve zemin emniyeti - 30 DK",
        "Vinç, kaldırma ve malzeme düşmesi - 30 DK",
        "Şantiye içi trafik ve iş makinesi riski - 30 DK",
    ],
    "yol_asfalt": [
        "Sıcak asfalt ve yanık riskleri - 30 DK",
        "Trafik altında çalışma güvenliği - 30 DK",
        "İş makineleriyle güvenli çalışma - 30 DK",
        "Bitüm, buhar ve kimyasal maruziyet - 30 DK",
        "Gece çalışması, görünürlük ve işaretleme - 30 DK",
    ],
    "acik_maden": [
        "Şev, kademe ve kaya düşmesi riskleri - 30 DK",
        "Patlatma sahası ve emniyet mesafeleri - 30 DK",
        "Kırma-eleme tesislerinde güvenli çalışma - 30 DK",
        "Toz, gürültü ve titreşim maruziyeti - 30 DK",
        "Ocak içi trafik ve iş makinesi güvenliği - 30 DK",
    ],
    "kimyasal_boya": [
        "Kimyasal etiketleme ve SDS/MSDS okuma - 30 DK",
        "Solvent ve buhar maruziyetinden korunma - 30 DK",
        "Parlama, patlama ve statik elektrik riski - 30 DK",
        "Kimyasal depolama ve uyumsuz maddeler - 30 DK",
        "Dökülme, sızıntı ve acil müdahale - 30 DK",
    ],
    "dokum_metal": [
        "Ergitme ocakları ve sıcak metal sıçraması - 30 DK",
        "Pota, vinç ve kaldırma operasyonları - 30 DK",
        "Yanık, ısı stresi ve termal riskler - 30 DK",
        "Duman, toz ve gaz maruziyeti - 30 DK",
        "Kalıp bozma ve sıkışma-ezilme riskleri - 30 DK",
    ],
    "makine_imalat": [
        "Makine koruyucuları ve emniyet tertibatları - 30 DK",
        "Sıkışma, ezilme ve kesilme riskleri - 30 DK",
        "Bakım-onarımda kilitleme/etiketleme - 30 DK",
        "Taşlama, kesme ve el aletleri güvenliği - 30 DK",
        "Montajda kaldırma-taşıma ve ergonomi - 30 DK",
    ],
    "kaynakli_imalat": [
        "Kaynak ışını ve göz-yüz koruması - 30 DK",
        "Kaynak dumanı ve havalandırma - 30 DK",
        "Sıcak çalışma izni ve yangın riski - 30 DK",
        "Basınçlı gaz tüpleriyle güvenli çalışma - 30 DK",
        "Kapalı alanda kaynak ve gaz ölçümü - 30 DK",
    ],
    "ahsap_mobilya": [
        "Kesici makineler ve koruyucu sistemler - 30 DK",
        "Talaş/toz maruziyeti ve patlama riski - 30 DK",
        "Vernik, boya ve solvent kullanımı - 30 DK",
        "Zımpara, pres ve el aleti güvenliği - 30 DK",
        "Yangın riski ve düzenli temizlik - 30 DK",
    ],
    "gida_uretim": [
        "Hijyen, çapraz bulaşma ve gıda güvenliği - 30 DK",
        "Kaygan zemin ve düşme riskleri - 30 DK",
        "Kesici-delici ekipmanlarla çalışma - 30 DK",
        "Sıcak yüzey, buhar ve yanık riski - 30 DK",
        "Soğuk oda ve ergonomik riskler - 30 DK",
    ],
    "depo_lojistik": [
        "Forklift ve yaya trafiği güvenliği - 30 DK",
        "Raf sistemleri ve devrilme riskleri - 30 DK",
        "Yükleme-boşaltma rampalarında güvenlik - 30 DK",
        "Elle taşıma, istifleme ve ergonomi - 30 DK",
        "Malzeme düşmesi ve alan düzeni - 30 DK",
    ],
    "elektrik_bakim": [
        "Elektrik çarpması ve ark parlaması - 30 DK",
        "Enerji kesme, kilitleme ve etiketleme - 30 DK",
        "Pano, kablo ve tesisat çalışmalarında güvenlik - 30 DK",
        "İzole ekipman ve uygun KKD kullanımı - 30 DK",
        "Yetkisiz müdahale ve çalışma izinleri - 30 DK",
    ],
    "ofis": [
        "Ekranlı araçlarla çalışma ve ergonomi - 30 DK",
        "Elektrikli ofis ekipmanlarının güvenli kullanımı - 30 DK",
        "Yangın, tahliye ve toplanma alanı - 30 DK",
        "Kayma, takılma ve düşme riskleri - 30 DK",
        "Psikososyal riskler ve stres yönetimi - 30 DK",
    ],
    "saglik": [
        "Biyolojik riskler ve enfeksiyon kontrolü - 30 DK",
        "Kesici-delici alet yaralanmaları - 30 DK",
        "Hasta taşıma ve ergonomik riskler - 30 DK",
        "Dezenfektan ve kimyasal kullanımı - 30 DK",
        "Şiddet, acil durum ve güvenli iletişim - 30 DK",
    ],
    "temizlik": [
        "Temizlik kimyasallarıyla güvenli çalışma - 30 DK",
        "Islak zemin, kayma ve düşme riskleri - 30 DK",
        "Biyolojik riskler ve atıklarla çalışma - 30 DK",
        "Yüksek alan temizliği ve merdiven güvenliği - 30 DK",
        "Kesici-delici atık yaralanmaları - 30 DK",
    ],
    "genel_uretim": [
        "Makine ve ekipmanlarla güvenli çalışma - 30 DK",
        "İşyeri içi trafik ve yaya yolları - 30 DK",
        "Elle taşıma, ergonomi ve istifleme - 30 DK",
        "Yangın, acil durum ve tahliye uygulamaları - 30 DK",
        "KKD kullanımı ve işyeri düzeni - 30 DK",
    ],
}


def tehlike_kurali(tehlike_sinifi: str) -> dict:
    return TEHLIKE_EGITIM_KURALLARI.get(
        (tehlike_sinifi or "").strip(), TEHLIKE_EGITIM_KURALLARI["Çok Tehlikeli"]
    )


def sektor_adi(sektor_kodu: str | None) -> str:
    return dict(SEKTOR_SECENEKLERI).get(sektor_kodu or "", "Genel Fabrika / Üretim")


def sektor_kodu_cozumle(sektor: str | None) -> str:
    """UI'dan gelen kod veya görünen adı sektörel anahtara çevirir."""
    if not sektor:
        return "genel_uretim"
    raw = sektor.strip()
    if raw in SEKTOREL_EGITIM_KONULARI:
        return raw
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return kod
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
    out = []
    for (baslik_mi, metin), dk in zip(konular, dagitim):
        out.append((baslik_mi, f"{sure_ekini_temizle(metin)} - {dk} DK"))
    return out


def egitim_konularini_hazirla(tehlike_sinifi: str, sektor: str | None = None):
    """Belgede basılacak sol/sağ konu listelerini üretir.

    Returns: (sol, sag, toplam_dakika, toplam_saat) where sol/sag are list of (is_heading, text)
    """
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
    sektorel = [sure_ekini_temizle(k) for k in sektorel_konular(sektor)[:5]]
    ana = "1. Genel Konular / 2. Teknik Konular / 3. Sağlık Konuları / 4. İş ve İşyerine Özgü Riskler"
    if sektorel:
        return ana + " | Sektöre Özgü: " + "; ".join(sektorel)
    return ana


def meta_payload() -> dict:
    return {
        "hazard_rules": TEHLIKE_EGITIM_KURALLARI,
        "sectors": [{"code": c, "label": l} for c, l in SEKTOR_SECENEKLERI],
    }
