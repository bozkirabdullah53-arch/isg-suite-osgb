"""P1-08: Postgres CI only — migration sonrası canlı benzeri kısıt smoke."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("CI_POSTGRES") != "1",
    reason="Only runs in CI Postgres job",
)

EXPECTED_RLS_TABLES = {
    "annual_plan_evaluation_items",
    "annual_plan_evaluations",
    "annual_plan_items",
    "annual_plan_unplanned_activities",
    "branches",
    "chemical_products",
    "companies",
    "company_subscriptions",
    "document_approvals",
    "document_records",
    "drill_records",
    "e_sign_artifacts",
    "e_sign_requests",
    "e_signature_audit_events",
    "e_signature_requests",
    "emergency_plan_floors",
    "emergency_plans",
    "emergency_team_assignments",
    "emergency_teams",
    "employees",
    "eyas_events",
    "eyas_steps",
    "eyas_workflows",
    "health_records",
    "incident_events",
    "isg_records",
    "legal_acceptances",
    "medula_error_logs",
    "notifications",
    "ohs_committee_meeting_versions",
    "ohs_committee_meetings",
    "ohs_committee_members",
    "ohs_committee_signature_steps",
    "organization_memberships",
    "periodic_controls",
    "ppe_assignments",
    "prescription_items",
    "prescription_submission_attempts",
    "prescription_submissions",
    "prescriptions",
    "risk_assessments",
    "service_contracts",
    "service_visits",
    "site_qr_sessions",
    "training_sessions",
    "workplace_assignments",
    "workplace_departments",
    "workplace_measurements",
    "workplace_memberships",
}


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
    assert ver == "0078_training_nace_registry"


def test_same_name_different_osgb_allowed(pg_session: Session):
    from app.models.entities import Company, OsgbOrganization

    o1 = OsgbOrganization(name="CI OSGB A", is_active=True)
    o2 = OsgbOrganization(name="CI OSGB B", is_active=True)
    pg_session.add_all([o1, o2])
    pg_session.flush()

    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o1.id, is_active=True))
    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o2.id, is_active=True))
    pg_session.flush()

    pg_session.add(Company(name="CI Shared Name Ltd", osgb_id=o1.id, is_active=True))
    with pytest.raises(IntegrityError):
        pg_session.flush()


def test_expected_rls_policies_are_enabled_and_forced(pg_session: Session):
    rows = pg_session.execute(
        text(
            """
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS rls_enabled,
                   c.relforcerowsecurity AS force_rls,
                   COUNT(p.oid)::int AS policy_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_policy p ON p.polrelid = c.oid
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname = ANY(:tables)
            GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
            """
        ),
        {"tables": sorted(EXPECTED_RLS_TABLES)},
    ).mappings().all()
    by_table = {row["table_name"]: row for row in rows}

    assert set(by_table) == EXPECTED_RLS_TABLES
    for table_name in EXPECTED_RLS_TABLES:
        row = by_table[table_name]
        assert row["rls_enabled"] is True, table_name
        assert row["force_rls"] is True, table_name
        assert row["policy_count"] == 1, table_name


def test_training_nace_registry_schema_and_constraints(pg_session: Session):
    inspector = inspect(pg_session.bind)
    assert inspector.has_table("training_nace_catalog_versions")
    assert inspector.has_table("training_nace_catalog_entries")

    version_columns = {
        column["name"] for column in inspector.get_columns("training_nace_catalog_versions")
    }
    assert {
        "version_code",
        "content_hash",
        "source_label",
        "source_url",
        "status",
        "entry_count",
        "created_by_id",
        "created_at",
        "activated_by_id",
        "activated_at",
    } <= version_columns

    entry_columns = {
        column["name"] for column in inspector.get_columns("training_nace_catalog_entries")
    }
    assert {
        "version_id",
        "nace_code",
        "nace_key",
        "description",
        "division_code",
        "activity_group_code",
        "main_sector_code",
        "main_sector_name",
        "profile_code",
        "profile_name",
        "hazard_class",
        "risk_tags_json",
        "special_risks_json",
        "topics_json",
        "lesson_hours",
        "instruction_minutes",
        "scheduled_minutes",
        "sector_lesson_hours",
        "sector_instruction_minutes",
        "sector_scheduled_minutes",
        "mapping_status",
        "validation_errors_json",
    } <= entry_columns

    version_uqs = inspector.get_unique_constraints("training_nace_catalog_versions")
    assert any(
        constraint.get("name") == "uq_training_nace_catalog_content_hash"
        and set(constraint.get("column_names") or []) == {"content_hash"}
        for constraint in version_uqs
    )
    entry_uqs = inspector.get_unique_constraints("training_nace_catalog_entries")
    assert any(
        constraint.get("name") == "uq_training_nace_catalog_entry"
        and set(constraint.get("column_names") or []) == {"version_id", "nace_code"}
        for constraint in entry_uqs
    )


def test_committee_approval_schema_and_constraints(pg_session: Session):
    inspector = inspect(pg_session.bind)
    meeting_columns = {column["name"] for column in inspector.get_columns("ohs_committee_meetings")}
    assert {
        "approval_workflow_id",
        "approval_status",
        "approval_current_step",
        "document_version",
        "approval_submitted_at",
        "approval_completed_at",
        "approval_invalidated_at",
        "updated_at",
    } <= meeting_columns

    member_columns = {column["name"] for column in inspector.get_columns("ohs_committee_members")}
    assert {
        "removed_at",
        "removed_by_id",
        "removal_reason_code",
        "removal_reason_text",
        "removal_document_version",
    } <= member_columns

    assert inspector.has_table("ohs_committee_signature_steps")
    assert inspector.has_table("ohs_committee_meeting_versions")

    signature_uqs = inspector.get_unique_constraints("ohs_committee_signature_steps")
    assert any(
        constraint.get("name") == "uq_committee_signature_version_step"
        and set(constraint.get("column_names") or []) == {"meeting_id", "document_version", "step_order"}
        for constraint in signature_uqs
    )
    version_uqs = inspector.get_unique_constraints("ohs_committee_meeting_versions")
    assert any(
        constraint.get("name") == "uq_committee_meeting_version"
        and set(constraint.get("column_names") or []) == {"meeting_id", "document_version"}
        for constraint in version_uqs
    )


def test_new_committee_history_tables_hide_cross_tenant_rows(pg_session: Session):
    from app.models.entities import Company, OsgbOrganization, User, UserRole

    osgb_a = OsgbOrganization(name="CI Committee RLS A", is_active=True)
    osgb_b = OsgbOrganization(name="CI Committee RLS B", is_active=True)
    pg_session.add_all([osgb_a, osgb_b])
    pg_session.flush()
    company_a = Company(name="CI Committee Company A", osgb_id=osgb_a.id, is_active=True)
    company_b = Company(name="CI Committee Company B", osgb_id=osgb_b.id, is_active=True)
    pg_session.add_all([company_a, company_b])
    pg_session.flush()
    user = User(
        email="committee-rls@example.test",
        full_name="Committee RLS User",
        hashed_password="test-hash",
        role=UserRole.GLOBAL_ADMIN,
        is_active=True,
    )
    pg_session.add(user)
    pg_session.flush()
    meeting_ids = []
    for company in (company_a, company_b):
        meeting_ids.append(
            pg_session.execute(
                text("""
                    INSERT INTO ohs_committee_meetings
                        (company_id, meeting_date, is_active, created_by_id, created_at,
                         status, signature_status, approval_status, document_version)
                    VALUES
                        (:company_id, CURRENT_DATE, true, :user_id, CURRENT_TIMESTAMP,
                         'draft', 'not_signed', 'draft', 1)
                    RETURNING id
                """),
                {"company_id": company.id, "user_id": user.id},
            ).scalar_one()
        )
    for company, meeting_id in zip((company_a, company_b), meeting_ids, strict=True):
        pg_session.execute(
            text("""
                INSERT INTO ohs_committee_meeting_versions
                    (meeting_id, company_id, document_version, meeting_snapshot_json,
                     archive_reason, created_by_id, created_at)
                VALUES
                    (:meeting_id, :company_id, 1, '{}', 'ci', :user_id, CURRENT_TIMESTAMP)
            """),
            {"meeting_id": meeting_id, "company_id": company.id, "user_id": user.id},
        )
    pg_session.flush()

    pg_session.execute(
        text("""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ci_committee_rls_reader') THEN
                CREATE ROLE ci_committee_rls_reader NOLOGIN NOSUPERUSER NOBYPASSRLS;
              END IF;
            END
            $$;
        """)
    )
    pg_session.execute(text("GRANT USAGE ON SCHEMA public TO ci_committee_rls_reader"))
    pg_session.execute(text("GRANT SELECT ON TABLE ohs_committee_meeting_versions TO ci_committee_rls_reader"))
    pg_session.execute(text("SET LOCAL ROLE ci_committee_rls_reader"))
    pg_session.execute(text("SELECT set_config('app.current_user_id', '9101', true)"))
    pg_session.execute(
        text("SELECT set_config('app.allowed_company_ids', :allowed, true)"),
        {"allowed": str(company_a.id)},
    )
    pg_session.execute(text("SELECT set_config('app.rls_bypass', '', true)"))
    visible = pg_session.execute(
        text("SELECT company_id FROM ohs_committee_meeting_versions ORDER BY company_id")
    ).scalars().all()
    pg_session.execute(text("RESET ROLE"))
    assert visible == [company_a.id]


def test_companies_rls_hides_cross_tenant_rows_for_non_bypass_role(pg_session: Session):
    from app.models.entities import Company, OsgbOrganization

    osgb_a = OsgbOrganization(name="CI RLS OSGB A", is_active=True)
    osgb_b = OsgbOrganization(name="CI RLS OSGB B", is_active=True)
    pg_session.add_all([osgb_a, osgb_b])
    pg_session.flush()
    company_a = Company(name="CI RLS Company A", osgb_id=osgb_a.id, is_active=True)
    company_b = Company(name="CI RLS Company B", osgb_id=osgb_b.id, is_active=True)
    pg_session.add_all([company_a, company_b])
    pg_session.flush()

    pg_session.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ci_rls_reader') THEN
                CREATE ROLE ci_rls_reader NOLOGIN NOSUPERUSER NOBYPASSRLS;
              END IF;
            END
            $$;
            """
        )
    )
    pg_session.execute(text("GRANT USAGE ON SCHEMA public TO ci_rls_reader"))
    pg_session.execute(text("GRANT SELECT ON TABLE companies TO ci_rls_reader"))
    pg_session.execute(text("SET LOCAL ROLE ci_rls_reader"))
    pg_session.execute(text("SELECT set_config('app.current_user_id', '9001', true)"))
    pg_session.execute(
        text("SELECT set_config('app.allowed_company_ids', :allowed, true)"),
        {"allowed": str(company_a.id)},
    )
    pg_session.execute(text("SELECT set_config('app.rls_bypass', '', true)"))
    pg_session.execute(text("SELECT set_config('app.rls_admin', '', true)"))

    visible = pg_session.execute(
        text("SELECT id FROM companies WHERE id IN (:a, :b) ORDER BY id"),
        {"a": company_a.id, "b": company_b.id},
    ).scalars().all()
    pg_session.execute(text("RESET ROLE"))

    assert visible == [company_a.id]
