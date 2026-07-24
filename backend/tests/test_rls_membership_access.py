"""P1-03 RLS helper + P1-04 membership expand + kısa access TTL."""
from __future__ import annotations

from datetime import datetime

from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.company_access import assigned_company_ids
from app.core.config import settings
from app.core.rls import apply_rls_user
from app.core.security import ALGORITHM, create_access_token
from app.models.entities import (
    Base,
    Company,
    OsgbOrganization,
    User,
    UserRole,
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
