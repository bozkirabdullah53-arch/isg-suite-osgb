"""EİSA OSGB kalıcı silmede training_participants FK regresyonu."""
from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_file = tmp_path / "osgb_purge_training.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    import app.core.database as dbmod
    import app.models.entities as ent
    import app.models.personnel_profile  # noqa: F401
    import app.models.personnel_profile_document  # noqa: F401

    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    session = dbmod.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_osgb_training_participant_cleanup_is_direct_and_scoped(db):
    """OSGB personellerinin eğitim katılımları Employee silinmeden önce doğrudan temizlenir."""
    from sqlalchemy import select

    from app.models.entities import (
        Company,
        Employee,
        OsgbOrganization,
        TrainingParticipant,
        TrainingSession,
        User,
        UserRole,
    )
    from app.services.osgb_purge import _purge_osgb_training_participants

    osgb = OsgbOrganization(name="Training FK OSGB", authorization_number="TR-FK-1", is_active=False)
    db.add(osgb)
    db.flush()

    company = Company(name="Training FK Company", osgb_id=osgb.id, is_active=True, hazard_class="Az Tehlikeli")
    db.add(company)
    db.flush()

    creator = User(
        email="training-fk@example.com",
        full_name="Training Creator",
        hashed_password="test-hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    db.add(creator)
    db.flush()

    employee = Employee(company_id=company.id, full_name="Silinecek Personel", is_active=True)
    db.add(employee)
    db.flush()

    training = TrainingSession(
        company_id=company.id,
        title="Regresyon Eğitimi",
        training_type="Temel İSG Eğitimi",
        delivery_method="Yüz yüze",
        start_date=date(2026, 8, 9),
        duration_hours=8,
        renewal_years=3,
        hazard_class="Az Tehlikeli",
        instructor_name="Test Eğitici",
        created_by_id=creator.id,
    )
    db.add(training)
    db.flush()

    participant = TrainingParticipant(training_id=training.id, employee_id=employee.id, attended=True)
    db.add(participant)
    db.commit()

    participant_id = participant.id
    employee_id = employee.id
    training_id = training.id

    _purge_osgb_training_participants(db, osgb.id)
    db.commit()

    assert db.get(TrainingParticipant, participant_id) is None
    assert db.get(Employee, employee_id) is not None
    assert db.get(TrainingSession, training_id) is not None
    assert db.scalars(
        select(TrainingParticipant).where(TrainingParticipant.employee_id == employee_id)
    ).all() == []
