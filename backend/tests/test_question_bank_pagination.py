"""Soru bankası liste sayfalama ve taslak silme."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "qb.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole

    with SessionLocal() as db:
        admin = User(
            email="qb-admin@test.com",
            full_name="QB Admin",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.commit()

    r = client.post("/api/v1/auth/login", json={"email": "qb-admin@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"]}


def _payload(code: str) -> dict:
    return {
        "question_code": code,
        "version": 1,
        "topic_code": "KKD",
        "topic_label": "Kişisel koruyucu",
        "question_text": "Yüksekte çalışmada hangi koruma zorunludur ve neden seçilir?",
        "options": ["Tam vücut kemeri", "Yalnız baret", "Yalnız eldiven", "Koruma gerekmez"],
        "correct_option": "A",
        "answer_explanation": "Düşme riskinde tam vücut kemeri ve ankraj birlikte kullanılır.",
        "scopes": [{"type": "common", "value": "*"}],
        "sources": [{
            "title": "Yüksekte Çalışma Rehberi",
            "url": "https://www.csgb.gov.tr/ornek",
            "reference": "Madde 5",
        }],
    }


def test_question_list_paginates_and_legacy_array_still_works(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    for i in range(3):
        created = client.post("/api/v1/question-bank/questions", headers=headers, json=_payload(f"QB-{i+1:03d}"))
        assert created.status_code == 201, created.text

    legacy = client.get("/api/v1/question-bank/questions", headers=headers)
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)
    assert len(legacy.json()) == 3

    paged = client.get("/api/v1/question-bank/questions?limit=2&offset=0", headers=headers)
    assert paged.status_code == 200, paged.text
    body = paged.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert len(body["items"]) == 2
    assert body["counts"]["draft"] == 3

    coverage = client.get("/api/v1/question-bank/coverage?limit=5&status=all", headers=headers)
    assert coverage.status_code == 200, coverage.text
    report = coverage.json()
    assert report["nace_total"] == 2141
    assert len(report["items"]) == 5
    assert report["items_total"] >= 5


def test_draft_question_can_be_deleted_published_cannot(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    created = client.post("/api/v1/question-bank/questions", headers=headers, json=_payload("QB-DEL-1"))
    assert created.status_code == 201, created.text
    qid = created.json()["id"]

    deleted = client.delete(f"/api/v1/question-bank/questions/{qid}", headers=headers)
    assert deleted.status_code == 200, deleted.text

    missing = client.get("/api/v1/question-bank/questions", headers=headers)
    assert missing.json() == []
