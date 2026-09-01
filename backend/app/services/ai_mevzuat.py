"""Mevzuat bilgi tabanı — İSG uzmanı + mevzuat uzmanı karar-destek motoru.

Her tehlike kategorisi için:
- ilgili mevzuat (kanun md. + yönetmelik + TSE standardı)
- alınacak tedbirler (koruyucu/kontrol)
- önleyici faaliyetler (sistemik)
- ceza riski aralığı (6331 md.26/27)

Kural tabanlı; ücretli AI API gerektirmez. ai_assistant.py tarafından kullanılır.

Kaynaklar:
- 6331 sayılı İş Sağlığı ve Güvenliği Kanunu
- Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik
- İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği
- Yüksekte Çalışma ile İlgili Yönetmelik
- İşyerinde Patlayıcı Ortamların Oluşabilecek Yerlerde Çalışma Hakkında Yönetmelik (ATEKS)
- Kimyasal Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik
- Gürültü Yönetmeliği, Titreşim Yönetmeliği
- Kişisel Koruyucu Donanım Yönetmeliği
- TS EN standartları (12811, 13374, 12477 vb.)
"""
from __future__ import annotations

from typing import Any

MEVZUAT_ENGINE = "mevzuat-v1-6331"

# Kategori adı → mevzuat bilgisi (ai_hazard_hint.py kategori adlarıyla birebir eşleşir)
_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "Yüksekte Çalışma Riskleri": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": (
            "Yüksekte Çalışma ile İlgili Yönetmelik (RG 02.04.2015); "
            "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği"
        ),
        "standart": "TS EN 12811 (Geçici İskele), TS EN 13374 (Korkuluk), TS EN 12477 (Yüksekte Çalışma Ekipmanı)",
        "tedbirler": [
            "110 cm ana korkuluk, 55 cm orta korkuluk ve 10 cm dizek (ayak tabanı) ile yatay/köşe platform korkulukları",
            "İskele platformu en az 60 cm genişlik, dört kat genişlemeli, emniyet kemeri veya yaşam hattı bağlantı noktası",
            "Düşme durdurma sistemleri: ağ, koruma küpeştesi veya şişme yastık (4 m'den yüksek)",
            "İskele montaj/söküm yalnızca sertifikalı personel tarafından (TS EN 12811)",
            "Merdiven başı döşemesi, sabit yatay iskele, gerekirse sepetli vinç",
        ],
        "onleyici_faaliyet": [
            "Yüksekte çalışma prosedürü hazırlayın; yetkilendirilmiş personel listesi tutun",
            "Periyodik iskele kontrol formu (montaj öncesi, haftalık, kullanım sonrası) (Yüksekte Çalışma Y. md.9)",
            "Korkuluk/iskele kontrol sicili (İş Ekipmanları Y. md.6)",
            "Çalışanlara yüksekte çalışma eğitimi (6331 md.17 + Eğitim Y.)",
        ],
        "ceza_min_tl": 50000,
        "ceza_max_tl": 300000,
    },
    "Yangın ve Patlama Riskleri": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.11 (Acil Durum), md.12 (Tehlikeli Kimyasallar)",
        "yonetmelik": (
            "İşyerinde Patlayıcı Ortamların Oluşabilecek Yerlerde Çalışma Hakkında Yönetmelik (ATEKS); "
            "Binaların Yangından Korunması Hakkında Yönetmelik"
        ),
        "standart": "TS EN 1127-1 (Patlayıcı Ortam), TS EN 60079 (Ex Ekipman), NFPA 70E",
        "tedbirler": [
            "Sıcak iş (kaynak/kesme) izin sistemi; ATEX bölgesi sınıflandırması (bölge 0/1/2/20/21/22)",
            "Yanıcı/parlayıcı madde depolama: havalandırma, statik elektrik topraklama, kıvılcım önleyici",
            "Yangın söndürme sistemi (sprinkler/CO2/kuru kimyasal) + yangın dedektörü + acil aydınlatma",
            "Tahliye yolu ve acil çıkış kapıları (bölge kapısı 30 dk dayanım), tahliye planı",
            "Atex sertifikalı ekipman (Ex-proof) ve aletler; sigara içilmeyen alan işareti",
        ],
        "onleyici_faaliyet": [
            "Yangın ve tahliye tatbikatı (yılda en az 2) (6331 md.11)",
            "Patlayıcı ortam risk değerlendirmesi dokümanı (ATEKS Y. md.5)",
            "Yangın güvenlik sorumlusu atayın; periyodik yangın söndürme kontrolü (İş Ekipmanları Y.)",
            "Acil durum planı + tahliye rotası; yangın dolabı/söndürücü kontrol sicili",
        ],
        "ceza_min_tl": 80000,
        "ceza_max_tl": 600000,
    },
    "Elektrik Riskleri": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": (
            "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği; "
            "İşyeri Binaları ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine Dair Yönetmelik"
        ),
        "standart": "TS HD 60364 (Elektrik Tesisat), TS EN 61140 (Güvenlik), İç Tesisat Yönetmeliği",
        "tedbirler": [
            "Topraklama + kaçak akım rölesi (30 mA hassasiyet) ve aşırı akım koruması (sigorta)",
            "Pano kapıları kilitli, uyarı işareti; pano önünde yalıtkan paspas",
            "Yetkili/eğitimli personel (elektrikçi belgesi) dışında müdahale yok",
            "Periyodik elektrik tesisat kontrolü (yıllık) + topraklama ölçümü",
            "Kablo kapakları, açık hat yok; kablo kanalları ve kablo tavası kullanımı",
        ],
        "onleyici_faaliyet": [
            "Elektrik güvenlik prosedürü; lockout/tagout (LOTO) sistemi",
            "Periyodik elektrik tesisat kontrol sicili (İş Ekipmanları Y. md.6)",
            "Çalışanlara elektrik güvenliği eğitimi (6331 md.17)",
            "Paratoner + topraklama ölçüm raporu (yıllık)",
        ],
        "ceza_min_tl": 50000,
        "ceza_max_tl": 250000,
    },
    "Kimyasal Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.12 (Tehlikeli Kimyasallar), md.15 (Sağlık Gözetimi)",
        "yonetmelik": (
            "Kimyasal Maddelerle Çalışmalarda Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik (RG 12.08.2013); "
            "Güvenlik Bilgi Formu Hazırlanması ve Dağıtılması Hakkında Yönetmelik"
        ),
        "standart": "GHS/CLP Sınıflandırma, SDS (12 bölüm), TS EN 374 (Kimyasal KKD)",
        "tedbirler": [
            "SDS (Güvenlik Bilgi Formu) temini + tehlike etiketleme (GHS piktogram)",
            "Kapalı/havalandırmalı çalışma, lokal egzoz (LEV) sistemleri; maruziyet ölçümü",
            "Uygun KKD: kimyasal eldiven, gözlük, maske/tam yüz siperi (SDS bölüm 8)",
            "Dökülme/takılma kontrolü: tahliye bariyeri, kiti, nötralize madde",
            "Kimyasal depolama: ayrık dolap, yangın dayanımlı, uyumsuz kimyasallar ayrı",
        ],
        "onleyici_faaliyet": [
            "Kimyasal envanter + SDS yönetim sistemi (Kimyasal Y. md.14)",
            "Periyodik ortam ölçümü (maruziyet sınır değerleri; Kimyasal Y. md.18)",
            "Çalışan periyodik sağlık muayenesi (biyolojik izleme; 6331 md.15)",
            "Kimyasal dökülme tatbikatı + ilk yardım prosedürü",
        ],
        "ceza_min_tl": 60000,
        "ceza_max_tl": 400000,
    },
    "Biyolojik Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.15 (Sağlık Gözetimi)",
        "yonetmelik": "Biyoolojik Tehlikeli Çalışmalar Hakkında Yönetmelik; Enfeksiyon Kontrol Yönetmeliği",
        "standart": "TS EN 14683 (Maske), TS EN 455 (Eldiven), WHO enfeksiyon kontrol rehberi",
        "tedbirler": [
            "Standart önlemler (el hijyeni, KKD): eldiven, maske, önlük, gözlük",
            "Kesici-delici alet güvenliği: tek kullanımlık, atık kutusu (sarı konteyner)",
            "Vektör/zararlı kontrol; ortam dezenfeksiyonu (UV, kimyasal)",
            "Risk grubuna göre biyogüvenlik seviyesi (BSL-1/2/3) çalışma alanı",
        ],
        "onleyici_faaliyet": [
            "Biyolojik risk değerlendirme dokümanı (biyolojik Y.)",
            "Çalışan aşı programı (hepatit B vb.) + periyodik sağlık muayenesi (6331 md.15)",
            "Atık yönetimi prosedürü (tıbbi atık, kesici-delici)",
            "Enfeksiyon kontrol eğitimi (6331 md.17)",
        ],
        "ceza_min_tl": 50000,
        "ceza_max_tl": 250000,
    },
    "Ergonomik Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": "Manuel Taşıma İşlerine İlişkin Yönetmelik; Ekranlı Araçlarla Çalışmada Sağlık ve Güvenlik Önlemleri Hakkında Yönetmelik",
        "standart": "TS EN 1005-4 (Manuel Taşıma), ISO 6385 (Ergonomi), NIOSH kaldırma denklemi",
        "tedbirler": [
            "Ağır yük için mekanik kaldırma aracı (forklift, transpalet, vinç)",
            "Tekrarlayan hareket: iş rotasyonu, mola planı, ergonomik düzenleme (tezgah yüksekliği)",
            "Ekranlı çalışma: ergonomik sandalye, monitör mesafesi (50-70 cm), ara mola (20-20-20 kuralı)",
            "Manuel taşıma: güvenli kaldırma tekniği eğitimi, yük sınırı (erkek 25 kg, kadın 15 kg)",
        ],
        "onleyici_faaliyet": [
            "Ergonomik risk değerlendirme (NIOSH/REBA/RULA) dokümanı",
            "İş rotasyonu prosedürü; tekrarlayan hareket haritalaması",
            "Ekranlı çalışma sağlık muayenesi (6331 md.15) + ergonomik self-assessment formu",
            "Çalışanlara ergonomi + güvenli kaldırma eğitimi (6331 md.17)",
        ],
        "ceza_min_tl": 30000,
        "ceza_max_tl": 150000,
    },
    "Psikososyal Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": "İSGK kapsamında psikososyal risk değerlendirme rehberi (ÇSGB)",
        "standart": "ISO 45003 (Psikolojik İSG), WHO iş stresi rehberi",
        "tedbirler": [
            "İş yükü/vardiya dengeleme; gerçekçi hedeflendirme",
            "Mobbing/çatışma önleme prosedürü; bildirim kanalı (anonim)",
            "Tükenmişlik takibi: periyodik anket (CBI/MBI), yönetici 1:1 görüşmeler",
            "Çalışan destek programı (EAP); psikolojik danışmanlık erişimi",
        ],
        "onleyici_faaliyet": [
            "Psikososyal risk değerlendirme anketi (yıllık)",
            "Yönetici/çalışan iletişim eğitimi; çatışma yönetimi prosedürü",
            "Vardiya/çalışma süresi denetimi; aşırı mesai sınırlandırması",
        ],
        "ceza_min_tl": 30000,
        "ceza_max_tl": 150000,
    },
    "Nakliye ve Trafik Riskleri": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": "Tehlikeli Madde Taşımacılığı Yönetmeliği (ADR); İş Ekipmanları Yönetmeliği",
        "standart": "TS EN 13155 (Vinç), ADR Sınıf 1-9, TS ISO 2292 (Forklift)",
        "tedbirler": [
            "Forklift/araç yaya yolu ayrımı; yaya güvenlik bölgesi ve yansıtıcı yelek",
            "Araç bakım ve periyodik kontrol (forklift, vinç); operatör sertifikası",
            "Yükleme-boşaltma planı; yük sabitleme (kıtıştırma, kayış)",
            "Tesis içi hız sınırı (15 km/s), yansıtıcı işaretler, ayna/köşe aynaları",
        ],
        "onleyici_faaliyet": [
            "Tesis içi trafik planı + yaya yolu haritası",
            "Forklift/araç operatör yetki belgesi sicili",
            "Periyodik araç kontrol sicili (İş Ekipmanları Y. md.6)",
            "Yaya ve araç güvenliği eğitimi (6331 md.17)",
        ],
        "ceza_min_tl": 40000,
        "ceza_max_tl": 200000,
    },
    "İnşaat ve Yapı Riskleri": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri), md.25 (Tehlikeli İşler)",
        "yonetmelik": "İnşaat İşlerinde İSG Yönetmeliği (RG 05.10.2004); Yüksekte Çalışma Yönetmeliği",
        "standart": "TS EN 12811 (İskele), TS EN 13374 (Korkuluk), TS 12477, TS EN 13306 (İnşaat)",
        "tedbirler": [
            "Şantiye güvenlik planı; İSG koordinatörü atama (İnşaat Y. md.5)",
            "Düşme koruması: kenar korkulukları, güvenlik ağı, platform",
            "Kazı güvenliği: kazı tahkimatı, şev eğimi, daneli çökme önleme",
            "Kişisel koruyucu donanım: baret, güvenlik ayakkabısı, yelek",
            "Sıfır kazası: günlük araç briefingi (toolbox talk) + KKD kontrolü girişte",
        ],
        "onleyici_faaliyet": [
            "Şantiye İSG planı + risk değerlendirme dokümanı (İnşaat Y. md.4)",
            "İSG koordinatörü (KPS/KPY) atama + sözleşme",
            "Günlük KKD + iskele/kazı kontrol formu",
            "İnşaat İSG eğitimi (6331 md.17 + İnşaat Y.)",
        ],
        "ceza_min_tl": 60000,
        "ceza_max_tl": 400000,
    },
    "Mekanik Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "standart": "TS EN 349 (Makine Aralığı), TS EN 954-1 (Kontrol Sistemi), TS EN ISO 12100 (Makine Güvenliği)",
        "tedbirler": [
            "Dönen/kayış aksam koruyucuları: sabit kapak, ızgara, fotoelektrik bariyer",
            "Pres/konveyör güvenlik: iki el kumanda, ışık perdesi, acil stop",
            "Lockout/tagout (LOTO) bakım/temizlik sırasında enerji izolasyonu",
            "Vinç/kaldırma ekipmanı periyodik kontrolü (yıllık, sertifikalı kuruluş)",
            "KKD: önlük, kol koruyucu, güvenlik ayakkabısı, gözlük",
        ],
        "onleyici_faaliyet": [
            "Makine güvenlik risk değerlendirme dokümanı (ISO 12100)",
            "Periyodik makine kontrol sicili (İş Ekipmanları Y. md.6)",
            "LOTO prosedürü + enerji izolasyon planı",
            "Operatör makine güvenliği eğitimi (6331 md.17)",
        ],
        "ceza_min_tl": 50000,
        "ceza_max_tl": 300000,
    },
    "Fiziksel Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.15 (Sağlık Gözetimi)",
        "yonetmelik": "Gürültü Yönetmeliği (RG 28.07.2013); Titreşim Yönetmeliği; İyonize Radyasyon Güvenliği Yönetmeliği",
        "standart": "TS EN 458 (Gürültü KKD), ISO 1999 (Gürültü), TS EN 14253 (Titreşim)",
        "tedbirler": [
            "Gürültü: sessiz ekipman seçimi, akustik izolasyon, KKD (kulak tıkacı/siper)",
            "Titreşim: titreşim yalıtım koltuğu, dengesiz aletler için el koruyucu, süre azaltma",
            "Toz: kapalı sistem, LEV (lokal egzoz), nemlendirme, P3 maske",
            "Aydınlatma: doğal + yapay 500-1000 lux, acil aydınlatma",
            "Termal: ısınma/soğutma, hava sirkülasyonu; sıcak stresinde su ve mola",
            "Radyasyon: sınırlı süre, kurşun/kalkan koruma, dozimetre",
        ],
        "onleyici_faaliyet": [
            "Gürültü/titreşim periyodik ortam ölçümü (Gürültü Y. md.9; Titreşim Y. md.5)",
            "Çalışan periyodik sağlık muayenesi (odyometri, radyasyon doz) (6331 md.15)",
            "Maruziyet sınır değer takibi (gürültü 87 dB(A), titreşim 5 m/s²)",
            "Fiziksel riskler eğitimi (6331 md.17)",
        ],
        "ceza_min_tl": 40000,
        "ceza_max_tl": 250000,
    },
    "Diğer Riskler": {
        "kanun": "6331 sayılı İSG Kanunu",
        "madde": "md.10 (Risk Değerlendirme), md.4 (İşveren Yükümlülükleri)",
        "yonetmelik": "İSG mevzuatı genel hükümleri",
        "standart": "—",
        "tedbirler": [
            "Risk değerlendirme dokümanını güncelleyin (6331 md.10)",
            "Uygun KKD ve kontroller tanımlayın",
            "Çalışan bilgilendirmesi ve eğitimi (6331 md.17)",
        ],
        "onleyici_faaliyet": [
            "Periyodik risk değerlendirme gözden geçirme (yıllık veya değişiklikte)",
            "DÖF (düzeltici/önleyici faaliyet) kaydı açın",
            "Çalışan görüş ve katılımı (6331 md.4)",
        ],
        "ceza_min_tl": 30000,
        "ceza_max_tl": 150000,
    },
}


_VISUAL_HAZARD_PROFILES: dict[str, dict[str, Any]] = {
    "stair_obstruction": {
        "category": "Mekanik Riskler",
        "hazard_code": "MEK-008",
        "hazard_name": "Merdiven ve geçiş alanında malzeme engeli",
        "detail_category": "Merdivenler",
        "mevzuat": {
            "kanun": "6331 sayılı İSG Kanunu",
            "madde": "md.4 ve md.10 (aday dayanak; uzman doğrulaması gerekli)",
            "yonetmelik": "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik; İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
            "standart": "Uygulanabilir işyeri standardı ve yerel düzenleme uzman tarafından doğrulanmalı",
        },
        "tedbirler": [
            "Merdiven basamakları ve sahanlıktaki kova, poşet, kutu ve diğer malzemeleri kaldırın; geçiş yüzeyini tamamen açık bırakın.",
            "Malzemeleri merdiven ve geçiş dışında tanımlı, güvenli depolama alanına alın.",
            "Merdiven ve sahanlığın açıklığını, takılma ve düşme riskini yerinde kontrol edin.",
        ],
        "onleyici_faaliyet": [
            "Merdiven ve geçiş alanı düzen/temizlik kontrolünü günlük veya vardiya saha kontrol listesine ekleyin.",
            "Geçici malzeme bırakılmasını önleyen depolama ve sorumluluk kuralı belirleyin.",
            "Düzeltme sonrası aynı açıdan kontrol fotoğrafı alın ve uzman doğrulamasıyla kapatın.",
        ],
        "ceza_riski": {
            "min_tl": None,
            "max_tl": None,
            "display": "İhlal niteliği ve güncel idari para cezası tarife doğrulaması bekliyor.",
            "status": "needs_expert_review",
            "basis": "Merdiven/geçiş alanının malzeme ile engellenmesi",
        },
    },
    "housekeeping_obstruction": {
        "category": "Mekanik Riskler",
        "hazard_code": "MEK-008",
        "hazard_name": "Sahanlık ve geçiş alanında düzensizlik",
        "detail_category": "Genel işyeri düzeni ve temizlik",
        "mevzuat": {
            "kanun": "6331 sayılı İSG Kanunu",
            "madde": "md.4 ve md.10 (aday dayanak; uzman doğrulaması gerekli)",
            "yonetmelik": "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik; İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
            "standart": "Uygulanabilir işyeri standardı ve yerel düzenleme uzman tarafından doğrulanmalı",
        },
        "tedbirler": [
            "Sahanlık ve geçiş alanındaki kova, bidon, kutu, poşet ve diğer dağınık malzemeleri kaldırın.",
            "Geçiş yolunu açık ve temiz tutun; malzemeleri belirlenmiş depolama alanına taşıyın.",
            "Alanı yerinde kontrol ederek takılma, kayma ve düşmeye neden olabilecek engelleri giderin.",
        ],
        "onleyici_faaliyet": [
            "Genel işyeri düzeni ve temizlik kontrolünü saha denetim planına ekleyin.",
            "Malzeme bırakma, toplama ve sorumluluk adımlarını yazılı işyeri kuralına bağlayın.",
            "Düzeltme sonrası kontrol fotoğrafı alın ve uzman doğrulamasıyla kapatın.",
        ],
        "ceza_riski": {
            "min_tl": None,
            "max_tl": None,
            "display": "İhlal niteliği ve güncel idari para cezası tarife doğrulaması bekliyor.",
            "status": "needs_expert_review",
            "basis": "Sahanlık/geçiş alanında düzen ve açıklık eksikliği",
        },
    },
}


def get_visual_hazard_profile(hazard_key: str | None) -> dict[str, Any] | None:
    """Görsel bulgu için yalnızca kanıtlanmış, dar kapsamlı profil döndürür."""
    key = str(hazard_key or "").strip()
    profile = _VISUAL_HAZARD_PROFILES.get(key)
    if not profile:
        return None

    return {
        **profile,
        "mevzuat": dict(profile["mevzuat"]),
        "tedbirler": list(profile["tedbirler"]),
        "onleyici_faaliyet": list(profile["onleyici_faaliyet"]),
        "ceza_riski": dict(profile["ceza_riski"]),
    }


def build_visual_report(
    *,
    hazard_key: str,
    text: str | None = None,
    confidence: float | int | None = None,
) -> dict[str, Any] | None:
    """Görsel tehlike kimliğini ilgili mevzuat ve aksiyonlarla eşleştirir.

    Bu paket, geniş kategori mevzuat listesini görsel bulguya otomatik olarak
    kopyalamaz. Fotoğrafta desteklenen tehlikeye özgü tedbir ve DÖF üretir;
    ceza tutarını da uzman doğrulaması olmadan sayısallaştırmaz.
    """
    profile = get_visual_hazard_profile(hazard_key)
    if not profile:
        return None

    try:
        confidence_value = max(0.0, min(1.0, float(confidence or 0)))
    except (TypeError, ValueError):
        confidence_value = 0.0

    observation = (text or "").strip() or profile["hazard_name"]
    penalty = profile["ceza_riski"]
    report_lines = [
        f"TESPİT: {observation}",
        f"TEHLİKE: {profile['hazard_name']}",
        f"MEVZUAT: {profile['mevzuat']['kanun']}; {profile['mevzuat']['yonetmelik']}",
        "TEDBİRLER: " + " | ".join(profile["tedbirler"]),
        "ÖNLEYİCİ FAALİYETLER: " + " | ".join(profile["onleyici_faaliyet"]),
        f"CEZA DEĞERLENDİRMESİ: {penalty['display']}",
    ]

    return {
        "engine": MEVZUAT_ENGINE,
        "category": profile["category"],
        "hazard_key": hazard_key,
        "hazard_code": profile["hazard_code"],
        "hazard_name": profile["hazard_name"],
        "detail_category": profile["detail_category"],
        "matched": True,
        "confidence": confidence_value,
        "mevzuat": profile["mevzuat"],
        "tedbirler": profile["tedbirler"],
        "onleyici_faaliyet": profile["onleyici_faaliyet"],
        "ceza_riski": penalty,
        "source": "ai_vision_visual_hazard",
        "report_text": "\n".join(report_lines),
    }


def get_mevzuat_for_category(category_name: str) -> dict[str, Any] | None:
    """Kategori adı → mevzuat bilgisi (kanun, yonetmelik, standart, tedbirler, onleyici)."""
    return _KNOWLEDGE.get(category_name)


def build_report(
    *,
    text: str | None = None,
    hazard_hint: dict[str, Any] | None = None,
    company_id: int | None = None,
    db=None,
) -> dict[str, Any]:
    """Tespit metni + hazard hint → mevzuat uzmanı raporu.

    Bir İSG uzmanı ve mevzuat uzmanı gibi:
    - ilgili mevzuatı (kanun/yönetmelik/TSE) gösterir
    - alınacak tedbirleri (koruyucu/kontrol) listeler
    - önleyici faaliyetleri (sistemik) önerir
    - ceza riski aralığı verir
    - rapor metni üretir
    """
    from app.services.ai_hazard_hint import suggest_hazard_from_text

    blob = " ".join(p.strip() for p in [text] if p and p.strip())
    hh = hazard_hint or suggest_hazard_from_text(blob or "")
    category = hh.get("suggested_category") if hh.get("matched") else None
    mevzuat = get_mevzuat_for_category(category or "Diğer Riskler")

    if not mevzuat:
        return {
            "engine": MEVZUAT_ENGINE,
            "category": category,
            "matched": False,
            "report_text": "Tehlike kategorisi eşleşmedi; manuel risk değerlendirmesi yapın.",
            "mevzuat": None,
            "tedbirler": [],
            "onleyici_faaliyet": [],
            "ceza_riski": None,
        }

    kanun = mevzuat["kanun"]
    madde = mevzuat["madde"]
    yonetmelik = mevzuat["yonetmelik"]
    standart = mevzuat["standart"]
    tedbirler = mevzuat["tedbirler"]
    onleyici = mevzuat["onleyici_faaliyet"]
    ceza_min = mevzuat["ceza_min_tl"]
    ceza_max = mevzuat["ceza_max_tl"]

    report_lines = [
        f"TESPİT: {blob or 'Saha tespiti'}",
        f"TEHLİKE KATEGORİSİ: {category} (güven: {int((hh.get('confidence') or 0) * 100)}%)",
        "",
        f"İLGİLİ MEVZUAT:",
        f"  • {kanun} {madde}",
        f"  • {yonetmelik}",
        f"  • Standartlar: {standart}",
        "",
        "ALINACAK TEDBİRLER (koruyucu/kontrol):",
    ]
    for i, t in enumerate(tedbirler, 1):
        report_lines.append(f"  {i}. {t}")
    report_lines.append("")
    report_lines.append("ÖNLEYİCİ FAALİYETLER (sistemik):")
    for i, t in enumerate(onleyici, 1):
        report_lines.append(f"  {i}. {t}")
    report_lines.append("")
    report_lines.append(
        f"CEZA RİSKİ: {ceza_min:,} – {ceza_max:,} TL "
        f"(6331 md.26/27; gerçek ceza ihlal niteliğine göre değişir)"
    )

    return {
        "engine": MEVZUAT_ENGINE,
        "category": category,
        "matched": True,
        "confidence": hh.get("confidence", 0),
        "mevzuat": {
            "kanun": kanun,
            "madde": madde,
            "yonetmelik": yonetmelik,
            "standart": standart,
        },
        "tedbirler": tedbirler,
        "onleyici_faaliyet": onleyici,
        "ceza_riski": {"min_tl": ceza_min, "max_tl": ceza_max},
        "report_text": "\n".join(report_lines),
    }
