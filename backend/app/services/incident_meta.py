"""Olay / ramak kala meta sabitleri — İSG PRO ramak_kala uyarlaması."""
from __future__ import annotations

EVENT_TYPES = {
    "ramak_kala": {"adi": "Ramak Kala Olayı", "renk": "primary"},
    "is_kazasi": {"adi": "İş Kazası", "renk": "danger"},
    "meslek_hastaligi": {"adi": "Meslek Hastalığı Şüphesi", "renk": "warning"},
    "tehlike": {"adi": "Tehlikeli Durum / Uygunsuzluk", "renk": "info"},
    "acil_durum": {"adi": "Acil Durum Olayı", "renk": "dark"},
}

EVENT_PREFIX = {
    "ramak_kala": "RK",
    "is_kazasi": "IK",
    "meslek_hastaligi": "MH",
    "tehlike": "TD",
    "acil_durum": "AD",
}

CLASSIFICATIONS = [
    "Düşme / kayma / takılma",
    "Yüksekten düşme",
    "Aynı seviyede düşme",
    "Merdiven kullanımı",
    "İskele uygunsuzluğu",
    "Platform çalışması",
    "Çatı çalışması",
    "Kapalı alan çalışması",
    "Kazı çalışması",
    "Göçük riski",
    "El-kol sıkışması",
    "Ezilme / sıkışma",
    "Kesilme / batma / delinme",
    "Cisim çarpması",
    "Malzeme düşmesi",
    "Malzeme devrilmesi",
    "Makine koruyucu eksikliği",
    "Makine ekipman uygunsuzluğu",
    "Dönen aksam tehlikesi",
    "Pres makinesi",
    "Konveyör sistemi",
    "CNC tezgahı",
    "Torna / freze / matkap",
    "Testere / kesici ekipman",
    "Elektrik tehlikesi",
    "Elektrik çarpması",
    "Elektrik arkı",
    "Topraklama eksikliği",
    "Kaçak akım rölesi eksikliği",
    "Elektrik panosu uygunsuzluğu",
    "Kablo / priz / uzatma uygunsuzluğu",
    "Yangın / patlama riski",
    "Patlayıcı ortam (ATEX)",
    "Parlayıcı madde",
    "Yanıcı sıvı / solvent",
    "LPG / doğalgaz",
    "Statik elektrik",
    "Kimyasal maruziyet / dökülme",
    "Kimyasal sıçrama",
    "Asit / baz maruziyeti",
    "Gaz / buhar maruziyeti",
    "Toz maruziyeti",
    "Silika tozu",
    "Ahşap tozu",
    "Metal tozu",
    "Kaynak dumanı",
    "Kurşun / asit / akü üretimi kaynaklı tehlike",
    "Forklift / araç trafiği",
    "İş makinesi kaynaklı tehlike",
    "Yaya-araç çarpışması",
    "Geri manevra riski",
    "Trafik altında çalışma",
    "Vinç çalışması",
    "Caraskal / kaldırma ekipmanı",
    "Asılı yük",
    "Yük düşmesi",
    "Sapancı / işaretçi hatası",
    "Elle taşıma / ergonomi",
    "Ağır kaldırma",
    "Tekrarlayan hareket",
    "Uygunsuz çalışma pozisyonu",
    "KKD kullanılmaması",
    "KKD uygunsuz kullanımı",
    "Göz / yüz koruması eksikliği",
    "Solunum koruması eksikliği",
    "Sıcak yüzey / ergimiş metal / sıçrama",
    "Yanık / haşlanma",
    "Kaynak / kesme / taşlama",
    "Basınçlı kap",
    "Basınçlı hava",
    "Kompresör",
    "Buhar hattı",
    "Hortum patlaması",
    "Havalandırma yetersizliği",
    "Yetersiz aydınlatma",
    "Gürültü",
    "Titreşim",
    "Sıcak ortam",
    "Soğuk ortam",
    "Termal konfor",
    "Depolama / istifleme uygunsuzluğu",
    "Raf devrilmesi",
    "Düzensizlik / temizlik eksikliği",
    "Atık yönetimi uygunsuzluğu",
    "Acil durum eksikliği",
    "Tahliye uygunsuzluğu",
    "Acil çıkış kapalı",
    "Yangın söndürücü eksikliği",
    "İlk yardım eksikliği",
    "Eğitim eksikliği",
    "Talimat eksikliği",
    "Denetim eksikliği",
    "Prosedür eksikliği",
    "Bakım eksikliği",
    "Periyodik kontrol eksikliği",
    "İş izin sistemi eksikliği",
    "Yetkisiz çalışma",
    "Alt işveren koordinasyon eksikliği",
    "Çalışan davranışı / güvensiz hareket",
    "Psikososyal risk",
    "Stres",
    "Şiddet",
    "Sabotaj",
    "Deprem",
    "Sel",
    "Fırtına",
    "Diğer",
]

ROOT_CAUSE_CATEGORIES = [
    "Eğitim / talimat eksikliği",
    "Denetim / gözetim eksikliği",
    "Bakım / periyodik kontrol eksikliği",
    "Makine / ekipman uygunsuzluğu",
    "KKD eksikliği veya uygunsuz kullanımı",
    "Zemin / ortam uygunsuzluğu",
    "Kimyasal güvenlik önlemi eksikliği",
    "Havalandırma / ortam ölçümü eksikliği",
    "İş organizasyonu / vardiya / yoğunluk",
    "Prosedür / talimat yokluğu",
    "Acil durum hazırlığı eksikliği",
    "Risk analizinde eksik değerlendirme",
    "Yetkisiz çalışma",
    "İş izin sistemi eksikliği",
    "Yetersiz aydınlatma",
    "Uygun olmayan el aleti kullanımı",
    "Elektriksel uygunsuzluk",
    "Yüksekte çalışma önlemi eksikliği",
    "Ergonomik uygunsuzluk",
    "İletişim / koordinasyon eksikliği",
    "Alt işveren koordinasyon eksikliği",
    "Malzeme istifleme / depolama uygunsuzluğu",
    "Trafik / forklift / saha içi araç uygunsuzluğu",
    "Çalışan davranışı / güvensiz hareket",
    "Yönetim sistemi eksikliği",
]

RISK_ANALYSIS_OPTIONS = [
    ("var_yeterli", "Var, tedbirler yeterli"),
    ("var_yetersiz", "Var, tedbirler yetersiz"),
    ("yok", "Risk analizinde yok, yeni tehlike olarak eklenmeli"),
    ("emin_degil", "Emin değilim, İSG uzmanı değerlendirsin"),
]

EMERGENCY_OPTIONS = [
    "Yangın riski",
    "Patlama riski",
    "Kimyasal yayılım / dökülme",
    "Zehirlenme",
    "Elektrik kaynaklı acil durum",
    "Tahliye gerektirebilecek olay",
    "İlk yardım gerektirebilecek olay",
    "Hayır, acil durum planını ilgilendirmiyor",
]

ACCIDENT_TYPES = [
    "Düşme (yüksekten)",
    "Düşme (aynı seviyede)",
    "Ezilme / sıkışma",
    "Kesik / delinme",
    "Çarpma / çarptırma",
    "Elektrik çarpması",
    "Kimyasal maruziyet",
    "Yanık / haşlanma",
    "Patlama / yangın",
    "Forklift / araç kazası",
    "Elle taşıma / zorlanma",
    "Diğer",
]

EMERGENCY_TYPES = [
    "Yangın",
    "Patlama",
    "Kimyasal sızıntı / dökülme",
    "Zehirlenme / gaz kaçağı",
    "Elektrik çarpması / ark",
    "Doğal afet (deprem, sel vb.)",
    "Kaza (ulaşım, iş makinesi)",
    "Kişisel saldırı / sabotaj",
    "Diğer",
]


def risk_level_for(score: int) -> str:
    if score <= 4:
        return "Düşük Risk"
    if score <= 9:
        return "Orta Risk"
    if score <= 15:
        return "Yüksek Risk"
    return "Çok Yüksek Risk"


def build_auto_warning(
    *,
    event_type: str,
    injury: bool,
    health_complaint: bool,
    medical: bool,
    incapacity: bool,
    sgk: bool,
    police: bool,
) -> str:
    notes: list[str] = []
    if event_type == "ramak_kala":
        if injury or health_complaint or medical:
            notes.append(
                "UYARI: Bu olay ramak kala değil, iş kazası olarak değerlendirilebilir. "
                "SGK bildirimi olay tarihinden sonraki 3 iş günü içinde yapılmalıdır."
            )
        if incapacity:
            notes.append(
                "İş göremezlik raporu alındığı için bu olay iş kazasıdır. SGK bildirimi zorunludur."
            )
    if event_type == "is_kazasi":
        if not sgk:
            notes.append(
                "SGK'ya bildirim yapılmadı! Olay tarihinden sonraki 3 iş günü içinde bildirim yapılmalıdır."
            )
        if not police:
            notes.append(
                "Kolluk kuvvetlerine bildirim yapılmadı! İş kazası derhal kolluğa bildirilmelidir."
            )
    return "\n\n".join(notes)


def meta_payload() -> dict:
    return {
        "event_types": [
            {"code": k, "label": v.get("adi", k), "color": v.get("renk")}
            for k, v in EVENT_TYPES.items()
        ],
        "classifications": CLASSIFICATIONS,
        "root_cause_categories": ROOT_CAUSE_CATEGORIES,
        "risk_analysis_options": [{"code": c, "label": l} for c, l in RISK_ANALYSIS_OPTIONS],
        "emergency_options": EMERGENCY_OPTIONS,
        "accident_types": ACCIDENT_TYPES,
        "emergency_types": EMERGENCY_TYPES,
    }
