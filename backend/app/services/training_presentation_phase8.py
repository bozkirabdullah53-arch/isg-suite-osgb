"""Optional Phase 8 traceability and instructor-content hardening.

This compatibility layer is additive and disabled by default. When enabled it
upgrades only new exact-NACE exam/presentation work with source-linked learning
concepts and a 20/20 question-to-slide coverage gate. Historical snapshots and
core training/PDF/certificate flows are never rewritten.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from typing import Any, Callable

TRACEABILITY_ENV = "NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED"
TRACEABILITY_FORCE_OFF_ENV = "NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF"
TRACEABILITY_VERSION = "presentation-question-traceability-v1"
MANIFEST_VERSION = "nace-training-presentation-manifest-v2-traceability"
SOURCE_CHECK_DATE = "2026-08-08"

_BASE_SOURCE = {
    "title": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
    "url": "https://www.csgb.gov.tr/media/2670/6331_isgkanunu_tr.pdf",
    "reference": "Madde 4, 10, 16 ve 17",
    "effective_date": "2012-06-30",
    "checked_at": SOURCE_CHECK_DATE,
}
_GUIDANCE_SOURCE = {
    "title": "ÇSGB/İSGGM İş Sağlığı ve Güvenliği yayın ve rehberleri",
    "url": "https://www.csgb.gov.tr/isggm/yayinlar-ve-afisler/",
    "reference": "İşe ve riske özgü resmî uygulama rehberleri",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_DUST_SOURCE = {
    "title": "ÇSGB İSGÜM Tozla Mücadele kaynakları",
    "url": "https://www.csgb.gov.tr/isgum/hizli-erisim/tozla-mucadele/",
    "reference": "Toz ve kimyasal maruziyet mevzuat/uygulama kaynakları",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_SECTOR_SOURCE = {
    "title": "ÇSGB Rehberlik ve Teftiş Başkanlığı sektör İSG yayınları",
    "url": "https://www.csgb.gov.tr/rtb/yayinlar/diger-yayinlar/",
    "reference": "Maden, metal, kimya ve yapı sektör rehberleri",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}


def phase8_active() -> bool:
    enabled = str(os.getenv(TRACEABILITY_ENV, "false") or "").strip().casefold()
    force_off = str(os.getenv(TRACEABILITY_FORCE_OFF_ENV, "false") or "").strip().casefold()
    return enabled in {"1", "true", "yes", "on"} and force_off not in {"1", "true", "yes", "on"}


def _fold(value: object) -> str:
    text = " ".join(str(value or "").casefold().split())
    return text.translate(str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"}))


def _pack(code: str, hazard: str, controls: tuple[str, ...], safe_behavior: str, *, source: dict[str, Any] = _GUIDANCE_SOURCE) -> dict[str, Any]:
    return {
        "code": code,
        "hazard": hazard,
        "controls": controls,
        "safe_behavior": safe_behavior,
        "sources": [_BASE_SOURCE, source],
    }


# Deliberately curated knowledge packs. Unsupported topics fail closed instead of
# receiving a generic cross-sector presentation.
_RULES: tuple[tuple[tuple[str, ...], dict[str, Any]], ...] = (
    (("kursun",), _pack(
        "lead-exposure",
        "Kurşun içeren toz ve duman, solunum ve kirli yüzeylerle temas yoluyla çalışan maruziyetine neden olabilir.",
        (
            "Maruziyet kaynağında kapalı proses, yerel emiş veya eşdeğer mühendislik kontrolü uygulanmalı; tozun ortama yayılması önlenmelidir.",
            "Kirli-temiz alan ayrımı, el-yüz hijyeni ve iş kıyafetlerinin kontrollü kullanımı maruziyetin işyeri dışına taşınmasını önlemelidir.",
        ),
        "Havalandırma veya hijyen kontrolü yetersizse işi normal kabul etmemek, uygunsuzluğu bildirmek ve belirlenen maruziyet/sağlık gözetimi programına uymak gerekir.",
        source=_DUST_SOURCE,
    )),
    (("sulfurik asit", "asit sicrama", "asit dokulme"), _pack(
        "sulfuric-acid",
        "Sülfürik asit koroziftir; sıçrama ve dökülme cilt ve gözlerde ciddi kimyasal yaralanma riski oluşturur.",
        (
            "Kapalı veya kontrollü transfer, kimyasala dayanıklı ekipman ve güvenli depolama düzeni ile sıçrama/dökülme olasılığı azaltılmalıdır.",
            "Acil göz duşu ve acil duş erişimi açık tutulmalı; dökülme müdahalesi işyerinin kimyasal acil durum planı ve SDS bilgileriyle yürütülmelidir.",
        ),
        "Sıçrama veya dökülmede doğaçlama müdahale yerine alanı güvenli hale getirmek, işyeri prosedürünü uygulamak ve maruziyeti derhal bildirmek gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("hidrojen", "aku sarj"), _pack(
        "hydrogen-charging",
        "Akü şarjında açığa çıkabilen hidrojen yeterince seyreltilmezse yanıcı/patlayıcı atmosfer oluşturabilir.",
        (
            "Şarj alanında yeterli havalandırma sağlanmalı ve gaz birikimine yol açabilecek kapalı hacimler kontrol edilmelidir.",
            "Ateşleme kaynakları kontrol edilmeli; elektrik ekipmanı ve çalışma düzeni patlayıcı ortam risk değerlendirmesine uygun olmalıdır.",
        ),
        "Havalandırma arızası, gaz şüphesi veya uygunsuz ateşleme kaynağı görüldüğünde şarj işlemini güvenli prosedüre göre durdurup yetkiliye bildirmek gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("enerji izolasyonu", "kisa devre", "elektrik"), _pack(
        "electrical-isolation",
        "Elektrik enerjisi, beklenmeyen enerjilenme ve kısa devre; bakım ve müdahale sırasında elektrik çarpması, ark ve hareketli ekipman risklerini artırır.",
        (
            "Bakım öncesinde enerji kaynakları belirlenmeli, güvenli şekilde izole edilmeli ve yetkisiz yeniden enerjilenme önlenmelidir.",
            "Elektrik panoları ve ekipmana yalnız yetkili kişiler müdahale etmeli; koruyucu düzenekler devre dışı bırakılmamalıdır.",
        ),
        "Enerjinin kesildiği doğrulanmadan bakım alanına girmemek; izolasyon bozulursa çalışmayı durdurup yeniden güvenli hale getirmek gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("traktor", "tarim makinelerinde devrilme", "devrilme-kapilma"), _pack(
        "agricultural-machinery-rollover",
        "Traktör ve tarım makinelerinde devrilme, hareketli parçalara kapılma ve araç-yaya etkileşimi ağır yaralanma riski oluşturur.",
        (
            "Devrilmeye karşı koruyucu yapı ve emniyet kemeri birlikte kullanılmalı; koruyucular, kuyruk mili muhafazası ve güvenli bağlantı düzeni devrede tutulmalıdır.",
            "Eğim, zemin, hız, yük ve ekipman bağlantısı işe başlamadan değerlendirilerek yetkisiz yolcu ve tehlikeli manevra önlenmelidir.",
        ),
        "Makine tamamen durmadan ve enerji güvenliği sağlanmadan hareketli bölgeye yaklaşmamak; devrilme riski olan koşulda işi durdurmak gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("pestisit", "gubre", "zirai kimyasal"), _pack(
        "agricultural-chemicals",
        "Pestisit ve gübreler soluma, cilt-göz teması, zehirlenme, kimyasal yanık ve çevresel yayılım riski oluşturabilir.",
        (
            "Etiket ve güvenlik bilgi formuna uygun ürün, doz, karışım, uygulama ekipmanı ve kişisel koruma kullanılmalıdır.",
            "Depolama, hazırlama ve uygulama alanları kontrol edilmeli; rüzgârla sürüklenme, geri tepme, sızıntı ve kontamine ambalaj güvenli yönetilmelidir.",
        ),
        "Etiketsiz ürün kullanmamak, uygunsuz karışım yapmamak; maruziyette işi durdurup ürün bilgisindeki ilk yardım ve işyeri acil prosedürünü uygulamak gerekir.",
        source=_DUST_SOURCE,
    )),
    (("sicaklik", "gunes", "biyolojik etken", "hayvan temasi"), _pack(
        "agricultural-outdoor-biological",
        "Sıcak-soğuk, güneş, böcek/kene, biyolojik etkenler ve hayvan teması ısı hastalığı, enfeksiyon ve travma riski doğurabilir.",
        (
            "İş; hava koşulu, gölge, su, dinlenme, uygun kıyafet ve maruziyet süresi dikkate alınarak planlanmalıdır.",
            "Biyolojik temas ve hayvan davranışı için hijyen, aşılama/sağlık gözetimi, güvenli yaklaşım ve uygun kişisel koruma uygulanmalıdır.",
        ),
        "Isı hastalığı belirtisi, saldırgan hayvan veya biyolojik maruziyet şüphesinde çalışmayı sürdürmemek ve işyeri sağlık/acil prosedürüne başvurmak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("sera", "yuksekte calisma", "elektrik riskleri"), _pack(
        "greenhouse-height-electrical",
        "Seralarda nemli ortam elektriğin etkisini artırabilir; merdiven/platform kullanımı ve örtü-bakım işleri düşme riski oluşturur.",
        (
            "Elektrik tesisatı nemli ortama uygun korunmalı; kaçak akım ve koruyucu düzenekler çalışır tutulmalı, müdahale yalnız yetkili kişilerce yapılmalıdır.",
            "Yüksekte iş için uygun erişim ekipmanı, sağlam zemin ve düşmeyi önleyici tedbirler seçilmeli; doğaçlama yükseltiler kullanılmamalıdır.",
        ),
        "Islak/hasarlı elektrik ekipmanını kullanmamak; güvenli erişim veya düşme koruması yoksa yüksekte işe başlamamak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("uzak saha", "elle tasima", "ergonomi"), _pack(
        "remote-field-manual-handling",
        "Elle taşıma ve tekrarlı tarım işleri kas-iskelet zorlanmasına; uzak sahada iletişim ve yardım gecikmesi sonuçların ağırlaşmasına neden olabilir.",
        (
            "Yük, mesafe, zemin ve tekrar sıklığı değerlendirilerek mekanik yardım, ekip çalışması ve uygun çalışma yüksekliği kullanılmalıdır.",
            "Uzak saha için konum, haberleşme, hava koşulu, ulaşım, ilk yardım ve acil yardım düzeni işe başlamadan doğrulanmalıdır.",
        ),
        "Tek başına güvenli kaldırılamayan yükü taşımamak; haberleşme veya acil yardım imkânı yoksa uzak saha işini başlatmamak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("elle tasima", "yangin", "tahliye", "acil durum"), _pack(
        "manual-fire-emergency",
        "Ağır/uygunsuz taşıma, yangın ve acil durumda kontrolsüz hareket; kas-iskelet yaralanması, yanık ve tahliye gecikmesi risklerini artırabilir.",
        (
            "Yükün ağırlığı, kavrama ve taşıma yolu değerlendirilerek mekanik yardım veya ekip çalışması kullanılmalıdır.",
            "Kaçış yolları ve acil ekipman erişilebilir tutulmalı; yangın ve tahliye davranışı işyerinin acil durum planına göre uygulanmalıdır.",
        ),
        "Taşıma koşulu güvenli değilse yardım istemek; alarm halinde işi bırakıp belirlenmiş tahliye ve toplanma düzenini izlemek gerekir.",
    )),
    (("ergimis metal", "curuf", "sicak yuzey sicrama"), _pack(
        "molten-metal",
        "Ergimiş metal, cüruf ve çok sıcak yüzeyler ciddi yanık, sıçrama ve yangın tehlikesi oluşturur.",
        (
            "Sıçrama hattı ve sıcak bölge fiziksel olarak kontrol edilmeli; çalışanlar güvenli mesafe ve bariyer düzenine uymalıdır.",
            "Nem/su, uygunsuz ekipman ve kontrolsüz malzeme teması gibi şiddetli sıçramaya yol açabilecek koşullar proses prosedürleriyle engellenmelidir.",
        ),
        "Sıcak bölgeye yalnız yetkili çalışma düzeni ve uygun koruma ile girmek; bariyer veya proses kontrolü bozulduğunda işi durdurmak gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("pota", "vinc", "kaldirma", "aski ekipmani", "agir plaka", "istifleme"), _pack(
        "lifting-loads",
        "Askıdaki yükler, uygunsuz sapan/aksesuar seçimi ve kontrolsüz kaldırma; düşen yük, ezilme ve çarpma riski oluşturur.",
        (
            "Kaldırma ekipmanı ve aksesuarları işe uygun seçilmeli, kullanım öncesi kontrol edilmeli ve yükün altında insan bulunmamalıdır.",
            "Kaldırma alanı ayrılmalı; operatör ile işaretçi/çalışan iletişimi ve istif kararlılığı işyeri planına göre sağlanmalıdır.",
        ),
        "Askı, yük dengesi veya iletişim şüpheliyse kaldırmayı başlatmamak; askıdaki yükün altına veya salınım alanına girmemek gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("metal tozu", "dokum dumani", "metal dumani", "gaz ve havalandirma"), _pack(
        "metal-fume",
        "Metal dumanı, proses gazları ve ince tozlar solunum yolu maruziyeti ve bazı proseslerde yangın/patlama riski oluşturabilir.",
        (
            "Emisyon kaynağında etkin emiş/havalandırma ve proses kapatması gibi mühendislik kontrolleri önceliklendirilmelidir.",
            "Maruziyet ölçümü, temizlik yöntemi ve gerekli solunum koruması risk değerlendirmesine göre belirlenmelidir.",
        ),
        "Emiş sistemi çalışmıyorsa veya görünür duman/toz kontrol dışına çıkıyorsa normal çalışmaya devam etmemek ve uygunsuzluğu bildirmek gerekir.",
        source=_DUST_SOURCE,
    )),
    (("isi stresi", "yaniklar"), _pack(
        "heat-stress",
        "Yüksek ısı yükü; ısı stresi, dikkat azalması ve sıcak yüzey kaynaklı yanık riskini artırabilir.",
        (
            "Isı kaynağına maruziyet mühendislik ve organizasyon tedbirleriyle azaltılmalı; iş-dinlenme ve sıvı erişimi işyeri değerlendirmesine göre planlanmalıdır.",
            "Sıcak yüzeyler işaretlenmeli/izole edilmeli ve işe uygun ısıya dayanıklı koruyucular kullanılmalıdır.",
        ),
        "Baş dönmesi, aşırı halsizlik veya ısı kontrolünün kaybı gibi belirtilerde çalışmayı sürdürmemek ve işyeri sağlık/acil prosedürüne göre yardım istemek gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("sikisma", "ezilme", "kalip bozma", "capak alma"), _pack(
        "crushing-entanglement",
        "Hareketli parçalar, sıkışma noktaları ve kontrolsüz malzeme hareketi ezilme, sıkışma ve uzuv yaralanması riski oluşturur.",
        (
            "Makine koruyucuları ve güvenlik sistemleri devrede tutulmalı; tehlikeli bölgeye erişim proses durdurma/izolasyon kurallarına bağlı olmalıdır.",
            "Malzeme sabitleme, uygun el aleti ve güvenli konumlandırma ile el-vücut tehlike hattından uzak tutulmalıdır.",
        ),
        "Sıkışan parçayı çalışan makinede elle düzeltmemek; koruyucu veya izolasyon yoksa işi durdurmak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("sev", "kaya dusmesi", "heyelan", "kademe"), _pack(
        "ground-control",
        "Şev/kademe kararsızlığı, kaya düşmesi ve heyelan; göçük, ezilme ve ölümcül çarpma tehlikesi oluşturabilir.",
        (
            "Şev ve kademe koşulları yetkin kişilerce değerlendirilerek güvenli geometri, mesafe ve erişim sınırları belirlenmelidir.",
            "Kaya düşmesi/heyelan belirtileri izlenmeli; tehlikeli alan fiziksel olarak ayrılmalı ve değişen saha koşullarında yeniden değerlendirme yapılmalıdır.",
        ),
        "Çatlak, dökülme, su etkisi veya beklenmeyen zemin hareketi görüldüğünde tehlikeli bölgeye girmemek ve işi durdurup yetkiliye bildirmek gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("patlatma", "emniyet mesafesi"), _pack(
        "blasting-safety",
        "Patlatma faaliyetleri; patlayıcı enerji, taş fırlaması, hava şoku ve yetkisiz giriş nedeniyle ağır sonuçlu tehlikeler oluşturur.",
        (
            "Patlatma yalnız yetkili kişiler, onaylı işyeri planı ve belirlenmiş güvenlik bölgeleri/uyarı düzeni kapsamında yürütülmelidir.",
            "Patlatma alanına erişim kontrol edilmeli; işaret, haberleşme ve yeniden giriş kararı yetkili prosedüre göre uygulanmalıdır.",
        ),
        "Yetki veya güvenlik bölgesi doğrulanmadan patlatma alanına yaklaşmamak; uyarı ve yeniden giriş talimatlarına kesinlikle uymak gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("kirma", "eleme", "konveyor"), _pack(
        "conveyor-machinery",
        "Kırıcı, elek ve konveyörlerde hareketli parçalar; kapılma, sıkışma ve fırlayan malzeme tehlikesi oluşturur.",
        (
            "Hareketli kısımlar uygun koruyucularla ayrılmalı; acil durdurma ve güvenlik düzenekleri erişilebilir/çalışır tutulmalıdır.",
            "Temizlik, sıkışma açma veya bakım öncesinde ekipman durdurulup enerji izolasyonu uygulanmalıdır.",
        ),
        "Çalışan ekipmanda sıkışmayı elle açmamak; koruyucu eksik veya acil durdurma çalışmıyorsa ekipmanı kullanmamak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("silika", "toz", "gurultu", "titresim"), _pack(
        "dust-noise-vibration",
        "Solunabilir toz/silika ile gürültü ve titreşim maruziyetleri meslek hastalığı ve işitme/kas-iskelet etkileri oluşturabilir.",
        (
            "Toz kaynağında ıslak yöntem, kapatma veya emiş gibi mühendislik kontrolleri; gürültü/titreşimde kaynak ve süre azaltma önceliklendirilmelidir.",
            "Kişisel maruziyet ölçümleri ve sağlık gözetimi risk değerlendirmesine göre planlanmalı; uygun KKD kalan risk için kullanılmalıdır.",
        ),
        "Toz bastırma veya diğer maruziyet kontrolleri devre dışıysa işi normal sürdürmemek ve uygunsuzluğu bildirmek gerekir.",
        source=_DUST_SOURCE,
    )),
    (("is makineleri", "kor nokta", "ocak ici trafik", "mobil ekipman"), _pack(
        "mobile-plant",
        "İş makinelerinin kör noktaları, geri manevra ve yaya-araç etkileşimi çarpma/ezilme riski oluşturur.",
        (
            "Yaya ve araç yolları mümkün olduğunca ayrılmalı; hız, park, geri manevra ve geçiş kuralları saha trafik planıyla belirlenmelidir.",
            "Kör noktalarda görüş yardımcıları, işaretçi veya kontrollü alan düzeni kullanılmalı; yetkisiz kişiler çalışma alanından uzak tutulmalıdır.",
        ),
        "Operatörle göz/iletişim teması kurulmadan kör noktaya girmemek ve belirlenmiş yaya güzergâhını terk etmemek gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("cam kirilmasi", "keskin kenar", "goz yaralan"), _pack(
        "sharp-edges",
        "Kırılabilir malzeme, keskin kenarlar ve fırlayan parçalar kesilme ve göz yaralanması riski oluşturur.",
        (
            "Malzeme güvenli taşıma/sabitleme yöntemiyle tutulmalı; kırılma hattı ve keskin kenarlar mümkün olduğunca fiziksel olarak kontrol edilmelidir.",
            "Kesim/kırılma riskine uygun göz-yüz ve el koruması, risk değerlendirmesinde belirlenen diğer tedbirlerle birlikte kullanılmalıdır.",
        ),
        "Çatlak veya dengesiz parçayı zorlamamak; kırık malzemeyi çıplak elle toplamamak ve uygun toplama ekipmanı kullanmak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("firin", "sicak urun", "termal sok"), _pack(
        "hot-furnace",
        "Fırın ve sıcak ürünler yanık, ısı stresi ve ani termal etkiler nedeniyle malzeme hasarı/fırlama tehlikesi oluşturabilir.",
        (
            "Sıcak bölge erişimi sınırlandırılmalı; yüzey ve ürün sıcaklığına uygun taşıma ekipmanı ve bariyer kullanılmalıdır.",
            "Proses sıcaklık/soğutma kuralları izlenmeli; kontrolsüz su veya sıcaklık değişimi gibi termal şok koşullarından kaçınılmalıdır.",
        ),
        "Sıcaklığı doğrulanmamış ürüne dokunmamak; bariyer veya taşıma ekipmanı uygunsuzsa işlemi durdurmak gerekir.",
        source=_SECTOR_SOURCE,
    )),
    (("seramik tozu", "solunum korun"), _pack(
        "silica-dust",
        "Seramik/silika içeren ince tozun solunması ciddi ve birikimli solunum sağlığı riski oluşturabilir.",
        (
            "Toz oluşumu ıslak yöntem, kapatma ve yerel emiş gibi kaynağa yönelik kontrollerle azaltılmalıdır.",
            "Kuru süpürme veya basınçlı hava ile toz yayma yerine uygun endüstriyel temizlik yöntemi kullanılmalı; kişisel maruziyet ölçümü planlanmalıdır.",
        ),
        "Toz kontrol sistemi çalışmıyorsa veya görünür toz yayılımı varsa çalışmayı sürdürmemek ve kaynağın kontrolünü istemek gerekir.",
        source=_DUST_SOURCE,
    )),
    (("pres", "kesim", "taslama", "parca firlama"), _pack(
        "press-grinding",
        "Pres, kesim ve taşlama ekipmanlarında sıkışma, kesilme, disk/parça fırlaması ve göz-yüz yaralanması riski vardır.",
        (
            "Koruyucular, uygun bağlama/sabitleme ve ekipmana uygun disk/bıçak seçimi kullanılmalı; hasarlı ekipman devre dışı bırakılmalıdır.",
            "Ayar, temizlik ve bakımda enerji izolasyonu uygulanmalı; çalışan tehlikeli fırlama hattından uzak konumlanmalıdır.",
        ),
        "Koruyucusuz ekipmanı kullanmamak; anormal titreşim, çatlak veya hasar görüldüğünde ekipmanı durdurmak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("ekranli", "ergonomi", "bilgisayar", "ofis"), _pack(
        "display-ergonomics",
        "Uzun süreli ekranlı çalışma; uygunsuz duruş, tekrarlı hareket ve görsel yük nedeniyle kas-iskelet ve yorgunluk risklerini artırabilir.",
        (
            "Çalışma istasyonu ekran, sandalye, masa ve giriş ekipmanları çalışana göre ayarlanmalı; nötr ve destekli çalışma duruşu hedeflenmelidir.",
            "İş organizasyonu uzun kesintisiz ekran maruziyetini azaltacak şekilde değişken görevler ve uygun dinlenme düzeni içermelidir.",
        ),
        "Ağrı veya uyuşma oluşturan çalışma düzenini normal kabul etmemek; istasyon ayarı ve iş organizasyonu için yöneticiyi/İSG birimini bilgilendirmek gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
    (("sunucu", "server", "veri merkezi"), _pack(
        "server-room",
        "Sunucu/sistem odalarında elektrik enerjisi, ısı yükü, kablo düzeni ve yangın riski birlikte yönetilmelidir.",
        (
            "Yetkisiz erişim sınırlandırılmalı; elektrik ve kablo düzeni uygun tutulmalı, havalandırma/soğutma ve yangın algılama sistemleri işler durumda olmalıdır.",
            "Bakım veya ekipman müdahalesi yalnız yetkili prosedür ve enerji güvenliği kurallarıyla yapılmalıdır.",
        ),
        "Aşırı ısı, yanık kokusu, alarm veya elektriksel uygunsuzlukta odaya kontrolsüz müdahale etmemek ve yetkili teknik/acil prosedürü başlatmak gerekir.",
        source=_GUIDANCE_SOURCE,
    )),
)


def resolve_topic_knowledge(topic: object) -> dict[str, Any] | None:
    normalized = _fold(topic)
    for needles, pack in _RULES:
        if any(needle in normalized for needle in needles):
            return deepcopy(pack)
    return None


def traceability_readiness(topics: list[object]) -> dict[str, Any]:
    resolved = [resolve_topic_knowledge(topic) for topic in topics]
    missing = [str(topics[i]) for i, item in enumerate(resolved) if item is None]
    return {
        "ready": len(topics) == 5 and not missing,
        "topic_count": len(topics),
        "supported_count": sum(item is not None for item in resolved),
        "missing_topics": missing,
        "version": TRACEABILITY_VERSION,
    }


def _short(value: object, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def phase8_exact_questions(snapshot: Any) -> tuple[dict[str, Any], ...]:
    try:
        topics = json.loads(getattr(snapshot, "training_topics_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        topics = []
    if not isinstance(topics, list) or len(topics) != 5:
        raise ValueError("Doğrulanmış NACE snapshot'ında tam olarak beş işe özgü eğitim konusu bulunmalıdır.")
    nace = str(getattr(snapshot, "nace_code", "") or "").strip()
    profile = str(getattr(snapshot, "content_profile_code", "") or "").strip()
    if not nace or not profile:
        raise ValueError("Doğrulanmış NACE snapshot'ında kod ve içerik profili zorunludur.")

    questions: list[dict[str, Any]] = []
    code_nace = nace.replace(".", "")
    for topic_index, raw_topic in enumerate(topics, start=1):
        topic = _short(raw_topic)
        knowledge = resolve_topic_knowledge(topic)
        if knowledge is None:
            raise ValueError(f"İçerik doğrulaması bekleniyor; güvenilir teknik bilgi paketi bulunamadı: {topic}")
        common = {
            "version": 2,
            "topic_code": f"exact-nace-{code_nace}-{topic_index:02d}",
            "topic_label": topic,
            "correct_option": "A",
            "sources": deepcopy(knowledge["sources"]),
            "scopes": [
                {"type": "nace", "value": nace},
                {"type": "sector", "value": profile},
            ],
            "knowledge_pack_code": knowledge["code"],
        }
        for variant in (1, 2, 3):
            q = {**common, "question_code": f"TR-NACE-{code_nace}-{topic_index:02d}-{variant}"}
            if variant == 1:
                q.update({
                    "question_text": f"{topic} kapsamında temel tehlikeyi en doğru tanımlayan ifade hangisidir?",
                    "options": [
                        knowledge["hazard"],
                        "Bu konu yalnız üretim hızını etkiler; çalışan güvenliği açısından özel bir tehlike oluşturmaz.",
                        "Risk yalnız vardiya sonunda ortaya çıkar ve çalışma sırasında kontrol gerektirmez.",
                        "Tehlike yalnız çalışanın dikkatsizliğinden kaynaklanır; iş ekipmanı ve proses koşulları önemli değildir.",
                    ],
                    "answer_explanation": knowledge["hazard"],
                    "learning_dimension": "hazard_recognition",
                })
            elif variant == 2:
                q.update({
                    "question_text": f"{topic} için öncelikli güvenli kontrol yaklaşımı hangisidir?",
                    "options": [
                        " ".join(knowledge["controls"]),
                        "Yalnız kişisel koruyucu donanım kullanmak ve kaynağa yönelik kontrolleri uygulamamak.",
                        "Kontrolleri ancak bir olay meydana geldikten sonra değerlendirmek.",
                        "Risk değerlendirmesi ve iş talimatı olmadan çalışan deneyimine göre devam etmek.",
                    ],
                    "answer_explanation": " ".join(knowledge["controls"]),
                    "learning_dimension": "control_measures",
                })
            else:
                q.update({
                    "question_text": f"{topic} konusunda güvenli saha davranışını en doğru açıklayan seçenek hangisidir?",
                    "options": [
                        knowledge["safe_behavior"],
                        "Koruyucu veya güvenlik düzeni işi yavaşlatıyorsa geçici olarak devre dışı bırakmak.",
                        "Belirsizlik veya uygunsuzluk olduğunda işi durdurmadan vardiya sonuna kadar devam etmek.",
                        "Tehlikeyi kayıt altına almadan yalnız sözlü olarak çalışma arkadaşlarına bırakmak.",
                    ],
                    "answer_explanation": knowledge["safe_behavior"],
                    "learning_dimension": "safe_behavior",
                })
            questions.append(q)
    if len(questions) != 15 or len({item["question_code"] for item in questions}) != 15:
        raise RuntimeError("Faz 8 işe özgü sınav paketi 15 benzersiz sorudan oluşmalıdır.")
    return tuple(questions)


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _question_source_refs(question: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for source in question.get("sources") or []:
        if isinstance(source, dict):
            value = str(source.get("url") or source.get("title") or "").strip()
        else:
            value = str(source or "").strip()
        if value and value not in refs:
            refs.append(value)
    return refs


def enrich_manifest_with_traceability(manifest: dict[str, Any], snapshot: Any) -> dict[str, Any]:
    result = deepcopy(manifest)
    topics = list(result.get("training_topics") or [])
    readiness = traceability_readiness(topics)
    if not readiness["ready"]:
        missing = "; ".join(readiness["missing_topics"][:3]) or f"konu sayısı={len(topics)}"
        raise ValueError(f"Sunum Faz 8 doğrulaması başarısız: {missing}")

    work_slides = [slide for slide in result.get("slides") or [] if slide.get("section_id") == "work_specific_topics"]
    if len(work_slides) != 5:
        raise ValueError(f"Faz 8 için beş işe özgü slayt bekleniyor; bulunan: {len(work_slides)}")

    knowledge_by_topic: list[dict[str, Any]] = []
    for topic, slide in zip(topics, work_slides, strict=True):
        knowledge = resolve_topic_knowledge(topic)
        if knowledge is None:
            raise ValueError(f"Teknik bilgi paketi bulunamadı: {topic}")
        blocks = [
            block for block in list(slide.get("content_blocks") or [])
            if str(block.get("type") or "") != "technical_content_pending_renderer"
        ]
        blocks.extend([
            {"type": "tehlike", "value": knowledge["hazard"]},
            {"type": "kontrol_tedbiri", "value": knowledge["controls"][0]},
            {"type": "kontrol_tedbiri", "value": knowledge["controls"][1]},
            {"type": "guvenli_davranis", "value": knowledge["safe_behavior"]},
        ])
        slide["content_blocks"] = blocks
        slide["knowledge_pack_code"] = knowledge["code"]
        slide["traceability_required"] = True
        knowledge_by_topic.append(knowledge)

    from app.services import training_question_bank as question_bank

    foundation = list(question_bank._foundational_questions())
    work_questions = list(phase8_exact_questions(snapshot))
    if len(foundation) != 5:
        raise ValueError(f"Faz 8 için beş temel soru bekleniyor; bulunan: {len(foundation)}")

    foundation_slides = [slide for slide in result.get("slides") or [] if slide.get("section_id") == "foundation_ohs"]
    if len(foundation_slides) < 2:
        raise ValueError("Temel İSG sorularını bağlamak için en az iki temel slayt gerekir.")

    concepts: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    for index, question in enumerate(foundation, start=1):
        slide = foundation_slides[0] if index <= 3 else foundation_slides[1]
        concept_id = f"LC-FOUNDATION-{index:02d}"
        sources = _question_source_refs(question) or list(slide.get("source_refs") or [])
        concepts.append({
            "concept_id": concept_id,
            "bucket": "foundation",
            "title": str(question.get("topic_label") or question.get("question_text") or f"Temel İSG {index}"),
            "statement": str(question.get("answer_explanation") or "").strip(),
            "slide_positions": [int(slide["position"])],
            "source_refs": sources,
        })
        links.append({
            "question_position": index,
            "question_code": str(question.get("question_code") or f"TR-TEMEL-{index:03d}"),
            "question_version": int(question.get("version") or 1),
            "bucket": "foundation",
            "answer_concept_id": concept_id,
            "slide_positions": [int(slide["position"])],
            "source_refs": sources,
            "nace_code": None,
        })

    nace = str(getattr(snapshot, "nace_code", "") or "").strip()
    for offset, question in enumerate(work_questions, start=1):
        match = re.search(r"-(\d{2})-[123]$", str(question["question_code"]))
        if match is None:
            raise ValueError("Faz 8 soru kodu konu indeksini taşımıyor.")
        topic_index = int(match.group(1))
        variant = int(str(question["question_code"]).rsplit("-", 1)[-1])
        slide = work_slides[topic_index - 1]
        knowledge = knowledge_by_topic[topic_index - 1]
        statement = (
            knowledge["hazard"] if variant == 1
            else " ".join(knowledge["controls"]) if variant == 2
            else knowledge["safe_behavior"]
        )
        concept_id = f"LC-{nace.replace('.', '')}-{topic_index:02d}-{variant}"
        sources = _question_source_refs(question) or list(slide.get("source_refs") or [])
        concepts.append({
            "concept_id": concept_id,
            "bucket": "work_specific",
            "topic_index": topic_index,
            "dimension": str(question.get("learning_dimension") or ""),
            "knowledge_pack_code": knowledge["code"],
            "title": str(question.get("topic_label") or ""),
            "statement": statement,
            "slide_positions": [int(slide["position"])],
            "source_refs": sources,
        })
        links.append({
            "question_position": offset + 5,
            "question_code": str(question["question_code"]),
            "question_version": int(question.get("version") or 2),
            "bucket": "work_specific",
            "answer_concept_id": concept_id,
            "slide_positions": [int(slide["position"])],
            "source_refs": sources,
            "nace_code": nace,
        })

    result["manifest_version"] = MANIFEST_VERSION
    result["traceability"] = {
        "version": TRACEABILITY_VERSION,
        "learning_concepts": concepts,
        "question_links": links,
        "coverage": {
            "question_total": 20,
            "linked_questions": len(links),
            "source_linked_questions": sum(bool(item["source_refs"]) for item in links),
            "orphan_questions": 0,
            "cross_sector_fallback": False,
            "supported_topics": 5,
            "status": "passed",
        },
    }
    result["rendering"] = {
        **dict(result.get("rendering") or {}),
        "traceability_ready": True,
        "instructor_mode_supported": True,
    }
    result.pop("content_hash", None)
    result["content_hash"] = _canonical_hash(result)
    validate_manifest_traceability(result)
    return result


def validate_manifest_traceability(manifest: dict[str, Any]) -> dict[str, Any]:
    trace = manifest.get("traceability") or {}
    coverage = trace.get("coverage") or {}
    concepts = trace.get("learning_concepts") or []
    links = trace.get("question_links") or []
    slides = {int(slide.get("position") or 0) for slide in manifest.get("slides") or []}
    concept_ids = {str(item.get("concept_id") or "") for item in concepts}
    errors: list[str] = []
    if trace.get("version") != TRACEABILITY_VERSION:
        errors.append("traceability_version")
    if int(coverage.get("question_total") or 0) != 20 or len(links) != 20:
        errors.append("question_total")
    codes = [str(item.get("question_code") or "") for item in links]
    if len(set(codes)) != 20 or any(not code for code in codes):
        errors.append("question_codes")
    for link in links:
        if str(link.get("answer_concept_id") or "") not in concept_ids:
            errors.append("orphan_concept")
        positions = [int(value) for value in link.get("slide_positions") or []]
        if not positions or any(position not in slides for position in positions):
            errors.append("orphan_slide")
        if not link.get("source_refs"):
            errors.append("missing_source")
    if any(not str(item.get("statement") or "").strip() for item in concepts):
        errors.append("empty_concept")
    if bool(coverage.get("cross_sector_fallback")):
        errors.append("cross_sector_fallback")
    if errors:
        raise ValueError("Sunum-sınav izlenebilirlik doğrulaması başarısız: " + ", ".join(sorted(set(errors))))
    return {
        "ok": True,
        "question_total": 20,
        "linked_questions": 20,
        "source_linked_questions": 20,
        "orphan_questions": 0,
        "version": TRACEABILITY_VERSION,
    }


def install_training_presentation_phase8() -> dict[str, str]:
    """Install idempotent wrappers; behavior changes only while Phase 8 env is active."""
    from app.api import training_presentation as api_module
    from app.services import training_exact_question_factory as factory
    from app.services import training_presentation_approval as approval
    from app.services import training_presentation_contract as contract
    from app.services import training_presentation_readiness as readiness
    from app.services import training_presentation_versions as versions

    current_manifest = contract.build_presentation_manifest_preview
    if getattr(current_manifest, "_phase8_traceability_active", False):
        return {"phase8_patch": "already-active", "enabled": str(phase8_active()).lower()}

    original_exact: Callable[..., Any] = factory.exact_questions_from_snapshot
    original_manifest: Callable[..., Any] = current_manifest
    original_readiness: Callable[..., Any] = readiness.training_presentation_readiness
    original_approve: Callable[..., Any] = approval.approve_presentation_version

    def exact_wrapper(snapshot):
        if not phase8_active():
            return original_exact(snapshot)
        return phase8_exact_questions(snapshot)

    exact_wrapper._phase8_traceability_active = True
    factory.exact_questions_from_snapshot = exact_wrapper

    def manifest_wrapper(*, training, snapshot, exam_readiness):
        manifest = original_manifest(training=training, snapshot=snapshot, exam_readiness=exam_readiness)
        if not phase8_active():
            return manifest
        if snapshot is None:
            from app.services.training_presentation_contract import PresentationContractError
            raise PresentationContractError("Faz 8 için doğrulanmış NACE snapshot zorunludur.")
        try:
            return enrich_manifest_with_traceability(manifest, snapshot)
        except ValueError as exc:
            from app.services.training_presentation_contract import PresentationContractError
            raise PresentationContractError(str(exc)) from exc

    manifest_wrapper._phase8_traceability_active = True
    contract.build_presentation_manifest_preview = manifest_wrapper
    versions.build_presentation_manifest_preview = manifest_wrapper
    api_module.build_presentation_manifest_preview = manifest_wrapper

    def readiness_wrapper(db, *, training):
        payload = original_readiness(db, training=training)
        if not phase8_active():
            payload["traceability"] = {"enabled": False, "version": TRACEABILITY_VERSION}
            return payload
        topics = list((payload.get("source_data") or {}).get("training_topics") or [])
        quality = traceability_readiness(topics)
        check = {
            "code": "question_slide_traceability",
            "label": "20/20 soru-slayt ve teknik içerik paketi",
            "ok": bool(quality["ready"]),
            "detail": (
                "Beş konu için doğrulanmış teknik bilgi paketi hazır; yeni sunum 20/20 soru-slayt kapsamı olmadan üretilemez."
                if quality["ready"]
                else f"İçerik doğrulaması bekleniyor: {quality['supported_count']}/5 konu destekleniyor."
            ),
        }
        checks = list(payload.get("checks") or [])
        checks.append(check)
        payload["checks"] = checks
        blockers = list(payload.get("blockers") or [])
        if not quality["ready"]:
            blockers.append({"code": check["code"], "detail": check["detail"]})
        payload["blockers"] = blockers
        payload["generation_allowed"] = bool(payload.get("generation_allowed")) and bool(quality["ready"])
        payload["traceability"] = {"enabled": True, **quality}
        if not quality["ready"]:
            payload["next_action"] = "Bu NACE için teknik içerik doğrulaması tamamlanmadan sunum üretilmez; çekirdek eğitim akışı etkilenmez."
        return payload

    readiness_wrapper._phase8_traceability_active = True
    readiness.training_presentation_readiness = readiness_wrapper
    api_module.training_presentation_readiness = readiness_wrapper

    def approve_wrapper(db, *, row, user, method, confirmed_manifest_hash, note=None, esign_request_id=None):
        if phase8_active():
            try:
                manifest = json.loads(str(row.manifest_json or "{}"))
                validate_manifest_traceability(manifest)
            except (TypeError, json.JSONDecodeError, ValueError) as exc:
                raise approval.PresentationApprovalError(
                    "traceability_not_ready",
                    "20/20 soru-slayt-kaynak izlenebilirliği doğrulanmadan sunum onaylanamaz.",
                ) from exc
        return original_approve(
            db,
            row=row,
            user=user,
            method=method,
            confirmed_manifest_hash=confirmed_manifest_hash,
            note=note,
            esign_request_id=esign_request_id,
        )

    approve_wrapper._phase8_traceability_active = True
    approval.approve_presentation_version = approve_wrapper
    api_module.approve_presentation_version = approve_wrapper

    return {
        "phase8_patch": "active",
        "enabled": str(phase8_active()).lower(),
        "manifest": MANIFEST_VERSION,
        "traceability": TRACEABILITY_VERSION,
    }
