"""Onaylı soru bankasından denetlenebilir, sabit sınav kopyası üretimi."""
from __future__ import annotations

import hashlib
import json
import random
import re
import secrets
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    TrainingExamSnapshot,
    TrainingExamSnapshotItem,
    TrainingQuestion,
    TrainingQuestionScope,
    TrainingSession,
)
from app.services.special_training_profiles import resolve_special_profile_key
from app.services.training_topics import (
    SEKTOR_PROFIL,
    SEKTOREL_EGITIM_KONULARI,
    sektor_kodu_cozumle,
    sectors_list_for_api,
)

FOUNDATIONAL_QUESTION_COUNT = 5
EXISTING_QUESTION_COUNT = 15
QUESTION_COUNT = FOUNDATIONAL_QUESTION_COUNT + EXISTING_QUESTION_COUNT
BUCKET_TARGETS = {"common": 5, "technical": 5, "sector": 5}
# Kamuya açılmadan önce her grupta en az üç farklı sınav seti bulunmalıdır.
# Bu eşik sınav üretimindeki asgari 5x3 kuralını değiştirmez; içerik çeşitliliğini
# ayrı ve ölçülebilir bir yayın kriteri olarak raporlar.
RELEASE_BUCKET_TARGETS = {"common": 15, "technical": 15, "sector": 15}
SELECTION_POLICY = "foundation-5-plus-approved-5x3-v1"
CURATED_FALLBACK_POLICY = "foundation-5-plus-approved-db-curated-5x3-v1"
SPECIAL_QUESTION_COUNT = 20
_SPECIAL_PACKS = {"yuksekte_calisma": "special-yuksekte-calisma.json"}
VALID_HAZARDS = frozenset({"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"})
_NACE_PREFIX_RE = re.compile(r"^\d{2}(?:\.\d{2}){0,2}$")
_CATALOG = tuple(sectors_list_for_api())
_NACE_CATALOG = tuple(row for row in _CATALOG if row.get("nace"))
_NACE_VALUES = frozenset(str(row["nace"]) for row in _NACE_CATALOG)
_NACE_SECTION_PREFIXES = {"F": ("41", "42", "43")}
_SECTOR_VALUES = (
    frozenset(SEKTOR_PROFIL)
    | frozenset(SEKTOR_PROFIL.values())
    | frozenset(SEKTOREL_EGITIM_KONULARI)
    | frozenset(_NACE_SECTION_PREFIXES)
)
_CURATED_DATA_DIR = Path(__file__).resolve().parent / "data" / "training_exam_fallback"
_CURATED_HAZARD_PACKS = {
    "Az Tehlikeli": "hazard-low.json",
    "Tehlikeli": "hazard-dangerous.json",
    "Çok Tehlikeli": "hazard-very-dangerous.json",
}
_CURATED_SECTOR_PACKS = tuple(
    path.name for path in sorted(_CURATED_DATA_DIR.glob("sector-*.json"))
)
_CURATED_SECTOR_ALIASES = {
    "akaryakit_lpg_dolum_istasyonu": "kimya_kimyasal_uretim",
    "aricilik": "tarim_ziraat",
    "avukatlik_hukuk_burosu": "ofis_idari_hizmetler",
    "ayakkabi_deri_uretimi": "tekstil",
    "bakim_onarim_teknik_servis": "makine_imalat",
    "balikcilik_su_urunleri": "gida_uretimi_isleme",
    "banka_finans": "ofis_idari_hizmetler",
    "basin_yayin_medya": "ofis_idari_hizmetler",
    "belediye_kamu_hizmetleri": "ofis_idari_hizmetler",
    "beton_cimento_hazir_beton": "F",
    "bilisim_yazilim_it": "ofis_idari_hizmetler",
    "cam_seramik": "genel_uretim",
    "camasirhane_kuru_temizleme": "temizlik",
    "cenaze_hizmetleri": "saglik",
    "dagitim_kargo_kurye": "depo_lojistik",
    "demir_celik_hadde": "metal_isleme_torna_freze",
    "demiryolu": "depo_lojistik",
    "dijital_baski_matbaa": "kimyasal_boya",
    "eczane_medikal_satis": "saglik",
    "ekipman_kiralama": "makine_imalat",
    "elektrik_elektronik_uretim": "elektrik_bakim",
    "elektronik": "elektrik_bakim",
    "fabrika_genel_imalat": "genel_uretim",
    "gemi_insa_tersane": "kaynakli_imalat",
    "guvenlik_hizmetleri": "ofis_idari_hizmetler",
    "guzellik_kuafor_spa": "kimya_kimyasal_uretim",
    "havalimani_yer_hizmetleri": "depo_lojistik",
    "havacilik": "depo_lojistik",
    "hayvanat_bahcesi": "tarim_ziraat",
    "hirdavat_yapi_market": "market_perakende",
    "ilac_farmasotik_uretim": "kimya_kimyasal_uretim",
    "insaat": "F",
    "insaat_santiye": "F",
    "is_makinesi_agir_ekipman": "makine_imalat",
    "kablo_tel_uretimi": "elektrik_bakim",
    "kagit_karton_uretimi": "genel_uretim",
    "kozmetik_temizlik_urunleri": "kimya_kimyasal_uretim",
    "kurye": "depo_lojistik",
    "kuyumculuk_mucevher": "metal_isleme_torna_freze",
    "laboratuvar": "kimya_kimyasal_uretim",
    "laboratuvar_analiz": "kimya_kimyasal_uretim",
    "liman": "depo_lojistik",
    "makine_imalati": "makine_imalat",
    "muhendislik_proje_ofisi": "ofis_idari_hizmetler",
    "organizasyon_etkinlik": "ofis_idari_hizmetler",
    "ormancilik": "agac_isleri_marangozluk",
    "patlayici": "kimya_kimyasal_uretim",
    "petrol_dogalgaz": "kimya_kimyasal_uretim",
    "petrol_rafineri_depolama": "kimya_kimyasal_uretim",
    "reklam_tabela_baski": "genel_uretim",
    "seramik_fayans": "genel_uretim",
    "sigorta_broker": "ofis_idari_hizmetler",
    "spor_tesisi_fitness": "ofis_idari_hizmetler",
    "su_atiksu": "kimya_kimyasal_uretim",
    "telekom": "elektrik_bakim",
    "tip_dis_klinigi": "saglik",
    "turizm_seyahat": "ofis_idari_hizmetler",
    "tutun_urunleri_uretimi": "genel_uretim",
    "universite_yuksekogretim": "egitim_kurumu",
    "veterinerlik": "saglik",
    "yol_altyapi_insaati": "F",
    "yuksekte_calisma_cephe": "F",
}


class QuestionBankError(ValueError):
    pass


class InsufficientQuestionBankError(QuestionBankError):
    def __init__(self, counts: dict[str, int]):
        self.counts = counts
        super().__init__(
            "Bu eğitim için yeterli sayıda onaylanmış soru bulunmuyor. "
            f"Gerekli: {BUCKET_TARGETS}; bulunan: {counts}."
        )


def validate_question_for_publish(question: TrainingQuestion) -> None:
    options = [question.option_a, question.option_b, question.option_c, question.option_d]
    cleaned = [str(value or "").strip() for value in options]
    if any(len(value) < 2 for value in cleaned):
        raise QuestionBankError("Dört seçeneğin tamamı doldurulmalıdır.")
    if len({value.casefold() for value in cleaned}) != 4:
        raise QuestionBankError("Bir sorudaki seçenekler birbirinden farklı olmalıdır.")
    if question.correct_option not in "ABCD":
        raise QuestionBankError("Doğru seçenek A, B, C veya D olmalıdır.")
    if len(str(question.question_text or "").strip()) < 12:
        raise QuestionBankError("Soru metni yeterince açıklayıcı değildir.")
    if len(str(question.answer_explanation or "").strip()) < 12:
        raise QuestionBankError("Doğru cevabın gerekçesi yazılmalıdır.")
    if not question.scopes:
        raise QuestionBankError("En az bir kapsam (ortak, tehlike, sektör veya NACE) seçilmelidir.")
    for scope in question.scopes:
        kind = str(scope.scope_type or "").strip()
        value = str(scope.scope_value or "").strip()
        if kind == "common" and value != "*":
            raise QuestionBankError("Ortak soru kapsamının değeri * olmalıdır.")
        if kind == "hazard" and value not in VALID_HAZARDS:
            raise QuestionBankError("Tehlike sınıfı Az Tehlikeli, Tehlikeli veya Çok Tehlikeli olmalıdır.")
        if kind == "sector" and value not in _SECTOR_VALUES:
            raise QuestionBankError("Sektör kapsamı kayıtlı bir NACE veya sektör profili olmalıdır.")
        if kind == "nace" and not valid_nace_scope(value):
            raise QuestionBankError(
                "NACE kapsamı resmi katalogla eşleşen 2, 4 veya 6 haneli noktalı bir kod olmalıdır."
            )
    if not question.sources:
        raise QuestionBankError("Yayınlanacak her sorunun en az bir doğrulanabilir kaynağı olmalıdır.")
    for source in question.sources:
        if not str(source.title or "").strip() or not str(source.reference or "").strip():
            raise QuestionBankError("Kaynak adı ve mevzuat/madde referansı zorunludur.")
        url = str(source.url or "").strip()
        if not url.startswith("https://"):
            raise QuestionBankError("Kaynak bağlantısı güvenli bir https:// adresi olmalıdır.")


def _nace_value(training: TrainingSession, sector_code: str) -> str:
    if sector_code.startswith("nace_"):
        return sector_code.removeprefix("nace_").replace("_", ".")
    raw = str(training.sector or "").strip()
    return raw if raw and raw[0].isdigit() else ""


def valid_nace_scope(value: str) -> bool:
    """Yalnız resmi katalogda karşılığı olan bölüm/grup/tam NACE öneklerini kabul et."""
    value = str(value or "").strip()
    if not _NACE_PREFIX_RE.fullmatch(value):
        return False
    return any(nace == value or nace.startswith(f"{value}.") for nace in _NACE_VALUES)


def sector_scope_matches(ctx: dict[str, str], scope_value: str) -> bool:
    """İç profil kodlarını ve desteklenen NACE bölüm kodlarını eşleştir."""
    value = str(scope_value or "").strip()
    if value in {ctx["sector"], ctx["sector_code"]}:
        return True
    nace = str(ctx.get("nace") or "").strip()
    return bool(nace) and any(
        nace == prefix or nace.startswith(f"{prefix}.")
        for prefix in _NACE_SECTION_PREFIXES.get(value, ())
    )


def nace_scope_matches(nace: str, scope_value: str) -> bool:
    """30.11 yalnız 30.11 ve altını kapsar; 30.1 gibi belirsiz eşleşmeler yapılamaz."""
    nace = str(nace or "").strip()
    scope_value = str(scope_value or "").strip()
    if not valid_nace_scope(scope_value):
        return False
    return nace == scope_value or nace.startswith(f"{scope_value}.")


def _context(training: TrainingSession) -> dict[str, str]:
    sector_code = sektor_kodu_cozumle(training.sector)
    return {
        "hazard": str(training.hazard_class or "").strip(),
        "sector": SEKTOR_PROFIL.get(sector_code, sector_code),
        "sector_code": sector_code,
        "nace": _nace_value(training, sector_code),
    }


def _active_published_questions(db: Session) -> list[TrainingQuestion]:
    rows = list(
        db.scalars(
            select(TrainingQuestion)
            .options(
                selectinload(TrainingQuestion.scopes),
                selectinload(TrainingQuestion.sources),
            )
            .where(TrainingQuestion.status.in_(("published", "retired")))
            .order_by(TrainingQuestion.question_code, TrainingQuestion.version.desc())
        ).unique().all()
    )
    # Taslak/inceleme sürümü mevcut yayımlanmış sürümü kesmez. Ancak en yeni
    # tamamlanmış sürüm kaldırılmışsa eski sürüm yanlışlıkla yeniden aktif olmaz.
    latest_terminal: dict[str, TrainingQuestion] = {}
    for row in rows:
        latest_terminal.setdefault(row.question_code, row)
    return [row for row in latest_terminal.values() if row.status == "published"]


def _published_questions_for_training(
    db: Session, training: TrainingSession
) -> list[TrainingQuestion]:
    """Load only question versions that can match one training.

    Exam generation used to hydrate the entire published bank plus every scope
    and source, then discard almost all rows in Python. That becomes unbounded
    as NACE coverage grows. Filter by indexed scope columns first while keeping
    terminal-version semantics (a retired latest version cannot reactivate an
    older published version).
    """
    ctx = _context(training)
    sector_values = {
        ctx["sector"],
        ctx["sector_code"],
        "genel_uretim",
        "enerji_jenerator_trafo",
        "aku_uretimi",
        "depo_lojistik",
    }
    nace = ctx["nace"]
    nace_values: set[str] = set()
    if nace:
        parts = nace.split(".")
        nace_values.update(".".join(parts[:length]) for length in range(1, min(3, len(parts)) + 1))
        for section, prefixes in _NACE_SECTION_PREFIXES.items():
            if any(nace == prefix or nace.startswith(f"{prefix}.") for prefix in prefixes):
                sector_values.add(section)

    scope_filters = [
        and_(
            TrainingQuestionScope.scope_type == "common",
            TrainingQuestionScope.scope_value.in_(("", "*")),
        ),
        and_(
            TrainingQuestionScope.scope_type == "hazard",
            TrainingQuestionScope.scope_value == ctx["hazard"],
        ),
        and_(
            TrainingQuestionScope.scope_type == "sector",
            TrainingQuestionScope.scope_value.in_(sector_values),
        ),
    ]
    if nace_values:
        scope_filters.append(
            and_(
                TrainingQuestionScope.scope_type == "nace",
                TrainingQuestionScope.scope_value.in_(nace_values),
            )
        )

    rows = list(
        db.scalars(
            select(TrainingQuestion)
            .join(TrainingQuestion.scopes)
            .options(
                selectinload(TrainingQuestion.scopes),
                selectinload(TrainingQuestion.sources),
            )
            .where(
                TrainingQuestion.status.in_(("published", "retired")),
                or_(*scope_filters),
            )
            .order_by(TrainingQuestion.question_code, TrainingQuestion.version.desc())
        ).unique().all()
    )
    latest_terminal: dict[str, TrainingQuestion] = {}
    for row in rows:
        latest_terminal.setdefault(row.question_code, row)
    return [row for row in latest_terminal.values() if row.status == "published"]


def _buckets_for_context(
    rows: list[TrainingQuestion], ctx: dict[str, str]
) -> dict[str, list[TrainingQuestion]]:
    buckets: dict[str, list[TrainingQuestion]] = defaultdict(list)
    for row in rows:
        matched: set[str] = set()
        for scope in row.scopes:
            kind, value = scope.scope_type, str(scope.scope_value or "").strip()
            if kind == "common" and value in {"", "*"}:
                matched.add("common")
            elif kind == "hazard" and value.casefold() == ctx["hazard"].casefold():
                matched.add("technical")
            elif kind == "sector" and sector_scope_matches(ctx, value):
                matched.add("sector")
            elif kind == "nace" and nace_scope_matches(ctx["nace"], value):
                matched.add("sector")
        # En özel eşleşme önceliklidir; aynı soru iki grupta seçilemez.
        if "sector" in matched:
            buckets["sector"].append(row)
        elif "technical" in matched:
            buckets["technical"].append(row)
        elif "common" in matched:
            buckets["common"].append(row)
    return {name: buckets.get(name, []) for name in BUCKET_TARGETS}


def _scope_index(rows: list[TrainingQuestion]) -> dict:
    """Kapsama raporunda her NACE için tüm soru listesini yeniden taramayı önle."""
    by_id = {row.id: row for row in rows}
    common: set[int] = set()
    hazards: dict[str, set[int]] = defaultdict(set)
    sectors: dict[str, set[int]] = defaultdict(set)
    naces: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        for scope in row.scopes:
            kind = str(scope.scope_type or "").strip()
            value = str(scope.scope_value or "").strip()
            if kind == "common" and value == "*":
                common.add(row.id)
            elif kind == "hazard":
                hazards[value].add(row.id)
            elif kind == "sector":
                sectors[value].add(row.id)
            elif kind == "nace" and valid_nace_scope(value):
                naces[value].add(row.id)
    return {
        "by_id": by_id,
        "common": common,
        "hazards": hazards,
        "sectors": sectors,
        "naces": naces,
    }


def _indexed_bucket_counts(index: dict, ctx: dict[str, str]) -> dict[str, int]:
    """Özgüllük önceliğini koruyarak yalnız küme işlemleriyle sayım yap."""
    sector_ids = set(index["sectors"].get(ctx["sector"], set()))
    sector_ids.update(index["sectors"].get(ctx["sector_code"], set()))
    nace = ctx["nace"]
    if nace:
        for section, prefixes in _NACE_SECTION_PREFIXES.items():
            if any(nace == prefix or nace.startswith(f"{prefix}.") for prefix in prefixes):
                sector_ids.update(index["sectors"].get(section, set()))
        parts = nace.split(".")
        for length in range(1, min(len(parts), 3) + 1):
            sector_ids.update(index["naces"].get(".".join(parts[:length]), set()))
    technical_ids = set(index["hazards"].get(ctx["hazard"], set())) - sector_ids
    common_ids = set(index["common"]) - sector_ids - technical_ids
    return {
        "common": len(common_ids),
        "technical": len(technical_ids),
        "sector": len(sector_ids),
    }


def _candidate_buckets(db: Session, training: TrainingSession) -> dict[str, list[TrainingQuestion]]:
    return _buckets_for_context(_published_questions_for_training(db, training), _context(training))


def _counts_and_status(buckets_or_counts: dict) -> dict:
    counts = {
        name: value if isinstance(value, int) else len(value)
        for name, value in buckets_or_counts.items()
    }
    exam_ready = all(counts[name] >= needed for name, needed in BUCKET_TARGETS.items())
    release_ready = all(
        counts[name] >= needed for name, needed in RELEASE_BUCKET_TARGETS.items()
    )
    return {
        "available": counts,
        "ready": exam_ready,
        "release_ready": release_ready,
        "missing": {
            name: max(0, BUCKET_TARGETS[name] - counts[name]) for name in BUCKET_TARGETS
        },
        "release_missing": {
            name: max(0, RELEASE_BUCKET_TARGETS[name] - counts[name])
            for name in RELEASE_BUCKET_TARGETS
        },
    }


def question_bank_readiness(db: Session, training: TrainingSession) -> dict:
    buckets = _candidate_buckets(db, training)
    status = _counts_and_status(buckets)
    return {
        **status,
        "required": dict(BUCKET_TARGETS),
        "release_required": dict(RELEASE_BUCKET_TARGETS),
        "context": _context(training),
        "policy": SELECTION_POLICY,
    }


def question_bank_coverage(db: Session) -> dict:
    """Tüm resmi NACE faaliyetleri için asgari ve güçlü yayın kapsamını ölç."""
    rows = _active_published_questions(db)
    scope_index = _scope_index(rows)
    items: list[dict] = []
    profile_stats: dict[str, dict] = {}
    for sector in _NACE_CATALOG:
        code = str(sector.get("code") or "")
        nace = str(sector.get("nace") or "")
        profile = SEKTOR_PROFIL.get(code, code)
        ctx = {
            "hazard": str(sector.get("hazard_class") or "").strip(),
            "sector": profile,
            "sector_code": code,
            "nace": nace,
        }
        status = _counts_and_status(_indexed_bucket_counts(scope_index, ctx))
        item = {
            "code": code,
            "nace": nace,
            "name": sector.get("name") or sector.get("label") or code,
            "hazard": ctx["hazard"],
            "profile": profile,
            **status,
        }
        items.append(item)
        stats = profile_stats.setdefault(
            profile,
            {"profile": profile, "nace_count": 0, "exam_ready_count": 0, "release_ready_count": 0},
        )
        stats["nace_count"] += 1
        stats["exam_ready_count"] += int(status["ready"])
        stats["release_ready_count"] += int(status["release_ready"])

    exam_ready_count = sum(int(item["ready"]) for item in items)
    release_ready_count = sum(int(item["release_ready"]) for item in items)
    return {
        "catalog_records_total": len(_CATALOG),
        "nace_total": len(items),
        "general_fallback_total": len(_CATALOG) - len(items),
        "profile_total": len(profile_stats),
        "published_question_total": len(rows),
        "exam_ready_count": exam_ready_count,
        "release_ready_count": release_ready_count,
        "blocked_count": len(items) - exam_ready_count,
        "required": dict(BUCKET_TARGETS),
        "release_required": dict(RELEASE_BUCKET_TARGETS),
        "profiles": sorted(profile_stats.values(), key=lambda row: row["profile"]),
        "items": items,
    }


def _snapshot_item(question: TrainingQuestion, position: int, rnd: random.Random) -> dict:
    original = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }
    shuffled = list(original.items())
    rnd.shuffle(shuffled)
    options = {"ABCD"[i]: text for i, (_old_key, text) in enumerate(shuffled)}
    correct = next(
        "ABCD"[i] for i, (old_key, _text) in enumerate(shuffled) if old_key == question.correct_option
    )
    sources = [
        {
            "title": source.title,
            "url": source.url,
            "reference": source.reference,
            "effective_date": source.effective_date.isoformat() if source.effective_date else None,
            "checked_at": source.checked_at.isoformat() if source.checked_at else None,
        }
        for source in question.sources
    ]
    scopes = [
        {"type": scope.scope_type, "value": scope.scope_value}
        for scope in question.scopes
    ]
    return {
        "position": position,
        "question_id": question.id,
        "question_code": question.question_code,
        "question_version": question.version,
        "topic_code": question.topic_code,
        "topic_label": question.topic_label,
        "question_text": question.question_text,
        "options": options,
        "correct_option": correct,
        "answer_explanation": question.answer_explanation,
        "sources": sources,
        "scopes": scopes,
    }


@lru_cache(maxsize=None)
def _curated_pack(file_name: str) -> tuple[dict, ...]:
    """Load and fail closed on malformed bundled, source-reviewed questions."""
    path = _CURATED_DATA_DIR / file_name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Yedek sınav soru paketi okunamadı: {file_name}") from exc
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or len(items) < 5:
        raise RuntimeError(f"Yedek sınav soru paketi geçersiz: {file_name}")
    for item in items:
        options = item.get("options") if isinstance(item, dict) else None
        sources = item.get("sources") if isinstance(item, dict) else None
        scopes = item.get("scopes") if isinstance(item, dict) else None
        required = (
            (
                item.get("question_code"),
                item.get("topic_code"),
                item.get("topic_label"),
                item.get("question_text"),
                item.get("answer_explanation"),
            )
            if isinstance(item, dict)
            else ()
        )
        if (
            len(required) != 5
            or any(not str(value or "").strip() for value in required)
            or not isinstance(options, list)
            or len(options) != 4
            or len({str(value).strip().casefold() for value in options}) != 4
            or item.get("correct_option") not in "ABCD"
            or not isinstance(sources, list)
            or not sources
            or any(not str(source.get("url") or "").startswith("https://") for source in sources)
            or not isinstance(scopes, list)
            or not scopes
        ):
            raise RuntimeError(f"Yedek sınav soru paketi içeriği geçersiz: {file_name}")
    return tuple(items)


def _foundational_questions() -> tuple[dict, ...]:
    """Return the five fixed questions that lead every sector exam."""
    questions = _curated_pack("foundation.json")
    if len(questions) != FOUNDATIONAL_QUESTION_COUNT:
        raise RuntimeError(
            "Temel İSG soru paketi tam olarak "
            f"{FOUNDATIONAL_QUESTION_COUNT} soru içermelidir."
        )
    codes = [str(row["question_code"]) for row in questions]
    if len(set(codes)) != FOUNDATIONAL_QUESTION_COUNT:
        raise RuntimeError("Temel İSG soru kodları benzersiz olmalıdır.")
    return questions


def _curated_buckets(training: TrainingSession) -> dict[str, list[dict]]:
    ctx = _context(training)
    common = list(_curated_pack("common.json"))
    hazard_file = _CURATED_HAZARD_PACKS.get(ctx["hazard"])
    technical = list(_curated_pack(hazard_file)) if hazard_file else []
    sector_ctx = dict(ctx)
    sector_ctx["sector_code"] = _CURATED_SECTOR_ALIASES.get(
        ctx["sector_code"], ctx["sector_code"]
    )
    sector_ctx["sector"] = _CURATED_SECTOR_ALIASES.get(ctx["sector"], ctx["sector"])
    sector: list[dict] = []
    for file_name in _CURATED_SECTOR_PACKS:
        for item in _curated_pack(file_name):
            if any(
                (
                    scope.get("type") == "sector"
                    and sector_scope_matches(sector_ctx, scope.get("value", ""))
                )
                or (
                    scope.get("type") == "nace"
                    and nace_scope_matches(ctx["nace"], scope.get("value", ""))
                )
                for scope in item["scopes"]
            ):
                sector.append(item)
    return {"common": common, "technical": technical, "sector": sector}


def _curated_snapshot_item(question: dict, position: int, rnd: random.Random) -> dict:
    original = dict(zip("ABCD", question["options"], strict=True))
    shuffled = list(original.items())
    rnd.shuffle(shuffled)
    options = {"ABCD"[i]: text for i, (_old_key, text) in enumerate(shuffled)}
    correct = next(
        "ABCD"[i]
        for i, (old_key, _text) in enumerate(shuffled)
        if old_key == question["correct_option"]
    )
    return {
        "position": position,
        "question_id": None,
        "question_code": question["question_code"],
        "question_version": int(question.get("version") or 1),
        "topic_code": question["topic_code"],
        "topic_label": question["topic_label"],
        "question_text": question["question_text"],
        "options": options,
        "correct_option": correct,
        "answer_explanation": question["answer_explanation"],
        "sources": question["sources"],
        "scopes": question["scopes"],
    }


def _fixed_foundational_snapshot_item(question: dict, position: int) -> dict:
    """Freeze one foundational question without changing its option order."""
    options = dict(zip("ABCD", question["options"], strict=True))
    return {
        "position": position,
        "question_id": None,
        "question_code": question["question_code"],
        "question_version": int(question.get("version") or 1),
        "topic_code": question["topic_code"],
        "topic_label": question["topic_label"],
        "question_text": question["question_text"],
        "options": options,
        "correct_option": question["correct_option"],
        "answer_explanation": question["answer_explanation"],
        "sources": question["sources"],
        "scopes": question["scopes"],
    }


def _special_curated_questions(training) -> list[dict]:
    key = resolve_special_profile_key(training)
    file_name = _SPECIAL_PACKS.get(key or "")
    if not file_name:
        return []
    rows = list(_curated_pack(file_name))
    if len(rows) != SPECIAL_QUESTION_COUNT:
        raise RuntimeError(
            f"{key} özel eğitim soru paketi tam olarak {SPECIAL_QUESTION_COUNT} soru içermelidir."
        )
    codes = [str(row.get("question_code") or "") for row in rows]
    if len(set(codes)) != SPECIAL_QUESTION_COUNT:
        raise RuntimeError("Özel eğitim soru kodları benzersiz olmalıdır.")
    return rows


def _create_special_exam_snapshot(
    db: Session,
    *,
    training: TrainingSession,
    created_by_id: int,
    questions: list[dict],
) -> TrainingExamSnapshot:
    seed = secrets.token_hex(16)
    rnd = random.Random(seed)
    rnd.shuffle(questions)
    items = [
        _curated_snapshot_item(question, position, rnd)
        for position, question in enumerate(questions, start=1)
    ]
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version = int(
        db.scalar(
            select(func.max(TrainingExamSnapshot.version)).where(
                TrainingExamSnapshot.training_id == training.id
            )
        )
        or 0
    ) + 1
    exam = TrainingExamSnapshot(
        training_id=training.id,
        version=version,
        question_count=SPECIAL_QUESTION_COUNT,
        random_seed=seed,
        content_hash=content_hash,
        selection_policy="special-yuksekte-calisma-v1",
        created_by_id=created_by_id,
    )
    for item in items:
        exam.items.append(
            TrainingExamSnapshotItem(
                position=item["position"],
                question_id=item["question_id"],
                question_code=item["question_code"],
                question_version=item["question_version"],
                topic_code=item["topic_code"],
                topic_label=item["topic_label"],
                question_text=item["question_text"],
                options_json=json.dumps(item["options"], ensure_ascii=False, sort_keys=True),
                correct_option=item["correct_option"],
                answer_explanation=item["answer_explanation"],
                sources_json=json.dumps(item["sources"], ensure_ascii=False, sort_keys=True),
                scopes_json=json.dumps(item["scopes"], ensure_ascii=False, sort_keys=True),
            )
        )
    db.add(exam)
    db.flush()
    return exam


def create_exam_snapshot(
    db: Session,
    *,
    training: TrainingSession,
    created_by_id: int,
    allow_curated_fallback: bool = False,
) -> TrainingExamSnapshot:
    special_questions = _special_curated_questions(training)
    if special_questions:
        return _create_special_exam_snapshot(
            db,
            training=training,
            created_by_id=created_by_id,
            questions=special_questions,
        )

    buckets = _candidate_buckets(db, training)
    curated = (
        _curated_buckets(training)
        if allow_curated_fallback
        else {name: [] for name in BUCKET_TARGETS}
    )
    counts = {
        name: len(
            {row.question_code for row in buckets[name]}
            | {str(row["question_code"]) for row in curated[name]}
        )
        for name in BUCKET_TARGETS
    }
    if any(counts[name] < needed for name, needed in BUCKET_TARGETS.items()):
        raise InsufficientQuestionBankError(counts)

    seed = secrets.token_hex(16)
    rnd = random.Random(seed)
    foundational = _foundational_questions()
    selected: list[tuple[str, TrainingQuestion | dict]] = []
    used_codes: set[str] = {str(row["question_code"]) for row in foundational}
    used_curated = False
    for name, needed in BUCKET_TARGETS.items():
        db_rows = [row for row in buckets[name] if row.question_code not in used_codes]
        chosen_db = rnd.sample(db_rows, min(needed, len(db_rows)))
        selected.extend(("database", row) for row in chosen_db)
        used_codes.update(row.question_code for row in chosen_db)
        missing = needed - len(chosen_db)
        if missing:
            fallback_rows = [
                row for row in curated[name] if str(row["question_code"]) not in used_codes
            ]
            chosen_fallback = rnd.sample(fallback_rows, missing)
            selected.extend(("curated", row) for row in chosen_fallback)
            used_codes.update(str(row["question_code"]) for row in chosen_fallback)
            used_curated = True
    rnd.shuffle(selected)
    items = [
        _fixed_foundational_snapshot_item(question, position)
        for position, question in enumerate(foundational, start=1)
    ]
    items.extend([
        _snapshot_item(question, i, rnd)
        if origin == "database"
        else _curated_snapshot_item(question, i, rnd)
        for i, (origin, question) in enumerate(
            selected, start=FOUNDATIONAL_QUESTION_COUNT + 1
        )
    ])

    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version = int(
        db.scalar(
            select(func.max(TrainingExamSnapshot.version)).where(
                TrainingExamSnapshot.training_id == training.id
            )
        )
        or 0
    ) + 1
    exam = TrainingExamSnapshot(
        training_id=training.id,
        version=version,
        question_count=QUESTION_COUNT,
        random_seed=seed,
        content_hash=content_hash,
        selection_policy=CURATED_FALLBACK_POLICY if used_curated else SELECTION_POLICY,
        created_by_id=created_by_id,
    )
    for item in items:
        exam.items.append(
            TrainingExamSnapshotItem(
                position=item["position"],
                question_id=item["question_id"],
                question_code=item["question_code"],
                question_version=item["question_version"],
                topic_code=item["topic_code"],
                topic_label=item["topic_label"],
                question_text=item["question_text"],
                options_json=json.dumps(item["options"], ensure_ascii=False, sort_keys=True),
                correct_option=item["correct_option"],
                answer_explanation=item["answer_explanation"],
                sources_json=json.dumps(item["sources"], ensure_ascii=False, sort_keys=True),
                scopes_json=json.dumps(item["scopes"], ensure_ascii=False, sort_keys=True),
            )
        )
    db.add(exam)
    # Transaction ownership belongs to the API boundary. Committing here expires
    # both ``exam`` and the caller's ``training`` object and also clears PostgreSQL
    # SET LOCAL RLS context. The PDF builder still needs both objects, so an inner
    # commit can make the first exam request stall while SQLAlchemy tries to reload
    # expired rows without the request's tenant context.
    db.flush()
    return exam


def retire_question(question: TrainingQuestion, *, reviewer_id: int) -> None:
    if question.status != "published":
        raise QuestionBankError("Yalnız yayımlanmış bir soru kullanımdan kaldırılabilir.")
    question.status = "retired"
    question.retired_at = datetime.utcnow()
    question.reviewed_by_id = reviewer_id
