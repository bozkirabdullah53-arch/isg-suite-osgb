from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.entities import User, UserRole
from app.services.training_nace_registry import materialize_registry

pytestmark = pytest.mark.skipif(
    os.getenv("CI_POSTGRES") != "1",
    reason="Only runs in CI Postgres job",
)


def test_candidate_catalog_materializes_once_on_postgres():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionLocal() as db:
        admin = User(
            email="nace-registry-ci@example.test",
            full_name="NACE Registry CI",
            hashed_password="ci-test-hash",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()

        first = materialize_registry(db, created_by_id=admin.id)
        db.flush()
        second = materialize_registry(db, created_by_id=admin.id)

        assert first["created"] is True
        assert first["status"] == "candidate"
        assert first["entry_count"] == 2141
        assert second["created"] is False
        assert second["id"] == first["id"]
        assert db.execute(text("SELECT COUNT(*) FROM training_nace_catalog_versions")).scalar_one() == 1
        assert db.execute(text("SELECT COUNT(*) FROM training_nace_catalog_entries")).scalar_one() == 2141
        assert db.execute(
            text("SELECT COUNT(DISTINCT nace_code) FROM training_nace_catalog_entries")
        ).scalar_one() == 2141
        assert db.execute(
            text("SELECT COUNT(*) FROM training_nace_catalog_versions WHERE status='active'")
        ).scalar_one() == 0
        db.rollback()
