"""Değişiklik talebi API'si — akış, 4 göz ve KVKK veri sahibi uçları."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.entities import Company, Employee, User, UserRole


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        company = Company(name="A", is_active=True)
        db.add(company)
        db.flush()
        employee = Employee(company_id=company.id, full_name="Ali Veli", job_title="Eski", is_active=True)
        db.add(employee)
        db.flush()
        requester = User(
            email="requester@example.com",
            full_name="Talep Eden",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            is_active=True,
        )
        admin = User(
            email="admin@example.com",
            full_name="Global Admin",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add_all([requester, admin])
        db.commit()
        ids = {
            "company": company.id,
            "employee": employee.id,
            "requester": requester.id,
            "admin": admin.id,
        }
    monkeypatch.setattr("app.core.config.settings.backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr("app.core.config.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.api.change_requests.ensure_company_access", lambda db, u, cid: None)
    return factory, ids


def _client(factory, user_id: int):
    from app.api.deps import get_current_user
    from app.main import app

    def db_dep():
        with factory() as db:
            yield db

    def user_dep():
        with factory() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user] = user_dep
    return app, TestClient(app)


def _payload(company_id: int, **overrides) -> dict:
    payload = {
        "target_entity_type": "employee",
        "target_entity_id": "1",
        "field_name": "job_title",
        "old_value": "Eski",
        "requested_value": "Yeni",
        "justification": "Personelin ünvanı terfi nedeniyle güncellenmelidir.",
        "company_id": company_id,
        "requester_type": "employer",
        "channel": "platform",
    }
    payload.update(overrides)
    return payload


def _create(client, company_id: int, **overrides) -> dict:
    response = client.post("/api/v1/change-requests", json=_payload(company_id, **overrides))
    assert response.status_code == 200, response.text
    return response.json()


def test_create_and_list(setup):
    factory, ids = setup
    app, client = _client(factory, ids["requester"])
    try:
        created = _create(client, ids["company"])
        assert created["request_no"].startswith("CR-")
        assert created["status"] == "submitted"
        listed = client.get("/api/v1/change-requests").json()
        assert len(listed) == 1
    finally:
        app.dependency_overrides.clear()


def test_create_rejects_short_justification(setup):
    factory, ids = setup
    app, client = _client(factory, ids["requester"])
    try:
        response = client.post("/api/v1/change-requests", json=_payload(ids["company"], justification="kısa"))
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_detail_includes_events(setup):
    factory, ids = setup
    app, client = _client(factory, ids["requester"])
    try:
        created = _create(client, ids["company"])
        detail = client.get(f"/api/v1/change-requests/{created['id']}").json()
        assert detail["events"][0]["to_status"] == "submitted"
    finally:
        app.dependency_overrides.clear()


def test_requester_cannot_approve(setup):
    factory, ids = setup
    app, client = _client(factory, ids["requester"])
    try:
        created = _create(client, ids["company"])
        response = client.post(f"/api/v1/change-requests/{created['id']}/approve", json={"note": "ok"})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_full_flow_via_api(setup):
    factory, ids = setup
    created = None

    # Talep eden kendi talebini açar; doğrulama ve onay farklı bir yöneticide.
    app, client = _client(factory, ids["requester"])
    try:
        created = _create(client, ids["company"])
    finally:
        app.dependency_overrides.clear()

    app, client = _client(factory, ids["admin"])
    try:
        assert client.post(f"/api/v1/change-requests/{created['id']}/verify", json={"note": "kimlik doğrulandı"}).status_code == 200
    finally:
        app.dependency_overrides.clear()

    # 4 göz: doğrulayan onaylayamaz → onay için ikinci bir yönetici gerekir.
    with factory() as db:
        second = User(
            email="approver@example.com",
            full_name="İkinci Yönetici",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(second)
        db.commit()
        second_id = second.id

    app, client = _client(factory, second_id)
    try:
        assert client.post(f"/api/v1/change-requests/{created['id']}/approve", json={"note": "uygun"}).status_code == 200
    finally:
        app.dependency_overrides.clear()

    # Uygulama, onaylayandan farklı bir global admin ile yapılmalı; ikinci bir
    # aktör oluşturup servis üzerinden uygularız.
    from app.services import change_request as cr
    from app.services.change_request_apply import apply_change

    with factory() as db:
        applier = User(
            email="applier@example.com",
            full_name="Uygulayan",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(applier)
        db.commit()
        applier_id = applier.id
    with factory() as db:
        final = cr.apply_request(db, request_id=created["id"], user=db.get(User, applier_id), applier=apply_change)
    assert final.status == "applied"
    with factory() as db:
        assert db.get(Employee, ids["employee"]).job_title == "Yeni"


def test_reject_requires_reason(setup):
    factory, ids = setup
    app, client = _client(factory, ids["admin"])
    try:
        created = _create(client, ids["company"])
        response = client.post(f"/api/v1/change-requests/{created['id']}/reject", json={"reason": "kısa"})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_cancel_by_requester(setup):
    factory, ids = setup
    app, client = _client(factory, ids["requester"])
    try:
        created = _create(client, ids["company"])
        response = client.post(f"/api/v1/change-requests/{created['id']}/cancel", json={"note": "vazgeçildi"})
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    finally:
        app.dependency_overrides.clear()


def test_sla_overdue_endpoint(setup):
    factory, ids = setup
    app, client = _client(factory, ids["admin"])
    try:
        _create(client, ids["company"])
        response = client.get("/api/v1/change-requests/sla-overdue")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


def test_data_subject_request_and_export(setup):
    factory, ids = setup
    app, client = _client(factory, ids["admin"])
    try:
        response = client.post(
            "/api/v1/change-requests/data-subject",
            json={
                "request_kind": "access",
                "company_id": ids["company"],
                "employee_id": ids["employee"],
                "target_entity_type": "employee",
                "justification": "KVKK md.11 kapsamında kendi verilerime erişmek istiyorum.",
            },
        )
        assert response.status_code == 200, response.text
        request_id = response.json()["id"]
        assert response.json()["requester_type"] == "data_subject"
        assert response.json()["request_kind"] == "access"

        # Kimlik doğrulanmadan export engellenir.
        blocked = client.get(f"/api/v1/change-requests/{request_id}/export")
        assert blocked.status_code == 403

        assert client.post(
            f"/api/v1/change-requests/{request_id}/verify-identity",
            json={"note": "kayitli-yetkili-eslesmesi"},
        ).status_code == 200

        exported = client.get(f"/api/v1/change-requests/{request_id}/export")
        assert exported.status_code == 200, exported.text
        body = exported.json()
        assert body["person"]["full_name"] == "Ali Veli"
        assert body["identity_verified"] is True
    finally:
        app.dependency_overrides.clear()


def test_data_subject_rejects_bad_kind(setup):
    factory, ids = setup
    app, client = _client(factory, ids["admin"])
    try:
        response = client.post(
            "/api/v1/change-requests/data-subject",
            json={
                "request_kind": "gecersiz",
                "company_id": ids["company"],
                "justification": "Gerekçe yeterince uzun olmalıdır.",
            },
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_export_before_verification_is_blocked(setup):
    factory, ids = setup
    app, client = _client(factory, ids["admin"])
    try:
        response = client.post(
            "/api/v1/change-requests/data-subject",
            json={
                "request_kind": "access",
                "company_id": ids["company"],
                "employee_id": ids["employee"],
                "justification": "KVKK md.11 kapsamında kendi verilerime erişmek istiyorum.",
            },
        )
        request_id = response.json()["id"]
        assert client.get(f"/api/v1/change-requests/{request_id}/export").status_code == 403
    finally:
        app.dependency_overrides.clear()