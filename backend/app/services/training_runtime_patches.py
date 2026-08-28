"""Source-controlled runtime patches for approved training behavior.

The project historically rewrote Python source files during Render builds. This
module installs the same approved behavior in memory, idempotently, so the code
executed in production remains traceable to the repository.
"""
from __future__ import annotations

from functools import wraps
import sys
from typing import Any

OLD_HEADINGS = (
    "4. FAALİYETİN GENEL TEHLİKE VE RİSKLERİ",
    "4. Faaliyetin Genel Tehlike ve Riskleri",
    "4. Faaliyetin genel tehlike ve riskleri",
    "FAALİYETİN GENEL TEHLİKE VE RİSKLERİ",
    "Faaliyetin genel tehlike ve riskleri",
)
NEW_HEADING = "4. İŞE VE İŞYERİNE ÖZGÜ RİSKLER VE RİSK DEĞERLENDİRMESİNE DAYALI KONULAR"

SECTOR_QUESTION_ALIASES = {
    "elektrik_elektronik_uretim": "enerji_jenerator_trafo",
    "elektronik": "enerji_jenerator_trafo",
    "elektrik_tesisat_pano_montaj": "enerji_jenerator_trafo",
    "elektrik_bakim": "enerji_jenerator_trafo",
    "aku_uretimi": "aku_uretimi",
    "karayolu_tasimacilik": "depo_lojistik",
    "nakliye_karayolu_tasimaciligi": "depo_lojistik",
    "dagitim_kargo_kurye": "depo_lojistik",
    "e_ticaret_depo_fulfillment": "depo_lojistik",
    "ticaret_aracilik_ofis": "ofis_idari_hizmetler",
    "tarimsal_urun_toptan": "tarim_ziraat",
    "canli_hayvan_toptan": "tarim_ziraat",
    "gida_toptan_depo": "gida_uretimi_isleme",
    "tekstil_deri_toptan": "tekstil",
    "elektrik_elektronik_toptan": "elektrik_bakim",
    "kimyasal_toptan_depo": "kimya_kimyasal_uretim",
    "ecza_medikal_toptan": "saglik",
    "mobilya_ev_esyasi_toptan": "agac_isleri_marangozluk",
    "makine_ekipman_toptan": "makine_imalat",
    "otomotiv_toptan": "otomotiv",
    "yakit_toptan_depo": "kimya_kimyasal_uretim",
    "yapi_malzemeleri_toptan": "F",
    "atik_hurda_toptan": "atik_geri_donusum",
    "genel_toptan_depo": "depo_lojistik",
    "kimyasal_perakende": "kimya_kimyasal_uretim",
    "fabrika_genel_imalat": "genel_uretim",
}

BATTERY_TRAINING_TOPICS = (
    "Kurşun tozu ve dumanı maruziyeti, mühendislik kontrolleri, hijyen ve sağlık gözetimi",
    "Sülfürik asitle güvenli çalışma, sıçrama, dökülme, acil duş ve göz duşu",
    "Akü şarjında hidrojen gazı, havalandırma, patlama ve ateşleme kaynakları",
    "Elektrik, kısa devre, makine güvenliği ve bakımda enerji izolasyonu",
    "Elle taşıma, yangın, acil durum, tahliye ve periyodik kontroller",
)


def _replace_heading(value: Any) -> Any:
    if isinstance(value, str):
        result = value
        for old in OLD_HEADINGS:
            result = result.replace(old, NEW_HEADING)
        return value if result == value else result
    if isinstance(value, list):
        replaced = [_replace_heading(item) for item in value]
        return value if replaced == value else replaced
    if isinstance(value, tuple):
        replaced = tuple(_replace_heading(item) for item in value)
        return value if replaced == value else replaced
    if isinstance(value, dict):
        replaced = {
            _replace_heading(key): _replace_heading(item)
            for key, item in value.items()
        }
        return value if replaced == value else replaced
    return value


def _apply_exact_nace_topic_corrections(training_topics) -> int:
    """Install reviewed exact-NACE topic and technical-risk overrides."""
    topics_builder = getattr(training_topics, "_topics_with_dk", None)
    corrections = getattr(training_topics, "SEKTOREL_KONU_DUZELTMELERI", {})
    if not callable(topics_builder):
        raise RuntimeError("Eğitim konu oluşturucusu bulunamadı.")

    changed = 0
    for exact_key, profile_code in list(training_topics.SEKTOR_PROFIL.items()):
        corrected = corrections.get(profile_code)
        if not corrected:
            continue
        expected = topics_builder(list(corrected))
        if training_topics.SEKTOREL_EGITIM_KONULARI.get(exact_key) != expected:
            training_topics.SEKTOREL_EGITIM_KONULARI[exact_key] = expected
            changed += 1

    battery_topics = topics_builder(list(BATTERY_TRAINING_TOPICS))
    training_topics.SEKTOR_PROFIL["nace_27_20_01"] = "aku_uretimi"
    training_topics.SEKTOREL_EGITIM_KONULARI["aku_uretimi"] = battery_topics
    training_topics.SEKTOREL_EGITIM_KONULARI["nace_27_20_01"] = battery_topics

    from app.services.training_nace_risk_catalog import apply_reviewed_risk_profiles

    apply_reviewed_risk_profiles()
    return changed


def _patch_sector_profile_resolution() -> str:
    """Preserve stored catalog keys while retaining legacy profile resolution."""
    from app.services import training_topics

    _apply_exact_nace_topic_corrections(training_topics)
    current = training_topics.sektor_kodu_cozumle
    if getattr(current, "_source_controlled_sector_resolver_active", False):
        return "already-active"

    def source_controlled_resolver(sektor: str | None) -> str:
        if not sektor:
            return "genel_uretim"
        raw = sektor.strip()
        # Stored exact catalog keys remain exact so the training identity is not
        # destroyed. Legacy raw numeric NACE input keeps the approved historical
        # content-profile behavior for backward compatibility.
        if raw in training_topics.SEKTOREL_EGITIM_KONULARI:
            return raw
        if raw in training_topics.SEKTOR_PROFIL:
            return raw
        nace_code = "nace_" + raw.replace(".", "_")
        if nace_code in training_topics.SEKTOR_PROFIL:
            return training_topics.SEKTOR_PROFIL[nace_code]
        if nace_code in training_topics.SEKTOREL_EGITIM_KONULARI:
            return nace_code
        for kod, ad in training_topics.SEKTOR_SECENEKLERI:
            if ad.casefold() == raw.casefold():
                return kod
        for kod, ad in training_topics.PROFIL_ADLARI.items():
            if ad.casefold() == raw.casefold():
                return kod
        if raw in ("01", "02", "03", "04", "05"):
            return "genel_uretim"
        return "genel_uretim"

    source_controlled_resolver._source_controlled_sector_resolver_active = True
    training_topics.sektor_kodu_cozumle = source_controlled_resolver

    # Uvicorn/sitecustomize dışı test veya yardımcı başlangıçlarında daha önce
    # import edilmiş doğrudan fonksiyon referanslarını da aynı davranışa bağla.
    for module_name in (
        "app.services.training_pdfs",
        "app.services.training_question_bank",
        "app.api.trainings",
    ):
        module = sys.modules.get(module_name)
        if module is not None and hasattr(module, "sektor_kodu_cozumle"):
            setattr(module, "sektor_kodu_cozumle", source_controlled_resolver)
    return "active"


def _patch_training_topics() -> str:
    from app.services import training_topics

    for name, value in list(vars(training_topics).items()):
        if name.startswith("__"):
            continue
        replaced = _replace_heading(value)
        if replaced is not value:
            setattr(training_topics, name, replaced)

    wrapped_count = 0
    for function_name in (
        "egitim_konularini_hazirla",
        "katilim_formu_konu_ozeti",
    ):
        original = getattr(training_topics, function_name, None)
        if not callable(original) or getattr(original, "_fourth_heading_patched", False):
            continue

        @wraps(original)
        def wrapped(*args, __original=original, **kwargs):
            return _replace_heading(__original(*args, **kwargs))

        wrapped._fourth_heading_patched = True
        setattr(training_topics, function_name, wrapped)
        wrapped_count += 1

    return "active" if wrapped_count else "already-active"


def _patch_question_bank_candidates() -> str:
    """Install approved sector aliases and safe general-production fallback."""
    from app.services import training_question_bank as question_bank

    # FastAPI açık kurulumu sitecustomize sonrasında çalışsa bile yayın
    # doğrulamasının güncel profil kümesini görmesini sağla.
    question_bank._SECTOR_VALUES = (
        frozenset(question_bank._SECTOR_VALUES)
        | frozenset(question_bank.SEKTOR_PROFIL)
        | frozenset(question_bank.SEKTOR_PROFIL.values())
        | frozenset(question_bank.SEKTOREL_EGITIM_KONULARI)
    )

    current = question_bank._candidate_buckets
    if getattr(current, "_source_controlled_candidate_buckets_active", False):
        return "already-active"

    def source_controlled_candidate_buckets(db, training):
        rows = question_bank._published_questions_for_training(db, training)
        ctx = question_bank._context(training)
        buckets = question_bank._buckets_for_context(rows, ctx)
        if len(buckets["sector"]) >= question_bank.BUCKET_TARGETS["sector"]:
            return buckets

        preferred = (
            SECTOR_QUESTION_ALIASES.get(ctx["sector_code"])
            or SECTOR_QUESTION_ALIASES.get(ctx["sector"])
        )
        candidates = [preferred, "genel_uretim"] if preferred else ["genel_uretim"]
        existing = {row.id for row in buckets["sector"]}
        for scope_value in candidates:
            if not scope_value:
                continue
            fallback_ctx = dict(ctx)
            fallback_ctx["sector"] = scope_value
            fallback_ctx["sector_code"] = scope_value
            for row in question_bank._buckets_for_context(rows, fallback_ctx)["sector"]:
                if row.id not in existing:
                    buckets["sector"].append(row)
                    existing.add(row.id)
                if len(buckets["sector"]) >= question_bank.BUCKET_TARGETS["sector"]:
                    return buckets
        return buckets

    source_controlled_candidate_buckets._source_controlled_candidate_buckets_active = True
    question_bank._candidate_buckets = source_controlled_candidate_buckets
    return "active"


def _patch_certificate_renderer() -> str:
    from app.services import training_pdfs
    from app.services.training_height_2026 import (
        apply_height_training_profile_2026,
        draw_height_certificate_page,
        is_height_training,
    )
    from app.services.training_pdf_premium import draw_certificate_page

    # Özel profil yetki/dayanak düzeltmesi uygulama açılışında bir kez yüklenir.
    # Sözlükler yerinde güncellendiği için schema/API aynı kaynakları görür.
    apply_height_training_profile_2026()

    current = training_pdfs._draw_certificate_page
    if getattr(current, "_premium_renderer_active", False):
        return "already-active"

    @wraps(current)
    def premium_renderer(*args, **kwargs):
        kwargs["tp"] = training_pdfs
        training = kwargs.get("training")
        curriculum = kwargs.get("curriculum") or {}
        if is_height_training(training, curriculum):
            return draw_height_certificate_page(*args, **kwargs)
        return draw_certificate_page(*args, **kwargs)

    premium_renderer._premium_renderer_active = True
    training_pdfs._draw_certificate_page = premium_renderer
    return "active"


def install_training_runtime_patches() -> dict[str, Any]:
    """Install approved training behavior idempotently and without file writes."""
    from app.services.remote_training_live_video_sync import (
        install_remote_training_live_video_sync,
    )
    from app.services.remote_training_storage_guard import (
        install_remote_training_storage_guard,
    )
    from app.services.training_nace_classification import (
        install_training_nace_snapshot_hooks,
    )

    return {
        "sector_profiles": _patch_sector_profile_resolution(),
        "topics": _patch_training_topics(),
        "question_candidates": _patch_question_bank_candidates(),
        "premium_certificate": _patch_certificate_renderer(),
        "nace_snapshots": install_training_nace_snapshot_hooks(),
        "remote_training_storage_guard": install_remote_training_storage_guard(),
        "remote_training_live_video_sync": install_remote_training_live_video_sync(),
    }
