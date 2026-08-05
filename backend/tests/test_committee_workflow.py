from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.committee_professional import _find_duplicate_member_id
from app.core.database import SessionLocal
from app.models.entities import Company, ESignRequest, EyasStep, EyasWorkflow, User, UserRole
from app.services import committee_signature, committee_workflow


def _token() -> str:
    return uuid.uuid4().hex[:12]


def _create_company_and_users(db):
    suffix = _token()
    company = Company(name=f"Committee CI {suffix}", authorized_person="İşveren Yetkilisi", is_active=True)
    db.add(company)
    db.flush()
    users = {
        "admin": User(
            email=f"committee-admin-{suffix}@example.test",
            full_name="Global Yönetici",
            hashed_password="test-hash",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        ),
        "specialist": User(
            email=f"committee-specialist-{suffix}@example.test",
            full_name="İSG Uzmanı",
            hashed_password="test-hash",
            role=UserRole.SAFETY_SPECIALIST,
            is_active=True,
            company_id=company.id,
        ),
        "physician": User(
            email=f"committee-physician-{suffix}@example.test",
            full_name="İşyeri Hekimi",
            hashed_password="test-hash",
            role=UserRole.WORKPLACE_PHYSICIAN,
            is_active=True,
            company_id=company.id,
        ),
        "employer": User(
            email=f"committee-employer-{suffix}@example.test",
            full_name="İşveren Vekili",
            hashed_password="test-hash",
            role=UserRole.COMPANY_ADMIN,
            is_active=True,
            company_id=company.id,
        ),
        "unrelated": User(
            email=f"committee-unrelated-{suffix}@example.test",
            full_name="İlgisiz Kullanıcı",
            hashed_password="test-hash",
            role=UserRole.READ_ONLY,
            is_active=True,
            company_id=company.id,
        ),
    }
    db.add_all(users.values())
    db.commit()
    for user in users.values():
        db.refresh(user)
    return company, users


def _participants(users):
    return [
        {
            "step_order": 1,
            "role_key": "safety_specialist",
            "role_label": "İş Güvenliği Uzmanı",
            "assignee_user_id": users["specialist"].id,
            "assignee_name": users["specialist"].full_name,
        },
        {
            "step_order": 2,
            "role_key": "workplace_physician",
            "role_label": "İşyeri Hekimi",
            "assignee_user_id": users["physician"].id,
            "assignee_name": users["physician"].full_name,
        },
        {
            "step_order": 3,
            "role_key": "employer_representative",
            "role_label": "İşveren / vekili",
            "assignee_user_id": users["employer"].id,
            "assignee_name": users["employer"].full_name,
        },
    ]


def _insert_member(db, company_id: int, creator_id: int, *, role_code: str, mandatory: bool, name: str | None = None):
    identity = f"test:{company_id}:{_token()}"
    member_id = db.execute(
        text("""
            INSERT INTO ohs_committee_members
                (company_id, role_code, full_name, start_date, notes, is_active,
                 created_by_id, created_at, identity_key, source_type, is_mandatory)
            VALUES
                (:company_id, :role_code, :full_name, :start_date, NULL, true,
                 :creator_id, :created_at, :identity_key, 'manual', :mandatory)
            RETURNING id
        """),
        {
            "company_id": company_id,
            "role_code": role_code,
            "full_name": name or f"Kurul Üyesi {role_code}",
            "start_date": date.today(),
            "creator_id": creator_id,
            "created_at": datetime.utcnow(),
            "identity_key": identity,
            "mandatory": mandatory,
        },
    ).scalar_one()
    db.commit()
    return member_id, identity


def _insert_all_mandatory_members(db, company_id: int, creator_id: int):
    return [
        _insert_member(db, company_id, creator_id, role_code="igu", mandatory=True, name="İSG Uzmanı"),
        _insert_member(db, company_id, creator_id, role_code="hekim", mandatory=True, name="İşyeri Hekimi"),
        _insert_member(db, company_id, creator_id, role_code="isveren_vekili", mandatory=True, name="İşveren Vekili"),
    ]


def _insert_meeting(db, company_id: int, creator_id: int, *, snapshot=None, status="draft") -> int:
    now = datetime.utcnow()
    meeting_id = db.execute(
        text("""
            INSERT INTO ohs_committee_meetings
                (company_id, meeting_date, agenda, decisions, attendees, next_meeting_date,
                 notes, is_active, created_by_id, created_at, title, meeting_no,
                 revision_no, status, signature_status, member_snapshot_json,
                 approval_status, document_version, updated_at)
            VALUES
                (:company_id, :meeting_date, 'Gündem', 'Karar', 'Katılımcılar', NULL,
                 'Not', true, :creator_id, :created_at, 'İSG Kurulu Toplantısı', :meeting_no,
                 '00', :status, 'not_signed', :snapshot,
                 'draft', 1, :updated_at)
            RETURNING id
        """),
        {
            "company_id": company_id,
            "meeting_date": date.today(),
            "creator_id": creator_id,
            "created_at": now,
            "meeting_no": _token(),
            "status": status,
            "snapshot": json.dumps(snapshot or [], ensure_ascii=False),
            "updated_at": now,
        },
    ).scalar_one()
    db.commit()
    return meeting_id


def test_assigned_mandatory_participants_see_meeting_but_unrelated_user_cannot(monkeypatch):
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        meeting_id = _insert_meeting(db, company.id, users["admin"].id)
        monkeypatch.setattr(committee_workflow, "assigned_participants", lambda _db, _company_id: _participants(users))

        for key in ("specialist", "physician", "employer"):
            item = committee_workflow.work_queue_item(db, meeting_id, user=users[key])
            assert item["id"] == meeting_id
            assert item["is_participant"] is True
            assert item["company_id"] == company.id

        with pytest.raises(HTTPException) as exc:
            committee_workflow.work_queue_item(db, meeting_id, user=users["unrelated"])
        assert exc.value.status_code == 403

        other_company = Company(name=f"Other CI {_token()}", is_active=True)
        db.add(other_company)
        db.flush()
        outsider = User(
            email=f"other-{_token()}@example.test",
            full_name="Başka İşyeri Kullanıcısı",
            hashed_password="test-hash",
            role=UserRole.WORKPLACE_PHYSICIAN,
            is_active=True,
            company_id=other_company.id,
        )
        db.add(outsider)
        db.commit()
        with pytest.raises(HTTPException) as cross:
            committee_workflow.work_queue_item(db, meeting_id, user=outsider)
        assert cross.value.status_code in {403, 404}


def test_suggested_participants_preserves_specialist_physician_employer_order(monkeypatch):
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        _insert_all_mandatory_members(db, company.id, users["admin"].id)
        monkeypatch.setattr(
            committee_workflow.eyas_workplace,
            "suggested_assignees",
            lambda _db, _company_id: {"steps": [
                {"step_order": p["step_order"], "role_key": p["role_key"], "role_label": p["role_label"], "suggested_user_id": p["assignee_user_id"], "warnings": []}
                for p in _participants(users)
            ]},
        )
        result = committee_workflow.suggested_participants(db, company.id)
        assert [row["role_key"] for row in result] == [
            "safety_specialist",
            "workplace_physician",
            "employer_representative",
        ]
        assert [row["assignee_user_id"] for row in result] == [
            users["specialist"].id,
            users["physician"].id,
            users["employer"].id,
        ]


def test_remove_member_soft_deactivates_and_preserves_historical_snapshot():
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        member_id, identity = _insert_member(
            db, company.id, users["admin"].id,
            role_code="calisan_temsilcisi", mandatory=False, name="Tarihsel Çalışan",
        )
        original_snapshot = [{
            "member_id": member_id,
            "identity_key": identity,
            "full_name": "Tarihsel Çalışan",
            "role_code": "calisan_temsilcisi",
            "signature_status": "İmzalandı",
        }]
        meeting_id = _insert_meeting(db, company.id, users["admin"].id, snapshot=original_snapshot)

        result = committee_workflow.remove_member(
            db,
            member_id=member_id,
            user=users["admin"],
            reason_code="committee_restructured",
            reason_text="Kurul yapısı güncellendi.",
        )
        assert result["ok"] is True
        active, removed_at = db.execute(
            text("SELECT is_active, removed_at FROM ohs_committee_members WHERE id=:id"),
            {"id": member_id},
        ).one()
        assert active is False or active == 0
        assert removed_at is not None
        snapshot_after = db.scalar(
            text("SELECT member_snapshot_json FROM ohs_committee_meetings WHERE id=:id"),
            {"id": meeting_id},
        )
        assert json.loads(snapshot_after) == original_snapshot
        assert db.scalar(
            text("SELECT id FROM audit_logs WHERE action='committee.member.remove' AND entity_id=:entity_id ORDER BY id DESC LIMIT 1"),
            {"entity_id": str(member_id)},
        )
        assert _find_duplicate_member_id(
            db,
            company_id=company.id,
            identity_key=identity,
            employee_id=None,
            user_id=None,
        ) is None


def test_mandatory_removal_marks_nonfinal_meeting_incomplete_and_stale_request_is_safe():
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        _insert_member(db, company.id, users["admin"].id, role_code="igu", mandatory=True)
        _insert_member(db, company.id, users["admin"].id, role_code="hekim", mandatory=True)
        member_id, _ = _insert_member(db, company.id, users["admin"].id, role_code="isveren_vekili", mandatory=True)
        meeting_id = _insert_meeting(db, company.id, users["admin"].id, status="active")

        result = committee_workflow.remove_member(
            db,
            member_id=member_id,
            user=users["admin"],
            reason_code="assignment_ended",
            reason_text=None,
        )
        assert result["committee_incomplete"] is True
        status, approval_status = db.execute(
            text("SELECT status, approval_status FROM ohs_committee_meetings WHERE id=:id"),
            {"id": meeting_id},
        ).one()
        assert status == "draft"
        assert approval_status == "incomplete"
        assert "İşveren / İşveren Vekili" in result["missing_mandatory"]

        with pytest.raises(HTTPException) as stale:
            committee_workflow.remove_member(
                db,
                member_id=member_id,
                user=users["admin"],
                reason_code="assignment_ended",
                reason_text=None,
            )
        assert stale.value.status_code == 409


def test_mandatory_member_cannot_be_removed_during_active_approval_flow():
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        member_id, _ = _insert_member(db, company.id, users["admin"].id, role_code="hekim", mandatory=True)
        meeting_id = _insert_meeting(db, company.id, users["admin"].id)
        workflow = EyasWorkflow(
            company_id=company.id,
            title="Aktif Kurul Akışı",
            document_kind="ohs_committee_meeting",
            source_document_id=None,
            source_sha256="a" * 64,
            status="in_progress",
            current_step_order=1,
            created_by_id=users["admin"].id,
            is_active=True,
        )
        db.add(workflow)
        db.flush()
        db.execute(
            text("UPDATE ohs_committee_meetings SET approval_workflow_id=:workflow_id WHERE id=:id"),
            {"workflow_id": workflow.id, "id": meeting_id},
        )
        db.commit()

        with pytest.raises(HTTPException) as blocked:
            committee_workflow.remove_member(
                db,
                member_id=member_id,
                user=users["admin"],
                reason_code="assignment_ended",
                reason_text=None,
            )
        assert blocked.value.status_code == 409
        assert db.scalar(text("SELECT is_active FROM ohs_committee_members WHERE id=:id"), {"id": member_id}) in (True, 1)


def test_material_change_archives_version_and_invalidates_only_pending_signatures(monkeypatch):
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        meeting_id = _insert_meeting(db, company.id, users["admin"].id)
        workflow = EyasWorkflow(
            company_id=company.id,
            title="Sürümlü Kurul Akışı",
            document_kind="ohs_committee_meeting",
            source_document_id=None,
            source_sha256="b" * 64,
            status="in_progress",
            current_step_order=1,
            created_by_id=users["admin"].id,
            is_active=True,
        )
        db.add(workflow)
        db.flush()
        db.execute(
            text("UPDATE ohs_committee_meetings SET approval_workflow_id=:workflow_id, approval_status='waiting_for_approval' WHERE id=:id"),
            {"workflow_id": workflow.id, "id": meeting_id},
        )
        db.execute(
            text("""
                INSERT INTO ohs_committee_signature_steps
                    (meeting_id, company_id, document_version, step_order, signer_user_id,
                     role_label, status, created_at)
                VALUES
                    (:meeting_id, :company_id, 1, 1, :specialist, 'İş Güvenliği Uzmanı', 'signed', :now),
                    (:meeting_id, :company_id, 1, 2, :physician, 'İşyeri Hekimi', 'active', :now),
                    (:meeting_id, :company_id, 1, 3, :employer, 'İşveren / vekili', 'pending', :now)
            """),
            {
                "meeting_id": meeting_id,
                "company_id": company.id,
                "specialist": users["specialist"].id,
                "physician": users["physician"].id,
                "employer": users["employer"].id,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
        monkeypatch.setattr(committee_workflow, "can_manage_company", lambda _db, _user, _company_id: True)

        updated = committee_workflow.invalidate_approval_for_material_change(
            db,
            meeting_id=meeting_id,
            user=users["admin"],
            changed_fields=["agenda"],
        )
        assert updated["document_version"] == 2
        assert updated["approval_status"] == "revision_required"
        assert updated["approval_workflow_id"] is None
        archived = db.execute(
            text("SELECT document_version, approval_workflow_id FROM ohs_committee_meeting_versions WHERE meeting_id=:id"),
            {"id": meeting_id},
        ).one()
        assert archived.document_version == 1
        assert archived.approval_workflow_id == workflow.id
        statuses = db.execute(
            text("SELECT step_order, status FROM ohs_committee_signature_steps WHERE meeting_id=:id ORDER BY step_order"),
            {"id": meeting_id},
        ).all()
        assert statuses == [(1, "signed"), (2, "invalidated"), (3, "invalidated")]


def test_signature_request_cannot_be_completed_by_another_participant():
    with SessionLocal() as db:
        company, users = _create_company_and_users(db)
        meeting_id = _insert_meeting(db, company.id, users["admin"].id)
        request = ESignRequest(
            company_id=company.id,
            approval_id=None,
            document_title="Kurul Toplantısı",
            document_kind="ohs_committee_meeting",
            source_sha256="c" * 64,
            source_storage_path="test/source.pdf",
            source_bytes=100,
            one_time_token=uuid.uuid4().hex,
            token_expires_at=datetime.utcnow() + timedelta(minutes=15),
            status="pending",
            created_by_id=users["specialist"].id,
            is_active=True,
        )
        db.add(request)
        db.flush()
        db.execute(
            text("UPDATE ohs_committee_meetings SET approval_status='approved' WHERE id=:id"),
            {"id": meeting_id},
        )
        db.execute(
            text("""
                INSERT INTO ohs_committee_signature_steps
                    (meeting_id, company_id, document_version, step_order, signer_user_id,
                     role_label, status, esign_request_id, created_at)
                VALUES
                    (:meeting_id, :company_id, 1, 1, :signer,
                     'İş Güvenliği Uzmanı', 'active', :request_id, :now)
            """),
            {
                "meeting_id": meeting_id,
                "company_id": company.id,
                "signer": users["specialist"].id,
                "request_id": request.id,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
        assert committee_signature.authorize_completion(db, request, users["specialist"]) is True
        with pytest.raises(HTTPException) as forbidden:
            committee_signature.authorize_completion(db, request, users["physician"])
        assert forbidden.value.status_code == 403
