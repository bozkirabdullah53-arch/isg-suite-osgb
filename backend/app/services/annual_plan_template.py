"""Yıllık çalışma planı şablonu — İSG Hizmetleri Yön. + 6331 dayanaklı kalemler.

Madde numarası uydurulmaz; yalnızca yönetmelik / kanun adı + konu başlığı yazılır.
Tehlike sınıfına göre ek kalemler (çok tehlikeli işyerleri) eklenir.
"""
from __future__ import annotations

from typing import Any

# (ay, kategori, faaliyet, açıklama, sorumlu, not, mevzuat_dayanağı)
BASE_TEMPLATE: list[tuple[int, str, str, str, str, str, str]] = [
    (
        1,
        "yillik_calisma",
        "Yıllık İSG çalışma planının oluşturulması",
        "İSG faaliyetlerinin yıl geneline dağıtılması ve işveren onayı",
        "İSG Uzmanı / İşveren",
        "Yıl başında plan hazırlanır; değişikliklerde güncellenir.",
        "İSG Hizmetleri Yönetmeliği — yıllık çalışma planı",
    ),
    (
        1,
        "egitim",
        "Yıllık eğitim planının hazırlanması",
        "Temel İSG, yangın, KKD ve işe özel eğitimlerin planlanması",
        "İSG Uzmanı",
        "Çalışan sayısı ve tehlike sınıfına göre süreler belirlenir.",
        "Çalışanların İSG Eğitimlerinin Usul ve Esasları Hk. Yönetmelik",
    ),
    (
        2,
        "periyodik",
        "Elektrik tesisatı / topraklama kontrol planı",
        "Elektrik tesisatı, pano, topraklama ve paratoner kontrollerinin planlanması",
        "İdari İşler / Teknik Birim",
        "Yetkili kişi/kuruluş raporları dosyalanır.",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    ),
    (
        3,
        "tatbikat",
        "Yangın ve tahliye tatbikatı",
        "Acil durum ekipleriyle birlikte tahliye senaryosunun uygulanması",
        "İSG Uzmanı / Acil Durum Ekipleri",
        "Fotoğraflı tutanak alınır.",
        "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
    ),
    (
        4,
        "saglik",
        "Sağlık gözetimi takip kontrolü",
        "İşe giriş/periyodik muayene sürelerinin kontrolü",
        "İşyeri Hekimi",
        "Geciken muayeneler raporlanır.",
        "İşyeri Hekimi ve Diğer Sağlık Personeli Yönetmeliği",
    ),
    (
        5,
        "periyodik",
        "Kaldırma ekipmanları kontrolü",
        "Forklift, vinç, caraskal, transpalet, platform kontrolleri",
        "Bakım / Teknik Birim",
        "Rapor PDF'leri Periyodik Kontroller / belgeler modülüne yüklenir.",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    ),
    (
        6,
        "yillik_calisma",
        "Risk değerlendirmesi gözden geçirme",
        "Yeni faaliyet, ekipman, kaza veya değişiklikler bakımından risklerin gözden geçirilmesi",
        "İSG Uzmanı / İşveren",
        "Gerekirse revizyon yapılır.",
        "6331 sayılı İSG Kanunu — risk değerlendirmesi",
    ),
    (
        7,
        "kkd",
        "KKD zimmet ve uygunluk kontrolü",
        "Baret, gözlük, ayakkabı, eldiven, emniyet kemeri ve diğer KKD'lerin kontrolü",
        "İSG Uzmanı / Birim Sorumluları",
        "Eksik/hasarlı KKD yenilenir.",
        "Kişisel Koruyucu Donanım Yönetmeliği",
    ),
    (
        8,
        "periyodik",
        "Raf sistemleri ve depo ekipmanları kontrolü",
        "Depo rafları, forklift yolları, istifleme ve yükleme alanlarının kontrolü",
        "Depo Sorumlusu",
        "Raf etiketi ve kapasite bilgileri kontrol edilir.",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    ),
    (
        9,
        "egitim",
        "Yenileme / işe özel eğitimlerin kontrolü",
        "Yüksekte çalışma, kimyasal, kaynak, elektrik, forklift gibi işe özel eğitimler",
        "İSG Uzmanı",
        "Eksik eğitimler tamamlanır.",
        "Çalışanların İSG Eğitimlerinin Usul ve Esasları Hk. Yönetmelik",
    ),
    (
        10,
        "tatbikat",
        "Acil durum planı ve ekip listesi kontrolü",
        "Ekip üyeleri, toplanma alanı, tahliye güzergâhı ve acil telefonlar",
        "İSG Uzmanı",
        "Plan revizyonu gerekiyorsa Acil Durum / ekipler modülünde güncellenir.",
        "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
    ),
    (
        11,
        "yillik_calisma",
        "Yıl sonu veri toplama",
        "Eğitim, KKD, sağlık, periyodik kontrol, tespit ve ramak kala kayıtlarının toplanması",
        "İSG Uzmanı",
        "Yıllık değerlendirme raporuna hazırlık.",
        "İSG Hizmetleri Yönetmeliği — yıllık değerlendirme",
    ),
    (
        12,
        "yillik_calisma",
        "Yıllık değerlendirme raporu",
        "Yıl boyunca yapılan İSG faaliyetlerinin değerlendirilmesi",
        "İSG Uzmanı / İşveren",
        "Yıl sonu raporu alınır; işveren onayı aranır.",
        "İSG Hizmetleri Yönetmeliği — yıllık değerlendirme raporu",
    ),
]

# Tehlikeli / çok tehlikeli işyerlerine ek kalemler (ay + faaliyet benzersiz olmalı)
EXTRA_TEHLIKELI: list[tuple[int, str, str, str, str, str, str]] = [
    (
        2,
        "egitim",
        "Tehlike sınıfına göre eğitim sürelerinin gözden geçirilmesi",
        "Az/tehlikeli/çok tehlikeli sınıflara göre yıllık eğitim saatlerinin kontrolü",
        "İSG Uzmanı",
        "Eğitim modülündeki yenileme takibi ile karşılaştırılır.",
        "Çalışanların İSG Eğitimlerinin Usul ve Esasları Hk. Yönetmelik",
    ),
    (
        5,
        "yillik_calisma",
        "İSG kurulu / işyeri temsilcisi bilgilendirme",
        "Çalışan temsilcisi ve ilgili birimlerle planlanan faaliyetlerin paylaşımı",
        "İSG Uzmanı / İşveren",
        "Toplantı/tutanak belgelenir.",
        "6331 sayılı İSG Kanunu — çalışanların bilgilendirilmesi",
    ),
]

EXTRA_COK_TEHLIKELI: list[tuple[int, str, str, str, str, str, str]] = [
    (
        3,
        "periyodik",
        "Ortam ölçümleri ve maruziyet takibi planı",
        "Gürültü, toz, kimyasal, titreşim vb. ölçümlerin yıllık planlanması",
        "İSG Uzmanı / İşyeri Hekimi",
        "Ölçüm raporları belgelenir.",
        "6331 sayılı İSG Kanunu — ortam ölçümleri / sağlık gözetimi",
    ),
    (
        4,
        "egitim",
        "Yüksek riskli işlere özel eğitim takibi",
        "Yüksekte çalışma, kapalı alan, sıcak iş, elektrik vb. özel eğitimlerin kontrolü",
        "İSG Uzmanı",
        "Belge süreleri eğitim yenileme takibinden izlenir.",
        "Çalışanların İSG Eğitimlerinin Usul ve Esasları Hk. Yönetmelik",
    ),
    (
        8,
        "tatbikat",
        "İkinci acil durum tatbikatı / senaryo tekrarı",
        "Çok tehlikeli işyerlerinde yıl içinde ek tatbikat veya senaryo tekrarı",
        "İSG Uzmanı / Acil Durum Ekipleri",
        "Tutanak ve fotoğraf dosyalanır.",
        "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
    ),
]


def normalize_hazard_class(value: str | None) -> str:
    raw = (value or "").strip().casefold()
    if "çok" in raw or "cok" in raw:
        return "Çok Tehlikeli"
    if raw.startswith("az"):
        return "Az Tehlikeli"
    if "tehlikeli" in raw:
        return "Tehlikeli"
    return "Tehlikeli"


def template_for_hazard(hazard_class: str | None) -> list[tuple[int, str, str, str, str, str, str]]:
    """İşyeri tehlike sınıfına göre şablon kalemleri (idempotent anahtar: ay+faaliyet)."""
    klass = normalize_hazard_class(hazard_class)
    rows = list(BASE_TEMPLATE)
    if klass in ("Tehlikeli", "Çok Tehlikeli"):
        rows.extend(EXTRA_TEHLIKELI)
    if klass == "Çok Tehlikeli":
        rows.extend(EXTRA_COK_TEHLIKELI)
    rows.sort(key=lambda r: (r[0], r[2]))
    return rows


def template_rows_as_dicts(hazard_class: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "month": m,
            "category": cat,
            "activity": act,
            "description": desc,
            "responsible_name": resp,
            "notes": notes,
            "legal_basis": legal,
        }
        for m, cat, act, desc, resp, notes, legal in template_for_hazard(hazard_class)
    ]


# Geriye uyum: eski 6 alanlı döngüler için (legal_basis son alan)
TEMPLATE = [(m, c, a, d, r, n) for m, c, a, d, r, n, _ in BASE_TEMPLATE]
