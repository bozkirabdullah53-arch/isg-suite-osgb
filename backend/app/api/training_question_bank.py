"""Kaynaklı soru bankası yönetimi ve onaylı havuzdan sınav üretimi."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.config import training_question_bank_exam_active
from app.models.entities import (
    TrainingExamSnapshot,
    TrainingQuestion,
    TrainingQuestionScope,
    TrainingQuestionSource,
    TrainingSession,
    User,
    UserRole,
)
from app.schemas.training_question_bank import (
    ExamSnapshotResponse,
    QuestionBulkImportRequest,
    QuestionBulkImportResponse,
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
)
from app.services.training_question_bank import (
    InsufficientQuestionBankError,
    QuestionBankError,
    create_exam_snapshot,
    question_bank_coverage,
    question_bank_readiness,
    retire_question,
    validate_question_for_publish,
)

router = APIRouter(prefix="/question-bank", tags=["Eğitim Soru Bankası"])
exam_router = APIRouter(prefix="/trainings", tags=["Eğitim Sınavları"])
MANAGE = (UserRole.GLOBAL_ADMIN,)
GENERATE = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)


def _question_query():
    return select(TrainingQuestion).options(
        selectinload(TrainingQuestion.scopes),
        selectinload(TrainingQuestion.sources),
    )


def _get_question(db: Session, question_id: int) -> TrainingQuestion:
    row = db.scalar(_question_query().where(TrainingQuestion.id == question_id))
    if not row:
        raise HTTPException(404, "Soru bulunamadı.")
    return row


def _question_out(row: TrainingQuestion) -> QuestionResponse:
    return QuestionResponse(
        id=row.id,
        question_code=row.question_code,
        version=row.version,
        status=row.status,
        topic_code=row.topic_code,
        topic_label=row.topic_label,
        question_text=row.question_text,
        options={"A": row.option_a, "B": row.option_b, "C": row.option_c, "D": row.option_d},
        correct_option=row.correct_option,
        answer_explanation=row.answer_explanation,
        reviewer_note=row.reviewer_note,
        scopes=[{"type": x.scope_type, "value": x.scope_value} for x in row.scopes],
        sources=[
            {
                "title": x.title,
                "url": x.url,
                "reference": x.reference,
                "effective_date": x.effective_date,
                "checked_at": x.checked_at,
            }
            for x in row.sources
        ],
        created_by_id=row.created_by_id,
        reviewed_by_id=row.reviewed_by_id,
        reviewed_at=row.reviewed_at,
        published_at=row.published_at,
        retired_at=row.retired_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _set_scopes(row: TrainingQuestion, values) -> None:
    pairs = [(x.type, x.value.strip()) for x in values]
    if len(set(pairs)) != len(pairs):
        raise HTTPException(422, "Aynı soru kapsamı birden fazla kez eklenemez.")
    row.scopes[:] = [
        TrainingQuestionScope(scope_type=scope_type, scope_value=scope_value)
        for scope_type, scope_value in pairs
    ]


def _set_sources(row: TrainingQuestion, values) -> None:
    row.sources[:] = [
        TrainingQuestionSource(
            title=x.title.strip(),
            url=str(x.url),
            reference=x.reference.strip(),
            effective_date=x.effective_date,
        )
        for x in values
    ]


def _new_question_row(payload: QuestionCreate, *, created_by_id: int) -> TrainingQuestion:
    row = TrainingQuestion(
        question_code=payload.question_code.upper(),
        version=payload.version,
        status="draft",
        topic_code=payload.topic_code.strip(),
        topic_label=payload.topic_label.strip(),
        question_text=payload.question_text.strip(),
        option_a=payload.options[0],
        option_b=payload.options[1],
        option_c=payload.options[2],
        option_d=payload.options[3],
        correct_option=payload.correct_option,
        answer_explanation=payload.answer_explanation.strip(),
        created_by_id=created_by_id,
    )
    _set_scopes(row, payload.scopes)
    _set_sources(row, payload.sources)
    return row


@router.get("/questions", response_model=list[QuestionResponse])
def list_questions(
    status: str | None = Query(default=None, pattern=r"^(draft|in_review|published|retired)$"),
    topic_code: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*MANAGE)),
):
    query = _question_query()
    if status:
        query = query.where(TrainingQuestion.status == status)
    if topic_code:
        query = query.where(TrainingQuestion.topic_code == topic_code.strip())
    rows = db.scalars(query.order_by(TrainingQuestion.updated_at.desc())).unique().all()
    return [_question_out(row) for row in rows]


@router.get("/coverage")
def coverage_report(
    q: str | None = Query(default=None, max_length=120),
    hazard: str | None = Query(
        default=None, pattern=r"^(Az Tehlikeli|Tehlikeli|Çok Tehlikeli)$"
    ),
    status: str = Query(default="all", pattern=r"^(all|blocked|exam_ready|release_ready)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*MANAGE)),
):
    """2.141 NACE faaliyetinin gerçek yayımlanmış soru kapsamını raporlar."""
    report = question_bank_coverage(db)
    items = report.pop("items")
    needle = (q or "").strip().casefold()
    if needle:
        items = [
            item
            for item in items
            if needle
            in " ".join(
                str(item.get(key) or "") for key in ("nace", "name", "profile")
            ).casefold()
        ]
    if hazard:
        items = [item for item in items if item["hazard"] == hazard]
    if status == "blocked":
        items = [item for item in items if not item["ready"]]
    elif status == "exam_ready":
        items = [item for item in items if item["ready"]]
    elif status == "release_ready":
        items = [item for item in items if item["release_ready"]]
    total = len(items)
    return {
        **report,
        "items_total": total,
        "offset": offset,
        "limit": limit,
        "items": items[offset : offset + limit],
    }


@router.post("/questions", response_model=QuestionResponse, status_code=201)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    row = _new_question_row(payload, created_by_id=user.id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu soru kodu ve sürümü zaten mevcut.") from exc
    return _question_out(_get_question(db, row.id))


@router.post("/imports/questions", response_model=QuestionBulkImportResponse, status_code=201)
def import_question_drafts(
    payload: QuestionBulkImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    """En fazla 500 doğrulanmış soruyu tek işlemde yalnız taslak olarak içe al."""
    requested = [(item.question_code.upper(), item.version) for item in payload.items]
    if len(set(requested)) != len(requested):
        raise HTTPException(422, "Dosyada aynı soru kodu ve sürümü birden fazla kez bulunuyor.")

    codes = sorted({code for code, _version in requested})
    existing_rows = db.execute(
        select(TrainingQuestion.question_code, TrainingQuestion.version).where(
            TrainingQuestion.question_code.in_(codes)
        )
    ).all()
    conflicts = sorted(set(requested) & {(code, version) for code, version in existing_rows})
    if conflicts:
        sample = ", ".join(f"{code} v{version}" for code, version in conflicts[:8])
        raise HTTPException(
            409,
            f"İçe aktarma yapılmadı. Mevcut soru sürümleri bulundu: {sample}",
        )

    rows = [_new_question_row(item, created_by_id=user.id) for item in payload.items]
    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Toplu içe aktarma çakışma nedeniyle geri alındı.") from exc
    return QuestionBulkImportResponse(created=len(rows), question_ids=[row.id for row in rows])


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*MANAGE)),
):
    row = _get_question(db, question_id)
    if row.status not in {"draft", "in_review"}:
        raise HTTPException(409, "Yayımlanmış soru değiştirilemez; yeni bir sürüm oluşturulmalıdır.")
    values = payload.model_dump(exclude_unset=True, exclude={"options", "scopes", "sources"})
    for key, value in values.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    if payload.options is not None:
        row.option_a, row.option_b, row.option_c, row.option_d = payload.options
    if payload.scopes is not None:
        _set_scopes(row, payload.scopes)
    if payload.sources is not None:
        _set_sources(row, payload.sources)
    row.status = "draft"
    db.commit()
    return _question_out(_get_question(db, question_id))


@router.post("/questions/{question_id}/submit", response_model=QuestionResponse)
def submit_question(
    question_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(*MANAGE)),
):
    row = _get_question(db, question_id)
    if row.status != "draft":
        raise HTTPException(409, "Yalnız taslak soru incelemeye gönderilebilir.")
    try:
        validate_question_for_publish(row)
    except QuestionBankError as exc:
        raise HTTPException(422, str(exc)) from exc
    row.status = "in_review"
    db.commit()
    return _question_out(_get_question(db, question_id))


@router.post("/questions/{question_id}/publish", response_model=QuestionResponse)
def publish_question(
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    row = _get_question(db, question_id)
    if row.status != "in_review":
        raise HTTPException(409, "Soru önce incelemeye gönderilmelidir.")
    if row.created_by_id == user.id:
        raise HTTPException(409, "Dört göz ilkesi: Soruyu hazırlayan kullanıcı aynı soruyu yayımlayamaz.")
    try:
        validate_question_for_publish(row)
    except QuestionBankError as exc:
        raise HTTPException(422, str(exc)) from exc
    now = datetime.utcnow()
    # Yeni sürüm yayımlandığında aynı soru kodunun önceki sürümleri tekrar
    # seçilemez. Geçmiş kayıtlar korunur, yalnız aktif havuzdan kaldırılır.
    previous_versions = db.scalars(
        select(TrainingQuestion).where(
            TrainingQuestion.question_code == row.question_code,
            TrainingQuestion.status == "published",
            TrainingQuestion.id != row.id,
        )
    ).all()
    for previous in previous_versions:
        previous.status = "retired"
        previous.retired_at = now
        previous.reviewed_by_id = user.id
    row.status = "published"
    row.reviewed_by_id = user.id
    row.reviewed_at = now
    row.published_at = now
    db.commit()
    return _question_out(_get_question(db, question_id))


@router.post("/questions/{question_id}/retire", response_model=QuestionResponse)
def retire_published_question(
    question_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    row = _get_question(db, question_id)
    try:
        retire_question(row, reviewer_id=user.id)
    except QuestionBankError as exc:
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    return _question_out(_get_question(db, question_id))


def _training_for_user(db: Session, training_id: int, user: User) -> TrainingSession:
    row = db.get(TrainingSession, training_id)
    if not row:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


@exam_router.get("/{training_id}/exam-readiness")
def exam_readiness(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*GENERATE)),
):
    return question_bank_readiness(db, _training_for_user(db, training_id, user))


def _exam_out(row: TrainingExamSnapshot) -> ExamSnapshotResponse:
    return ExamSnapshotResponse(
        id=row.id,
        training_id=row.training_id,
        version=row.version,
        question_count=row.question_count,
        content_hash=row.content_hash,
        selection_policy=row.selection_policy,
        created_at=row.created_at,
        items=[
            {
                "position": item.position,
                "question_code": item.question_code,
                "question_version": item.question_version,
                "topic_code": item.topic_code,
                "topic_label": item.topic_label,
                "question_text": item.question_text,
                "options": json.loads(item.options_json),
                "correct_option": item.correct_option,
                "answer_explanation": item.answer_explanation,
                "sources": json.loads(item.sources_json),
            }
            for item in row.items
        ],
    )


@exam_router.post("/{training_id}/exam-snapshots", response_model=ExamSnapshotResponse, status_code=201)
def generate_exam_snapshot(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*GENERATE)),
):
    if not training_question_bank_exam_active():
        raise HTTPException(
            503,
            "Kaynaklı sınav üretimi, NACE kapsama hazırlığı tamamlanana kadar güvenli biçimde kapalıdır.",
        )
    training = _training_for_user(db, training_id, user)
    readiness = question_bank_readiness(db, training)
    if not readiness["release_ready"]:
        raise HTTPException(
            422,
            {
                "message": "Bu NACE için güçlü yayın eşiği tamamlanmadan sınav üretilemez.",
                "available": readiness["available"],
                "required": readiness["release_required"],
            },
        )
    try:
        row = create_exam_snapshot(db, training=training, created_by_id=user.id)
    except InsufficientQuestionBankError as exc:
        db.rollback()
        raise HTTPException(422, {"message": str(exc), "available": exc.counts}) from exc
    payload = _exam_out(row)
    db.commit()
    return payload


@exam_router.get("/{training_id}/exam-snapshots/latest", response_model=ExamSnapshotResponse)
def latest_exam_snapshot(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*GENERATE)),
):
    _training_for_user(db, training_id, user)
    row = db.scalar(
        select(TrainingExamSnapshot)
        .options(selectinload(TrainingExamSnapshot.items))
        .where(TrainingExamSnapshot.training_id == training_id)
        .order_by(TrainingExamSnapshot.version.desc())
    )
    if not row:
        raise HTTPException(404, "Bu eğitim için henüz onaylı soru bankasından sınav oluşturulmadı.")
    return _exam_out(row)
