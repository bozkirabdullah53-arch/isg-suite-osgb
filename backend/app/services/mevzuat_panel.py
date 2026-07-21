"""
0.9.118 — OSGB mevzuat mini panel (highlights-v1).

Ücretli mevzuat API yok: küratörlü 6331 özetleri + mevcut risk_regulations kataloğu.
Madde numarası uydurulmaz; yalnızca mevzuat adı / konu başlığı.
"""
from __future__ import annotations

from typing import Any

from app.services.risk_regulations import (
    GENERAL_REGULATIONS,
    REGULATIONS,
    get_all_regulations,
    get_regulations_by_keyword,
    get_regulations_for_category,
)

PANEL_ENGINE = "highlights-v1"
LAST_REVIEWED = "2026-07-21"

# Küratörlü öne çıkanlar — OSGB yöneticisi için operasyonel hatırlatma (stub, resmi yorum değil)
HIGHLIGHTS: list[dict[str, Any]] = [
    {
        "id": "6331-risk",
        "title": "Risk değerlendirmesi sürekliliği",
        "topic": "Risk",
        "summary": (
            "İşveren; işyerindeki tehlike ve riskleri belirleyip önlem almakla yükümlüdür. "
            "Değişiklik, kaza veya yeni süreç sonrası değerlendirme gözden geçirilmelidir."
        ),
        "instrument": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
        "osgb_tip": "Saha uzmanının risk modülü kayıtlarını Hizmet Denetimi’nden izleyin.",
    },
    {
        "id": "hizmet-sure",
        "title": "OSGB hizmet süreleri (kapasite)",
        "topic": "Hizmet süresi",
        "summary": (
            "İşyeri tehlike sınıfı ve çalışan sayısına göre İSG profesyoneli aylık asgari süreleri "
            "yönetmelikle belirlenir; fiili saha süresi ile karşılaştırılmalıdır."
        ),
        "instrument": "İş Sağlığı ve Güvenliği Hizmetleri Yönetmeliği",
        "osgb_tip": "Kapasite Motoru ve görevlendirme zorunlu dakikalarını kullanın.",
    },
    {
        "id": "egitim",
        "title": "Çalışan İSG eğitimleri",
        "topic": "Eğitim",
        "summary": (
            "Çalışanlara işe giriş ve periyodik İSG eğitimleri verilir; süre ve içerik "
            "tehlike sınıfına göre yönetmelikte düzenlenir."
        ),
        "instrument": "Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik",
        "osgb_tip": "Eğitim tamamlanma oranını Hizmet Denetimi checklist’inden takip edin.",
    },
    {
        "id": "saglik",
        "title": "Sağlık gözetimi",
        "topic": "Sağlık",
        "summary": (
            "İşyeri hekimi; işe giriş ve periyodik muayene ile çalışan sağlık gözetimini yürütür. "
            "Meslek hastalığı şüphesinde bildirim yükümlülükleri vardır."
        ),
        "instrument": "İşyeri Hekimi ve Diğer Sağlık Personeli Yönetmeliği",
        "osgb_tip": "Hekim / DSP görevlendirme ve muayene kayıtlarını denetim panelinden kontrol edin.",
    },
    {
        "id": "kaza-bildirim",
        "title": "İş kazası kayıt ve bildirim",
        "topic": "Olay",
        "summary": (
            "İş kazası ve meslek hastalığı kayıt altına alınır; yasal sürelerde ilgili mercilere "
            "bildirim yapılır. OSGB süreç takibini kolaylaştırır, bildirim sorumluluğu işverendedir."
        ),
        "instrument": "İş Kazası ve Meslek Hastalığı Kayıt ve Bildirim Yönetmeliği",
        "osgb_tip": "Olay kayıtlarının saha tarafından açıldığını Hizmet Denetimi’nden izleyin.",
    },
    {
        "id": "acil",
        "title": "Acil durum planı",
        "topic": "Acil durum",
        "summary": (
            "İşyerinde acil durumları önceden belirleyip plan, tatbikat ve ekipler oluşturulmalıdır."
        ),
        "instrument": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
        "osgb_tip": "Yıllık plan / tatbikat kalemlerini saha tamamlanma durumundan izleyin.",
    },
    {
        "id": "katip",
        "title": "İSG-KATİP görevlendirme",
        "topic": "KATİP",
        "summary": (
            "OSGB üzerinden verilen hizmetlerde görevlendirme ve sözleşme bilgilerinin "
            "İSG-KATİP ile uyumu denetimlerde sık sorulur."
        ),
        "instrument": "İş Sağlığı ve Güvenliği Hizmetleri Yönetmeliği / İSG-KATİP uygulamaları",
        "osgb_tip": "Görevlendirmeler ekranındaki KATİP hazırlık özetini kullanın.",
    },
    {
        "id": "kkd",
        "title": "Kişisel koruyucu donanım",
        "topic": "KKD",
        "summary": (
            "Risklere uygun KKD seçimi, kullanımı ve bakımı işverenin sorumluluğundadır; "
            "uygunluk işaretli ürünler tercih edilir."
        ),
        "instrument": "Kişisel Koruyucu Donanım Yönetmeliği",
        "osgb_tip": "Saha KKD takip kayıtlarını denetim checklist’inden izleyin.",
    },
]


def build_mevzuat_panel(*, q: str | None = None, category: str | None = None) -> dict[str, Any]:
    """OSGB yöneticisi için mevzuat mini panel payload."""
    query = (q or "").strip()
    cat = (category or "").strip() or None

    categories = [
        {"name": name, "regulation_count": len(regs)}
        for name, regs in sorted(REGULATIONS.items(), key=lambda x: x[0])
    ]

    catalog: list[str]
    if cat:
        catalog = list(get_regulations_for_category(cat))
        if not catalog:
            catalog = list(GENERAL_REGULATIONS)
    elif query:
        catalog = get_regulations_by_keyword(query)
    else:
        catalog = list(GENERAL_REGULATIONS)

    highlights = HIGHLIGHTS
    if query:
        ql = query.casefold()
        highlights = [
            h
            for h in HIGHLIGHTS
            if ql in h["title"].casefold()
            or ql in h["summary"].casefold()
            or ql in h["topic"].casefold()
            or ql in h["instrument"].casefold()
        ]

    return {
        "engine": PANEL_ENGINE,
        "last_reviewed": LAST_REVIEWED,
        "disclaimer": (
            "Bu panel bilgilendirme amaçlıdır; resmi mevzuat metni ve güncel Resmî Gazete "
            "yayımları esas alınmalıdır. Madde numarası üretilmez."
        ),
        "highlights": highlights,
        "categories": categories,
        "selected_category": cat,
        "query": query or None,
        "catalog": [{"name": name} for name in catalog],
        "catalog_total": len(get_all_regulations()),
        "general_count": len(GENERAL_REGULATIONS),
    }
