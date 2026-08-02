"""Onaylı soru bankasından denetlenebilir, sabit sınav kopyası üretimi."""
from __future__ import annotations

import hashlib
import json
import random
import secrets
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    TrainingExamSnapshot,
    TrainingExamSnapshotItem,
    TrainingQuestion,
    TrainingSession,
)
from app.services.training_topics import SEKTOR_PROFIL, sektor_kodu_cozumle

QUESTION_COUNT = 15
BUCKET_TARGETS = {"common": 5, "technical": 5, "sector": 5}
SELECTION_POLICY = "approved-5x3-v1"


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


def _context(training: TrainingSession) -> dict[str, str]:
    sector_code = sektor_kodu_cozumle(training.sector)
    return {
        "hazard": str(training.hazard_class or "").strip(),
        "sector": SEKTOR_PROFIL.get(sector_code, sector_code),
        "sector_code": sector_code,
        "nace": _nace_value(training, sector_code),
    }


def _candidate_buckets(db: Session, training: TrainingSession) -> dict[str, list[TrainingQuestion]]:
    rows = list(
        db.scalars(
            select(TrainingQuestion)
            .options(
                selectinload(TrainingQuestion.scopes),
                selectinload(TrainingQuestion.sources),
            )
            .where(TrainingQuestion.status == "published")
            .order_by(TrainingQuestion.question_code, TrainingQuestion.version.desc())
        ).all()
    )
    # Aynı kodun yalnız en güncel yayımlanmış sürümü sınava girebilir.
    latest: dict[str, TrainingQuestion] = {}
    for row in rows:
        latest.setdefault(row.question_code, row)

    ctx = _context(training)
    buckets: dict[str, list[TrainingQuestion]] = defaultdict(list)
    for row in latest.values():
        matched: set[str] = set()
        for scope in row.scopes:
            kind, value = scope.scope_type, str(scope.scope_value or "").strip()
            if kind == "common" and value in {"", "*"}:
                matched.add("common")
            elif kind == "hazard" and value.casefold() == ctx["hazard"].casefold():
                matched.add("technical")
            elif kind == "sector" and value in {ctx["sector"], ctx["sector_code"]}:
                matched.add("sector")
            elif kind == "nace" and ctx["nace"] and ctx["nace"].startswith(value):
                matched.add("sector")
        # En özel eşleşme önceliklidir; aynı soru iki grupta seçilemez.
        if "sector" in matched:
            buckets["sector"].append(row)
        elif "technical" in matched:
            buckets["technical"].append(row)
        elif "common" in matched:
            buckets["common"].append(row)
    return {name: buckets.get(name, []) for name in BUCKET_TARGETS}


def question_bank_readiness(db: Session, training: TrainingSession) -> dict:
    buckets = _candidate_buckets(db, training)
    counts = {name: len(rows) for name, rows in buckets.items()}
    return {
        "ready": all(counts[name] >= needed for name, needed in BUCKET_TARGETS.items()),
        "required": dict(BUCKET_TARGETS),
        "available": counts,
        "context": _context(training),
        "policy": SELECTION_POLICY,
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


def create_exam_snapshot(
    db: Session, *, training: TrainingSession, created_by_id: int
) -> TrainingExamSnapshot:
    buckets = _candidate_buckets(db, training)
    counts = {name: len(rows) for name, rows in buckets.items()}
    if any(counts[name] < needed for name, needed in BUCKET_TARGETS.items()):
        raise InsufficientQuestionBankError(counts)

    seed = secrets.token_hex(16)
    rnd = random.Random(seed)
    selected: list[TrainingQuestion] = []
    for name, needed in BUCKET_TARGETS.items():
        selected.extend(rnd.sample(buckets[name], needed))
    rnd.shuffle(selected)
    items = [_snapshot_item(question, i, rnd) for i, question in enumerate(selected, start=1)]

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
        selection_policy=SELECTION_POLICY,
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
    db.commit()
    return db.scalar(
        select(TrainingExamSnapshot)
        .options(selectinload(TrainingExamSnapshot.items))
        .where(TrainingExamSnapshot.id == exam.id)
    )


def retire_question(question: TrainingQuestion, *, reviewer_id: int) -> None:
    if question.status != "published":
        raise QuestionBankError("Yalnız yayımlanmış bir soru kullanımdan kaldırılabilir.")
    question.status = "retired"
    question.retired_at = datetime.utcnow()
    question.reviewed_by_id = reviewer_id
