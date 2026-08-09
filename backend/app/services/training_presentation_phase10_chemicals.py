"""Fail-closed curated chemical/paint training coverage for exact-NACE exams.

This additive patch supplies reviewed technical knowledge for the five canonical
``kimyasal_boya`` training topics used by paint, varnish, ink, solvent and
thinner manufacturing NACE records (including 20.30.90). It wraps the Phase 8
resolver only while its own feature flag is enabled. Unsupported topics still
delegate to the existing Phase 9/Phase 8 resolver chain; no cross-sector
fallback is introduced and no historical exam/presentation row is rewritten.
"""
from __future__ import annotations

import os
import unicodedata
from copy import deepcopy
from typing import Any, Callable

CHEMICAL_PACK_ENV = "NACE_TRAINING_PRESENTATION_CHEMICAL_PACK_ENABLED"
CHEMICAL_PACK_FORCE_OFF_ENV = "NACE_TRAINING_PRESENTATION_CHEMICAL_PACK_FORCE_OFF"
CHEMICAL_PACK_VERSION = "nace-training-presentation-chemical-pack-v1"
SOURCE_CHECK_DATE = "2026-08-09"

_BASE_SOURCE = {
    "title": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
    "url": "https://www.csgb.gov.tr/media/2670/6331_isgkanunu_tr.pdf",
    "reference": "Risk değerlendirmesi, bilgilendirme, eğitim ve önleme yükümlülükleri",
    "effective_date": "2012-06-30",
    "checked_at": SOURCE_CHECK_DATE,
}
_ISGGM_CHEMICAL_SOURCE = {
    "title": "ÇSGB İSGGM Yayınlar ve Afişler – Kimyasal Güvenlik",
    "url": "https://www.csgb.gov.tr/isggm/yayinlar-ve-afisler/",
    "reference": "Malzeme Güvenlik Bilgi Formları (MSDS), tehlikeli malzeme etiketleme ve kimyasal risk yayınları",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}
_ISGUM_CHEMICAL_SOURCE = {
    "title": "ÇSGB İSGÜM İSG Dokümanları – Boya ve Kimyasal Güvenliği",
    "url": "https://www.csgb.gov.tr/isgum/hizli-erisim/%C4%B1sg-dokumanlari/",
    "reference": "Boya sektöründe solvent kullanımı, patlayıcı ortamlar, endüstriyel havalandırma ve kimyasal yangın/patlama riskleri",
    "effective_date": None,
    "checked_at": SOURCE_CHECK_DATE,
}


def chemical_pack_active() -> bool:
    enabled = str(os.getenv(CHEMICAL_PACK_ENV, "false") or "").strip().casefold()
    force_off = str(os.getenv(CHEMICAL_PACK_FORCE_OFF_ENV, "false") or "").strip().casefold()
    return enabled in {"1", "true", "yes", "on"} and force_off not in {"1", "true", "yes", "on"}


def _fold(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in raw if not unicodedata.combining(char))
    text = " ".join(without_marks.split())
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
        "coverage_version": CHEMICAL_PACK_VERSION,
    }


_CHEMICAL_RULES: tuple[tuple[tuple[str, ...], dict[str, Any]], ...] = (
    (("kimyasal etiketler", "sds", "maruziyet yollari"), _pack(
        "chemical-label-sds-exposure",
        "Etiketsiz veya yanlış tanımlanmış kimyasallar ile Güvenlik Bilgi Formu (SDS) bilgisi bilinmeden yapılan çalışma; solunum, cilt/göz teması veya yutma yoluyla tehlikeli maruziyete ve hatalı acil müdahaleye neden olabilir.",
        (
            "Kimyasal kullanılmadan önce ürün etiketi ve güncel SDS incelenmeli; tehlike sınıfları, maruziyet yolları, güvenli kullanım, depolama, ilk yardım ve yangın/dökülme bilgileri iş talimatına yansıtılmalıdır.",
            "İkincil kaplar dâhil kimyasal kapları içeriği ve tehlikeleri anlaşılır biçimde tanımlanmalı; maruziyet kaynağında kapatma, yerel emiş ve uygun iş organizasyonu kişisel koruyucudan önce değerlendirilmelidir.",
        ),
        "Etiketi olmayan, içeriği belirsiz veya SDS bilgisine erişilemeyen kimyasalı kullanmamak; güvenli kullanım ve maruziyet kontrolü doğrulanmadan işe başlamamak gerekir.",
        source=_ISGGM_CHEMICAL_SOURCE,
    )),
    (("solvent", "izosiyanat", "aerosol", "toksik buhar"), _pack(
        "chemical-solvent-isocyanate-vapour",
        "Solvent, izosiyanat ve aerosol içeren boya/kaplama prosesleri; uçucu ve toksik buhar, sis veya aerosol yoluyla solunum maruziyeti ile cilt/göz temasına, bazı maddelerde duyarlanmaya ve ciddi sağlık etkilerine yol açabilir.",
        (
            "Mümkün olan yerde daha az tehlikeli madde/proses seçimi, kapalı sistem ve kirleticiyi oluştuğu noktada yakalayan yerel emiş havalandırması uygulanmalı; proses açıklıkları ve gereksiz buharlaşma azaltılmalıdır.",
            "Maruziyet değerlendirmesi ve ölçüm sonuçlarına göre çalışma süresi, hijyen, cilt-göz koruması ve gerekiyorsa uygun solunum koruyucu belirlenmeli; havalandırma performansı düzenli kontrol edilmelidir.",
        ),
        "Emiş sistemi çalışmıyorsa, yoğun koku/buhar/sis görülüyorsa veya beklenmeyen sağlık belirtisi oluşuyorsa çalışmayı normal kabul etmeden durdurup yetkili kişiye bildirmek gerekir.",
        source=_ISGUM_CHEMICAL_SOURCE,
    )),
    (("yanici atmosfer", "statik elektrik", "ex-proof"), _pack(
        "chemical-flammable-atmosphere-static-ex",
        "Yanıcı solvent buharlarının hava ile tehlikeli derişime ulaşması ve statik elektrik, kıvılcım, sıcak yüzey veya uygun olmayan elektrik ekipmanı gibi ateşleme kaynaklarıyla karşılaşması yangın veya patlamaya neden olabilir.",
        (
            "Yanıcı buhar oluşumu kapalı proses ve yeterli havalandırmayla sınırlandırılmalı; patlayıcı ortam riski değerlendirilerek tehlikeli bölgeler ve ateşleme kaynakları kontrol altına alınmalıdır.",
            "Yanıcı sıvı transferinde uygun iletken bağlantı, eşpotansiyel bağlama/topraklama uygulanmalı; elektrikli ekipman belirlenen patlayıcı ortam bölgesine ve koruma seviyesine uygun seçilmelidir.",
        ),
        "Havalandırma arızası, solvent sızıntısı, uygunsuz elektrik ekipmanı veya bağlama/topraklama eksikliği varsa işlemi başlatmamak ve ateşleme kaynağı oluşturmadan alanı güvenli prosedüre göre yönetmek gerekir.",
        source=_ISGUM_CHEMICAL_SOURCE,
    )),
    (("uyumsuz kimyasallar", "depolanmasi", "transferi"), _pack(
        "chemical-storage-compatibility-transfer",
        "Birbiriyle tehlikeli reaksiyon verebilen kimyasalların birlikte depolanması veya yanlış kaba/hatta aktarılması; ısı açığa çıkması, sıçrama, toksik gaz oluşumu, yangın, patlama ve çevresel yayılım riski oluşturabilir.",
        (
            "Depolama ve transfer SDS bilgileri ile kimyasal uyumluluğa göre planlanmalı; asit, baz, oksitleyici, yanıcı ve reaktif maddeler gerekli ayırma ve uygun ikincil sızdırmazlık tedbirleriyle muhafaza edilmelidir.",
            "Transfer için kimyasala uyumlu kap, pompa, hortum ve bağlantılar kullanılmalı; bütün kaplar doğru etiketli tutulmalı, dolum alanında taşma/sızıntı kontrolü ve güvenli havalandırma sağlanmalıdır.",
        ),
        "Kimyasalın kimliği, uyumluluğu, hedef kabı veya transfer hattı doğrulanmadan aktarma yapmamak; şüpheli veya hasarlı kap/bağlantıyı kullanımdan çıkarmak gerekir.",
        source=_ISGUM_CHEMICAL_SOURCE,
    )),
    (("dokulme", "sizinti", "acil dus", "mudahale"), _pack(
        "chemical-spill-leak-emergency-shower",
        "Kimyasal dökülme veya sızıntı; cilt/göz sıçraması, toksik veya yanıcı buhar yayılması, kayma, yangın/patlama ve çevresel yayılım gibi birden fazla acil tehlike oluşturabilir.",
        (
            "Dökülme müdahalesi maddenin SDS bilgisine ve işyeri acil prosedürüne göre planlanmalı; uygun sızıntı kontrolü, uyumlu emici/toplama ekipmanı, kişisel koruyucular ve güvenli atık kabı hazır bulundurulmalıdır.",
            "Korozif veya ciddi sıçrama riski bulunan çalışma alanlarında erişilebilir göz duşu/acil duş ve açık kaçış yolu sağlanmalı; acil ekipmanın önü kapatılmamalı ve işlerliği kontrol edilmelidir.",
        ),
        "Dökülen kimyasalı çıplak elle, uygunsuz emiciyle veya kanalizasyona yıkayarak temizlememek; alanı izole edip SDS ve acil durum prosedürüne göre yetkili müdahaleyi başlatmak gerekir.",
        source=_ISGUM_CHEMICAL_SOURCE,
    )),
)


def resolve_chemical_topic_knowledge(topic: object) -> dict[str, Any] | None:
    normalized = _fold(topic)
    for needles, pack in _CHEMICAL_RULES:
        if all(needle in normalized for needle in needles):
            return deepcopy(pack)
    return None


def chemical_coverage_readiness(topics: list[object]) -> dict[str, Any]:
    matches = [resolve_chemical_topic_knowledge(topic) for topic in topics]
    missing = [str(topics[i]) for i, item in enumerate(matches) if item is None]
    return {
        "enabled": chemical_pack_active(),
        "version": CHEMICAL_PACK_VERSION,
        "topic_count": len(topics),
        "supported_count": sum(item is not None for item in matches),
        "full_profile": len(topics) == 5 and not missing,
        "missing_topics": missing,
    }


def install_training_presentation_phase10_chemicals() -> dict[str, str]:
    """Install the chemical exact-first resolver wrapper idempotently."""
    from app.services import training_presentation_phase8 as phase8

    current: Callable[[object], dict[str, Any] | None] = phase8.resolve_topic_knowledge
    if getattr(current, "_phase10_chemical_pack_active", False):
        return {
            "chemical_pack": "already-active",
            "enabled": str(chemical_pack_active()).lower(),
            "version": CHEMICAL_PACK_VERSION,
        }

    original = current

    def resolver_wrapper(topic: object) -> dict[str, Any] | None:
        if chemical_pack_active():
            curated = resolve_chemical_topic_knowledge(topic)
            if curated is not None:
                return curated
        return original(topic)

    resolver_wrapper._phase10_chemical_pack_active = True
    phase8.resolve_topic_knowledge = resolver_wrapper
    return {
        "chemical_pack": "active",
        "enabled": str(chemical_pack_active()).lower(),
        "version": CHEMICAL_PACK_VERSION,
    }
