"""
MEVZUAT MOTORU - Regulation Engine
Tehlike türüne göre ilgili mevzuatı otomatik getirir.
"""

import json

REGULATIONS = {
    "Fiziksel Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "İş Hijyeni Ölçüm ve Test Yöntemlerine Dair Yönetmelik",
        "Gürültü Yönetmeliği (2003/10/EC uyumlu)",
        "Titreşim Yönetmeliği (2002/44/EC uyumlu)",
        "Termal Konfor Şartları ile İlgili Yönetmelik",
        "Aydınlatma Yönetmeliği",
        "Radyasyon Güvenliği Yönetmeliği",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    ],
    "Mekanik Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Makine Emniyeti Yönetmeliği (2006/42/AT)",
        "Asansör Bakım İşletme Yönetmeliği",
        "Basınçlı Ekipmanlar Yönetmeliği (2014/68/AB)",
        "Elle Taşıma İşleri Yönetmeliği",
    ],
    "Elektrik Riskleri": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "Elektrik Tesislerinde Topraklamalar Yönetmeliği",
        "Elektrik İç Tesisleri Yönetmeliği",
        "Elektrik Tesisleri Proje Yönetmeliği",
        "Elektrik Kuvvetli Akım Tesisleri Yönetmeliği",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Yıldırımdan Korunma Yönetmeliği",
        "TS EN 50110-1 Elektrik Tesislerinin İşletilmesi",
    ],
    "Kimyasal Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Kimyasal Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
        "Kanserojen ve Mutajen Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
        "Tehlikeli Kimyasalların Envanteri Hakkında Tebliğ",
        "Maddelerin ve Karışımların Sınıflandırılması, Etiketlenmesi ve Ambalajlanması Yönetmeliği (SEA)",
        "Büyük Endüstriyel Kazaların Kontrolü Hakkında Yönetmelik",
        "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik",
        "Kişisel Koruyucu Donanım Yönetmeliği",
        "Tehlikeli Atık Yönetmeliği",
        "Asbestle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
    ],
    "Biyolojik Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Biyolojik Etkenlere Maruziyet Risklerinin Önlenmesi Hakkında Yönetmelik",
        "Kişisel Koruyucu Donanım Yönetmeliği",
        "Atık Yönetimi Yönetmeliği",
        "Tıbbi Atık Yönetmeliği",
        "İş Hijyeni Ölçüm ve Test Yöntemlerine Dair Yönetmelik",
        "Enfeksiyon Hastalıkları Bildirim Sistemi Genelgesi",
    ],
    "Ergonomik Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Elle Taşıma İşleri Yönetmeliği",
        "Ekranlı Araçlarla Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
        "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    ],
    "Psikososyal Riskler": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
        "İşyerinde Psikolojik Tacizin (Mobbing) Önlenmesi Genelgesi",
        "Çalışma Süreleri Yönetmeliği",
        "İş Kanunu (4857 Sayılı) - Çalışma Süreleri ve Vardiya Düzenlemeleri",
        "Kadın Çalışanların Gece Postalarında Çalıştırılma Koşulları Hakkında Yönetmelik",
    ],
    "Yangın ve Patlama Riskleri": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Binaların Yangından Korunması Hakkında Yönetmelik",
        "Patlayıcı Ortamların Tehlikelerinden Çalışanların Korunması Hakkında Yönetmelik (ATEX)",
        "Yanıcı, Patlayıcı, Tehlikeli ve Zararlı Maddelerle Çalışılan İşyerlerinde Alınacak Güvenlik Önlemleri Hakkında Yönetmelik",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Sıvılaştırılmış Petrol Gazları (LPG) Piyasası ve Enerji Piyasası Düzenleme Kurumu Yönetmelikleri",
        "Doğalgaz Piyasası Yönetmelikleri",
        "Acil Durum Yönetmeliği",
        "Yangın Söndürme ve Yangın Algılama Sistemleri ile İlgili Standartlar",
    ],
    "Çevresel Riskler": [
        "Çevre Kanunu (2872 Sayılı)",
        "Atık Yönetimi Yönetmeliği",
        "Tehlikeli Atık Yönetmeliği",
        "Su Kirliliği Kontrolü Yönetmeliği",
        "Hava Kalitesi Değerlendirme ve Yönetimi Yönetmeliği",
        "Çevresel Etki Değerlendirmesi (ÇED) Yönetmeliği",
        "Gürültü Kontrol Yönetmeliği",
        "Sıfır Atık Yönetmeliği",
        "Ambalaj Atıklarının Kontrolü Yönetmeliği",
    ],
    "Yüksekte Çalışma Riskleri": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Yapı İşlerinde İş Sağlığı ve Güvenliği Yönetmeliği",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Kişisel Koruyucu Donanım Yönetmeliği",
        "Dikey Geçitlerde ve Yüksekte Çalışma Koşullarında Alınacak Güvenlik Önlemleri Hakkında Yönetmelik",
        "İskele Yönetmeliği",
        "Yapı İşlerinde İSG Yönetmeliği",
    ],
    "Nakliye ve Trafik Riskleri": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Karayolları Trafik Kanunu (2918 Sayılı)",
        "Tehlikeli Maddelerin Karayoluyla Taşınması Hakkında Yönetmelik (ADR)",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Sürücü Çalışma Süreleri Yönetmeliği",
        "Araç Muayene ve Periyodik Kontrol Yönetmelikleri",
    ],
    "İnşaat ve Yapı Riskleri": [
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
        "Yapı İşlerinde İş Sağlığı ve Güvenliği Yönetmeliği",
        "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "Kişisel Koruyucu Donanım Yönetmeliği",
        "Yapı Denetim Kanunu (4708 Sayılı)",
        "İmar Kanunu (3194 Sayılı)",
        "Kazı Çalışmalarında Alınacak Güvenlik Önlemleri Tebliği",
        "Vinç ve Kaldırma Ekipmanları Yönetmeliği",
        "Asansör Yönetmeliği (Bakım ve İşletme)",
    ],
}


# Genel mevzuat (tüm sektörler için geçerli)
GENERAL_REGULATIONS = [
    "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
    "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
    "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik",
    "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    "Kişisel Koruyucu Donanım Yönetmeliği",
    "Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik",
    "Acil Durum Yönetmeliği",
    "İş Kazası ve Meslek Hastalığı Kayıt ve Bildirim Yönetmeliği",
    "İşyeri Hekimi ve İş Güvenliği Uzmanı Görev, Yetki ve Yükümlülükleri Yönetmeliği",
    "Çalışanların Patlayıcı Ortamların Tehlikelerinden Korunması Hakkında Yönetmelik",
    "Elle Taşıma İşleri Yönetmeliği",
    "Ekranlı Araçlarla Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
    "Kanserojen ve Mutajen Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
    "Kimyasal Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
    "Biyolojik Etkenlere Maruziyet Risklerinin Önlenmesi Hakkında Yönetmelik",
    "Yapı İşlerinde İş Sağlığı ve Güvenliği Yönetmeliği",
    "Geçici veya Belirli Süreli İşlerde İş Sağlığı ve Güvenliği Hakkında Yönetmelik",
    "İş Sağlığı ve Güvenliği Hizmetleri Yönetmeliği",
    "4857 Sayılı İş Kanunu",
    "5510 Sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu (İş Kazası ve Meslek Hastalığı bölümleri)",
]


def get_regulations_for_hazard(hazard):
    """Tehlike için ilgili mevzuatı getir"""
    import json
    if hazard and hazard.regulations:
        try:
            return json.loads(hazard.regulations)
        except:
            pass
    return []


def get_regulations_for_category(category_name):
    """Kategori adına göre mevzuat getir"""
    return REGULATIONS.get(category_name, GENERAL_REGULATIONS)


def get_all_regulations():
    """Tüm mevzuat listesi"""
    all_regs = list(GENERAL_REGULATIONS)
    for key, regs in REGULATIONS.items():
        for r in regs:
            if r not in all_regs:
                all_regs.append(r)
    return sorted(all_regs)


def get_regulations_by_keyword(keyword):
    """Anahtar kelimeye göre mevzuat ara"""
    keyword = keyword.lower()
    results = []
    for reg in get_all_regulations():
        if keyword in reg.lower():
            results.append(reg)
    return results


# Tehlike koduna göre mevzuat eşleştirmesi
HAZARD_REGULATION_MAP = {
    "FZK": ["Gürültü Yönetmeliği", "Titreşim Yönetmeliği", "İş Hijyeni Ölçüm Yönetmeliği"],
    "MEK": ["Makine Emniyeti Yönetmeliği", "İş Ekipmanları Yönetmeliği"],
    "ELE": ["Elektrik İç Tesisleri Yönetmeliği", "Topraklamalar Yönetmeliği"],
    "KMY": ["Kimyasal Maddelerle Çalışma Yönetmeliği", "SEA Yönetmeliği", "Kanserojen Yönetmeliği"],
    "BIO": ["Biyolojik Etkenler Yönetmeliği"],
    "ERG": ["Elle Taşıma Yönetmeliği", "Ekranlı Araçlar Yönetmeliği"],
    "PSI": ["Mobbing Genelgesi", "Çalışma Süreleri Yönetmeliği"],
    "YAN": ["Yangından Korunma Yönetmeliği", "ATEX Yönetmeliği"],
    "ATX": ["ATEX Yönetmeliği", "Yangından Korunma Yönetmeliği"],
    "CEV": ["Çevre Kanunu", "Atık Yönetimi Yönetmeliği"],
    "YKC": ["Yapı İşleri Yönetmeliği", "Yüksekte Çalışma Yönetmeliği"],
    "INS": ["Yapı İşleri Yönetmeliği", "Yapı Denetim Kanunu"],
    "NAK": ["ADR Yönetmeliği", "Karayolları Trafik Kanunu"],
    "AHM": ["Tozla Mücadele Yönetmeliği", "ATEX Yönetmeliği", "İş Ekipmanları Yönetmeliği"],
    "ALT": ["Yapı İşlerinde İSG Yönetmeliği", "İş Ekipmanları Yönetmeliği", "Trafik Güvenliği Mevzuatı"],
    "ATK": ["Atık Yönetimi Yönetmeliği", "Biyolojik Etkenler Yönetmeliği"],
    "BAS": ["Basınçlı Ekipmanlar Mevzuatı", "İş Ekipmanları Yönetmeliği"],
    "DER": ["Kimyasal Maddelerle Çalışma Yönetmeliği", "SEA Yönetmeliği"],
    "ENE": ["Elektrik İç Tesisleri Yönetmeliği", "Topraklamalar Yönetmeliği", "İş Ekipmanları Yönetmeliği"],
    "GID": ["İş Ekipmanları Yönetmeliği", "Kimyasal Maddelerle Çalışma Yönetmeliği", "Gıda Hijyeni Mevzuatı"],
    "KIM": ["Kimyasal Maddelerle Çalışma Yönetmeliği", "SEA Yönetmeliği", "Kanserojen ve Mutajen Maddelerle Çalışma Yönetmeliği"],
    "LOJ": ["İş Ekipmanları Yönetmeliği", "Elle Taşıma İşleri Yönetmeliği"],
    "MAD": ["Maden İşyerlerinde İş Sağlığı ve Güvenliği Yönetmeliği", "ATEX Yönetmeliği", "İş Ekipmanları Yönetmeliği"],
    "MET": ["İş Ekipmanları Yönetmeliği", "Kimyasal Maddelerle Çalışma Yönetmeliği", "KKD Yönetmeliği"],
    "OFI": ["Ekranlı Araçlarla Çalışma Yönetmeliği", "İşyeri Bina ve Eklentileri Yönetmeliği"],
    "OTO": ["6331 Sayılı İş Sağlığı ve Güvenliği Kanunu", "İş Ekipmanları Yönetmeliği", "Kimyasal Maddelerle Çalışma Yönetmeliği"],
    "PAT": ["ATEX Yönetmeliği", "Binaların Yangından Korunması Hakkında Yönetmelik", "Tehlikeli Kimyasallar Yönetmeliği"],
    "PER": ["İşyeri Bina ve Eklentileri Yönetmeliği", "Elle Taşıma İşleri Yönetmeliği"],
    "PET": ["Kimyasal Maddelerle Çalışma Yönetmeliği", "ATEX Yönetmeliği", "Binaların Yangından Korunması Hakkında Yönetmelik"],
    "SAG": ["Biyolojik Etkenler Yönetmeliği", "Radyasyon Güvenliği Mevzuatı", "Tıbbi Atıkların Kontrolü Yönetmeliği"],
    "TAR": ["6331 Sayılı Kanun", "İş Ekipmanları Yönetmeliği", "Kimyasal Maddelerle Çalışma Yönetmeliği"],
    "TEK": ["İş Ekipmanları Yönetmeliği", "Tozla Mücadele Yönetmeliği"],
    "TER": ["Tersane İşleri İSG Mevzuatı", "Kapalı Alan Çalışma Prosedürleri", "İş Ekipmanları Yönetmeliği"],
    "TUR": ["İş Ekipmanları Yönetmeliği", "Kimyasal Maddelerle Çalışma Yönetmeliği"],
}


def get_regulations_for_hazard_code(hazard_code):
    """Tehlike koduna göre spesifik mevzuat getir"""
    prefix = hazard_code.split("-")[0]
    return HAZARD_REGULATION_MAP.get(prefix, [])
