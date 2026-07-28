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

# (kod, ad, tehlike_sinifi, 5 sektörel konu) — ISG Pro 2026 tam katalog aktarımı
# Kaynak: training_sector_catalog.py / Pro egitim/sector_catalog.py
_SECTOR_RAW: list[tuple[str, str, str, list[str]]] = [
    ("ahsap_mobilya_uretimi", "Ahşap / Mobilya Üretimi", "Tehlikeli", ["Testere, freze, planya ve CNC makinelerinde kesilme-kapılma", "Ahşap tozu maruziyeti, emiş sistemi ve toz patlaması", "Vernik, boya, tiner ve yapıştırıcılarla güvenli çalışma", "Zımpara, pres, çivi tabancası ve el aleti güvenliği", "Talaş-atık yönetimi, yangın önleme ve düzenli temizlik"]),
    ("ahsap_mobilya", "Ahşap ve Mobilya Üretimi", "Tehlikeli", ["Testere, freze, planya ve CNC makinelerinde kesilme-kapılma", "Ahşap tozu maruziyeti, emiş sistemi ve toz patlaması", "Vernik, boya, tiner ve yapıştırıcılarla güvenli çalışma", "Zımpara, pres, çivi tabancası ve el aleti güvenliği", "Talaş-atık yönetimi, yangın önleme ve düzenli temizlik"]),
    ("akaryakit_lpg_dolum_istasyonu", "Akaryakıt / LPG / Dolum İstasyonu", "Tehlikeli", ["Yanıcı gaz-sıvı sızıntısı ve patlayıcı ortamlar", "Hidrojen sülfür, toksik gaz ve gaz ölçümü", "Tank, reaktör ve kapalı alanda çalışma", "Dolum-boşaltım, statik elektrik ve topraklama", "Sıcak çalışma, yangın ve acil durdurma sistemleri"]),
    ("aku_uretimi", "Akü ve Batarya Üretimi", "Çok Tehlikeli", ["Kurşun ve kurşun bileşikleriyle güvenli çalışma", "Sülfürik asit, elektrolit ve kimyasal sıçrama riskleri", "Akü şarjında hidrojen gazı, havalandırma ve patlama riski", "Kimyasal dökülme, göz duşu ve acil müdahale", "Hijyen, sağlık gözetimi ve uygun kişisel koruyucu donanım"]),
    ("aluminyum_profil_isleme", "Alüminyum / Profil İşleme", "Tehlikeli", ["Kaynak ışını, göz-yüz koruması ve sıcak metal sıçraması", "Kaynak dumanı, gazlar ve lokal havalandırma", "Sıcak çalışma izni, kıvılcım kontrolü ve yangın gözcülüğü", "Basınçlı gaz tüpleri, regülatör ve hortum güvenliği", "Kapalı alanda kaynak, gaz ölçümü ve kurtarma planı"]),
    ("alisveris_merkezi_avm", "Alışveriş Merkezi / AVM", "Tehlikeli", ["Müşteri ve çalışan alanlarında kayma-düşme", "Raf, istif ve malzeme düşmesi riskleri", "Depo, palet, transpalet ve elle taşıma", "Soğuk depo, kesici ekipman ve temizlik kimyasalları", "Yangın, acil çıkış ve kalabalık tahliyesi"]),
    ("ambalaj_paketleme", "Ambalaj / Paketleme", "Tehlikeli", ["Kesim, baskı, sarım ve katlama makinelerinde kapılma", "Mürekkep, solvent ve temizlik kimyasallarıyla çalışma", "Kâğıt tozu, gürültü ve havalandırma", "Bobin, palet ve ağır malzeme taşıma güvenliği", "Yangın yükü, statik elektrik ve acil durumlar"]),
    ("asansor_montaj_ve_bakim", "Asansör / Montaj ve Bakım", "Tehlikeli", ["Makine koruyucuları, emniyet tertibatları ve acil durdurma", "Kesilme, sıkışma, ezilme ve parça fırlaması riskleri", "Bakım ve ayarda enerji izolasyonu ile kilitleme-etiketleme", "Taşlama, kesme, matkap ve el aletleriyle güvenli çalışma", "Montaj, kaldırma-taşıma ve ergonomik zorlanmalar"]),
    ("atik_yonetimi_geri_donusum", "Atık Yönetimi / Geri Dönüşüm", "Tehlikeli", ["Kesici-delici atıklar ve elle ayırma riskleri", "Pres, balya, kırıcı ve konveyör makineleri", "Biyolojik etken, toz, gaz ve koku maruziyeti", "Atık yangını, batarya ve kimyasal uyumsuzluk", "Araç trafiği, istif ve acil durum prosedürleri"]),
    ("atik_geri_donusum", "Atık Yönetimi ve Geri Dönüşüm", "Tehlikeli", ["Kesici-delici atıklar ve elle ayırma riskleri", "Pres, balya, kırıcı ve konveyör makineleri", "Biyolojik etken, toz, gaz ve koku maruziyeti", "Atık yangını, batarya ve kimyasal uyumsuzluk", "Araç trafiği, istif ve acil durum prosedürleri"]),
    ("avukatlik_hukuk_burosu", "Avukatlık / Hukuk Bürosu", "Tehlikeli", ["Kanalizasyon gazları, oksijen yetersizliği ve kapalı alan", "Biyolojik etkenler, sıçrama ve hijyen", "Klor, ozon, asit-baz ve kimyasal dozlama", "Havuz, tank, düşme ve boğulma riskleri", "Pompa, elektrik, bakım ve enerji izolasyonu"]),
    ("ayakkabi_deri_uretimi", "Ayakkabı / Deri Üretimi", "Tehlikeli", ["Dokuma, örme, eğirme ve sarım makinelerine kapılma", "Tekstil tozu, lif, boya ve kimyasal maruziyet", "Kesim, dikim, ütü ve sıcak yüzey riskleri", "Gürültü, ergonomi ve tekrarlayan hareketler", "Yangın yükü, acil çıkış ve istif güvenliği"]),
    ("acik_maden", "Açık Maden, Taş Ocağı ve Agrega", "Çok Tehlikeli", ["Şev, kademe, kaya düşmesi ve heyelan riskleri", "Patlatma operasyonu ve emniyet mesafeleri", "Kırma-eleme, konveyör ve sıkışma riskleri", "Toz, silika, gürültü ve titreşim maruziyeti", "Ocak içi trafik, iş makineleri ve kör noktalar"]),
    ("agac_isleri_marangozluk", "Ağaç İşleri / Marangozluk", "Tehlikeli", ["Testere, freze, planya ve CNC makinelerinde kesilme-kapılma", "Ahşap tozu maruziyeti, emiş sistemi ve toz patlaması", "Vernik, boya, tiner ve yapıştırıcılarla güvenli çalışma", "Zımpara, pres, çivi tabancası ve el aleti güvenliği", "Talaş-atık yönetimi, yangın önleme ve düzenli temizlik"]),
    ("bakim_onarim_teknik_servis", "Bakım-Onarım / Teknik Servis", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("balikcilik_su_urunleri", "Balıkçılık / Su Ürünleri", "Tehlikeli", ["Kanalizasyon gazları, oksijen yetersizliği ve kapalı alan", "Biyolojik etkenler, sıçrama ve hijyen", "Klor, ozon, asit-baz ve kimyasal dozlama", "Havuz, tank, düşme ve boğulma riskleri", "Pompa, elektrik, bakım ve enerji izolasyonu"]),
    ("banka_finans_2", "Banka / Finans", "Tehlikeli", ["Ekranlı çalışma, ergonomi ve hareketsizlik", "İş stresi, müşteri baskısı ve psikososyal riskler", "Elektrik, yangın ve acil tahliye", "Güvenlik, saldırı ve nakit işlem riskleri", "Arşiv, depo ve kayma-takılma riskleri"]),
    ("banka_finans", "Banka, Finans ve Çağrı Merkezi", "Tehlikeli", ["Ekranlı çalışma, ergonomi ve hareketsizlik", "İş stresi, müşteri baskısı ve psikososyal riskler", "Elektrik, yangın ve acil tahliye", "Güvenlik, saldırı ve nakit işlem riskleri", "Arşiv, depo ve kayma-takılma riskleri"]),
    ("basin_yayin_medya", "Basın / Yayın / Medya", "Tehlikeli", ["Ekranlı araçlar, oturma düzeni ve ergonomi", "Elektrikli ofis ekipmanlarının güvenli kullanımı", "Yangın, tahliye ve toplanma alanı uygulamaları", "Kayma, takılma, düşme ve düzen riskleri", "Psikososyal riskler, iş yükü ve stres yönetimi"]),
    ("belediye_kamu_hizmetleri", "Belediye / Kamu Hizmetleri", "Tehlikeli", ["Saha, yol, park-bahçe ve trafik altında çalışma", "Atık toplama, biyolojik risk ve kesici-delici atıklar", "Kazı, altyapı, kanalizasyon ve kapalı alanlar", "İş makineleri, araçlar ve yaya güvenliği", "Halka açık alanlarda acil durum ve şiddet riski"]),
    ("belediye", "Belediye, Kamu ve Saha Hizmetleri", "Tehlikeli", ["Saha, yol, park-bahçe ve trafik altında çalışma", "Atık toplama, biyolojik risk ve kesici-delici atıklar", "Kazı, altyapı, kanalizasyon ve kapalı alanlar", "İş makineleri, araçlar ve yaya güvenliği", "Halka açık alanlarda acil durum ve şiddet riski"]),
    ("beton_cimento_hazir_beton", "Beton / Çimento / Hazır Beton", "Tehlikeli", ["Çimento ve silika tozu maruziyeti", "Konveyör, kırıcı, mikser ve döner ekipmana kapılma", "Beton pompası, hortum savrulması ve basınç riskleri", "Mobil ekipman, saha trafiği ve kör noktalar", "Kimyasal katkı, alkalin yanık ve temizlik işlemleri"]),
    ("bilisim_yazilim_it", "Bilişim / Yazılım / IT", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("boyahaneler_boya_uretimi", "Boyahaneler / Boya Üretimi", "Tehlikeli", ["Kimyasal etiketler, SDS ve maruziyet yolları", "Solvent, izosiyanat, aerosol ve toksik buhar maruziyeti", "Yanıcı atmosfer, statik elektrik ve ex-proof ekipman", "Uyumsuz kimyasalların güvenli depolanması ve transferi", "Dökülme, sızıntı, acil duş ve müdahale prosedürleri"]),
    ("cam_seramik_porselen", "Cam / Seramik / Porselen", "Tehlikeli", ["Cam kırılması, keskin kenar ve göz yaralanmaları", "Fırın, sıcak ürün ve termal şok riskleri", "Silika, seramik tozu ve solunum korunması", "Pres, kesim, taşlama ve parça fırlaması riskleri", "Ağır plaka taşıma, vinç ve istifleme güvenliği"]),
    ("cam_seramik", "Cam, Seramik ve Taş Ürünleri", "Tehlikeli", ["Cam kırılması, keskin kenar ve göz yaralanmaları", "Fırın, sıcak ürün ve termal şok riskleri", "Silika, seramik tozu ve solunum korunması", "Pres, kesim, taşlama ve parça fırlaması riskleri", "Ağır plaka taşıma, vinç ve istifleme güvenliği"]),
    ("dagitim_kargo_kurye", "Dağıtım / Kargo / Kurye", "Tehlikeli", ["Motosiklet/bisiklet sürüşü ve trafik riskleri", "Hava koşulları, görünürlük ve kişisel koruyucular", "Paket taşıma, ergonomi ve düşme riskleri", "Müşteri alanı, saldırı ve yalnız çalışma", "Araç bakım kontrolü ve acil haberleşme"]),
    ("demir_celik_hadde", "Demir-Çelik / Hadde", "Tehlikeli", ["Ergimiş metal, cüruf ve sıcak yüzey sıçramaları", "Pota, vinç, kaldırma ve askı ekipmanı güvenliği", "Döküm dumanı, metal tozu, gaz ve havalandırma", "Isı stresi, yanıklar ve uygun KKD kullanımı", "Kalıp bozma, çapak alma ve sıkışma-ezilme riskleri"]),
    ("demiryolu", "Demiryolu, Metro ve Raylı Sistemler", "Tehlikeli", ["Hat üzerinde çalışma ve tren çarpması riski", "Katener, üçüncü ray ve yüksek gerilim", "Makas, bakım makinesi ve sıkışma riskleri", "Tünel, istasyon ve tahliye güvenliği", "Gece çalışması, işaretleme ve haberleşme"]),
    ("depo_lojistik", "Depo, Lojistik ve Dağıtım Merkezi", "Tehlikeli", ["Forklift, transpalet ve yaya trafiği güvenliği", "Raf sistemleri, istif ve yük düşmesi riskleri", "Yükleme rampası, dorse ve araç sabitleme", "Elle taşıma, kaldırma yardımcıları ve ergonomi", "Akü şarj alanı, yangın ve acil çıkış düzeni"]),
    ("depolama_lojistik_depo", "Depolama / Lojistik Depo", "Tehlikeli", ["Forklift, transpalet ve yaya trafiği güvenliği", "Raf sistemleri, istif ve yük düşmesi riskleri", "Yükleme rampası, dorse ve araç sabitleme", "Elle taşıma, kaldırma yardımcıları ve ergonomi", "Akü şarj alanı, yangın ve acil çıkış düzeni"]),
    ("dijital_baski_matbaa", "Dijital Baskı / Matbaa", "Tehlikeli", ["Kesim, baskı, sarım ve katlama makinelerinde kapılma", "Mürekkep, solvent ve temizlik kimyasallarıyla çalışma", "Kâğıt tozu, gürültü ve havalandırma", "Bobin, palet ve ağır malzeme taşıma güvenliği", "Yangın yükü, statik elektrik ve acil durumlar"]),
    ("diger_belirtilmemis", "Diğer / Belirtilmemiş", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("dogalgaz_enerji_dagitim", "Doğalgaz / Enerji Dağıtım", "Tehlikeli", ["Yanıcı gaz-sıvı sızıntısı ve patlayıcı ortamlar", "Hidrojen sülfür, toksik gaz ve gaz ölçümü", "Tank, reaktör ve kapalı alanda çalışma", "Dolum-boşaltım, statik elektrik ve topraklama", "Sıcak çalışma, yangın ve acil durdurma sistemleri"]),
    ("dokum_metal", "Döküm, Metal ve Metal Kaplama", "Çok Tehlikeli", ["Ergimiş metal, cüruf ve sıcak yüzey sıçramaları", "Pota, vinç, kaldırma ve askı ekipmanı güvenliği", "Döküm dumanı, metal tozu, gaz ve havalandırma", "Isı stresi, yanıklar ve uygun KKD kullanımı", "Kalıp bozma, çapak alma ve sıkışma-ezilme riskleri"]),
    ("e_ticaret_depo_fulfillment", "E-ticaret / Depo Fulfillment", "Tehlikeli", ["Forklift, transpalet ve yaya trafiği güvenliği", "Raf sistemleri, istif ve yük düşmesi riskleri", "Yükleme rampası, dorse ve araç sabitleme", "Elle taşıma, kaldırma yardımcıları ve ergonomi", "Akü şarj alanı, yangın ve acil çıkış düzeni"]),
    ("eczane_medikal_satis", "Eczane / Medikal Satış", "Tehlikeli", ["Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon", "Kesici-delici yaralanmaları ve tıbbi atıklar", "Hasta taşıma, ergonomi ve şiddet riski", "İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri", "Acil durum, tahliye ve güvenli sağlık hizmeti sunumu"]),
    ("elektrik_elektronik_uretim", "Elektrik / Elektronik Üretim", "Tehlikeli", ["Lehim dumanı, flux ve kimyasal maruziyet", "Elektrik, statik elektrik ve hassas ekipman güvenliği", "Otomatik montaj hatlarında sıkışma ve robot riski", "Ergonomi, tekrarlayan iş ve ekranlı çalışma", "Batarya, test cihazı ve yangın riskleri"]),
    ("elektrik_tesisat_pano_montaj", "Elektrik Tesisat / Pano Montaj", "Tehlikeli", ["Elektrik çarpması ve ark parlaması", "Enerji kesme, doğrulama, kilitleme ve etiketleme", "Pano, kablo ve tesisat çalışmalarında güvenlik", "İzole ekipman, ölçü aleti ve uygun KKD kullanımı", "Yetkisiz müdahale, çalışma izni ve acil kurtarma"]),
    ("elektrik_bakim", "Elektrik Tesisatı ve Bakım", "Çok Tehlikeli", ["Elektrik çarpması ve ark parlaması", "Enerji kesme, doğrulama, kilitleme ve etiketleme", "Pano, kablo ve tesisat çalışmalarında güvenlik", "İzole ekipman, ölçü aleti ve uygun KKD kullanımı", "Yetkisiz müdahale, çalışma izni ve acil kurtarma"]),
    ("elektronik_atik_bertaraf", "Elektronik Atık / Bertaraf", "Tehlikeli", ["Lehim dumanı, flux ve kimyasal maruziyet", "Elektrik, statik elektrik ve hassas ekipman güvenliği", "Otomatik montaj hatlarında sıkışma ve robot riski", "Ergonomi, tekrarlayan iş ve ekranlı çalışma", "Batarya, test cihazı ve yangın riskleri"]),
    ("elektronik", "Elektronik, Beyaz Eşya ve Montaj", "Tehlikeli", ["Lehim dumanı, flux ve kimyasal maruziyet", "Elektrik, statik elektrik ve hassas ekipman güvenliği", "Otomatik montaj hatlarında sıkışma ve robot riski", "Ergonomi, tekrarlayan iş ve ekranlı çalışma", "Batarya, test cihazı ve yangın riskleri"]),
    ("enerji_jenerator_trafo", "Enerji / Jeneratör / Trafo", "Tehlikeli", ["Yüksek gerilim, ark parlaması ve elektriksel izolasyon", "Türbin, jeneratör ve döner ekipman güvenliği", "Kazan, buhar, basınçlı sistem ve sıcak yüzeyler", "Bakımda kilitleme-etiketleme ve çalışma izinleri", "Yangın, kimyasal su şartlandırma ve acil durumlar"]),
    ("enerji_uretim", "Enerji Üretim Tesisleri", "Çok Tehlikeli", ["Yüksek gerilim, ark parlaması ve elektriksel izolasyon", "Türbin, jeneratör ve döner ekipman güvenliği", "Kazan, buhar, basınçlı sistem ve sıcak yüzeyler", "Bakımda kilitleme-etiketleme ve çalışma izinleri", "Yangın, kimyasal su şartlandırma ve acil durumlar"]),
    ("egitim_okul_kurs", "Eğitim / Okul / Kurs", "Tehlikeli", ["Öğrenci, çalışan ve ziyaretçi güvenliği", "Laboratuvar, atölye ve spor alanı riskleri", "Yangın, deprem, tahliye ve toplanma alanları", "Elektrik, merdiven ve kayma-düşme riskleri", "Şiddet, psikososyal risk ve acil iletişim"]),
    ("fabrika_genel_imalat", "Fabrika / Genel İmalat", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("firin_unlu_mamuller", "Fırın / Unlu Mamuller", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("gemi_insa_tersane", "Gemi İnşa / Tersane", "Tehlikeli", ["Konteyner, vinç ve askıda yük operasyonları", "Araç-yaya trafiği ve terminal kör noktaları", "Rıhtımdan/sudan düşme ve kurtarma", "Tehlikeli yük, yakıt ve kimyasal sızıntılar", "Gemi-kara geçişi, hava koşulları ve acil durumlar"]),
    ("genel_uretim", "Genel Fabrika ve Üretim", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("yenilenebilir_enerji", "Güneş ve Rüzgâr Enerjisi", "Tehlikeli", ["Rüzgâr türbininde yüksekte çalışma ve kurtarma", "Güneş paneli DC gerilimi ve ark riski", "Kanat, kule, inverter ve mekanik bakım güvenliği", "Olumsuz hava, yıldırım ve uzak saha çalışması", "Enerji depolama bataryaları ve yangın riskleri"]),
    ("guvenlik_hizmetleri", "Güvenlik Hizmetleri", "Tehlikeli", ["Şiddet, saldırı ve çatışma durumlarında güvenlik", "Devriye, yalnız çalışma ve haberleşme", "Yangın, tahliye ve kalabalık yönetimi", "Gece vardiyası, yorgunluk ve psikososyal riskler", "Şüpheli paket, acil olay ve kolluk koordinasyonu"]),
    ("guzellik_kuafor_spa", "Güzellik / Kuaför / Spa", "Tehlikeli", ["Bıçak, dilimleyici ve mutfak ekipmanları", "Kızgın yağ, buhar, fırın ve yanık riskleri", "LPG/doğalgaz, davlumbaz ve yangın güvenliği", "Kaygan zemin, temizlik kimyasalları ve hijyen", "Elle taşıma, ergonomi ve soğuk depo riskleri"]),
    ("gida_uretim", "Gıda ve İçecek Üretimi", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("gida_uretimi_isleme", "Gıda Üretimi / İşleme", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("haberlesme_telekomunikasyon", "Haberleşme / Telekomünikasyon", "Tehlikeli", ["Direk, kule ve çatıda yüksekte çalışma", "Elektrik, RF alanı ve enerji izolasyonu", "Saha trafiği, yol kenarı ve yalnız çalışma", "Fiber kablo, el aletleri ve göz yaralanmaları", "Olumsuz hava, erişim ve acil haberleşme"]),
    ("saglik", "Hastane, Klinik ve Sağlık Hizmetleri", "Tehlikeli", ["Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon", "Kesici-delici yaralanmaları ve tıbbi atıklar", "Hasta taşıma, ergonomi ve şiddet riski", "İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri", "Acil durum, tahliye ve güvenli sağlık hizmeti sunumu"]),
    ("havalimani_yer_hizmetleri", "Havalimanı / Yer Hizmetleri", "Tehlikeli", ["Konteyner, vinç ve askıda yük operasyonları", "Araç-yaya trafiği ve terminal kör noktaları", "Rıhtımdan/sudan düşme ve kurtarma", "Tehlikeli yük, yakıt ve kimyasal sızıntılar", "Gemi-kara geçişi, hava koşulları ve acil durumlar"]),
    ("havacilik", "Havalimanı ve Havacılık Yer Hizmetleri", "Tehlikeli", ["Apron araç trafiği ve uçak çevresi güvenliği", "Jet blast, pervane ve hareketli yüzey tehlikeleri", "Yakıt ikmali, yangın ve statik elektrik", "Bagaj, kargo ve ergonomik yükleme riskleri", "Gürültü, hava koşulları ve acil durum prosedürleri"]),
    ("hayvancilik_ciftlik", "Hayvancılık / Çiftlik", "Tehlikeli", ["Hayvan saldırısı, ezilme ve sıkışma riskleri", "Zoonozlar, biyolojik etkenler ve hijyen", "Gübre gazları, kapalı alan ve havalandırma", "Sağım, yemleme makineleri ve elektrik riskleri", "Ergonomi, kaygan zemin ve acil müdahale"]),
    ("hayvancilik", "Hayvancılık ve Hayvansal Üretim", "Tehlikeli", ["Hayvan saldırısı, ezilme ve sıkışma riskleri", "Zoonozlar, biyolojik etkenler ve hijyen", "Gübre gazları, kapalı alan ve havalandırma", "Sağım, yemleme makineleri ve elektrik riskleri", "Ergonomi, kaygan zemin ve acil müdahale"]),
    ("hazir_giyim_konfeksiyon", "Hazır Giyim / Konfeksiyon", "Tehlikeli", ["Dokuma, örme, eğirme ve sarım makinelerine kapılma", "Tekstil tozu, lif, boya ve kimyasal maruziyet", "Kesim, dikim, ütü ve sıcak yüzey riskleri", "Gürültü, ergonomi ve tekrarlayan hareketler", "Yangın yükü, acil çıkış ve istif güvenliği"]),
    ("hirdavat_yapi_market", "Hırdavat / Yapı Market", "Tehlikeli", ["Müşteri ve çalışan alanlarında kayma-düşme", "Raf, istif ve malzeme düşmesi riskleri", "Depo, palet, transpalet ve elle taşıma", "Soğuk depo, kesici ekipman ve temizlik kimyasalları", "Yangın, acil çıkış ve kalabalık tahliyesi"]),
    ("ilac_farmasotik_uretim", "İlaç / Farmasötik Üretim", "Tehlikeli", ["Farmasötik toz ve aktif madde maruziyeti", "Solvent, dezenfektan ve laboratuvar kimyasalları", "Karıştırıcı, tabletleme ve dolum makinelerinde güvenlik", "Temiz oda, biyolojik risk ve hijyen prosedürleri", "Basınçlı sistem, sterilizasyon ve acil durumlar"]),
    ("ilac_kozmetik", "İlaç, Kozmetik ve Medikal Üretim", "Tehlikeli", ["Farmasötik toz ve aktif madde maruziyeti", "Solvent, dezenfektan ve laboratuvar kimyasalları", "Karıştırıcı, tabletleme ve dolum makinelerinde güvenlik", "Temiz oda, biyolojik risk ve hijyen prosedürleri", "Basınçlı sistem, sterilizasyon ve acil durumlar"]),
    ("insaat_santiye", "İnşaat / Şantiye", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("insaat", "İnşaat ve Şantiye", "Çok Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("iskele_kalip_yapi_ekipmani", "İskele / Kalıp / Yapı Ekipmanı", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("ic_mimarlik_dekorasyon", "İç Mimarlık / Dekorasyon", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("is_makinesi_agir_ekipman", "İş Makinesi / Ağır Ekipman", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("kablo_tel_uretimi", "Kablo / Tel Üretimi", "Tehlikeli", ["Lehim dumanı, flux ve kimyasal maruziyet", "Elektrik, statik elektrik ve hassas ekipman güvenliği", "Otomatik montaj hatlarında sıkışma ve robot riski", "Ergonomi, tekrarlayan iş ve ekranlı çalışma", "Batarya, test cihazı ve yangın riskleri"]),
    ("kamu_kurumu_idare", "Kamu Kurumu / İdare", "Tehlikeli", ["Saha, yol, park-bahçe ve trafik altında çalışma", "Atık toplama, biyolojik risk ve kesici-delici atıklar", "Kazı, altyapı, kanalizasyon ve kapalı alanlar", "İş makineleri, araçlar ve yaya güvenliği", "Halka açık alanlarda acil durum ve şiddet riski"]),
    ("karayolu_tasimacilik", "Karayolu Taşımacılığı ve Filo", "Tehlikeli", ["Güvenli sürüş, hız ve takip mesafesi", "Sürücü yorgunluğu, vardiya ve dikkat dağınıklığı", "Yük sabitleme, yükleme-boşaltma ve dorse güvenliği", "Araç bakımında kriko, lastik ve yol kenarı riskleri", "Trafik kazası, yangın ve acil durum prosedürleri"]),
    ("kaynakli_imalat", "Kaynaklı İmalat", "Çok Tehlikeli", ["Kaynak ışını, göz-yüz koruması ve sıcak metal sıçraması", "Kaynak dumanı, gazlar ve lokal havalandırma", "Sıcak çalışma izni, kıvılcım kontrolü ve yangın gözcülüğü", "Basınçlı gaz tüpleri, regülatör ve hortum güvenliği", "Kapalı alanda kaynak, gaz ölçümü ve kurtarma planı"]),
    ("kagit_karton_uretimi", "Kağıt / Karton Üretimi", "Tehlikeli", ["Kesim, baskı, sarım ve katlama makinelerinde kapılma", "Mürekkep, solvent ve temizlik kimyasallarıyla çalışma", "Kâğıt tozu, gürültü ve havalandırma", "Bobin, palet ve ağır malzeme taşıma güvenliği", "Yangın yükü, statik elektrik ve acil durumlar"]),
    ("kimya_kimyasal_uretim", "Kimya / Kimyasal Üretim", "Tehlikeli", ["Kimyasal etiketler, SDS ve maruziyet yolları", "Solvent, izosiyanat, aerosol ve toksik buhar maruziyeti", "Yanıcı atmosfer, statik elektrik ve ex-proof ekipman", "Uyumsuz kimyasalların güvenli depolanması ve transferi", "Dökülme, sızıntı, acil duş ve müdahale prosedürleri"]),
    ("kimyasal_boya", "Kimya, Boya ve Kaplama", "Çok Tehlikeli", ["Kimyasal etiketler, SDS ve maruziyet yolları", "Solvent, izosiyanat, aerosol ve toksik buhar maruziyeti", "Yanıcı atmosfer, statik elektrik ve ex-proof ekipman", "Uyumsuz kimyasalların güvenli depolanması ve transferi", "Dökülme, sızıntı, acil duş ve müdahale prosedürleri"]),
    ("konaklama_otel_pansiyon", "Konaklama / Otel / Pansiyon", "Tehlikeli", ["Mutfak, çamaşırhane, teknik servis ve sıcak yüzeyler", "Havuz kimyasalları ve biyolojik riskler", "Kat hizmetleri, ergonomi ve kayma-düşme", "Misafir güvenliği, şiddet ve gece vardiyası", "Yangın, kat tahliyesi ve acil durum yönetimi"]),
    ("kozmetik_temizlik_urunleri", "Kozmetik / Temizlik Ürünleri", "Tehlikeli", ["Farmasötik toz ve aktif madde maruziyeti", "Solvent, dezenfektan ve laboratuvar kimyasalları", "Karıştırıcı, tabletleme ve dolum makinelerinde güvenlik", "Temiz oda, biyolojik risk ve hijyen prosedürleri", "Basınçlı sistem, sterilizasyon ve acil durumlar"]),
    ("kurye", "Kurye, Kargo ve Saha Dağıtımı", "Tehlikeli", ["Motosiklet/bisiklet sürüşü ve trafik riskleri", "Hava koşulları, görünürlük ve kişisel koruyucular", "Paket taşıma, ergonomi ve düşme riskleri", "Müşteri alanı, saldırı ve yalnız çalışma", "Araç bakım kontrolü ve acil haberleşme"]),
    ("kuyumculuk_mucevher", "Kuyumculuk / Mücevher", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),
    ("kagit_matbaa", "Kâğıt, Ambalaj ve Matbaa", "Tehlikeli", ["Kesim, baskı, sarım ve katlama makinelerinde kapılma", "Mürekkep, solvent ve temizlik kimyasallarıyla çalışma", "Kâğıt tozu, gürültü ve havalandırma", "Bobin, palet ve ağır malzeme taşıma güvenliği", "Yangın yükü, statik elektrik ve acil durumlar"]),
    ("laboratuvar_analiz", "Laboratuvar / Analiz", "Tehlikeli", ["Asit-baz, solvent ve reaktif kimyasal güvenliği", "Çeker ocak, havalandırma ve maruziyet kontrolü", "Basınçlı gaz tüpleri ve kriyojenik sıvılar", "Cam malzeme, kesici-delici ve biyolojik riskler", "Kimyasal atık, dökülme ve acil duş-göz duşu"]),
    ("laboratuvar", "Laboratuvar ve Araştırma Merkezi", "Tehlikeli", ["Asit-baz, solvent ve reaktif kimyasal güvenliği", "Çeker ocak, havalandırma ve maruziyet kontrolü", "Basınçlı gaz tüpleri ve kriyojenik sıvılar", "Cam malzeme, kesici-delici ve biyolojik riskler", "Kimyasal atık, dökülme ve acil duş-göz duşu"]),
    ("lastik_kaucuk", "Lastik / Kauçuk", "Çok Tehlikeli", ["Enjeksiyon, ekstrüzyon ve pres makinelerinde sıkışma", "Sıcak kalıp, eriyik polimer ve yanık riskleri", "Hammadde tozu, katkı maddesi ve kimyasal maruziyet", "Granül besleme, kırma ve konveyör sistemleri güvenliği", "Yangın yükü, duman ve uygun söndürme yöntemleri"]),
    ("liman", "Liman, Terminal ve Konteyner Operasyonları", "Tehlikeli", ["Konteyner, vinç ve askıda yük operasyonları", "Araç-yaya trafiği ve terminal kör noktaları", "Rıhtımdan/sudan düşme ve kurtarma", "Tehlikeli yük, yakıt ve kimyasal sızıntılar", "Gemi-kara geçişi, hava koşulları ve acil durumlar"]),
    ("madencilik_maden_ocagi", "Madencilik / Maden Ocağı", "Tehlikeli", ["Şev, kademe, kaya düşmesi ve heyelan riskleri", "Patlatma operasyonu ve emniyet mesafeleri", "Kırma-eleme, konveyör ve sıkışma riskleri", "Toz, silika, gürültü ve titreşim maruziyeti", "Ocak içi trafik, iş makineleri ve kör noktalar"]),
    ("makine_imalati", "Makine İmalatı", "Tehlikeli", ["Makine koruyucuları, emniyet tertibatları ve acil durdurma", "Kesilme, sıkışma, ezilme ve parça fırlaması riskleri", "Bakım ve ayarda enerji izolasyonu ile kilitleme-etiketleme", "Taşlama, kesme, matkap ve el aletleriyle güvenli çalışma", "Montaj, kaldırma-taşıma ve ergonomik zorlanmalar"]),
    ("makine_imalat", "Makine İmalatı ve Montaj", "Tehlikeli", ["Makine koruyucuları, emniyet tertibatları ve acil durdurma", "Kesilme, sıkışma, ezilme ve parça fırlaması riskleri", "Bakım ve ayarda enerji izolasyonu ile kilitleme-etiketleme", "Taşlama, kesme, matkap ve el aletleriyle güvenli çalışma", "Montaj, kaldırma-taşıma ve ergonomik zorlanmalar"]),
    ("market_perakende", "Market / Perakende", "Tehlikeli", ["Müşteri ve çalışan alanlarında kayma-düşme", "Raf, istif ve malzeme düşmesi riskleri", "Depo, palet, transpalet ve elle taşıma", "Soğuk depo, kesici ekipman ve temizlik kimyasalları", "Yangın, acil çıkış ve kalabalık tahliyesi"]),
    ("metal_isleme_torna_freze", "Metal İşleme / Torna-Freze", "Tehlikeli", ["Makine koruyucuları, emniyet tertibatları ve acil durdurma", "Kesilme, sıkışma, ezilme ve parça fırlaması riskleri", "Bakım ve ayarda enerji izolasyonu ile kilitleme-etiketleme", "Taşlama, kesme, matkap ve el aletleriyle güvenli çalışma", "Montaj, kaldırma-taşıma ve ergonomik zorlanmalar"]),
    ("mobilya_ev_tekstili", "Mobilya / Ev Tekstili", "Tehlikeli", ["Testere, freze, planya ve CNC makinelerinde kesilme-kapılma", "Ahşap tozu maruziyeti, emiş sistemi ve toz patlaması", "Vernik, boya, tiner ve yapıştırıcılarla güvenli çalışma", "Zımpara, pres, çivi tabancası ve el aleti güvenliği", "Talaş-atık yönetimi, yangın önleme ve düzenli temizlik"]),
    ("muhendislik_proje_ofisi", "Mühendislik / Proje Ofisi", "Tehlikeli", ["Ekranlı araçlar, oturma düzeni ve ergonomi", "Elektrikli ofis ekipmanlarının güvenli kullanımı", "Yangın, tahliye ve toplanma alanı uygulamaları", "Kayma, takılma, düşme ve düzen riskleri", "Psikososyal riskler, iş yükü ve stres yönetimi"]),
    ("muteahhitlik_taahhut", "Müteahhitlik / Taahhüt", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("nakliye_karayolu_tasimaciligi", "Nakliye / Karayolu Taşımacılığı", "Tehlikeli", ["Trafik altında çalışma ve geçici trafik işaretlemesi", "Sıcak asfalt, bitüm sıçraması ve ısı stresi", "Finişer, silindir, freze ve iş makineleri güvenliği", "Bitüm dumanı, silika/toz ve gürültü maruziyeti", "Gece çalışması, görünürlük ve acil kaçış düzeni"]),
    ("ofis_idari_hizmetler", "Ofis / İdari Hizmetler", "Tehlikeli", ["Ekranlı araçlar, oturma düzeni ve ergonomi", "Elektrikli ofis ekipmanlarının güvenli kullanımı", "Yangın, tahliye ve toplanma alanı uygulamaları", "Kayma, takılma, düşme ve düzen riskleri", "Psikososyal riskler, iş yükü ve stres yönetimi"]),
    ("ofis", "Ofis ve İdari İşler", "Az Tehlikeli", ["Ekranlı araçlar, oturma düzeni ve ergonomi", "Elektrikli ofis ekipmanlarının güvenli kullanımı", "Yangın, tahliye ve toplanma alanı uygulamaları", "Kayma, takılma, düşme ve düzen riskleri", "Psikososyal riskler, iş yükü ve stres yönetimi"]),
    ("egitim_kurumu", "Okul, Kurs ve Eğitim Kurumu", "Tehlikeli", ["Öğrenci, çalışan ve ziyaretçi güvenliği", "Laboratuvar, atölye ve spor alanı riskleri", "Yangın, deprem, tahliye ve toplanma alanları", "Elektrik, merdiven ve kayma-düşme riskleri", "Şiddet, psikososyal risk ve acil iletişim"]),
    ("organizasyon_etkinlik", "Organizasyon / Etkinlik", "Tehlikeli", ["Ekranlı araçlar, oturma düzeni ve ergonomi", "Elektrikli ofis ekipmanlarının güvenli kullanımı", "Yangın, tahliye ve toplanma alanı uygulamaları", "Kayma, takılma, düşme ve düzen riskleri", "Psikososyal riskler, iş yükü ve stres yönetimi"]),
    ("ormancilik_kereste", "Ormancılık / Kereste", "Tehlikeli", ["Motorlu testere, kesim ve ağaç devrilme yönü", "Arazi, eğim, kaya ve düşme riskleri", "Traktör, sürütme ve orman araçları güvenliği", "Yangın, sıcaklık, böcek ve biyolojik riskler", "Uzak saha, haberleşme, ilk yardım ve kurtarma"]),
    ("ormancilik", "Ormancılık ve Ağaç Kesim İşleri", "Tehlikeli", ["Motorlu testere, kesim ve ağaç devrilme yönü", "Arazi, eğim, kaya ve düşme riskleri", "Traktör, sürütme ve orman araçları güvenliği", "Yangın, sıcaklık, böcek ve biyolojik riskler", "Uzak saha, haberleşme, ilk yardım ve kurtarma"]),
    ("turizm", "Otel, Konaklama ve Turizm", "Tehlikeli", ["Mutfak, çamaşırhane, teknik servis ve sıcak yüzeyler", "Havuz kimyasalları ve biyolojik riskler", "Kat hizmetleri, ergonomi ve kayma-düşme", "Misafir güvenliği, şiddet ve gece vardiyası", "Yangın, kat tahliyesi ve acil durum yönetimi"]),
    ("oto_lastik_servis", "Oto Lastik / Servis", "Tehlikeli", ["Pres, robotlu hücre ve hareketli hatlarda sıkışma riskleri", "Araç lifti, kriko ve bakım çukuru güvenliği", "Boya, solvent, kaynak dumanı ve kimyasal maruziyet", "Akü sökme-takma ve elektrikli araç yüksek gerilim riskleri", "Trafik, test sürüşü ve ergonomik montaj riskleri"]),
    ("otogaz_lpg_bayi", "Otogaz / LPG Bayi", "Tehlikeli", ["Yanıcı gaz-sıvı sızıntısı ve patlayıcı ortamlar", "Hidrojen sülfür, toksik gaz ve gaz ölçümü", "Tank, reaktör ve kapalı alanda çalışma", "Dolum-boşaltım, statik elektrik ve topraklama", "Sıcak çalışma, yangın ve acil durdurma sistemleri"]),
    ("otomotiv_yedek_parca", "Otomotiv / Yedek Parça", "Tehlikeli", ["Pres, robotlu hücre ve hareketli hatlarda sıkışma riskleri", "Araç lifti, kriko ve bakım çukuru güvenliği", "Boya, solvent, kaynak dumanı ve kimyasal maruziyet", "Akü sökme-takma ve elektrikli araç yüksek gerilim riskleri", "Trafik, test sürüşü ve ergonomik montaj riskleri"]),
    ("otomotiv_servis_bakim", "Otomotiv Servis / Bakım", "Tehlikeli", ["Pres, robotlu hücre ve hareketli hatlarda sıkışma riskleri", "Araç lifti, kriko ve bakım çukuru güvenliği", "Boya, solvent, kaynak dumanı ve kimyasal maruziyet", "Akü sökme-takma ve elektrikli araç yüksek gerilim riskleri", "Trafik, test sürüşü ve ergonomik montaj riskleri"]),
    ("otomotiv", "Otomotiv Üretimi ve Servis", "Tehlikeli", ["Pres, robotlu hücre ve hareketli hatlarda sıkışma riskleri", "Araç lifti, kriko ve bakım çukuru güvenliği", "Boya, solvent, kaynak dumanı ve kimyasal maruziyet", "Akü sökme-takma ve elektrikli araç yüksek gerilim riskleri", "Trafik, test sürüşü ve ergonomik montaj riskleri"]),
    ("patlayici", "Patlayıcı, Mühimmat ve Piroteknik", "Tehlikeli", ["Patlayıcı maddelerin özellikleri ve uyumsuzlukları", "Statik elektrik, kıvılcım ve ateşleme kaynaklarının kontrolü", "Üretim, dolum ve taşıma sırasında miktar-mesafe kuralları", "Patlayıcı depo, güvenlik mesafesi ve yıldırımdan korunma", "Acil durum, tahliye ve patlama sonrası müdahale"]),
    ("perakende", "Perakende, Market ve Mağazacılık", "Tehlikeli", ["Müşteri ve çalışan alanlarında kayma-düşme", "Raf, istif ve malzeme düşmesi riskleri", "Depo, palet, transpalet ve elle taşıma", "Soğuk depo, kesici ekipman ve temizlik kimyasalları", "Yangın, acil çıkış ve kalabalık tahliyesi"]),
    ("petrol_rafineri_depolama", "Petrol / Rafineri / Depolama", "Tehlikeli", ["Yanıcı gaz-sıvı sızıntısı ve patlayıcı ortamlar", "Hidrojen sülfür, toksik gaz ve gaz ölçümü", "Tank, reaktör ve kapalı alanda çalışma", "Dolum-boşaltım, statik elektrik ve topraklama", "Sıcak çalışma, yangın ve acil durdurma sistemleri"]),
    ("petrol_dogalgaz", "Petrol, Doğalgaz ve Rafineri", "Çok Tehlikeli", ["Yanıcı gaz-sıvı sızıntısı ve patlayıcı ortamlar", "Hidrojen sülfür, toksik gaz ve gaz ölçümü", "Tank, reaktör ve kapalı alanda çalışma", "Dolum-boşaltım, statik elektrik ve topraklama", "Sıcak çalışma, yangın ve acil durdurma sistemleri"]),
    ("plastik_enjeksiyon_ekstruzyon", "Plastik / Enjeksiyon / Ekstrüzyon", "Tehlikeli", ["Enjeksiyon, ekstrüzyon ve pres makinelerinde sıkışma", "Sıcak kalıp, eriyik polimer ve yanık riskleri", "Hammadde tozu, katkı maddesi ve kimyasal maruziyet", "Granül besleme, kırma ve konveyör sistemleri güvenliği", "Yangın yükü, duman ve uygun söndürme yöntemleri"]),
    ("plastik_kaucuk", "Plastik ve Kauçuk Ürünleri", "Tehlikeli", ["Enjeksiyon, ekstrüzyon ve pres makinelerinde sıkışma", "Sıcak kalıp, eriyik polimer ve yanık riskleri", "Hammadde tozu, katkı maddesi ve kimyasal maruziyet", "Granül besleme, kırma ve konveyör sistemleri güvenliği", "Yangın yükü, duman ve uygun söndürme yöntemleri"]),
    ("reklam_tabela_baski", "Reklam / Tabela / Baskı", "Tehlikeli", ["Kesim, baskı, sarım ve katlama makinelerinde kapılma", "Mürekkep, solvent ve temizlik kimyasallarıyla çalışma", "Kâğıt tozu, gürültü ve havalandırma", "Bobin, palet ve ağır malzeme taşıma güvenliği", "Yangın yükü, statik elektrik ve acil durumlar"]),
    ("restoran_cafe_mutfak", "Restoran / Cafe / Mutfak", "Tehlikeli", ["Bıçak, dilimleyici ve mutfak ekipmanları", "Kızgın yağ, buhar, fırın ve yanık riskleri", "LPG/doğalgaz, davlumbaz ve yangın güvenliği", "Kaygan zemin, temizlik kimyasalları ve hijyen", "Elle taşıma, ergonomi ve soğuk depo riskleri"]),
    ("restoran", "Restoran, Mutfak ve Toplu Yemek", "Tehlikeli", ["Bıçak, dilimleyici ve mutfak ekipmanları", "Kızgın yağ, buhar, fırın ve yanık riskleri", "LPG/doğalgaz, davlumbaz ve yangın güvenliği", "Kaygan zemin, temizlik kimyasalları ve hijyen", "Elle taşıma, ergonomi ve soğuk depo riskleri"]),
    ("saglik_hastane_klinik", "Sağlık / Hastane / Klinik", "Tehlikeli", ["Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon", "Kesici-delici yaralanmaları ve tıbbi atıklar", "Hasta taşıma, ergonomi ve şiddet riski", "İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri", "Acil durum, tahliye ve güvenli sağlık hizmeti sunumu"]),
    ("seramik_fayans", "Seramik / Fayans", "Tehlikeli", ["Cam kırılması, keskin kenar ve göz yaralanmaları", "Fırın, sıcak ürün ve termal şok riskleri", "Silika, seramik tozu ve solunum korunması", "Pres, kesim, taşlama ve parça fırlaması riskleri", "Ağır plaka taşıma, vinç ve istifleme güvenliği"]),
    ("sigorta_broker", "Sigorta / Broker", "Tehlikeli", ["Ekranlı çalışma, ergonomi ve hareketsizlik", "İş stresi, müşteri baskısı ve psikososyal riskler", "Elektrik, yangın ve acil tahliye", "Güvenlik, saldırı ve nakit işlem riskleri", "Arşiv, depo ve kayma-takılma riskleri"]),
    ("soguk_hava_deposu", "Soğuk Hava Deposu", "Tehlikeli", ["Forklift, transpalet ve yaya trafiği güvenliği", "Raf sistemleri, istif ve yük düşmesi riskleri", "Yükleme rampası, dorse ve araç sabitleme", "Elle taşıma, kaldırma yardımcıları ve ergonomi", "Akü şarj alanı, yangın ve acil çıkış düzeni"]),
    ("spor_tesisi_fitness", "Spor Tesisi / Fitness", "Tehlikeli", ["Mutfak, çamaşırhane, teknik servis ve sıcak yüzeyler", "Havuz kimyasalları ve biyolojik riskler", "Kat hizmetleri, ergonomi ve kayma-düşme", "Misafir güvenliği, şiddet ve gece vardiyası", "Yangın, kat tahliyesi ve acil durum yönetimi"]),
    ("su_atiksu", "Su, Atıksu ve Arıtma Tesisleri", "Tehlikeli", ["Kanalizasyon gazları, oksijen yetersizliği ve kapalı alan", "Biyolojik etkenler, sıçrama ve hijyen", "Klor, ozon, asit-baz ve kimyasal dozlama", "Havuz, tank, düşme ve boğulma riskleri", "Pompa, elektrik, bakım ve enerji izolasyonu"]),
    ("sut_sut_urunleri", "Süt / Süt Ürünleri", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("tarim_ziraat", "Tarım / Ziraat", "Tehlikeli", ["Traktör ve tarım makinelerinde devrilme-kapılma", "Pestisit, gübre ve kimyasal maruziyet", "Sıcaklık, güneş, biyolojik etken ve hayvan teması", "Sera, yüksekte çalışma ve elektrik riskleri", "Elle taşıma, ergonomi ve uzak saha acil durumları"]),
    ("tarim", "Tarım, Sera ve Bitkisel Üretim", "Tehlikeli", ["Traktör ve tarım makinelerinde devrilme-kapılma", "Pestisit, gübre ve kimyasal maruziyet", "Sıcaklık, güneş, biyolojik etken ve hayvan teması", "Sera, yüksekte çalışma ve elektrik riskleri", "Elle taşıma, ergonomi ve uzak saha acil durumları"]),
    ("tas_ocagi_maden_ocagi", "Taş Ocağı / Maden Ocağı", "Tehlikeli", ["Şev, kademe, kaya düşmesi ve heyelan riskleri", "Patlatma operasyonu ve emniyet mesafeleri", "Kırma-eleme, konveyör ve sıkışma riskleri", "Toz, silika, gürültü ve titreşim maruziyeti", "Ocak içi trafik, iş makineleri ve kör noktalar"]),
    ("tekstil_dokuma_boyama", "Tekstil / Dokuma / Boyama", "Tehlikeli", ["Ergimiş metal, cüruf ve sıcak yüzey sıçramaları", "Pota, vinç, kaldırma ve askı ekipmanı güvenliği", "Döküm dumanı, metal tozu, gaz ve havalandırma", "Isı stresi, yanıklar ve uygun KKD kullanımı", "Kalıp bozma, çapak alma ve sıkışma-ezilme riskleri"]),
    ("tekstil", "Tekstil ve Konfeksiyon", "Tehlikeli", ["Dokuma, örme, eğirme ve sarım makinelerine kapılma", "Tekstil tozu, lif, boya ve kimyasal maruziyet", "Kesim, dikim, ütü ve sıcak yüzey riskleri", "Gürültü, ergonomi ve tekrarlayan hareketler", "Yangın yükü, acil çıkış ve istif güvenliği"]),
    ("telekomunikasyon_altyapi", "Telekomünikasyon Altyapı", "Tehlikeli", ["Direk, kule ve çatıda yüksekte çalışma", "Elektrik, RF alanı ve enerji izolasyonu", "Saha trafiği, yol kenarı ve yalnız çalışma", "Fiber kablo, el aletleri ve göz yaralanmaları", "Olumsuz hava, erişim ve acil haberleşme"]),
    ("telekom", "Telekomünikasyon ve Saha Çalışmaları", "Çok Tehlikeli", ["Direk, kule ve çatıda yüksekte çalışma", "Elektrik, RF alanı ve enerji izolasyonu", "Saha trafiği, yol kenarı ve yalnız çalışma", "Fiber kablo, el aletleri ve göz yaralanmaları", "Olumsuz hava, erişim ve acil haberleşme"]),
    ("temizlik_facility_management", "Temizlik / Facility Management", "Tehlikeli", ["Temizlik kimyasalları, etiket ve güvenli seyreltme", "Islak zemin, kayma ve düşme riskleri", "Biyolojik riskler, atıklar ve hijyen", "Yüksek alan temizliği ve merdiven güvenliği", "Kesici-delici atıklar, ergonomi ve KKD"]),
    ("temizlik", "Temizlik ve Tesis Hizmetleri", "Tehlikeli", ["Temizlik kimyasalları, etiket ve güvenli seyreltme", "Islak zemin, kayma ve düşme riskleri", "Biyolojik riskler, atıklar ve hijyen", "Yüksek alan temizliği ve merdiven güvenliği", "Kesici-delici atıklar, ergonomi ve KKD"]),
    ("tersane_liman_hizmetleri", "Tersane / Liman Hizmetleri", "Tehlikeli", ["Konteyner, vinç ve askıda yük operasyonları", "Araç-yaya trafiği ve terminal kör noktaları", "Rıhtımdan/sudan düşme ve kurtarma", "Tehlikeli yük, yakıt ve kimyasal sızıntılar", "Gemi-kara geçişi, hava koşulları ve acil durumlar"]),
    ("tersane", "Tersane, Gemi İnşa ve Onarım", "Tehlikeli", ["Kapalı alan, gaz ölçümü ve tank çalışmaları", "Sıcak işler, kaynak, boya ve yangın riski", "Blok kaldırma, vinç ve askıda yük güvenliği", "İskele, gemi bordası ve yüksekte çalışma", "Basınçlı gaz, elektrik ve tahliye-kurtarma"]),
    ("toplu_tasima_ulasim", "Toplu Taşıma / Ulaşım", "Tehlikeli", ["Güvenli sürüş, hız ve takip mesafesi", "Sürücü yorgunluğu, vardiya ve dikkat dağınıklığı", "Yük sabitleme, yükleme-boşaltma ve dorse güvenliği", "Araç bakımında kriko, lastik ve yol kenarı riskleri", "Trafik kazası, yangın ve acil durum prosedürleri"]),
    ("turizm_seyahat", "Turizm / Seyahat", "Az Tehlikeli", ["Mutfak, çamaşırhane, teknik servis ve sıcak yüzeyler", "Havuz kimyasalları ve biyolojik riskler", "Kat hizmetleri, ergonomi ve kayma-düşme", "Misafir güvenliği, şiddet ve gece vardiyası", "Yangın, kat tahliyesi ve acil durum yönetimi"]),
    ("tip_dis_klinigi", "Tıp / Diş Kliniği", "Tehlikeli", ["Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon", "Kesici-delici yaralanmaları ve tıbbi atıklar", "Hasta taşıma, ergonomi ve şiddet riski", "İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri", "Acil durum, tahliye ve güvenli sağlık hizmeti sunumu"]),
    ("yapi_malzemeleri_uretimi", "Yapı Malzemeleri Üretimi", "Tehlikeli", ["Çimento ve silika tozu maruziyeti", "Konveyör, kırıcı, mikser ve döner ekipmana kapılma", "Beton pompası, hortum savrulması ve basınç riskleri", "Mobil ekipman, saha trafiği ve kör noktalar", "Kimyasal katkı, alkalin yanık ve temizlik işlemleri"]),
    ("yemek_uretimi_catering", "Yemek Üretimi / Catering", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("yenilenebilir_enerji_gunes_ruzgar", "Yenilenebilir Enerji / Güneş-Rüzgar", "Tehlikeli", ["Yüksek gerilim, ark parlaması ve elektriksel izolasyon", "Türbin, jeneratör ve döner ekipman güvenliği", "Kazan, buhar, basınçlı sistem ve sıcak yüzeyler", "Bakımda kilitleme-etiketleme ve çalışma izinleri", "Yangın, kimyasal su şartlandırma ve acil durumlar"]),
    ("kapali_maden", "Yeraltı Madenciliği", "Tehlikeli", ["Grizu, metan ve patlayıcı ortam kontrolü", "Göçük, tahkimat ve yeraltı kazı güvenliği", "Havalandırma, gaz ölçümü ve oksijen yetersizliği", "Yeraltı nakliyatı, makine ve elektrik riskleri", "Kaçış, kurtarma, öz kurtarıcı ve acil durum planı"]),
    ("yiyecek_icecek_uretimi", "Yiyecek-İçecek Üretimi", "Tehlikeli", ["Kesici, kıyıcı, karıştırıcı ve konveyör makinelerinde güvenlik", "Sıcak proses, buhar, kızgın yağ ve yanık riskleri", "Soğuk depo, amonyak/CO2 kaçağı ve termal riskler", "Temizlik kimyasalları, CIP ve kaygan zemin riskleri", "Biyolojik etkenler, hijyen ve ergonomik taşıma riskleri"]),
    ("yol_altyapi_insaati", "Yol / Altyapı İnşaatı", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("yol_asfalt", "Yol, Asfalt ve Altyapı", "Çok Tehlikeli", ["Trafik altında çalışma ve geçici trafik işaretlemesi", "Sıcak asfalt, bitüm sıçraması ve ısı stresi", "Finişer, silindir, freze ve iş makineleri güvenliği", "Bitüm dumanı, silika/toz ve gürültü maruziyeti", "Gece çalışması, görünürlük ve acil kaçış düzeni"]),
    ("yuksekte_calisma_cephe", "Yüksekte Çalışma / Cephe", "Tehlikeli", ["Yüksekte çalışma, düşmeyi önleme ve kurtarma", "İskele, merdiven, platform ve kenar koruma güvenliği", "Kazı, iksa, göçük ve yeraltı hatları", "Vinç, kaldırma ekipmanı ve düşen cisim riskleri", "Şantiye içi trafik, iş makineleri ve geçici elektrik"]),
    ("cagri_merkezi_contact_center", "Çağrı Merkezi / Contact Center", "Tehlikeli", ["Ekranlı çalışma, ergonomi ve hareketsizlik", "İş stresi, müşteri baskısı ve psikososyal riskler", "Elektrik, yangın ve acil tahliye", "Güvenlik, saldırı ve nakit işlem riskleri", "Arşiv, depo ve kayma-takılma riskleri"]),
    ("celik_yapi_metal_konstruksiyon", "Çelik Yapı / Metal Konstrüksiyon", "Tehlikeli", ["Kaynak ışını, göz-yüz koruması ve sıcak metal sıçraması", "Kaynak dumanı, gazlar ve lokal havalandırma", "Sıcak çalışma izni, kıvılcım kontrolü ve yangın gözcülüğü", "Basınçlı gaz tüpleri, regülatör ve hortum güvenliği", "Kapalı alanda kaynak, gaz ölçümü ve kurtarma planı"]),
    ("cimento_klinker", "Çimento / Klinker", "Tehlikeli", ["Çimento ve silika tozu maruziyeti", "Konveyör, kırıcı, mikser ve döner ekipmana kapılma", "Beton pompası, hortum savrulması ve basınç riskleri", "Mobil ekipman, saha trafiği ve kör noktalar", "Kimyasal katkı, alkalin yanık ve temizlik işlemleri"]),
    ("cimento_beton", "Çimento, Beton ve Prefabrik", "Çok Tehlikeli", ["Çimento ve silika tozu maruziyeti", "Konveyör, kırıcı, mikser ve döner ekipmana kapılma", "Beton pompası, hortum savrulması ve basınç riskleri", "Mobil ekipman, saha trafiği ve kör noktalar", "Kimyasal katkı, alkalin yanık ve temizlik işlemleri"]),
    ("ozel_guvenlik", "Özel Güvenlik", "Tehlikeli", ["Şiddet, saldırı ve çatışma durumlarında güvenlik", "Devriye, yalnız çalışma ve haberleşme", "Yangın, tahliye ve kalabalık yönetimi", "Gece vardiyası, yorgunluk ve psikososyal riskler", "Şüpheli paket, acil olay ve kolluk koordinasyonu"]),
    ("guvenlik", "Özel Güvenlik Hizmetleri", "Tehlikeli", ["Şiddet, saldırı ve çatışma durumlarında güvenlik", "Devriye, yalnız çalışma ve haberleşme", "Yangın, tahliye ve kalabalık yönetimi", "Gece vardiyası, yorgunluk ve psikososyal riskler", "Şüpheli paket, acil olay ve kolluk koordinasyonu"]),
    ("universite_yuksekogretim", "Üniversite / Yükseköğretim", "Tehlikeli", ["Öğrenci, çalışan ve ziyaretçi güvenliği", "Laboratuvar, atölye ve spor alanı riskleri", "Yangın, deprem, tahliye ve toplanma alanları", "Elektrik, merdiven ve kayma-düşme riskleri", "Şiddet, psikososyal risk ve acil iletişim"]),
    ("uretim_imalathane_genel", "Üretim / İmalathane (Genel)", "Tehlikeli", ["Makine ve ekipmanlarla güvenli çalışma", "İşyeri içi araç-yaya trafiği ve kör noktalar", "Elle taşıma, ergonomi ve güvenli istifleme", "Yangın, acil durum ve tahliye uygulamaları", "KKD kullanımı, bakım güvenliği ve işyeri düzeni"]),

    # --- legacy Suite kodlari (mevcut kayitlar icin) ---
    ('agac_ormancilik', 'Ağaç İşleri / Ormancılık', 'Tehlikeli', ['Kesici makineler', 'Zincirli testere', 'Devrilen ağaç riski', 'Toz ve gürültü', 'KKD kullanımı']),
    ('asansor_montaj', 'Asansör / Montaj-Bakım', 'Çok Tehlikeli', ['Yüksekte çalışma', 'Kuyu ve makine dairesi', 'Elektrik enerjisi', 'Kaldırma ekipmanı', 'Kilitleme-etiketleme']),
    ('avcilik_balikcilik', 'Avcılık / Balıkçılık', 'Tehlikeli', ['Deniz/göl çalışma', 'Soğuk ve kaygan zemin', 'Kesici aletler', 'Kimyasal koruma', 'Acil kurtarma']),
    ('bakim_onarim', 'Bakım Onarım Atölyesi', 'Tehlikeli', ['Kilitleme/etiketleme', 'El aletleri', 'Kaynak ve sıcak iş', 'Sıkışma-ezilme', 'Atık yağ/kimyasal']),
    ('berber_kuafor', 'Berber / Kuaför', 'Az Tehlikeli', ['Kimyasal boya/solüsyon', 'Kesici aletler', 'Ergonomi', 'Hijyen', 'Elektrikli ekipman']),
    ('boya_kaplama', 'Boya / Kaplama / Galvaniz', 'Çok Tehlikeli', ['Solvent buharı', 'Parlama-patlama', 'SDS okuma', 'Depolama uyumsuzluğu', 'Dökülme müdahalesi']),
    ('cati_isleri', 'Çatı İşleri', 'Çok Tehlikeli', ['Düşme önleme', 'İskele/platform', 'Hava koşulları', 'Malzeme düşmesi', 'Elektrik hattı mesafesi']),
    ('demir_celik', 'Demir-Çelik / Hadde', 'Çok Tehlikeli', ['Sıcak metal', 'Vinç ve pota', 'Yanık/ısı stresi', 'Gaz ve duman', 'Sıkışma-ezilme']),
    ('egitim_okul', 'Eğitim / Okul / Kreş', 'Az Tehlikeli', ['Yangın tahliye', 'Kayma-takılma', 'Kimyasal laboratuvar', 'Şiddet/güvenlik', 'İlk yardım']),
    ('elektronik_imalat', 'Elektronik İmalat', 'Tehlikeli', ['Lehim dumanı', 'Statik elektrik', 'Kimyasal temizleyici', 'Kesici delici', 'Ergonomi']),
    ('finans_ofis', 'Finans / Banka / Ofis', 'Az Tehlikeli', ['Ekranlı araç', 'Ergonomi', 'Yangın tahliye', 'Kayma-takılma', 'Psikososyal risk']),
    ('guvenlik_ozel', 'Güvenlik / Özel Güvenlik', 'Tehlikeli', ['Şiddet riski', 'Gece çalışma', 'Acil müdahale', 'İletişim', 'KKD ve ekipman']),
    ('hazir_giyim', 'Hazır Giyim / Tekstil Atölye', 'Tehlikeli', ['Dikiş makineleri', 'Toz ve gürültü', 'Yangın', 'Ergonomi', 'Kimyasal boya']),
    ('itim_matbaa', 'İletişim / Matbaa / Baskı', 'Tehlikeli', ['Solvent mürekkep', 'Makine sıkışması', 'Gürültü', 'Kağıt kesici', 'Yangın']),
    ('kagit_ambalaj', 'Kağıt / Ambalaj', 'Tehlikeli', ['Makine koruyucu', 'Kağıt kesici', 'Forklift', 'Toz', 'Yangın yükü']),
    ('konaklama_otel', 'Konaklama / Otel / Restoran', 'Az Tehlikeli', ['Mutfak yanık/kesik', 'Kaygan zemin', 'Kimyasal temizlik', 'Yangın tahliye', 'Ergonomi']),
    ('kuyumculuk', 'Kuyumculuk / Metal İşleme Küçük', 'Tehlikeli', ['Asit/siyanür riski', 'Yüksek sıcaklık', 'Göz koruması', 'Havalandırma', 'Yangın']),
    ('madencilik_yeralti', 'Madencilik (Yeraltı)', 'Çok Tehlikeli', ['Göçük / tahkimat', 'Gaz ölçümü', 'Patlatma', 'Nakliye', 'Acil kaçış']),
    ('mobilya_dekorasyon', 'Mobilya / Dekorasyon Montaj', 'Tehlikeli', ['El aletleri', 'Yüksekte montaj', 'Toz', 'Kimyasal tutkal', 'Elektrik']),
    ('plastik_enjeksiyon', 'Plastik / Enjeksiyon', 'Tehlikeli', ['Sıcak kalıp', 'Makine koruyucu', 'Duman-gaz', 'Ezilme', 'Yangın']),
    ('soguk_hava', 'Soğuk Hava Deposu', 'Tehlikeli', ['Soğuk stres', 'Kaygan zemin', 'Forklift', 'Kapalı alan', 'Acil çıkış']),
    ('tasimacilik', 'Taşımacılık / Şoförlük', 'Tehlikeli', ['Trafik güvenliği', 'Yük bağlama', 'Yorgunluk', 'Elle taşıma', 'Acil durum']),
    ('ticaret_perakende', 'Ticaret / Perakende / Market', 'Az Tehlikeli', ['Kayma-takılma', 'Elle taşıma', 'Yangın tahliye', 'Şiddet', 'Depo forklift']),
    ('yapi_denetim', 'Yapı Denetim / Mühendislik Ofisi', 'Az Tehlikeli', ['Saha ziyareti riski', 'PPE', 'Ekranlı araç', 'Araç kullanımı', 'Yangın']),
    ('yuksekte_calisma', 'Yüksekte Çalışma Hizmetleri', 'Çok Tehlikeli', ['Düşme önleme sistemleri', 'İskele/platform', 'Rüzgar etkisi', 'Malzeme düşmesi', 'Kurtarma planı']),
]

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
