"""Real PostgreSQL RLS integration, using a disposable schema and non-owner role."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def load_migration(name):
    path = Path(__file__).parents[1] / 'alembic' / 'versions' / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_postgres_workplace_reader_cannot_mutate_clinical_records():
    url = os.getenv('HEALTH_RLS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set HEALTH_RLS_TEST_DATABASE_URL to a disposable PostgreSQL database')
    from app.core.rls import apply_rls_user
    from app.models.entities import UserRole
    from sqlalchemy.orm import Session
    engine = sa.create_engine(url)
    schema = 'health_test_' + uuid4().hex
    role = 'health_reader_' + uuid4().hex
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(sa.text(f'CREATE SCHEMA {schema}'))
            conn.execute(sa.text(f'SET LOCAL search_path TO {schema}'))
            conn.execute(sa.text(f'CREATE ROLE {role} NOLOGIN'))
            conn.execute(sa.text('CREATE TABLE health_records (id integer PRIMARY KEY, company_id integer, note text)'))
            conn.execute(sa.text('CREATE TABLE health_access_logs (id integer PRIMARY KEY, company_id integer, actor_user_id integer)'))
            conn.execute(sa.text("INSERT INTO health_records VALUES (1,10,'own'), (2,20,'other')"))
            old = load_migration('0086_health_clinical_p0.py')
            new = load_migration('0115_workplace_health_read.py')
            operations = Operations(MigrationContext.configure(conn))
            old.op = operations
            new.op = operations
            for table in ('health_records', 'health_access_logs'):
                old._clinical_rls(table)
            new.upgrade()
            conn.execute(sa.text(f'GRANT USAGE ON SCHEMA {schema} TO {role}'))
            conn.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {role}'))
            conn.execute(sa.text(f'SET LOCAL ROLE {role}'))
            db = Session(bind=conn)
            user = SimpleNamespace(id=7, company_id=10, osgb_id=1, email='manager@test.com', role=UserRole.COMPANY_ADMIN)
            apply_rls_user(db, user)
            assert conn.execute(sa.text('SELECT id FROM health_records')).scalars().all() == [1]
            assert conn.execute(sa.text("UPDATE health_records SET note='changed'")).rowcount == 0
            assert conn.execute(sa.text('DELETE FROM health_records')).rowcount == 0
            with pytest.raises(sa.exc.DBAPIError):
                with conn.begin_nested():
                    conn.execute(sa.text("INSERT INTO health_records VALUES (3,10,'new')"))
            conn.execute(sa.text('INSERT INTO health_access_logs VALUES (1,10,7)'))
            for sql in ['INSERT INTO health_access_logs VALUES (2,20,7)', 'INSERT INTO health_access_logs VALUES (3,10,8)']:
                with pytest.raises(sa.exc.DBAPIError):
                    with conn.begin_nested():
                        conn.execute(sa.text(sql))
            assert conn.execute(sa.text('UPDATE health_access_logs SET actor_user_id=8')).rowcount == 0
            assert conn.execute(sa.text('DELETE FROM health_access_logs')).rowcount == 0
            user.email = 'shared@kiosk.isgsuite.tr'
            apply_rls_user(db, user)
            assert conn.execute(sa.text('SELECT id FROM health_records')).scalars().all() == []
            conn.execute(sa.text('RESET ROLE'))
            new.downgrade()
            assert conn.execute(sa.text("SELECT note FROM health_records WHERE id=1")).scalar_one() == 'own'
        finally:
            tx.rollback()  # schema and role were created inside the transaction
    engine.dispose()
