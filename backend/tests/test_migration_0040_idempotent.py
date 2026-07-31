"""0040: eski unique constraint + stale index drop prod hatasını önle."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import op
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations


def _load_0040():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0040_assignment_active_unique.py"
    spec = importlib.util.spec_from_file_location("mig_0040", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_0040_upgrade_after_named_unique_constraint(tmp_path):
    """Prod senaryosu: uq_company_professional_assignment constraint var; DROP INDEX IF EXISTS gerekir."""
    url = f"sqlite:///{(tmp_path / 'm40.db').as_posix()}"
    engine = sa.create_engine(url)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE workplace_assignments (
                id INTEGER PRIMARY KEY,
                company_id INTEGER NOT NULL,
                professional_id INTEGER NOT NULL,
                professional_type VARCHAR(40) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active'
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX uq_company_professional_assignment "
            "ON workplace_assignments (company_id, professional_id, professional_type)"
        )

    mod = _load_0040()
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()
            # İkinci kez de güvenli (idempotent)
            mod.upgrade()

    insp = sa.inspect(engine)
    names = {i["name"] for i in insp.get_indexes("workplace_assignments")}
    assert "uq_assignment_active_company_pro_type" in names
    assert "uq_company_professional_assignment" not in names
