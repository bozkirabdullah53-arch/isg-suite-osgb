"""İSG temel eğitim — 6331 kapsamı sektör kataloğu ve belge konuları.

Belgede basılan müfredat: genel + teknik + sağlık + işyerine özgü (sektör) konular.
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

# (kod, ad, tehlike_sinifi, 5 sektörel konu) — A→Z Türkçe ada göre sıralı
_SECTOR_RAW: list[tuple[str, str, str, list[str]]] = [
    ("acik_maden", "Açık Maden / Taş Ocağı / Agrega", "Çok Tehlikeli", [
        "Şev, kademe ve kaya düşmesi", "Patlatma sahası emniyeti", "Kırma-eleme güvenliği",
        "Toz, gürültü, titreşim", "Ocak içi trafik / iş makinesi",
    ]),
    ("agac_ormancilik", "Ağaç İşleri / Ormancılık", "Tehlikeli", [
        "Kesici makineler", "Zincirli testere", "Devrilen ağaç riski", "Toz ve gürültü", "KKD kullanımı",
    ]),
    ("ahsap_mobilya", "Ahşap / Mobilya", "Tehlikeli", [
        "Kesici makineler ve koruyucular", "Talaş/toz ve patlama", "Vernik/boya/solvent",
        "Pres ve el aleti", "Yangın ve temizlik",
    ]),
    ("aku_uretimi", "Akü Üretimi", "Çok Tehlikeli", [
        "Kurşun ve bileşikleri", "Sülfürik asit sıçraması", "Hidrojen gazı / patlama",
        "Kimyasal dökülme", "Havalandırma ve KKD",
    ]),
    ("asansor_montaj", "Asansör / Montaj-Bakım", "Çok Tehlikeli", [
        "Yüksekte çalışma", "Kuyu ve makine dairesi", "Elektrik enerjisi", "Kaldırma ekipmanı", "Kilitleme-etiketleme",
    ]),
    ("avcilik_balikcilik", "Avcılık / Balıkçılık", "Tehlikeli", [
        "Deniz/göl çalışma", "Soğuk ve kaygan zemin", "Kesici aletler", "Kimyasal koruma", "Acil kurtarma",
    ]),
    ("bakim_onarim", "Bakım Onarım Atölyesi", "Tehlikeli", [
        "Kilitleme/etiketleme", "El aletleri", "Kaynak ve sıcak iş", "Sıkışma-ezilme", "Atık yağ/kimyasal",
    ]),
    ("berber_kuafor", "Berber / Kuaför", "Az Tehlikeli", [
        "Kimyasal boya/solüsyon", "Kesici aletler", "Ergonomi", "Hijyen", "Elektrikli ekipman",
    ]),
    ("boya_kaplama", "Boya / Kaplama / Galvaniz", "Çok Tehlikeli", [
        "Solvent buharı", "Parlama-patlama", "SDS okuma", "Depolama uyumsuzluğu", "Dökülme müdahalesi",
    ]),
    ("cam_seramik", "Cam / Seramik / Porselen", "Tehlikeli", [
        "Yüksek sıcaklık fırın", "Kesici kırık malzeme", "Toz maruziyeti", "Ağır kaldırma", "Göz koruması",
    ]),
    ("cati_isleri", "Çatı İşleri", "Çok Tehlikeli", [
        "Düşme önleme", "İskele/platform", "Hava koşulları", "Malzeme düşmesi", "Elektrik hattı mesafesi",
    ]),
    ("cimento_beton", "Çimento / Beton / Hazır Beton", "Çok Tehlikeli", [
        "Toz (silika)", "Mikser ve pompa", "Kimyasal yanık", "Ağır taşıma", "Trafik ve yaya yolları",
    ]),
    ("demir_celik", "Demir-Çelik / Hadde", "Çok Tehlikeli", [
        "Sıcak metal", "Vinç ve pota", "Yanık/ısı stresi", "Gaz ve duman", "Sıkışma-ezilme",
    ]),
    ("depo_lojistik", "Depo / Lojistik / Antrepo", "Tehlikeli", [
        "Forklift-yaya trafiği", "Raf devrilmesi", "Rampa yükleme", "Elle taşıma", "Malzeme düşmesi",
    ]),
    ("dokum_metal", "Döküm / Metal Dökümhane", "Çok Tehlikeli", [
        "Ergitme ocağı", "Sıcak metal sıçraması", "Pota/vinç", "Duman-toz-gaz", "Kalıp bozma riski",
    ]),
    ("egitim_okul", "Eğitim / Okul / Kreş", "Az Tehlikeli", [
        "Yangın tahliye", "Kayma-takılma", "Kimyasal laboratuvar", "Şiddet/güvenlik", "İlk yardım",
    ]),
    ("elektrik_bakim", "Elektrik Bakım / Tesisat", "Çok Tehlikeli", [
        "Çarpılma / ark", "Enerji kesme LOTO", "Pano-kablo", "İzole KKD", "Çalışma izni",
    ]),
    ("elektronik_imalat", "Elektronik İmalat", "Tehlikeli", [
        "Lehim dumanı", "Statik elektrik", "Kimyasal temizleyici", "Kesici delici", "Ergonomi",
    ]),
    ("enerji_uretim", "Enerji Üretim / Santral", "Çok Tehlikeli", [
        "Yüksek gerilim", "Basınçlı sistemler", "Kapalı alan", "Yangın-patlama", "İzolasyon prosedürü",
    ]),
    ("finans_ofis", "Finans / Banka / Ofis", "Az Tehlikeli", [
        "Ekranlı araç", "Ergonomi", "Yangın tahliye", "Kayma-takılma", "Psikososyal risk",
    ]),
    ("gida_uretim", "Gıda Üretim / İşleme", "Tehlikeli", [
        "Hijyen / çapraz bulaşma", "Kaygan zemin", "Kesici ekipman", "Sıcak buhar/yanık", "Soğuk oda",
    ]),
    ("guvenlik_ozel", "Güvenlik / Özel Güvenlik", "Tehlikeli", [
        "Şiddet riski", "Gece çalışma", "Acil müdahale", "İletişim", "KKD ve ekipman",
    ]),
    ("hazir_giyim", "Hazır Giyim / Tekstil Atölye", "Tehlikeli", [
        "Dikiş makineleri", "Toz ve gürültü", "Yangın", "Ergonomi", "Kimyasal boya",
    ]),
    ("insaat", "İnşaat / Şantiye", "Çok Tehlikeli", [
        "Yüksekte çalışma / düşme", "İskele-merdiven", "Kazı-göçük", "Vinç-kaldırma", "Şantiye trafiği",
    ]),
    ("itim_matbaa", "İletişim / Matbaa / Baskı", "Tehlikeli", [
        "Solvent mürekkep", "Makine sıkışması", "Gürültü", "Kağıt kesici", "Yangın",
    ]),
    ("kagit_ambalaj", "Kağıt / Ambalaj", "Tehlikeli", [
        "Makine koruyucu", "Kağıt kesici", "Forklift", "Toz", "Yangın yükü",
    ]),
    ("kaynakli_imalat", "Kaynaklı İmalat", "Çok Tehlikeli", [
        "Kaynak ışını", "Kaynak dumanı", "Sıcak iş izni", "Basınçlı gaz tüpleri", "Kapalı alan kaynak",
    ]),
    ("kimyasal_boya", "Kimyasal / Boya / İlaç", "Çok Tehlikeli", [
        "Etiketleme / SDS", "Solvent buharı", "Parlama-patlama", "Uyumsuz madde depolama", "Dökülme müdahalesi",
    ]),
    ("konaklama_otel", "Konaklama / Otel / Restoran", "Az Tehlikeli", [
        "Mutfak yanık/kesik", "Kaygan zemin", "Kimyasal temizlik", "Yangın tahliye", "Ergonomi",
    ]),
    ("kuyumculuk", "Kuyumculuk / Metal İşleme Küçük", "Tehlikeli", [
        "Asit/siyanür riski", "Yüksek sıcaklık", "Göz koruması", "Havalandırma", "Yangın",
    ]),
    ("lastik_kaucuk", "Lastik / Kauçuk", "Çok Tehlikeli", [
        "Makine sıkışması", "Kimyasal katkı", "Yüksek sıcaklık", "Toz-duman", "Yangın",
    ]),
    ("madencilik_yeralti", "Madencilik (Yeraltı)", "Çok Tehlikeli", [
        "Göçük / tahkimat", "Gaz ölçümü", "Patlatma", "Nakliye", "Acil kaçış",
    ]),
    ("makine_imalat", "Makine İmalat / Montaj", "Tehlikeli", [
        "Makine koruyucuları", "Sıkışma-kesilme", "LOTO bakım", "Taşlama-kesme", "Kaldırma-ergonomi",
    ]),
    ("mobilya_dekorasyon", "Mobilya / Dekorasyon Montaj", "Tehlikeli", [
        "El aletleri", "Yüksekte montaj", "Toz", "Kimyasal tutkal", "Elektrik",
    ]),
    ("otomotiv", "Otomotiv / Yedek Parça", "Tehlikeli", [
        "Pres hatları", "Kaynak robotları", "Kimyasal", "Ergonomi", "İç lojistik",
    ]),
    ("petrol_dogalgaz", "Petrol / Doğalgaz / Rafineri", "Çok Tehlikeli", [
        "Patlayıcı atmosfer", "Yangın", "Basınçlı ekipman", "Zehirli gaz", "İzinli çalışma",
    ]),
    ("plastik_enjeksiyon", "Plastik / Enjeksiyon", "Tehlikeli", [
        "Sıcak kalıp", "Makine koruyucu", "Duman-gaz", "Ezilme", "Yangın",
    ]),
    ("saglik", "Sağlık Sektörü / Hastane", "Tehlikeli", [
        "Biyolojik risk", "Kesici-delici yaralanma", "Hasta taşıma", "Dezenfektan", "Şiddet / acil",
    ]),
    ("soguk_hava", "Soğuk Hava Deposu", "Tehlikeli", [
        "Soğuk stres", "Kaygan zemin", "Forklift", "Kapalı alan", "Acil çıkış",
    ]),
    ("tarim", "Tarım / Hayvancılık", "Tehlikeli", [
        "İş makinesi", "Pestisit", "Hayvan yaralanması", "Güneş/ısı", "Elle kaldırma",
    ]),
    ("tasimacilik", "Taşımacılık / Şoförlük", "Tehlikeli", [
        "Trafik güvenliği", "Yük bağlama", "Yorgunluk", "Elle taşıma", "Acil durum",
    ]),
    ("telekom", "Telekomünikasyon / Anten", "Çok Tehlikeli", [
        "Yüksekte çalışma", "RF maruziyet", "Elektrik", "Çatı/kule", "Hava koşulları",
    ]),
    ("temizlik", "Temizlik İşleri", "Tehlikeli", [
        "Temizlik kimyasalları", "Islak zemin", "Biyolojik atık", "Yüksek alan temizliği", "Kesici atık",
    ]),
    ("tekstil", "Tekstil / Dokuma / Boyahane", "Tehlikeli", [
        "Makine sıkışması", "Kimyasal boya", "Gürültü", "Toz", "Yangın",
    ]),
    ("ticaret_perakende", "Ticaret / Perakende / Market", "Az Tehlikeli", [
        "Kayma-takılma", "Elle taşıma", "Yangın tahliye", "Şiddet", "Depo forklift",
    ]),
    ("turizm_seyahat", "Turizm / Seyahat Acentesi", "Az Tehlikeli", [
        "Ekranlı araç", "Yangın", "Ergonomi", "Acil tahliye", "Psikososyal",
    ]),
    ("yapi_denetim", "Yapı Denetim / Mühendislik Ofisi", "Az Tehlikeli", [
        "Saha ziyareti riski", "PPE", "Ekranlı araç", "Araç kullanımı", "Yangın",
    ]),
    ("yol_asfalt", "Yol / Asfalt / Altyapı", "Çok Tehlikeli", [
        "Sıcak asfalt yanığı", "Trafik altında çalışma", "İş makineleri", "Bitüm buharı", "Gece görünürlük",
    ]),
    ("yuksekte_calisma", "Yüksekte Çalışma Hizmetleri", "Çok Tehlikeli", [
        "Düşme önleme sistemleri", "İskele/platform", "Rüzgar etkisi", "Malzeme düşmesi", "Kurtarma planı",
    ]),
    ("genel_uretim", "Genel Fabrika / Üretim", "Tehlikeli", [
        "Makine-ekipman", "İç trafik", "Elle taşıma", "Yangın-tahliye", "KKD ve düzen",
    ]),
    ("ofis", "Ofis / İdari İşler", "Az Tehlikeli", [
        "Ekranlı araç / ergonomi", "Elektrikli ekipman", "Yangın-tahliye", "Kayma-takılma", "Psikososyal risk",
    ]),
]


def _topics_with_dk(topics: list[str]) -> list[str]:
    return [t if " DK" in t else f"{t} - 30 DK" for t in topics]


# Build maps
SEKTOR_SECENEKLERI: list[tuple[str, str]] = [(c, n) for c, n, _, _ in _SECTOR_RAW]
SEKTOREL_EGITIM_KONULARI: dict[str, list[str]] = {
    c: _topics_with_dk(topics) for c, _, _, topics in _SECTOR_RAW
}
SEKTOR_TEHLIKE: dict[str, str] = {c: h for c, _, h, _ in _SECTOR_RAW}


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
    for kod, ad in SEKTOR_SECENEKLERI:
        if ad.casefold() == raw.casefold():
            return kod
    # canlı API eski kodları (01-05) → genel
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
    sektorel = [sure_ekini_temizle(k) for k in sektorel_konular(sektor)[:5]]
    ana = "1. Genel / 2. Teknik / 3. Sağlık / 4. İşyerine Özgü Riskler"
    if sektorel:
        return ana + " | Sektör: " + "; ".join(sektorel)
    return ana


def sectors_list_for_api() -> list[dict]:
    """Canlı uyumlu: code, name, topics + hazard_class, label."""
    items = []
    for code, name, hazard, topics in sorted(_SECTOR_RAW, key=lambda x: x[1].casefold()):
        clean = [sure_ekini_temizle(t) for t in topics]
        items.append({
            "code": code,
            "name": name,
            "label": name,
            "hazard_class": hazard,
            "topics": clean,
        })
    return items


def meta_payload() -> dict:
    return {
        "hazard_rules": TEHLIKE_EGITIM_KURALLARI,
        "sectors": sectors_list_for_api(),
    }
