"""Sequential electronic-signature pipeline for approved committee meetings.

Every signature step is bound to one meeting version, one real user and one
OSGB Signer request/artifact. Completed artifacts are never deleted.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.models.entities import Company, ESignArtifact, ESignRequest, EyasStep, EyasWorkflow, User
from app.services import esign_pipeline as pipe
from app.services.audit import add_audit_log
from app.services.committee_meeting_pdf import build_committee_meeting_pdf


def _meeting(db: Session, meeting_id: int) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM ohs_committee_meetings WHERE id=:id AND is_active=true"),
        {"id": meeting_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Kurul toplantısı bulunamadı.")
    return dict(row)


def _rows(db: Session, meeting_id: int, document_version: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT s.*, u.full_name AS signer_name
              FROM ohs_committee_signature_steps s
              JOIN users u ON u.id=s.signer_user_id
             WHERE s.meeting_id=:meeting_id AND s.document_version=:document_version
             ORDER BY s.step_order
        """),
        {"meeting_id": meeting_id, "document_version": document_version},
    ).mappings().all()
    return [dict(row) for row in rows]


def workflow_data(db: Session, meeting_id: int, document_version: int, user: User | None = None) -> dict[str, Any] | None:
    rows = _rows(db, meeting_id, document_version)
    if not rows:
        return None
    active = next((row for row in rows if row["status"] == "active"), None)
    return {
        "document_version": document_version,
        "status": "signed" if all(row["status"] == "signed" for row in rows) else "in_progress",
        "current_step_order": active["step_order"] if active else None,
        "steps": [
            {
                "id": row["id"],
                "step_order": row["step_order"],
                "signer_user_id": row["signer_user_id"],
                "signer_name": row["signer_name"],
                "role_label": row["role_label"],
                "status": row["status"],
                "esign_request_id": row["esign_request_id"],
                "esign_artifact_id": row["esign_artifact_id"],
                "signed_at": row["signed_at"],
                "can_sign": bool(user and row["status"] == "active" and row["signer_user_id"] == user.id),
            }
            for row in rows
        ],
    }


def initialize_signature_steps(db: Session, meeting_id: int, workflow: EyasWorkflow) -> None:
    meeting = _meeting(db, meeting_id)
    version = int(meeting.get("document_version") or 1)
    if _rows(db, meeting_id, version):
        return
    approval_steps = list(
        db.scalars(
            select(EyasStep)
            .where(EyasStep.workflow_id == workflow.id)
            .order_by(EyasStep.step_order)
        ).all()
    )
    if len(approval_steps) != 3 or any(step.status != "approved" for step in approval_steps):
        raise HTTPException(409, "Elektronik imza adımları yalnız tüm dijital onaylar tamamlandığında başlatılır.")
    now = datetime.utcnow()
    for index, step in enumerate(approval_steps):
        db.execute(
            text("""
                INSERT INTO ohs_committee_signature_steps
                    (meeting_id, company_id, document_version, step_order, signer_user_id,
                     role_label, status, created_at)
                VALUES
                    (:meeting_id, :company_id, :version, :step_order, :user_id,
                     :role_label, :status, :now)
            """),
            {
                "meeting_id": meeting_id,
                "company_id": meeting["company_id"],
                "version": version,
                "step_order": step.step_order,
                "user_id": step.assignee_user_id,
                "role_label": step.role_label,
                "status": "active" if index == 0 else "pending",
                "now": now,
            },
        )
    db.execute(
        text("""
            UPDATE ohs_committee_meetings
               SET signature_status='waiting_for_signature', updated_at=:now
             WHERE id=:meeting_id
        """),
        {"now": now, "meeting_id": meeting_id},
    )
    from app.services.committee_workflow import notify_user
    first = approval_steps[0]
    notify_user(
        db,
        meeting_id=meeting_id,
        company_id=meeting["company_id"],
        user_id=first.assignee_user_id,
        title="İSG Kurulu toplantısında elektronik imza sırası sizde",
        message="Dijital onaylar tamamlandı. Belgenin elektronik imza adımı sizi bekliyor.",
        warning=True,
    )


def invalidate_signature_steps(db: Session, meeting_id: int, document_version: int, now: datetime) -> None:
    request_ids = list(
        db.scalars(
            text("""
                SELECT esign_request_id
                  FROM ohs_committee_signature_steps
                 WHERE meeting_id=:meeting_id AND document_version=:version
                   AND esign_request_id IS NOT NULL
                   AND status IN ('pending','active')
            """),
            {"meeting_id": meeting_id, "version": document_version},
        ).all()
    )
    db.execute(
        text("""
            UPDATE ohs_committee_signature_steps
               SET status='invalidated', invalidated_at=:now
             WHERE meeting_id=:meeting_id AND document_version=:version
               AND status IN ('pending','active')
        """),
        {"now": now, "meeting_id": meeting_id, "version": document_version},
    )
    if request_ids:
        ids = ",".join(str(int(item)) for item in request_ids)
        db.execute(
            text(f"UPDATE e_sign_requests SET status='cancelled', is_active=false WHERE id IN ({ids}) AND status='pending'")
        )


def _current_step(db: Session, meeting_id: int, user: User) -> tuple[dict[str, Any], dict[str, Any]]:
    meeting = _meeting(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    version = int(meeting.get("document_version") or 1)
    row = db.execute(
        text("""
            SELECT * FROM ohs_committee_signature_steps
             WHERE meeting_id=:meeting_id AND document_version=:version
               AND status='active'
             LIMIT 1
        """),
        {"meeting_id": meeting_id, "version": version},
    ).mappings().first()
    if not row:
        raise HTTPException(409, "Aktif elektronik imza adımı bulunmuyor.")
    step = dict(row)
    if step["signer_user_id"] != user.id:
        raise HTTPException(403, "Bu elektronik imza adımı başka bir kullanıcıya aittir.")
    if meeting.get("approval_status") != "approved":
        raise HTTPException(409, "Elektronik imza için önce üç dijital onay tamamlanmalıdır.")
    return meeting, step


def _render_source_pdf(db: Session, meeting: dict[str, Any]) -> bytes:
    from app.services.committee_workflow import approval_members_for_pdf, snapshot_members
    company = db.get(Company, meeting["company_id"])
    members = approval_members_for_pdf(db, meeting, snapshot_members(meeting))
    return build_committee_meeting_pdf(
        company={"name": company.name if company else "—", "address": getattr(company, "address", None)},
        meeting=meeting,
        members=members,
    )


def _source_for_step(db: Session, meeting: dict[str, Any], step: dict[str, Any]) -> bytes:
    if int(step["step_order"]) == 1:
        return _render_source_pdf(db, meeting)
    previous = db.execute(
        text("""
            SELECT a.signed_storage_path
              FROM ohs_committee_signature_steps s
              JOIN e_sign_artifacts a ON a.id=s.esign_artifact_id
             WHERE s.meeting_id=:meeting_id AND s.document_version=:version
               AND s.step_order=:previous_order AND s.status='signed'
        """),
        {
            "meeting_id": meeting["id"],
            "version": int(meeting.get("document_version") or 1),
            "previous_order": int(step["step_order"]) - 1,
        },
    ).scalar()
    if not previous:
        raise HTTPException(409, "Önceki elektronik imza artefaktı bulunamadı.")
    try:
        return pipe.read_stored(previous)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(409, "Önceki imzalı belge okunamadı.") from exc


def create_signature_request(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    ip: str | None = None,
) -> dict[str, Any]:
    meeting, step = _current_step(db, meeting_id, user)
    if step.get("esign_request_id"):
        existing = db.get(ESignRequest, step["esign_request_id"])
        if existing and existing.is_active and existing.status == "pending":
            return _request_out(existing, meeting_id)
    source = _source_for_step(db, meeting, step)
    try:
        relative = pipe.store_esign_bytes(meeting["company_id"], "source", source)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    token = pipe.new_one_time_token()
    title = meeting.get("title") or f"İSG Kurulu Toplantısı #{meeting_id}"
    request_row = ESignRequest(
        company_id=meeting["company_id"],
        approval_id=None,
        document_title=title[:220],
        document_kind="ohs_committee_meeting",
        source_sha256=pipe.sha256_hex(source),
        source_storage_path=relative,
        source_bytes=len(source),
        one_time_token=token,
        token_expires_at=pipe.token_expiry(),
        status="pending",
        created_by_id=user.id,
    )
    db.add(request_row)
    db.flush()
    db.execute(
        text("""
            UPDATE ohs_committee_signature_steps
               SET esign_request_id=:request_id
             WHERE id=:step_id AND status='active'
        """),
        {"request_id": request_row.id, "step_id": step["id"]},
    )
    add_audit_log(
        db,
        user=user,
        action="committee.signature.request",
        entity_type="ohs_committee_meeting",
        entity_id=str(meeting_id),
        module="ohs_committee",
        description=f"Elektronik imza talebi oluşturuldu: sürüm {meeting.get('document_version')}, adım {step['step_order']}",
        ip_address=ip,
    )
    db.commit()
    db.refresh(request_row)
    return _request_out(request_row, meeting_id)


def _request_out(row: ESignRequest, meeting_id: int) -> dict[str, Any]:
    return {
        "id": row.id,
        "meeting_id": meeting_id,
        "company_id": row.company_id,
        "document_title": row.document_title,
        "document_kind": row.document_kind,
        "source_sha256": row.source_sha256,
        "source_bytes": row.source_bytes,
        "one_time_token": row.one_time_token,
        "token_expires_at": row.token_expires_at,
        "status": row.status,
        "source_path": f"/api/v1/ohs-committee/meetings/{meeting_id}/signature-source",
    }


def signature_source(db: Session, meeting_id: int, user: User) -> tuple[bytes, str]:
    meeting, step = _current_step(db, meeting_id, user)
    request_id = step.get("esign_request_id")
    if not request_id:
        raise HTTPException(409, "Önce elektronik imza talebi oluşturun.")
    request_row = db.get(ESignRequest, request_id)
    if not request_row or not request_row.is_active or request_row.status != "pending":
        raise HTTPException(409, "Elektronik imza talebi kullanılamıyor.")
    if request_row.created_by_id != user.id:
        raise HTTPException(403, "Bu elektronik imza talebi başka kullanıcıya aittir.")
    try:
        raw = pipe.read_stored(request_row.source_storage_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, "İmzalanacak PDF bulunamadı.") from exc
    filename = f"OHS_Committee_Meeting_{meeting_id}_v{meeting.get('document_version') or 1}_sign.pdf"
    return raw, filename


def committee_link_for_request(db: Session, request_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("SELECT * FROM ohs_committee_signature_steps WHERE esign_request_id=:request_id"),
        {"request_id": request_id},
    ).mappings().first()
    return dict(row) if row else None


def authorize_completion(db: Session, request_row: ESignRequest, user: User) -> bool:
    link = committee_link_for_request(db, request_row.id)
    if not link:
        return False
    ensure_company_access(db, user, link["company_id"])
    if link["signer_user_id"] != user.id or request_row.created_by_id != user.id:
        raise HTTPException(403, "Başka bir katılımcı adına elektronik imza tamamlayamazsınız.")
    if link["status"] != "active":
        raise HTTPException(409, "Bu elektronik imza adımı artık aktif değil.")
    meeting = _meeting(db, link["meeting_id"])
    if int(meeting.get("document_version") or 1) != int(link["document_version"]):
        raise HTTPException(409, "Belge sürümü değişti. Yeni imza talebi oluşturun.")
    return True


def complete_signature_step(
    db: Session,
    *,
    request_id: int,
    artifact_id: int,
    user: User,
    signed_at: datetime,
    ip: str | None = None,
) -> None:
    link = committee_link_for_request(db, request_id)
    if not link:
        return
    if link["signer_user_id"] != user.id or link["status"] != "active":
        raise HTTPException(403, "Bu elektronik imza adımını tamamlama yetkiniz yok.")
    meeting = _meeting(db, link["meeting_id"])
    version = int(meeting.get("document_version") or 1)
    if version != int(link["document_version"]):
        raise HTTPException(409, "Belge sürümü değişti; bu imza kaydı işlenemez.")
    db.execute(
        text("""
            UPDATE ohs_committee_signature_steps
               SET status='signed', esign_artifact_id=:artifact_id, signed_at=:signed_at
             WHERE id=:step_id AND status='active'
        """),
        {"artifact_id": artifact_id, "signed_at": signed_at, "step_id": link["id"]},
    )
    next_step = db.execute(
        text("""
            SELECT * FROM ohs_committee_signature_steps
             WHERE meeting_id=:meeting_id AND document_version=:version
               AND step_order>:step_order AND status='pending'
             ORDER BY step_order LIMIT 1
        """),
        {"meeting_id": link["meeting_id"], "version": version, "step_order": link["step_order"]},
    ).mappings().first()
    from app.services.committee_workflow import notify_user
    if next_step:
        db.execute(
            text("UPDATE ohs_committee_signature_steps SET status='active' WHERE id=:id AND status='pending'"),
            {"id": next_step["id"]},
        )
        db.execute(
            text("UPDATE ohs_committee_meetings SET signature_status='waiting_for_signature', updated_at=:now WHERE id=:id"),
            {"now": signed_at, "id": link["meeting_id"]},
        )
        notify_user(
            db,
            meeting_id=link["meeting_id"],
            company_id=link["company_id"],
            user_id=next_step["signer_user_id"],
            title="İSG Kurulu toplantısında elektronik imza sırası sizde",
            message=f"{next_step['role_label']} elektronik imza adımı sizi bekliyor.",
            warning=True,
        )
    else:
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET signature_status='signed', status='signed', updated_at=:now
                 WHERE id=:id
            """),
            {"now": signed_at, "id": link["meeting_id"]},
        )
        signer_ids = list(
            db.scalars(
                text("""
                    SELECT signer_user_id FROM ohs_committee_signature_steps
                     WHERE meeting_id=:meeting_id AND document_version=:version
                """),
                {"meeting_id": link["meeting_id"], "version": version},
            ).all()
        )
        for signer_id in signer_ids:
            notify_user(
                db,
                meeting_id=link["meeting_id"],
                company_id=link["company_id"],
                user_id=int(signer_id),
                title="İSG Kurulu toplantısının tüm imzaları tamamlandı",
                message="Toplantı tutanağı üç zorunlu katılımcı tarafından elektronik olarak imzalandı.",
            )
    add_audit_log(
        db,
        user=user,
        action="committee.signature.complete",
        entity_type="ohs_committee_meeting",
        entity_id=str(link["meeting_id"]),
        module="ohs_committee",
        description=f"Elektronik imza tamamlandı: sürüm {version}, adım {link['step_order']}, artefakt {artifact_id}",
        ip_address=ip,
    )


def final_signed_artifact(db: Session, meeting_id: int, document_version: int) -> ESignArtifact | None:
    rows = _rows(db, meeting_id, document_version)
    if not rows or any(row["status"] != "signed" for row in rows):
        return None
    artifact_id = rows[-1].get("esign_artifact_id")
    return db.get(ESignArtifact, artifact_id) if artifact_id else None


def final_signed_bytes(db: Session, meeting_id: int, document_version: int) -> bytes | None:
    artifact = final_signed_artifact(db, meeting_id, document_version)
    if not artifact:
        return None
    try:
        return pipe.read_stored(artifact.signed_storage_path)
    except Exception:
        return None
