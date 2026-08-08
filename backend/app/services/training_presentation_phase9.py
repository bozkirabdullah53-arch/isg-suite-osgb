"""Optional Phase 9 NACE coverage expansion and instructor-mode v2 marker.

Phase 9 is an additive compatibility layer installed after Phase 8. It adds
exact-first, source-controlled knowledge packs for reviewed training topics
without changing the Phase 8 fallback contract. When disabled, every lookup is
delegated to the original Phase 8 resolver and generated manifests remain v1.

No historical presentation, exam, PDF or certificate row is rewritten.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from typing import Any, Callable

COVERAGE_V2_ENV = "NACE_TRAINING_PRESENTATION_COVERAGE_V2_ENABLED"
COVERAGE_V2_FORCE_OFF_ENV = "NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF"
COVERAGE_V2_VERSION = "nace-training-presentation-coverage-v2"
INSTRUCTOR_UI_VERSION = "instructor-mode-v2"
SOURCE_CHECK_DATE = "2026-08-09"

_BASE_SOURCE = {
    "title": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
    "url": "https://www.csgb.gov.tr/media/2670/6331_isgkanunu_tr.pdf",
    "reference": "İşverenin genel yükümlülüğü, risk değerlendirmesi, bilgilendirme ve eğitim hükümleri",
    "effective_date": "2012-06-30",
    "checked_at": SOURCE_CHECK_DATE,
}
_CONSTRUCTION_SOURCE = {
    "title": "ÇSGB İnşaat Sektöründe İş Sağlığı ve Güvenliği",
    "url": "https://guvenliinsaat.csgb.gov.tr/",
    "reference": "Yapı işleri, yüksekte çalışma, iskele, kazı, kaldırma, saha trafiği ve elektrik güvenliği içerikleri",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_CONSTRUCTION_LEGISLATION_SOURCE = {
    "title": "ÇSGB İnşaat Sektörü İSG Mevzuatı",
    "url": "https://guvenliinsaat.csgb.gov.tr/mevzuat/",
    "reference": "Yapı İşlerinde İSG Yönetmeliği ve ilgili iş ekipmanı/acil durum düzenlemeleri",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_PUBLICATIONS_SOURCE = {
    "title": "ÇSGB İSGGM Yayınlar ve Afişler",
    "url": "https://www.csgb.gov.tr/isggm/yayinlar-ve-afisler/",
    "reference": "Resmî İSG rehberleri ve uygulama dokümanları",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_LOGISTICS_SOURCE = {
    **_PUBLICATIONS_SOURCE,
    "reference": "Forkliftlerde Güvenli Çalışma Uygulama Rehberi; Güvenli İstifleme Rehberi; Elle Taşıma İşleri Yönetmeliği Uygulama Rehberi; lojistik depolama yayınları",
}
_HEALTH_SOURCE = {
    **_PUBLICATIONS_SOURCE,
    "reference": "Kamu Hastanelerinde İSG Uygulama Rehberi; biyolojik etken, ergonomi, kesici-delici ve acil durum rehberleri",
}


def phase9_active() -> bool:
    enabled = str(os.getenv(COVERAGE_V2_ENV, "false") or "").strip().casefold()
    force_off = str(os.getenv(COVERAGE_V2_FORCE_OFF_ENV, "false") or "").strip().casefold()
    return enabled in {"1", "true", "yes", "on"} and force_off not in {"1", "true", "yes", "on"}


def _fold(value: object) -> str:
    text = " ".join(str(value or "").casefold().split())
    return text.translate(str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"}))


def _pack(
    code: str,
    hazard: str,
    controls: tuple[str, str],
    safe_behavior: str,
    *,
    source: dict[str, Any],
) -> dict[str, Any]:
    return {
        "code": code,
        "hazard": hazard,
        "controls": controls,
        "safe_behavior": safe_behavior,
        "sources": [deepcopy(_BASE_SOURCE), deepcopy(source)],
        "coverage_version": COVERAGE_V2_VERSION,
    }


# Rules intentionally require multiple distinctive fragments. This prevents a
# generic word such as "elektrik", "yangın" or "ergonomi" from stealing a
# topic that belongs to another sector. Phase 8 remains the only fallback.
_PHASE9_RULES: tuple[tuple[tuple[str, ...], dict[str, Any]], ...] = (
    # Construction / site work
    (("yuksekte calisma", "dusmeyi onleme", "kurtarma"), _pack(
        "construction-work-at-height",
        "Korunmasız kenar, açıklık veya uygun olmayan erişim üzerinden yüksekte çalışma; yüksekten düşme ve düşme sonrası askıda kalma gibi ağır sonuçlu tehlikeler oluşturur.",
        (
            "İş mümkünse yükseğe çıkmadan planlanmalı; yüksekte çalışma gerekiyorsa güvenli çalışma platformu, korkuluk veya eşdeğer toplu korunma tedbirleri kişisel düşüş durdurma sistemlerinden önce değerlendirilmelidir.",
            "Kullanılacak erişim ve düşmeye karşı koruma sistemi işe uygun seçilmeli; düşme sonrası kurtarma yöntemi ve yetkili müdahale düzeni çalışma başlamadan belirlenmelidir.",
        ),
        "Kenar koruması, güvenli erişim veya planlanan düşmeye karşı koruma/kurtarma düzeni hazır değilse yüksekte çalışmaya başlamamak gerekir.",
        source=_CONSTRUCTION_SOURCE,
    )),
    (("iskele", "merdiven", "platform", "kenar koruma"), _pack(
        "construction-scaffold-access",
        "Eksik, uygunsuz kurulmuş veya değiştirilmiş iskele/platform ile amacına uygun kullanılmayan merdivenler; düşme, devrilme ve malzeme düşmesi riskini artırır.",
        (
            "İskele ve çalışma platformları işe/projeye uygun kurulmalı, güvenli erişim ve kenar koruması sağlanmalı; kullanımdan önce ve güvenliği etkileyen değişikliklerden sonra kontrol edilmelidir.",
            "Merdivenler yalnız uygun koşullarda ve güvenli erişim amacıyla kullanılmalı; doğaçlama platform, yükseltme veya sabitleme yöntemi oluşturulmamalıdır.",
        ),
        "Eksik korkuluk, dengesiz platform, uygunsuz erişim veya yetkisiz değişiklik görüldüğünde iskeleyi/merdiveni kullanmamak ve alanı sorumlu kişiye bildirmek gerekir.",
        source=_CONSTRUCTION_SOURCE,
    )),
    (("kazi", "iksa", "gocuk", "yeralti hatlari"), _pack(
        "construction-excavation",
        "Kazı yüzeyinin veya çevresindeki zeminin kararsızlığı göçük ve gömülmeye; önceden belirlenmeyen yeraltı hatları ise elektrik, gaz, su veya diğer enerji kaynaklı ciddi olaylara yol açabilir.",
        (
            "Kazı başlamadan zemin ve çevre koşulları ile yeraltı tesisleri değerlendirilip işaretlenmeli; gerekli şev, iksa veya eşdeğer göçük önleme sistemi yetkin planlamaya göre kurulmalıdır.",
            "Kazıya güvenli giriş-çıkış sağlanmalı; kazı kenarında yük, araç ve malzeme düzeni zeminin kararlılığını bozmayacak şekilde kontrol edilmeli ve değişen koşullarda yeniden değerlendirme yapılmalıdır.",
        ),
        "İksa/şev bozulması, su girişi, çatlak, zemin hareketi veya bilinmeyen hat şüphesi varsa kazıya girmemek; yeniden kontrol edilmeden çalışmayı sürdürmemek gerekir.",
        source=_CONSTRUCTION_LEGISLATION_SOURCE,
    )),
    (("vinc", "kaldirma ekipmani", "dusen cisim"), _pack(
        "construction-lifting-dropped-objects",
        "Askıdaki yük, uygunsuz kaldırma aksesuarı veya yüksekte sabitlenmemiş malzeme; ezilme, çarpma ve düşen cisim kaynaklı ağır yaralanma riski oluşturur.",
        (
            "Kaldırma operasyonu işe uygun ekipman ve aksesuarlarla planlanmalı; yükün güzergâhı ve çalışma alanı kontrol edilerek insanların askıdaki yükün altında veya salınım bölgesinde bulunması önlenmelidir.",
            "Yüksekteki malzeme, el aleti ve parçalar düşmeye karşı güvenli şekilde tutulmalı; kaldırma ekipmanının kontrolleri ve operatör/işaretçi iletişimi işyeri prosedürüne göre sağlanmalıdır.",
        ),
        "Yük dengesi, aksesuar, iletişim veya çalışma alanı güvenliği doğrulanmadan kaldırmayı başlatmamak ve askıdaki yükün altına girmemek gerekir.",
        source=_CONSTRUCTION_SOURCE,
    )),
    (("santiye ici trafik", "is makineleri", "gecici elektrik"), _pack(
        "construction-traffic-temporary-electric",
        "Şantiye araçları ve iş makinelerinin kör noktaları ile geçici elektrik tesisatındaki hasar, uygunsuz bağlantı veya çevresel etkiler; çarpma, ezilme ve elektrik çarpması tehlikelerini birlikte oluşturabilir.",
        (
            "Yaya ve araç hareketleri mümkün olduğunca ayrılmalı; hız, geri manevra, kör nokta, aydınlatma ve işaretçi gereksinimleri saha trafik planı ile yönetilmelidir.",
            "Geçici elektrik dağıtımı uygun koruma düzenleriyle kurulmalı; kablo, pano, priz ve bağlantılar fiziksel hasar ve yetkisiz müdahaleden korunmalı, yalnız yetkili kişilerce kontrol edilmelidir.",
        ),
        "Belirlenmiş yaya yolunu terk etmemek; hasarlı kablo/pano veya güvenli olmayan araç manevrası görüldüğünde tehlikeli alana girmeden işi durdurup bildirmek gerekir.",
        source=_CONSTRUCTION_LEGISLATION_SOURCE,
    )),

    # Warehouse / logistics
    (("forklift", "transpalet", "yaya trafigi"), _pack(
        "logistics-forklift-pedestrian",
        "Forklift ve transpaletlerin yaya ile aynı alanda kontrolsüz hareketi; özellikle kör nokta, geri manevra ve kavşaklarda çarpma ve ezilme riski oluşturur.",
        (
            "Yaya ve araç yolları mümkün olduğunca ayrılmalı; hız sınırları, geçiş öncelikleri, kör nokta kontrolleri ve yük görüşünü etkileyen durumlar saha trafik düzeninde açıkça belirlenmelidir.",
            "Araçlar yalnız yetkili kişilerce kullanılmalı; günlük kullanım öncesi kontroller, güvenli park ve yükün görüş/dengeyi bozmayacak şekilde taşınması sağlanmalıdır.",
        ),
        "Forklift sürücüsüyle güvenli iletişim kurulmadan araç hareket alanına girmemek ve belirlenmiş yaya güzergâhını kullanmak gerekir.",
        source=_LOGISTICS_SOURCE,
    )),
    (("raf sistemleri", "istif", "yuk dusmesi"), _pack(
        "logistics-racking-stacking",
        "Hasarlı veya aşırı/uygunsuz yüklenmiş raflar ile kararsız istifler; malzeme devrilmesi, yük düşmesi ve ezilme riski oluşturur.",
        (
            "Raf sistemleri üretici/işyeri kurallarına uygun kullanılmalı; hasar, ankraj, koruyucu ve yükleme durumu düzenli kontrol edilerek darbeye uğrayan veya şüpheli bölüm güvenli hale getirilmelidir.",
            "İstif yüksekliği, yük dağılımı, palet durumu ve malzeme geometrisi kararlılığı bozmayacak şekilde planlanmalı; yaya geçişleri düşebilecek yüklerden korunmalıdır.",
        ),
        "Hasarlı raf, kırık palet veya eğilmiş/kararsız istif görüldüğünde malzemeyi çekmeye ya da düzeltmeye çalışmadan alanı güvenli hale getirip bildirmek gerekir.",
        source=_LOGISTICS_SOURCE,
    )),
    (("yukleme rampasi", "dorse", "arac sabitleme"), _pack(
        "logistics-loading-dock",
        "Yükleme rampasında dorse/araç hareketi, rampa kenarı ve seviye farkı; araç-rampa ayrılması, düşme ve ezilme riskleri oluşturabilir.",
        (
            "Yükleme başlamadan araç/dorse güvenli konuma alınmalı ve işyerinin belirlediği sabitleme/ayırma yöntemi uygulanmalı; sürücü ile depo operasyonu arasında hareket izni açıkça koordine edilmelidir.",
            "Rampa, köprü/plaka ve yükleme alanı kapasite ve fiziksel durum açısından uygun olmalı; rampa kenarı ile araç-yaya hareketleri işaretleme ve fiziksel düzenlemelerle kontrol edilmelidir.",
        ),
        "Araç sabitlemesi, rampa bağlantısı veya sürücü-depo iletişimi doğrulanmadan yükleme ekipmanıyla dorseye girmemek gerekir.",
        source=_LOGISTICS_SOURCE,
    )),
    (("elle tasima", "kaldirma yardimcilari", "ergonomi"), _pack(
        "logistics-manual-handling",
        "Ağır, hacimli, dengesiz veya sık tekrarlanan elle taşıma işleri; bel, omuz ve diğer kas-iskelet sisteminde zorlanma ve akut yaralanma riski oluşturur.",
        (
            "Yükün ağırlığı, şekli, kavrama olanağı, taşıma mesafesi ve çalışma ortamı değerlendirilerek mümkün olduğunda mekanik kaldırma/taşıma yardımcıları veya ekip çalışması kullanılmalıdır.",
            "İş yüksekliği ve yerleşim gereksiz eğilme, uzanma ve dönmeyi azaltacak şekilde düzenlenmeli; tekrar ve süre iş organizasyonuyla kontrol edilmelidir.",
        ),
        "Güvenli kaldırma sınırını aşan, kavranamayan veya görüşü kapatan yükü tek başına taşımamak; uygun yardımcı ekipman veya destek istemek gerekir.",
        source=_LOGISTICS_SOURCE,
    )),
    (("aku sarj alani", "yangin", "acil cikis"), _pack(
        "logistics-battery-charging-fire",
        "Akü şarjı sırasında elektriksel arıza, elektrolit teması ve bazı akü tiplerinde yanıcı gaz oluşumu; yangın, patlama ve kimyasal maruziyet risklerini artırabilir.",
        (
            "Şarj alanı uygun havalandırma, elektrik güvenliği ve ateşleme kaynağı kontrolüyle düzenlenmeli; kullanılan akü/şarj ekipmanının talimatları ve kimyasal acil durum gereklilikleri uygulanmalıdır.",
            "Yangın ekipmanı ve acil çıkışlar erişilebilir tutulmalı; şarj alanında uygunsuz depolama, sigara/açık alev ve kaçış yolunu kapatan malzeme bulunmamalıdır.",
        ),
        "Aşırı ısınma, koku, sızıntı, hasarlı kablo veya havalandırma arızasında şarjı normal sürdürmemek; alan prosedürüne göre güvenli durdurma ve bildirim yapmak gerekir.",
        source=_LOGISTICS_SOURCE,
    )),

    # Hospital / healthcare
    (("biyolojik etken", "enfeksiyon kontrolu", "izolasyon"), _pack(
        "health-biological-exposure",
        "Kan, vücut sıvıları, damlacık/aerosol veya kontamine yüzey ve malzemeler üzerinden biyolojik etkenlere maruziyet; çalışanlarda enfeksiyon riski oluşturabilir.",
        (
            "Maruziyet yolları risk değerlendirmesinde belirlenmeli; uygun izolasyon, mühendislik/organizasyon tedbirleri, el hijyeni ve işe uygun kişisel koruyucu donanım birlikte uygulanmalıdır.",
            "Temizlik, dezenfeksiyon, atık yönetimi ve maruziyet sonrası bildirim/tıbbi değerlendirme süreçleri işyerinin enfeksiyon kontrol prosedürleriyle uyumlu yürütülmelidir.",
        ),
        "İzolasyon veya koruyucu tedbirleri belirsiz bir alana kontrolsüz girmemek; maruziyet veya koruma ihlalini derhal işyeri prosedürüne göre bildirmek gerekir.",
        source=_HEALTH_SOURCE,
    )),
    (("kesici-delici", "tibbi atik"), _pack(
        "health-sharps-medical-waste",
        "İğne, bistüri ve diğer kesici-delici tıbbi araçlar; yaralanma ile birlikte kan yoluyla bulaşan etkenlere maruziyet riski oluşturabilir; uygunsuz atık yönetimi riski yayabilir.",
        (
            "Kesici-delici araçlar işlem sırasında güvenli teknikle kullanılmalı ve kullanım sonrası uygun, delinmeye dayanıklı atık kabına gecikmeden bırakılmalı; elle yeniden düzenleme ve kontrolsüz taşıma önlenmelidir.",
            "Tıbbi atıklar türüne uygun kap/torba ve kapalı taşıma düzeniyle yönetilmeli; atık alanlarına yetkisiz erişim ve taşma/dökülme engellenmelidir.",
        ),
        "Kesici-delici yaralanmayı önemsiz saymamak; yaralanma veya kontamine temas sonrası işyerinin maruziyet bildirim ve sağlık değerlendirme prosedürünü hemen uygulamak gerekir.",
        source=_HEALTH_SOURCE,
    )),
    (("hasta tasima", "ergonomi", "siddet"), _pack(
        "health-patient-handling-violence",
        "Hastanın manuel kaldırılması veya kontrolsüz transferi kas-iskelet zorlanmasına; hasta/yakın kaynaklı saldırgan davranışlar ise fiziksel ve psikososyal yaralanmalara yol açabilir.",
        (
            "Hasta mobilitesi ve transfer gereksinimi önceden değerlendirilmeli; uygun kaldırma/transfer yardımcıları, ekip desteği ve çalışma alanı düzeni kullanılarak elle kaldırma azaltılmalıdır.",
            "Şiddet riski bulunan alanlarda iletişim, çağrı/destek, güvenli kaçış ve olay bildirimi süreçleri tanımlanmalı; çalışan tek başına kontrol edemeyeceği çatışmaya zorlanmamalıdır.",
        ),
        "Transfer güvenli değilse tek başına kaldırmaya girişmemek; şiddet riski yükseldiğinde kişisel müdahaleyi büyütmeden destek çağırmak ve belirlenmiş güvenlik prosedürünü izlemek gerekir.",
        source=_HEALTH_SOURCE,
    )),
    (("ilac", "dezenfektan", "sterilizasyon", "radyasyon"), _pack(
        "health-chemical-sterilization-radiation",
        "İlaç ve dezenfektan kimyasalları, sterilizasyon ajanları ve iyonlaştırıcı/diğer radyasyon kaynakları farklı maruziyet yollarıyla akut veya birikimli sağlık riski oluşturabilir.",
        (
            "Her ajan/kaynak kendi risk değerlendirmesi, güvenlik bilgi/talimatı ve yetkilendirme düzenine göre kullanılmalı; kapalı sistem, havalandırma, mesafe/zaman/kalkanlama gibi kaynağa özgü mühendislik kontrolleri önceliklendirilmelidir.",
            "Depolama, hazırlama, dozlama, sterilizasyon ve atık süreçleri ayrıştırılmalı; gerekli ölçüm/izleme, sağlık gözetimi ve kişisel koruyucu donanım kaynağın niteliğine göre belirlenmelidir.",
        ),
        "Kaynağın etiketi/talimatı, havalandırması, koruyucusu veya yetkilendirme koşulu belirsizse işlemi sürdürmemek ve sorumlu birimden doğrulama istemek gerekir.",
        source=_HEALTH_SOURCE,
    )),
    (("acil durum", "tahliye", "guvenli saglik hizmeti"), _pack(
        "health-emergency-evacuation",
        "Yangın, afet, kimyasal/biyolojik olay veya altyapı kesintisi sırasında hastaların hareket kabiliyeti ve kritik bakım gereksinimleri tahliyeyi diğer işyerlerine göre daha karmaşık hale getirebilir.",
        (
            "Acil durum planı; hasta/çalışan/ziyaretçi hareketi, kritik birimler, alternatif güzergâhlar, destek gerektiren kişiler ve görevli ekiplerin koordinasyonunu içerecek şekilde işyerinin fiilî koşullarına göre hazırlanmalıdır.",
            "Kaçış yolları ve acil ekipman erişilebilir tutulmalı; görevli personel planı bilmeli ve tatbikat/olaylardan elde edilen bulgularla plan güncellenmelidir.",
        ),
        "Acil durumda kişisel inisiyatifle plan dışı tahliye rotası oluşturmamak; hasta güvenliğini ve görev dağılımını gözeterek işyerinin komuta ve tahliye prosedürünü uygulamak gerekir.",
        source=_HEALTH_SOURCE,
    )),
)


def resolve_phase9_topic_knowledge(topic: object) -> dict[str, Any] | None:
    normalized = _fold(topic)
    for required_fragments, pack in _PHASE9_RULES:
        if all(fragment in normalized for fragment in required_fragments):
            return deepcopy(pack)
    return None


def phase9_coverage_readiness(topics: list[object]) -> dict[str, Any]:
    matches = [resolve_phase9_topic_knowledge(topic) for topic in topics]
    return {
        "enabled": phase9_active(),
        "version": COVERAGE_V2_VERSION,
        "topic_count": len(topics),
        "phase9_supported_count": sum(item is not None for item in matches),
        "phase9_full_profile": len(topics) == 5 and all(item is not None for item in matches),
        "phase9_supported_topics": [str(topics[i]) for i, item in enumerate(matches) if item is not None],
    }


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mark_manifest_for_phase9_ui(manifest: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(manifest)
    topics = list(result.get("training_topics") or [])
    coverage = phase9_coverage_readiness(topics)
    result["rendering"] = {
        **dict(result.get("rendering") or {}),
        "instructor_mode_ui": INSTRUCTOR_UI_VERSION,
        "coverage_v2_active": True,
    }
    result["coverage_v2"] = coverage
    result.pop("content_hash", None)
    result["content_hash"] = _canonical_hash(result)
    return result


def install_training_presentation_phase9() -> dict[str, str]:
    """Install idempotent exact-first Phase 9 wrappers after Phase 8."""
    from app.services import training_presentation_phase8 as phase8

    resolver_state = "already-active"
    current_resolver: Callable[[object], dict[str, Any] | None] = phase8.resolve_topic_knowledge
    if not getattr(current_resolver, "_phase9_coverage_v2_active", False):
        original_resolver = current_resolver

        def resolver_wrapper(topic: object) -> dict[str, Any] | None:
            if phase9_active():
                curated = resolve_phase9_topic_knowledge(topic)
                if curated is not None:
                    return curated
            return original_resolver(topic)

        resolver_wrapper._phase9_coverage_v2_active = True
        phase8.resolve_topic_knowledge = resolver_wrapper
        resolver_state = "active"

    manifest_state = "already-active"
    current_enricher: Callable[..., dict[str, Any]] = phase8.enrich_manifest_with_traceability
    if not getattr(current_enricher, "_phase9_coverage_v2_active", False):
        original_enricher = current_enricher

        def enrich_wrapper(manifest: dict[str, Any], snapshot: Any) -> dict[str, Any]:
            result = original_enricher(manifest, snapshot)
            if not phase9_active():
                return result
            result = mark_manifest_for_phase9_ui(result)
            phase8.validate_manifest_traceability(result)
            return result

        enrich_wrapper._phase9_coverage_v2_active = True
        phase8.enrich_manifest_with_traceability = enrich_wrapper
        manifest_state = "active"

    return {
        "phase9_patch": "active" if "active" in {resolver_state, manifest_state} else "already-active",
        "resolver": resolver_state,
        "manifest": manifest_state,
        "enabled": str(phase9_active()).lower(),
        "coverage": COVERAGE_V2_VERSION,
        "instructor_ui": INSTRUCTOR_UI_VERSION,
    }
