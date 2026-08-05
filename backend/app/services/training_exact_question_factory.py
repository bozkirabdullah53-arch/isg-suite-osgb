"""Deterministic, source-controlled exact-NACE exam question factory.

This module is used only for trainings with a persisted ``verified`` NACE
snapshot. It creates five fixed foundational questions plus fifteen questions
that are derived from the five frozen work-specific training topics. Historical
exam snapshots are never rewritten.
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    TrainingExamSnapshot,
    TrainingExamSnapshotItem,
    TrainingSession,
)
from app.models.training_nace import TrainingNaceSnapshot

EXACT_NACE_POLICY = "exact-nace-snapshot-foundation-5-plus-work-specific-15-v2"
WORK_SPECIFIC_COUNT = 15
SOURCE_CHECK_DATE = date(2026, 8, 5).isoformat()

_OFFICIAL_SOURCES = [
    {
        "title": "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
        "url": "https://www.csgb.gov.tr/media/2670/6331_isgkanunu_tr.pdf",
        "reference": "Madde 4, 10, 16 ve 17",
        "effective_date": "2012-06-30",
        "checked_at": SOURCE_CHECK_DATE,
    },
    {
        "title": "ÇSGB İş Sağlığı ve Güvenliği Genel Müdürlüğü Sıkça Sorulan Sorular",
        "url": "https://www.csgb.gov.tr/tr/sikca-sorulan-sorular/is-sagligi-ve-guvenligi-genel-mudurlugu/",
        "reference": "Soru 126, 130, 133 ve 137",
        "effective_date": None,
        "checked_at": SOURCE_CHECK_DATE,
    },
]


def verified_snapshot(db: Session, training: TrainingSession) -> TrainingNaceSnapshot | None:
    if not getattr(training, "id", None):
        return None
    row = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id,
            TrainingNaceSnapshot.classification_status == "verified",
        )
    )
    if row is None:
        return None
    if not str(row.catalog_key or "").startswith("nace_") or not str(row.nace_code or ""):
        return None
    return row


def _json_list(raw: str | None) -> list[str]:
    try:
        values = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _short(value: str, limit: int = 170) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _question(
    *,
    nace_code: str,
    profile_code: str,
    topic: str,
    topic_index: int,
    variant: int,
) -> dict:
    topic_text = _short(topic)
    code_nace = nace_code.replace(".", "")
    code = f"TR-NACE-{code_nace}-{topic_index:02d}-{variant}"
    common = {
        "question_code": code,
        "version": 1,
        "topic_code": f"exact-nace-{code_nace}-{topic_index:02d}",
        "topic_label": topic_text,
        "correct_option": "A",
        "sources": list(_OFFICIAL_SOURCES),
        "scopes": [
            {"type": "nace", "value": nace_code},
            {"type": "sector", "value": profile_code},
        ],
    }
    if variant == 1:
        return {
            **common,
            "question_text": (
                f"{topic_text} konusu için işe başlamadan önce yapılması gereken en doğru hazırlık hangisidir?"
            ),
            "options": [
                "Güncel risk değerlendirmesini, iş adımlarını, güvenli çalışma talimatlarını ve acil durum düzenini birlikte incelemek",
                "Yalnız kişisel koruyucu donanım dağıtarak diğer kontrolleri çalışan deneyimine bırakmak",
                "Tehlikeleri ancak bir olay yaşandıktan sonra değerlendirmek",
                "İşin hızlı tamamlanması için kontrol ve bilgilendirme adımlarını atlamak",
            ],
            "answer_explanation": (
                "Eğitim işe ve işyerine özgü riskler ile korunma tedbirlerine dayanmalı; risk değerlendirmesi, talimatlar ve acil durum düzeni birlikte ele alınmalıdır."
            ),
        }
    if variant == 2:
        return {
            **common,
            "question_text": (
                f"{topic_text} kapsamındaki risklerin kontrolünde aşağıdaki yaklaşımlardan hangisi öncelik sırasına uygundur?"
            ),
            "options": [
                "Önce tehlikeyi ortadan kaldırmak veya azaltmak; ardından mühendislik ve organizasyon tedbirlerini, son aşamada uygun KKD'yi uygulamak",
                "Bütün riskler için yalnız uyarı levhası asmak",
                "Toplu korunma mümkün olsa da yalnız çalışanın dikkatine güvenmek",
                "Maliyet oluşmaması için sadece olay sonrası düzeltme yapmak",
            ],
            "answer_explanation": (
                "İSG yaklaşımı riski kaynağında önlemeyi, toplu korunmayı ve uygun organizasyon tedbirlerini kişisel korunmadan önce değerlendirmeyi gerektirir."
            ),
        }
    return {
        **common,
        "question_text": (
            f"{topic_text} eğitiminin sahada etkili olduğunun en güvenilir göstergesi hangisidir?"
        ),
        "options": [
            "Çalışanın tehlikeyi ve kontrol tedbirlerini açıklayabilmesi, uygulamada doğru davranışı göstermesi ve uygunsuzluğu bildirmesi",
            "Katılım listesinde adının bulunması; öğrenme ve uygulamanın hiç değerlendirilmemesi",
            "Eğitim sunumunun çalışanlara gönderilmiş olması",
            "Çalışanın yalnızca kıdemli olması",
        ],
        "answer_explanation": (
            "Eğitimin amacı yalnız katılım kaydı oluşturmak değil, çalışanın bilgi ve davranışında güvenli uygulamaya yansıyan olumlu değişiklik sağlamaktır."
        ),
    }


def exact_questions_from_snapshot(snapshot: TrainingNaceSnapshot) -> tuple[dict, ...]:
    topics = _json_list(snapshot.training_topics_json)
    if len(topics) != 5:
        raise ValueError(
            "Doğrulanmış NACE snapshot'ında tam olarak beş işe özgü eğitim konusu bulunmalıdır."
        )
    nace = str(snapshot.nace_code or "").strip()
    profile = str(snapshot.content_profile_code or "").strip()
    if not nace or not profile:
        raise ValueError("Doğrulanmış NACE snapshot'ında kod ve içerik profili zorunludur.")
    questions = tuple(
        _question(
            nace_code=nace,
            profile_code=profile,
            topic=topic,
            topic_index=topic_index,
            variant=variant,
        )
        for topic_index, topic in enumerate(topics, start=1)
        for variant in (1, 2, 3)
    )
    codes = {str(item["question_code"]) for item in questions}
    if len(questions) != WORK_SPECIFIC_COUNT or len(codes) != WORK_SPECIFIC_COUNT:
        raise RuntimeError("İşe özgü sınav paketi 15 benzersiz sorudan oluşmalıdır.")
    return questions


def exact_question_readiness(db: Session, training: TrainingSession) -> dict:
    snapshot = verified_snapshot(db, training)
    if snapshot is None:
        return {
            "ready": False,
            "release_ready": False,
            "verified_snapshot": False,
            "available": {"foundation": 0, "work_specific": 0},
            "required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "release_required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "missing": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "release_missing": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "policy": EXACT_NACE_POLICY,
        }
    try:
        count = len(exact_questions_from_snapshot(snapshot))
    except ValueError as exc:
        return {
            "ready": False,
            "release_ready": False,
            "verified_snapshot": True,
            "available": {"foundation": 5, "work_specific": 0},
            "required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "release_required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
            "missing": {"foundation": 0, "work_specific": WORK_SPECIFIC_COUNT},
            "release_missing": {"foundation": 0, "work_specific": WORK_SPECIFIC_COUNT},
            "policy": EXACT_NACE_POLICY,
            "reason": str(exc),
        }
    return {
        "ready": count == WORK_SPECIFIC_COUNT,
        "release_ready": count == WORK_SPECIFIC_COUNT,
        "verified_snapshot": True,
        "available": {"foundation": 5, "work_specific": count},
        "required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
        "release_required": {"foundation": 5, "work_specific": WORK_SPECIFIC_COUNT},
        "missing": {"foundation": 0, "work_specific": max(0, WORK_SPECIFIC_COUNT - count)},
        "release_missing": {"foundation": 0, "work_specific": max(0, WORK_SPECIFIC_COUNT - count)},
        "policy": EXACT_NACE_POLICY,
        "context": {
            "catalog_key": snapshot.catalog_key,
            "nace": snapshot.nace_code,
            "profile": snapshot.content_profile_code,
            "hazard": snapshot.hazard_class,
        },
    }


def create_exact_nace_exam_snapshot(
    db: Session,
    *,
    training: TrainingSession,
    created_by_id: int,
) -> TrainingExamSnapshot:
    from app.services import training_question_bank as question_bank

    snapshot = verified_snapshot(db, training)
    if snapshot is None:
        raise ValueError("Sınav için persisted ve verified NACE snapshot bulunamadı.")
    exact_questions = list(exact_questions_from_snapshot(snapshot))
    seed = secrets.token_hex(16)
    rnd = random.Random(seed)
    rnd.shuffle(exact_questions)

    foundational = question_bank._foundational_questions()
    items = [
        question_bank._fixed_foundational_snapshot_item(question, position)
        for position, question in enumerate(foundational, start=1)
    ]
    items.extend(
        question_bank._curated_snapshot_item(question, position, rnd)
        for position, question in enumerate(exact_questions, start=6)
    )
    if len(items) != 20:
        raise RuntimeError(f"Exact NACE sınavı 20 soru olmalıdır: {len(items)}")

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
        question_count=20,
        random_seed=seed,
        content_hash=content_hash,
        selection_policy=EXACT_NACE_POLICY,
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
