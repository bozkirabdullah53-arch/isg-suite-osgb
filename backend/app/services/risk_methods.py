"""Risk değerlendirme yöntemleri — yöntem katalogları ve çalışma alanı metası.

The catalogue deliberately distinguishes methods that are currently executable
from methods that are listed for the staged rollout.  A method must not appear
to work by falling back to another method's calculation engine.
"""
from __future__ import annotations

from typing import Any

# Kod -> rapor etiketi
METHOD_CATALOG: dict[str, dict[str, Any]] = {
    "5x5_l": {
        "code": "5x5_l",
        "label": "5x5 Matris (L Tipi)",
        "formula": "Risk Skoru = Olasılık × Şiddet",
        "short": "5x5 Matris (L Tipi) — Risk Skoru = Olasılık × Şiddet",
        "probability_axis": "Olasılık (1–5)",
        "severity_axis": "Şiddet (1–5)",
        "levels": [
            ("1–5", "Kabul Edilebilir", "İzleme yeterli olabilir."),
            ("6–8", "Düşük", "Planlı iyileştirme önerilir."),
            ("9–12", "Orta", "Önlemler planlanmalı ve takip edilmelidir."),
            ("13–16", "Yüksek", "Kısa sürede düzeltici faaliyet gerekir."),
            ("17–25", "Çok Yüksek", "İş durdurulabilir; acil önlem zorunlu."),
        ],
        "probability_defs": [
            (1, "Çok düşük — pratikte beklenmez"),
            (2, "Düşük — nadiren gerçekleşebilir"),
            (3, "Orta — ara sıra gerçekleşebilir"),
            (4, "Yüksek — sık gerçekleşebilir"),
            (5, "Çok yüksek — sürekli / kaçınılmaz"),
        ],
        "severity_defs": [
            (1, "Önemsiz — ilk yardım / ihmal edilebilir"),
            (2, "Hafif — ayakta tedavi"),
            (3, "Orta — iş günü kaybı / yaralanma"),
            (4, "Ciddi — kalıcı zarar / ağır yaralanma"),
            (5, "Felaket — ölüm / çoklu ölüm"),
        ],
        "narrative": (
            "L tipi matris yönteminde her tehlike için olasılık ve şiddet 1–5 skalasında "
            "değerlendirilir; çarpım sonucu risk skoru ve seviye belirlenir. Önlem hiyerarşisine "
            "göre mevcut ve ilave kontroller tanımlanır; DÖF ile takip edilir."
        ),
        "implemented": True,
    },
    "fine_kinney": {
        "code": "fine_kinney",
        "label": "Fine-Kinney Yöntemi",
        "formula": "Risk = Olasılık × Frekans × Şiddet",
        "short": "Fine-Kinney — Risk = Olasılık × Frekans × Şiddet",
        "probability_axis": "Olasılık",
        "frequency_axis": "Frekans / maruziyet sıklığı",
        "severity_axis": "Şiddet",
        "levels": [
            ("<20", "Kabul Edilebilir Risk", "Mevcut önlemler sürdürülür; yasal ve özel gereklilikler ayrıca uygulanır."),
            ("20–<70", "Olası Risk", "Gözetim altında tutulmalı; kontrol yöntemleri geliştirilmelidir."),
            ("70–<200", "Ciddi / Önemli Risk", "Dikkatle izlenmeli, makul sürede iyileştirilmeli ve yıllık plana alınmalıdır."),
            ("200–<400", "Yüksek Risk", "Kısa dönemde iyileştirilmelidir."),
            ("≥400", "Çok Yüksek / Kabul Edilemez Risk", "Çalışma durdurulmalı; risk düşürülmeden başlanmamalıdır."),
        ],
        "probability_defs": [
            (0.1, "Mümkün değil"),
            (0.2, "Beklenmez"),
            (0.5, "Beklenmez fakat mümkün"),
            (1, "Mümkün fakat düşük ihtimal"),
            (3, "Nadir fakat olabilir"),
            (6, "Oldukça mümkün, yüksek ihtimal"),
            (10, "Çok kuvvetli ihtimal, beklenir"),
        ],
        "severity_defs": [
            (1, "Ufak ilk yardım"),
            (3, "Küçük hasar — dahili ilk yardım"),
            (7, "Önemli hasar — dış tedavi / iş günü kaybı"),
            (15, "Kalıcı hasar — sakatlık / uzuv kaybı"),
            (40, "Ölüm — ölümlü kaza / ciddi çevresel zarar"),
            (100, "Felaket — birden fazla ölüm / çevresel felaket"),
        ],
        "frequency_defs": [
            (0.5, "Çok seyrek — yılda bir veya daha az"),
            (1, "Oldukça nadir — yılda bir veya birkaç kez"),
            (2, "Nadir — ayda bir veya birkaç kez"),
            (3, "Ara sıra — haftada bir veya birkaç kez"),
            (6, "Sıklıkla — günde bir veya daha fazla"),
            (10, "Sürekli — sürekli veya saatte birden fazla"),
        ],
        "narrative": (
            "Fine-Kinney yönteminde olasılık, frekans (maruziyet) ve şiddet çarpılarak "
            "risk değeri bulunur. İlk değerlendirmede saha koşulları ve mevcut kontroller "
            "uzman ekibin gerekçeli değerlendirmesiyle dikkate alınır; önlem hiyerarşisi ve "
            "DÖF takibi ayrı izlenir. Termin günleri yazılımın planlama önerisidir."
        ),
        "implemented": True,
    },
    "x_matrix": {
        "code": "x_matrix",
        "label": "X Tipi Matris",
        "formula": "Risk = Olasılık × Şiddet (X matris yerleşimi)",
        "short": "X Tipi Matris — Olasılık × Şiddet",
        "probability_axis": "Olasılık",
        "severity_axis": "Şiddet",
        "levels": [
            ("Düşük bölge", "Kabul edilebilir / düşük", "İzleme"),
            ("Orta bölge", "Orta", "Planlı önlem"),
            ("Yüksek bölge", "Yüksek / çok yüksek", "Acil önlem"),
        ],
        "probability_defs": [],
        "severity_defs": [],
        "narrative": (
            "X tipi matriste olasılık ve şiddet eksenleri çapraz yerleştirilir; "
            "kesişim bölgesi risk önceliğini gösterir."
        ),
        "implemented": False,
    },
    "hazop": {
        "code": "hazop",
        "label": "HAZOP (Tehlike ve İşletilebilirlik)",
        "formula": "Sapma analizi (parametre + kılavuz kelime)",
        "short": "HAZOP — sapma / kılavuz kelime analizi",
        "probability_axis": "Sapma olasılığı (nitel)",
        "severity_axis": "Sonuç şiddeti (nitel)",
        "levels": [
            ("Düşük", "Kabul edilebilir", "İzleme"),
            ("Orta", "Önemli", "Önlem planı"),
            ("Yüksek", "Kritik", "Acil önlem"),
        ],
        "probability_defs": [],
        "severity_defs": [],
        "narrative": (
            "HAZOP; proses parametreleri ve kılavuz kelimeler (yok, daha fazla, ters vb.) "
            "ile sapmaları sistematik inceler. Özellikle proses/kimya tesislerinde tercih edilir."
        ),
        "implemented": False,
    },
    "fmea": {
        "code": "fmea",
        "label": "FMEA (Hata Türleri ve Etkileri Analizi)",
        "formula": "RPN = Şiddet × Olasılık × Saptanabilirlik",
        "short": "FMEA — RPN = Şiddet × Olasılık × Saptanabilirlik",
        "probability_axis": "Olasılık / meydana gelme",
        "severity_axis": "Şiddet",
        "levels": [
            ("Düşük RPN", "Öncelik düşük", "İzleme"),
            ("Orta RPN", "Öncelik orta", "İyileştirme"),
            ("Yüksek RPN", "Öncelik yüksek", "Acil düzeltici faaliyet"),
        ],
        "probability_defs": [],
        "severity_defs": [],
        "narrative": (
            "FMEA; olası hata türlerini, etkilerini ve saptanabilirliğini puanlayarak "
            "RPN önceliği üretir. Makine, ürün ve proses güvenilirliğinde kullanılır."
        ),
        "implemented": False,
    },
    "what_if": {
        "code": "what_if",
        "label": "What-If Analizi",
        "formula": "Senaryo soruları → sonuç / önlem",
        "short": "What-If — senaryo tabanlı analiz",
        "probability_axis": "Senaryo olasılığı (nitel)",
        "severity_axis": "Senaryo sonucu",
        "levels": [
            ("Düşük", "Kabul edilebilir", "İzleme"),
            ("Orta", "Önemli", "Önlem"),
            ("Yüksek", "Kritik", "Acil önlem"),
        ],
        "probability_defs": [],
        "severity_defs": [],
        "narrative": (
            "What-If analizinde 'ne olur?' senaryoları ile tehlikeler ve önlemler "
            "yapılandırılmış beyin fırtınası ile belirlenir."
        ),
        "implemented": False,
    },
    "jsa": {
        "code": "jsa",
        "label": "İş Güvenliği Analizi (JSA / JHA)",
        "formula": "İş adımları → tehlike → önlem",
        "short": "JSA/JHA — iş adımı bazlı tehlike analizi",
        "probability_axis": "Adım riski (nitel/nicel)",
        "severity_axis": "Adım sonucu",
        "levels": [
            ("Düşük", "Kabul edilebilir", "İzleme"),
            ("Orta", "Önemli", "Önlem"),
            ("Yüksek", "Kritik", "Acil önlem"),
        ],
        "probability_defs": [],
        "severity_defs": [],
        "narrative": (
            "İş güvenliği analizinde iş adımları ayrılır; her adımın tehlikeleri ve "
            "kontrolleri tanımlanır. Saha ve bakım işlerinde yaygındır."
        ),
        "implemented": False,
    },
}

DEFAULT_METHOD = "5x5_l"

CONTROL_HIERARCHY = (
    "1) Tehlikeyi kaynağında yok etme / yerine koyma",
    "2) Mühendislik önlemleri (izolasyon, havalandırma, koruyucu)",
    "3) İdari önlemler (talimat, eğitim, rotasyon, izinli çalışma)",
    "4) Kişisel koruyucu donanım (son çare; tamamlayıcı)",
)

LEGAL_BASIS = (
    "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
    "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
    "İş Sağlığı ve Güvenliği Hizmetleri Yönetmeliği",
    "İşyerlerinde Acil Durumlar Hakkında Yönetmelik (ilgili bölümler)",
    "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği (ilgili)",
)

DEFINITIONS = (
    ("Tehlike", "Zarar veya hasar verme potansiyeli olan kaynak, durum veya işlem."),
    ("Risk", "Tehlikeden kaynaklanan kayıp, yaralanma veya diğer zararlı sonuç olasılığı."),
    ("Risk değerlendirmesi", "Tehlikelerin belirlenmesi, risklerin analiz ve kontrolü süreci."),
    ("Önlem hiyerarşisi", "Kontrol önlemlerinin etkinlik sırasına göre uygulanması."),
    ("DÖF", "Düzeltici / önleyici faaliyet kaydı ve takibi."),
    ("Artık risk", "Kontrol önlemleri uygulandıktan sonra kalan risk seviyesi."),
)

PURPOSE = (
    "Bu risk değerlendirmesinin amacı; işyerindeki tehlikeleri sistematik olarak belirlemek, "
    "riskleri önceliklendirmek, mevcut ve ilave kontrol önlemlerini tanımlamak, sorumlu ve "
    "terminleri izlemek ve İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği ile "
    "6331 sayılı Kanun kapsamındaki yükümlülüklere uygun belgelendirme sağlamaktır."
)

SCOPE = (
    "Değerlendirme; işyerinin tüm bölümlerini, faaliyetlerini, makine/ekipmanlarını, "
    "kimyasal süreçlerini, çalışan gruplarını ve ziyaretçi/taşeron erişimini kapsar. "
    "Yeni makine, proses değişikliği, kaza/meslek hastalığı veya ortam ölçümü değişikliği "
    "halinde süre beklenmeden gözden geçirilir."
)


def resolve_method(code: str | None) -> dict[str, Any]:
    key = (code or DEFAULT_METHOD).strip()
    return METHOD_CATALOG.get(key) or METHOD_CATALOG[DEFAULT_METHOD]


def method_choices() -> list[dict[str, Any]]:
    return [
        {
            "code": m["code"],
            "label": m["label"],
            "short": m["short"],
            "implemented": bool(m.get("implemented")),
        }
        for m in METHOD_CATALOG.values()
    ]


def method_label(code: str | None) -> str:
    return resolve_method(code)["short"]
