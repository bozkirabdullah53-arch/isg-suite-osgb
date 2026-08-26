"""Görsel saha denetimi için değişmez başlangıç katalogları.

Katalog burada tutulur; veritabanına idempotent olarak yazılır. Kullanıcıların
eklediği tehlikeler bu sistem kataloğunu değiştirmez ve yalnızca kendi tenant
kapsamlarında görünür.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.field_inspection import FieldHazardCategory


FIELD_HAZARD_CATEGORIES: tuple[str, ...] = (
    "Genel işyeri düzeni ve temizlik",
    "Kayma, takılma ve düşme",
    "Yüksekte çalışma",
    "Merdivenler",
    "İskeleler",
    "Korkuluklar ve kenar koruma",
    "Açıklıklar ve döşeme boşlukları",
    "Çatı çalışmaları",
    "İnşaat ve şantiye güvenliği",
    "Kazı ve kanal çalışmaları",
    "Yıkım çalışmaları",
    "Kalıp ve beton işleri",
    "Donatı ve demir işleri",
    "Kaldırma ve taşıma işleri",
    "Vinçler ve kaldırma ekipmanları",
    "Sapan, halat ve kaldırma aksesuarları",
    "Forklift ve iş makineleri",
    "Araç-yaya trafiği",
    "Makine ve ekipman güvenliği",
    "Makine koruyucuları",
    "Kilitleme/etiketleme ve enerji izolasyonu",
    "Elektrik güvenliği",
    "Elektrik panoları ve kablolar",
    "Topraklama ve kaçak akım",
    "Yangın güvenliği",
    "Acil çıkışlar ve kaçış yolları",
    "Yangın tüpleri ve yangın ekipmanları",
    "Patlama ve parlama riski",
    "Patlayıcı ortamlar",
    "Sıcak işler",
    "Kaynak, kesme ve taşlama",
    "Kimyasal maddeler",
    "Kimyasal etiketleme ve SDS",
    "Kimyasal depolama",
    "Sızıntı ve dökülmeler",
    "Basınçlı kaplar",
    "Tüpler ve basınçlı gazlar",
    "Kapalı alanlar",
    "Havalandırma",
    "Toz ve silis maruziyeti",
    "Asbest ihtimali",
    "Gürültü",
    "Titreşim",
    "Aydınlatma",
    "Isı, soğuk ve termal ortam",
    "Radyasyon",
    "Ergonomi",
    "Manuel taşıma",
    "Tekrarlı işler",
    "Kişisel koruyucu donanımlar",
    "İş kıyafeti ve görünürlük",
    "Acil durum ve tahliye",
    "İlk yardım",
    "Sağlık hizmetleri ve hastane riskleri",
    "Biyolojik riskler",
    "Kesici-delici tıbbi atıklar",
    "Gıda ve hijyen",
    "Tarım ve hayvancılık",
    "Orman ve peyzaj işleri",
    "Maden ve agrega",
    "Akü, pil ve enerji depolama",
    "Şarj alanları",
    "Isıl kaçak ve batarya yangını",
    "Depo ve raf sistemleri",
    "Yükleme-boşaltma rampaları",
    "Atık yönetimi",
    "Kanalizasyon ve atık su",
    "Enerji ve elektrik üretim tesisleri",
    "Su baskını ve doğal afetler",
    "Psikososyal riskler",
    "Çalışma izinleri ve talimatlar",
    "Eğitim ve yetkinlik eksiklikleri",
    "İşaretleme ve uyarı levhaları",
    "İşyerinin bina ve eklentileri",
    "Diğer görülebilir tehlikeler",
)

FIELD_SITE_TYPES: tuple[str, ...] = (
    "Üretim tesisi", "Fabrika", "İşleme tesisi", "İnşaat alanı", "Şantiye",
    "Depo", "Lojistik sahası", "Hastane", "Laboratuvar", "Okul", "Ofis",
    "Enerji tesisi", "Akü/pil üretim tesisi", "Kimyasal tesis", "Maden veya agrega sahası",
    "Tarım alanı", "Atölye", "Otopark", "Servis/bakım alanı", "Açık saha",
    "Kapalı saha", "Diğer",
)

FIELD_AREA_TYPES: tuple[str, ...] = (
    "Üretim alanı", "Makine dairesi", "Elektrik panosu bölümü", "Depo", "Sevkiyat alanı",
    "Yükleme-boşaltma alanı", "Vinç alanı", "İskele bölümü", "Çatı", "Merdiven",
    "Kazı alanı", "Kalıp alanı", "Donatı alanı", "Kaynak bölümü", "Boyahane",
    "Kimyasal depolama alanı", "Laboratuvar", "Hasta bakım alanı", "Acil servis", "Mutfak",
    "Ofis", "Arşiv", "Otopark", "Sosyal alan", "Atık alanı", "Yangın çıkışı",
    "Toplanma alanı", "Diğer",
)

FIELD_EQUIPMENT_TYPES: tuple[str, ...] = (
    "Elektrik panosu", "Forklift", "Vinç", "Pres makinesi", "Torna", "Kompresör",
    "İskele", "Merdiven", "Kazı çukuru", "Yangın tüpü", "Acil çıkış kapısı", "Raf sistemi",
    "Basınçlı kap", "Kimyasal tank", "Akü şarj cihazı", "Havalandırma sistemi", "Diğer",
)

# Maddeler otomatik üretilmez. Yalnızca uzman tarafından doğrulanmış kayıtlar
# ``verified`` yapılabilir; başlangıçta 6331'ün resmi PDF adresi bilinir ama
# makine, fotoğraftaki bulgu için madde seçmez.
OFFICIAL_LEGAL_SOURCE = "https://www.mevzuat.gov.tr/"
VERIFIED_6331_SOURCE = "https://www.mevzuat.gov.tr/MevzuatMetin/1.5.6331-20150404.pdf"
FIELD_LEGAL_CATALOG: tuple[dict[str, object], ...] = (
    {"name": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu", "source_url": VERIFIED_6331_SOURCE, "verified": True, "version": "mevzuat.gov.tr PDF"},
    {"name": "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Yapı İşlerinde İş Sağlığı ve Güvenliği Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Kişisel Koruyucu Donanım Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Sağlık ve Güvenlik İşaretleri Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Kimyasal Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Tozla Mücadele Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Gürültü Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Titreşim Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Patlayıcı Ortamların Tehlikelerinden Çalışanların Korunması Hakkında Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Binaların Yangından Korunması Hakkında Yönetmelik", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
    {"name": "Maden İşyerlerinde İş Sağlığı ve Güvenliği Yönetmeliği", "source_url": OFFICIAL_LEGAL_SOURCE, "verified": False},
)


def normalize_name(value: str | None) -> str:
    """Türkçe adlarda tenant içi tekrarları yakalamak için güvenli anahtar."""
    raw = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    translation = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})
    raw = raw.translate(translation)
    raw = "".join(char for char in unicodedata.normalize("NFKD", raw) if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", raw).strip()


def seed_field_catalog(db: Session) -> list[FieldHazardCategory]:
    """75 sistem kategorisini eksik olanlar için ekler; mevcut adları değiştirmez."""
    existing = {row.name: row for row in db.scalars(select(FieldHazardCategory)).all()}
    changed = False
    for order, name in enumerate(FIELD_HAZARD_CATEGORIES, start=1):
        row = existing.get(name)
        if row is None:
            row = FieldHazardCategory(
                name=name,
                sort_order=order,
                icon="shield-alert",
                is_system=True,
                is_active=True,
            )
            db.add(row)
            existing[name] = row
            changed = True
        elif row.sort_order != order or not row.is_system:
            row.sort_order = order
            row.is_system = True
            changed = True
    if changed:
        db.commit()
    return sorted(existing.values(), key=lambda item: (item.sort_order, item.id))


def legal_entry(name: str | None) -> dict[str, object] | None:
    clean = str(name or "").strip()
    return next((item for item in FIELD_LEGAL_CATALOG if item["name"] == clean), None)
