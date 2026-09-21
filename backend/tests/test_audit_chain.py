"""0121/0122 — append-only audit trail: FK detach akışı + zincir doğrulama endpoint'i.

Production'da (PostgreSQL) audit_logs tamamen append-only'dir; tek istisna
kullanıcı/firma kalıcı silme akışlarındaki FK bağı koparma (user_id/company_id
-> NULL) bakım güncellemesidir. Bu testler SQLite üzerinde:
- detach öncesi atıf (attribution) audit olayının yazıldığını,
- eski kayıtların user_id bağının koptuğunu,
- /security/audit-chain endpoint'inin yalnız global admin'e açık olduğunu ve
  doğrulamanın kendisinin de loglandığını doğrular.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "audit_chain.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed():
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import AuditLog, Company, OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Audit OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(
            name="Audit Co", osgb_id=osgb.id, is_active=True, hazard_class="Az Tehlikeli"
        )
        db.add(company)
        db.flush()
        admin = User(
            email="admin@test.com",
            full_name="Global Admin",
            hashed_password=get_password_hash("AdminPass123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
            token_version=0,
        )
        comp_admin = User(
            email="cadmin@test.com",
            full_name="Company Admin",
            hashed_password=get_password_hash("CAdminPass123!"),
            role=UserRole.COMPANY_ADMIN,
            company_id=company.id,
            osgb_id=osgb.id,
            is_active=True,
            token_version=0,
        )
        victim = User(
            email="victim@test.com",
            full_name="Victim User",
            hashed_password=get_password_hash("VictimPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            company_id=company.id,
            osgb_id=osgb.id,
            is_active=True,
            token_version=0,
        )
        db.add_all([admin, comp_admin, victim])
        db.flush()
        db.add(
            AuditLog(
                user_id=victim.id,
                company_id=company.id,
                action="legacy_action",
                entity_type="test",
                description="Victim'a ait geçmiş audit kaydı",
            )
        )
        db.commit()
        return {"admin": admin.id, "comp_admin": comp_admin.id, "victim": victim.id, "company": company.id}


def _token(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_user_writes_detach_attribution(client):
    ids = _seed()
    headers = _token(client, "admin@test.com", "AdminPass123!")

    response = client.delete(f"/api/v1/users/{ids['victim']}", headers=headers)
    assert response.status_code == 200, response.text

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import AuditLog

    with SessionLocal() as db:
        attribution = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "audit_actor_detach",
                AuditLog.entity_type == "user",
                AuditLog.entity_id == str(ids["victim"]),
            )
        )
        assert attribution is not None, "detach öncesi atıf olayı yazılmalı"
        assert "1 audit kaydının" in (attribution.description or "")

        legacy = db.scalar(select(AuditLog).where(AuditLog.action == "legacy_action"))
        assert legacy is not None
        assert legacy.user_id is None, "FK bağı koparılmalı (içerik korunur)"
        assert legacy.description == "Victim'a ait geçmiş audit kaydı"


def test_audit_chain_endpoint_requires_global_admin(client):
    ids = _seed()
    admin_headers = _token(client, "admin@test.com", "AdminPass123!")
    comp_headers = _token(client, "cadmin@test.com", "CAdminPass123!")

    forbidden = client.get("/api/v1/security/audit-chain", headers=comp_headers)
    assert forbidden.status_code == 403

    allowed = client.get("/api/v1/security/audit-chain", headers=admin_headers)
    assert allowed.status_code == 200, allowed.text
    payload = allowed.json()
    assert payload == {"supported": False, "reason": "postgresql_required"}


def test_audit_chain_verification_is_itself_logged(client):
    _seed()
    admin_headers = _token(client, "admin@test.com", "AdminPass123!")

    assert client.get("/api/v1/security/audit-chain", headers=admin_headers).status_code == 200

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.entities import AuditLog

    with SessionLocal() as db:
        row = db.scalar(select(AuditLog).where(AuditLog.action == "audit_chain_verified"))
        assert row is not None
        assert "supported=False" in (row.description or "")
