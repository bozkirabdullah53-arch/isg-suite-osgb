"""0065/0066: güncel metadata ile kurulmuş veritabanında tekrar çalışabilmeli."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


def _load_migration(filename: str, module_name: str):
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _create_current_eyas_schema(conn: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table("companies", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("document_records", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table(
        "eyas_workflows",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=True),
    )
    steps = sa.Table(
        "eyas_steps",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
    )
    sa.Index("ix_eyas_steps_wf_order", steps.c.workflow_id, steps.c.step_order, unique=True)
    sa.Table("eyas_events", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(conn)


def _create_prerequisite_schema(conn: sa.Connection) -> None:
    metadata = sa.MetaData()
    sa.Table("companies", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    sa.Table("document_records", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    metadata.create_all(conn)


def test_0065_0066_upgrade_is_safe_when_current_schema_already_exists(tmp_path):
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'eyas.db').as_posix()}")
    migration_0065 = _load_migration("0065_eyas_digital_approval.py", "mig_0065")
    migration_0066 = _load_migration("0066_eyas_source_key.py", "mig_0066")

    with engine.begin() as conn:
        _create_current_eyas_schema(conn)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration_0065.upgrade()
            migration_0066.upgrade()
            migration_0065.upgrade()
            migration_0066.upgrade()

    insp = sa.inspect(engine)
    assert {"eyas_workflows", "eyas_steps", "eyas_events"}.issubset(insp.get_table_names())
    assert "source_key" in {item["name"] for item in insp.get_columns("eyas_workflows")}
    assert "ix_eyas_steps_wf_order" in {item["name"] for item in insp.get_indexes("eyas_steps")}


def test_0065_0066_create_missing_schema_and_can_run_twice(tmp_path):
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'eyas-empty.db').as_posix()}")
    migration_0065 = _load_migration("0065_eyas_digital_approval.py", "mig_0065_empty")
    migration_0066 = _load_migration("0066_eyas_source_key.py", "mig_0066_empty")

    with engine.begin() as conn:
        _create_prerequisite_schema(conn)
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration_0065.upgrade()
            migration_0066.upgrade()
            migration_0065.upgrade()
            migration_0066.upgrade()

    insp = sa.inspect(engine)
    assert {"eyas_workflows", "eyas_steps", "eyas_events"}.issubset(insp.get_table_names())
    assert "source_key" in {item["name"] for item in insp.get_columns("eyas_workflows")}
    assert "ix_eyas_steps_wf_order" in {item["name"] for item in insp.get_indexes("eyas_steps")}
