"""P1-08: Postgres CI only — migration sonrası canlı benzeri kısıt smoke."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("CI_POSTGRES") != "1",
    reason="Only runs in CI Postgres job",
)


@pytest.fixture()
def pg_session():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionLocal() as db:
        yield db
        db.rollback()


def test_alembic_head_applied(pg_session: Session):
    ver = pg_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert ver is not None
    # Head dosya adı 0039… — en az 0039 olmalı (string compare revision id)
    assert str(ver) >= "0042"


def test_same_name_different_osgb_allowed(pg_session: Session):
    from app.models.entities import Company, OsgbOrganization

    o1 = OsgbOrganization(name="CI OSGB A", is_active=True)
    o2 = OsgbOrganization(name="CI OSGB B", is_active=True)
    pg_session.add_all([o1, o2])
    pg_session.flush()

    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o1.id, is_active=True))
    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o2.id, is_active=True))
    pg_session.flush()  # should not raise

    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o1.id, is_active=True))
    with pytest.raises(IntegrityError):
        pg_session.flush()
