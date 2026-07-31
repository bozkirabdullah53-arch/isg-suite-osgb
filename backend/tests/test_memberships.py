"""P1-04 membership helpers — fallback to User fields when tables empty."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.entities import (
    Base,
    Company,
    OrganizationMembership,
    OsgbOrganization,
    User,
    UserRole,
    WorkplaceMembership,
)
from app.services.memberships import (
    active_company_ids_for_user,
    active_osgb_ids_for_user,
    user_has_company_membership,
    user_has_osgb_membership,
)


def _session(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mem.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_fallback_to_user_fields(tmp_path):
    db = _session(tmp_path)
    o = OsgbOrganization(name="M OSGB", is_active=True)
    db.add(o)
    db.flush()
    c = Company(name="M Co", osgb_id=o.id, is_active=True)
    db.add(c)
    db.flush()
    u = User(
        email="m@test.com",
        full_name="M",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        osgb_id=o.id,
        company_id=c.id,
        is_active=True,
    )
    db.add(u)
    db.commit()

    assert active_osgb_ids_for_user(db, u) == [o.id]
    assert active_company_ids_for_user(db, u) == [c.id]
    assert user_has_osgb_membership(db, u, o.id)
    assert not user_has_osgb_membership(db, u, 999)
    assert user_has_company_membership(db, u, c.id)


def test_membership_table_overrides_user_fields(tmp_path):
    db = _session(tmp_path)
    o1 = OsgbOrganization(name="O1", is_active=True)
    o2 = OsgbOrganization(name="O2", is_active=True)
    db.add_all([o1, o2])
    db.flush()
    c1 = Company(name="C1", osgb_id=o1.id, is_active=True)
    c2 = Company(name="C2", osgb_id=o2.id, is_active=True)
    db.add_all([c1, c2])
    db.flush()
    u = User(
        email="multi@test.com",
        full_name="Multi",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        osgb_id=o1.id,
        company_id=c1.id,
        is_active=True,
    )
    db.add(u)
    db.flush()
    db.add_all(
        [
            OrganizationMembership(
                user_id=u.id, osgb_id=o1.id, role="company_admin", is_active=True, created_at=datetime.utcnow()
            ),
            OrganizationMembership(
                user_id=u.id, osgb_id=o2.id, role="company_admin", is_active=True, created_at=datetime.utcnow()
            ),
            WorkplaceMembership(
                user_id=u.id, company_id=c2.id, role="company_admin", is_active=True, created_at=datetime.utcnow()
            ),
        ]
    )
    db.commit()

    assert active_osgb_ids_for_user(db, u) == sorted([o1.id, o2.id])
    # Table satırları varsa user.company_id fallback kullanılmaz
    assert active_company_ids_for_user(db, u) == [c2.id]
    assert user_has_company_membership(db, u, c2.id)
    assert not user_has_company_membership(db, u, c1.id)
