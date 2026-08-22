"""P1-03 RLS helper + P1-04 membership expand + kısa access TTL."""
from __future__ import annotations

from datetime import date, datetime

import pytest
import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.company_access import assigned_company_ids
from app.core.config import settings
from app.core.rls import apply_rls_user
from app.core.security import ALGORITHM, create_access_token
from app.models.entities import (
    Base,
    AssignmentStatus,
    Company,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
    WorkplaceMembership,
)


def test_apply_rls_user_noop_on_sqlite(tmp_path):
    url = f"sqlite:///{(tmp_path / 'rls.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session() as db:
        apply_rls_user(db, 42)
        apply_rls_user(db, None)


def test_apply_rls_user_sets_allowed_companies_on_sqlite_noop(tmp_path):
    """SQLite'ta set_config yok — User nesnesiyle de no-op kalmalı."""
    url = f"sqlite:///{(tmp_path / 'rls2.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session() as db:
        o = OsgbOrganization(name="RLS OSGB", is_active=True)
        db.add(o)
        db.flush()
        c = Company(name="RLS Co", osgb_id=o.id, is_active=True)
        db.add(c)
        db.flush()
        u = User(
            email="rls@test.com",
            full_name="RLS",
            hashed_password="x",
            role=UserRole.COMPANY_ADMIN,
            company_id=None,
            osgb_id=o.id,
            is_active=True,
        )
        db.add(u)
        db.commit()
        apply_rls_user(db, u)


def test_membership_expands_assigned_companies(tmp_path):
    url = f"sqlite:///{(tmp_path / 'exp.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session() as db:
        o = OsgbOrganization(name="E OSGB", is_active=True)
        db.add(o)
        db.flush()
        c1 = Company(name="E1", osgb_id=o.id, is_active=True)
        c2 = Company(name="E2", osgb_id=o.id, is_active=True)
        db.add_all([c1, c2])
        db.flush()
        u = User(
            email="exp@test.com",
            full_name="Exp",
            hashed_password="x",
            role=UserRole.READ_ONLY,
            company_id=c1.id,
            osgb_id=o.id,
            is_active=True,
        )
        db.add(u)
        db.flush()
        assert assigned_company_ids(db, u) == [c1.id]
        db.add(
            WorkplaceMembership(
                user_id=u.id,
                company_id=c2.id,
                role="read_only",
                is_active=True,
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
        ids = assigned_company_ids(db, u)
        assert c1.id in ids and c2.id in ids


@pytest.mark.parametrize(
    ("role", "professional_type", "label"),
    [
        (UserRole.WORKPLACE_PHYSICIAN, ProfessionalType.WORKPLACE_PHYSICIAN, "Hekim"),
        (UserRole.OTHER_HEALTH_PERSONNEL, ProfessionalType.OTHER_HEALTH_PERSONNEL, "DSP"),
    ],
)
def test_health_roles_ignore_membership_and_legacy_company_without_active_assignment(
    tmp_path, role, professional_type, label
):
    url = f"sqlite:///{(tmp_path / 'health-strict.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session() as db:
        osgb = OsgbOrganization(name="Health Strict OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        assigned = Company(name="Assigned", osgb_id=osgb.id, is_active=True)
        legacy = Company(name="Legacy", osgb_id=osgb.id, is_active=True)
        membership = Company(name="Membership", osgb_id=osgb.id, is_active=True)
        db.add_all([assigned, legacy, membership])
        db.flush()
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name=f"Strict {label}",
            email=f"strict-{label.casefold()}@test.com",
            professional_type=professional_type,
            is_active=True,
        )
        db.add(pro)
        db.flush()
        user = User(
            email=f"strict-{label.casefold()}@test.com",
            full_name=f"Strict {label}",
            hashed_password="x",
            role=role,
            osgb_id=osgb.id,
            company_id=legacy.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add_all([
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=assigned.id,
                professional_id=pro.id,
                professional_type=professional_type,
                start_date=date(2025, 1, 1),
                status=AssignmentStatus.ACTIVE,
            ),
            WorkplaceMembership(
                user_id=user.id,
                company_id=membership.id,
                role=role.value,
                is_active=True,
                created_at=datetime.utcnow(),
            ),
        ])
        db.commit()
        assert assigned_company_ids(db, user) == [assigned.id]

        assignment = db.query(WorkplaceAssignment).one()
        assignment.status = AssignmentStatus.ENDED
        db.commit()
        assert assigned_company_ids(db, user) == []


def test_short_access_ttl_when_refresh_cookie_on(monkeypatch):
    settings.auth_refresh_cookie_enabled = True
    settings.access_token_expire_minutes = 60
    settings.access_token_expire_minutes_short = 15
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    try:
        tok = create_access_token("1", purpose="access", token_version=0)
        payload = jwt.decode(tok, settings.secret_key, algorithms=[ALGORITHM])
        # ~15 dk (900 sn); 60 dk olsaydı ~3600
        import time

        remaining = int(payload["exp"]) - int(time.time())
        assert 500 < remaining < 20 * 60
    finally:
        settings.auth_refresh_cookie_enabled = False
