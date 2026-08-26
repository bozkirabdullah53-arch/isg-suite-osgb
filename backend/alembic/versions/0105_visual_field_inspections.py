"""Additive GPS/photo/AI visual field inspection module.

Revision ID: 0105_visual_field_inspections
Revises: 0105_risk_media_analysis

All objects are new and nullable links to legacy risk data are intentionally
absent from the old tables. Existing field-inspection and risk rows are not
rewritten or migrated.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0105_visual_field_inspections"
down_revision: Union[str, None] = "0105_risk_media_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _index_exists(bind, name: str) -> bool:
    for table in sa.inspect(bind).get_table_names():
        if any(item.get("name") == name for item in sa.inspect(bind).get_indexes(table)):
            return True
    return False


def _columns(bind, table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(bind).get_columns(table)} if _table_exists(bind, table) else set()


def _index(name: str, table: str, *columns: str) -> None:
    bind = op.get_bind()
    if _table_exists(bind, table) and not _index_exists(bind, name):
        op.create_index(name, table, list(columns))


def _enable_rls(bind, table: str, expression: str) -> None:
    if bind.dialect.name != "postgresql" or not _table_exists(bind, table):
        return
    policy = f"{table}_company_scope"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f"""
        DO $policy$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE schemaname = current_schema()
              AND tablename = '{table}'
              AND policyname = '{policy}'
          ) THEN
            CREATE POLICY "{policy}" ON "{table}"
              FOR ALL
              USING (
                COALESCE(current_setting('app.current_user_id', true), '') = ''
                OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                OR ({expression})
              )
              WITH CHECK (
                COALESCE(current_setting('app.current_user_id', true), '') = ''
                OR COALESCE(current_setting('app.rls_bypass', true), '') = '1'
                OR ({expression})
              );
          END IF;
        END
        $policy$;
    """))


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "field_hazard_categories"):
        op.create_table(
            "field_hazard_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(180), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("icon", sa.String(60), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("name", name="uq_field_hazard_category_name"),
        )
    if not _table_exists(bind, "field_hazards"):
        op.create_table(
            "field_hazards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("field_hazard_categories.id", ondelete="CASCADE"), nullable=False),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="CASCADE"), nullable=True),
            sa.Column("name", sa.String(220), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("equipment_scope", sa.String(220), nullable=True),
            sa.Column("keywords_json", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("category_id", "company_id", "osgb_id", "name", name="uq_field_hazard_category_company_name"),
        )
    if not _table_exists(bind, "field_inspection_sites"):
        op.create_table(
            "field_inspection_sites",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(220), nullable=False), sa.Column("name_key", sa.String(220), nullable=False), sa.Column("site_type", sa.String(100), nullable=True),
            sa.Column("address", sa.String(500), nullable=True), sa.Column("description", sa.Text(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("company_id", "name_key", name="uq_field_site_company_name_key"),
        )
    if not _table_exists(bind, "field_inspection_areas"):
        op.create_table(
            "field_inspection_areas",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("field_inspection_sites.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(220), nullable=False), sa.Column("name_key", sa.String(220), nullable=False),
            sa.Column("description", sa.Text(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("site_id", "name_key", name="uq_field_area_site_name_key"),
        )
    if not _table_exists(bind, "field_inspection_equipment"):
        op.create_table(
            "field_inspection_equipment",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("field_inspection_sites.id", ondelete="CASCADE"), nullable=False), sa.Column("area_id", sa.Integer(), sa.ForeignKey("field_inspection_areas.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(220), nullable=False), sa.Column("name_key", sa.String(220), nullable=False), sa.Column("equipment_type", sa.String(120), nullable=True), sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("area_id", "name_key", name="uq_field_equipment_area_name_key"),
        )
    if not _table_exists(bind, "field_inspections"):
        op.create_table(
            "field_inspections",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("inspection_no", sa.String(40), nullable=False, unique=True), sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("site_id", sa.Integer(), sa.ForeignKey("field_inspection_sites.id", ondelete="RESTRICT"), nullable=False), sa.Column("area_id", sa.Integer(), sa.ForeignKey("field_inspection_areas.id", ondelete="RESTRICT"), nullable=False), sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("field_inspection_equipment.id", ondelete="SET NULL"), nullable=True),
            sa.Column("inspection_date", sa.Date(), nullable=False), sa.Column("inspection_at", sa.DateTime(), nullable=False), sa.Column("timezone", sa.String(80), nullable=False, server_default="Europe/Istanbul"),
            sa.Column("gps_lat", sa.Float(), nullable=True), sa.Column("gps_lng", sa.Float(), nullable=True), sa.Column("gps_accuracy_m", sa.Float(), nullable=True), sa.Column("gps_captured_at", sa.DateTime(), nullable=True), sa.Column("gps_status", sa.String(30), nullable=False, server_default="not_available"), sa.Column("gps_provider", sa.String(60), nullable=True), sa.Column("gps_reason", sa.String(500), nullable=True), sa.Column("manual_location_note", sa.String(500), nullable=True),
            sa.Column("selected_category_ids_json", sa.Text(), nullable=True), sa.Column("selected_hazard_ids_json", sa.Text(), nullable=True), sa.Column("scan_all_hazards", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("notes", sa.Text(), nullable=True), sa.Column("client_reference", sa.String(100), nullable=True),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"), sa.Column("ai_status", sa.String(40), nullable=False, server_default="not_started"), sa.Column("ai_job_id", sa.String(80), nullable=True), sa.Column("ai_error", sa.Text(), nullable=True), sa.Column("ai_model_name", sa.String(120), nullable=True), sa.Column("ai_model_version", sa.String(80), nullable=True), sa.Column("ai_prompt_version", sa.String(40), nullable=True), sa.Column("ai_analysis_at", sa.DateTime(), nullable=True), sa.Column("ai_general_assessment", sa.Text(), nullable=True), sa.Column("ai_warning", sa.Text(), nullable=True),
            sa.Column("report_revision_no", sa.Integer(), nullable=False, server_default="1"), sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("approved_at", sa.DateTime(), nullable=True), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("company_id", "client_reference", name="uq_field_inspection_company_client_ref"),
        )
    if not _table_exists(bind, "field_inspection_photos"):
        op.create_table(
            "field_inspection_photos",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("field_inspections.id", ondelete="CASCADE"), nullable=False), sa.Column("site_id", sa.Integer(), sa.ForeignKey("field_inspection_sites.id", ondelete="SET NULL"), nullable=True), sa.Column("area_id", sa.Integer(), sa.ForeignKey("field_inspection_areas.id", ondelete="SET NULL"), nullable=True), sa.Column("equipment_id", sa.Integer(), sa.ForeignKey("field_inspection_equipment.id", ondelete="SET NULL"), nullable=True), sa.Column("original_storage_path", sa.String(500), nullable=False), sa.Column("analysis_storage_path", sa.String(500), nullable=False), sa.Column("marked_storage_path", sa.String(500), nullable=False), sa.Column("preview_storage_path", sa.String(500), nullable=False), sa.Column("original_name", sa.String(255), nullable=True), sa.Column("content_type", sa.String(120), nullable=False, server_default="image/jpeg"), sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"), sa.Column("width", sa.Integer(), nullable=True), sa.Column("height", sa.Integer(), nullable=True), sa.Column("edit_meta_json", sa.Text(), nullable=True), sa.Column("captured_at", sa.DateTime(), nullable=True), sa.Column("timezone", sa.String(80), nullable=True), sa.Column("gps_lat", sa.Float(), nullable=True), sa.Column("gps_lng", sa.Float(), nullable=True), sa.Column("gps_accuracy_m", sa.Float(), nullable=True), sa.Column("gps_captured_at", sa.DateTime(), nullable=True), sa.Column("gps_status", sa.String(30), nullable=False, server_default="not_available"), sa.Column("gps_provider", sa.String(60), nullable=True), sa.Column("gps_reason", sa.String(500), nullable=True), sa.Column("manual_location_note", sa.String(500), nullable=True), sa.Column("blur_applied", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("client_reference", sa.String(100), nullable=True), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("deleted_at", sa.DateTime(), nullable=True), sa.UniqueConstraint("inspection_id", "client_reference", name="uq_field_photo_inspection_client_ref"),
        )
    for column, foreign_key in (
        ("site_id", "field_inspection_sites.id"),
        ("area_id", "field_inspection_areas.id"),
        ("equipment_id", "field_inspection_equipment.id"),
    ):
        if _table_exists(bind, "field_inspection_photos") and column not in _columns(bind, "field_inspection_photos"):
            op.add_column("field_inspection_photos", sa.Column(column, sa.Integer(), sa.ForeignKey(foreign_key, ondelete="SET NULL"), nullable=True))
    if _table_exists(bind, "field_inspection_photos") and "edit_meta_json" not in _columns(bind, "field_inspection_photos"):
        op.add_column("field_inspection_photos", sa.Column("edit_meta_json", sa.Text(), nullable=True))
    if _table_exists(bind, "field_inspection_photos") and "manual_location_note" not in _columns(bind, "field_inspection_photos"):
        op.add_column("field_inspection_photos", sa.Column("manual_location_note", sa.String(500), nullable=True))
    if not _table_exists(bind, "field_inspection_findings"):
        op.create_table(
            "field_inspection_findings",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("field_inspections.id", ondelete="CASCADE"), nullable=False), sa.Column("photo_id", sa.Integer(), sa.ForeignKey("field_inspection_photos.id", ondelete="SET NULL"), nullable=True), sa.Column("field_category_id", sa.Integer(), sa.ForeignKey("field_hazard_categories.id", ondelete="SET NULL"), nullable=True), sa.Column("field_hazard_id", sa.Integer(), sa.ForeignKey("field_hazards.id", ondelete="SET NULL"), nullable=True), sa.Column("finding_no", sa.Integer(), nullable=False), sa.Column("category_name", sa.String(180), nullable=True), sa.Column("hazard_name", sa.String(220), nullable=False), sa.Column("area_name", sa.String(220), nullable=True), sa.Column("equipment_name", sa.String(220), nullable=True), sa.Column("visual_evidence", sa.Text(), nullable=False), sa.Column("nonconformity_description", sa.Text(), nullable=False), sa.Column("possible_cause", sa.Text(), nullable=True), sa.Column("possible_harm", sa.Text(), nullable=True), sa.Column("possible_accident_or_disease", sa.Text(), nullable=True), sa.Column("suggested_priority", sa.String(30), nullable=False, server_default="medium"), sa.Column("priority_reason", sa.Text(), nullable=True), sa.Column("confidence", sa.Float(), nullable=True), sa.Column("uncertainty_note", sa.Text(), nullable=True), sa.Column("urgent_action", sa.Text(), nullable=True), sa.Column("corrective_action", sa.Text(), nullable=True), sa.Column("preventive_action", sa.Text(), nullable=True), sa.Column("engineering_control", sa.Text(), nullable=True), sa.Column("administrative_control", sa.Text(), nullable=True), sa.Column("training_need", sa.Text(), nullable=True), sa.Column("required_ppe", sa.Text(), nullable=True), sa.Column("suggested_responsible_role", sa.String(180), nullable=True), sa.Column("suggested_term_date", sa.Date(), nullable=True), sa.Column("status", sa.String(40), nullable=False, server_default="ai_draft"), sa.Column("source", sa.String(30), nullable=False, server_default="ai"), sa.Column("ai_model_name", sa.String(120), nullable=True), sa.Column("ai_model_version", sa.String(80), nullable=True), sa.Column("ai_prompt_version", sa.String(40), nullable=True), sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("reviewed_at", sa.DateTime(), nullable=True), sa.Column("review_note", sa.Text(), nullable=True), sa.Column("linked_risk_id", sa.Integer(), sa.ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True), sa.Column("linked_dof_id", sa.Integer(), sa.ForeignKey("risk_dofs.id", ondelete="SET NULL"), nullable=True), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.UniqueConstraint("inspection_id", "finding_no", name="uq_field_finding_inspection_no"),
        )
    if not _table_exists(bind, "field_inspection_annotations"):
        op.create_table(
            "field_inspection_annotations",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("field_inspections.id", ondelete="CASCADE"), nullable=False), sa.Column("photo_id", sa.Integer(), sa.ForeignKey("field_inspection_photos.id", ondelete="CASCADE"), nullable=False), sa.Column("finding_id", sa.Integer(), sa.ForeignKey("field_inspection_findings.id", ondelete="SET NULL"), nullable=True), sa.Column("shape_type", sa.String(30), nullable=False, server_default="rectangle"), sa.Column("x", sa.Float(), nullable=False, server_default="0"), sa.Column("y", sa.Float(), nullable=False, server_default="0"), sa.Column("width", sa.Float(), nullable=False, server_default="0"), sa.Column("height", sa.Float(), nullable=False, server_default="0"), sa.Column("points_json", sa.Text(), nullable=True), sa.Column("label", sa.String(220), nullable=True), sa.Column("color", sa.String(20), nullable=False, server_default="#dc2626"), sa.Column("source", sa.String(20), nullable=False, server_default="manual"), sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _table_exists(bind, "field_inspection_legal_references"):
        op.create_table(
            "field_inspection_legal_references",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("finding_id", sa.Integer(), sa.ForeignKey("field_inspection_findings.id", ondelete="CASCADE"), nullable=False), sa.Column("regulation_name", sa.String(300), nullable=False), sa.Column("article", sa.String(120), nullable=True), sa.Column("paragraph", sa.String(120), nullable=True), sa.Column("source_url", sa.String(600), nullable=True), sa.Column("source_version", sa.String(120), nullable=True), sa.Column("relation_explanation", sa.Text(), nullable=True), sa.Column("verification_status", sa.String(30), nullable=False, server_default="needs_expert_review"), sa.Column("verified_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if not _table_exists(bind, "field_inspection_actions"):
        op.create_table(
            "field_inspection_actions",
            sa.Column("id", sa.Integer(), primary_key=True), sa.Column("inspection_id", sa.Integer(), sa.ForeignKey("field_inspections.id", ondelete="CASCADE"), nullable=False), sa.Column("finding_id", sa.Integer(), sa.ForeignKey("field_inspection_findings.id", ondelete="SET NULL"), nullable=True), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(300), nullable=False), sa.Column("activity", sa.Text(), nullable=False), sa.Column("urgent_action", sa.Text(), nullable=True), sa.Column("permanent_solution", sa.Text(), nullable=True), sa.Column("preventive_action", sa.Text(), nullable=True), sa.Column("responsible_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True), sa.Column("responsible_person", sa.String(180), nullable=True), sa.Column("responsible_role", sa.String(180), nullable=True), sa.Column("term_date", sa.Date(), nullable=True), sa.Column("priority", sa.String(30), nullable=False, server_default="medium"), sa.Column("status", sa.String(30), nullable=False, server_default="open"), sa.Column("completion_date", sa.Date(), nullable=True), sa.Column("evidence_photo_id", sa.Integer(), sa.ForeignKey("field_inspection_photos.id", ondelete="SET NULL"), nullable=True), sa.Column("notes", sa.Text(), nullable=True), sa.Column("expert_control_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True), sa.Column("expert_control_at", sa.DateTime(), nullable=True), sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    _index("ix_field_hazard_categories_name", "field_hazard_categories", "name")
    _index("ix_field_hazard_categories_is_active", "field_hazard_categories", "is_active")
    _index("ix_field_hazards_category_id", "field_hazards", "category_id")
    _index("ix_field_hazards_company_id", "field_hazards", "company_id")
    _index("ix_field_hazards_osgb_id", "field_hazards", "osgb_id")
    _index("ix_field_hazards_name", "field_hazards", "name")
    for table, column in (("field_inspection_sites", "company_id"), ("field_inspection_sites", "name"), ("field_inspection_areas", "company_id"), ("field_inspection_areas", "site_id"), ("field_inspection_equipment", "company_id"), ("field_inspection_equipment", "site_id"), ("field_inspection_equipment", "area_id"), ("field_inspections", "company_id"), ("field_inspections", "inspection_no"), ("field_inspections", "inspection_date"), ("field_inspections", "inspection_at"), ("field_inspections", "gps_status"), ("field_inspections", "status"), ("field_inspections", "ai_status"), ("field_inspection_photos", "inspection_id"), ("field_inspection_photos", "site_id"), ("field_inspection_photos", "area_id"), ("field_inspection_photos", "equipment_id"), ("field_inspection_photos", "gps_status"), ("field_inspection_findings", "inspection_id"), ("field_inspection_findings", "photo_id"), ("field_inspection_findings", "field_category_id"), ("field_inspection_findings", "field_hazard_id"), ("field_inspection_findings", "status"), ("field_inspection_annotations", "inspection_id"), ("field_inspection_annotations", "photo_id"), ("field_inspection_annotations", "finding_id"), ("field_inspection_annotations", "is_deleted"), ("field_inspection_legal_references", "finding_id"), ("field_inspection_actions", "inspection_id"), ("field_inspection_actions", "finding_id"), ("field_inspection_actions", "company_id"), ("field_inspection_actions", "term_date"), ("field_inspection_actions", "status")):
        _index(f"ix_{table}_{column}", table, column)

    _enable_rls(bind, "field_hazards", '(("field_hazards".company_id IS NULL AND ("field_hazards".osgb_id IS NULL OR "field_hazards".osgb_id = NULLIF(current_setting(\'app.current_osgb_id\', true), \'\')::integer)) OR (COALESCE(current_setting(\'app.allowed_company_ids\', true), \'\') <> \'\' AND "field_hazards".company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')
    for table in ("field_inspection_sites", "field_inspection_areas", "field_inspection_equipment", "field_inspections", "field_inspection_actions"):
        _enable_rls(bind, table, f'(COALESCE(current_setting(\'app.allowed_company_ids\', true), \'\') <> \'\' AND "{table}".company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')
    _enable_rls(bind, "field_inspection_photos", 'EXISTS (SELECT 1 FROM field_inspections fi WHERE fi.id = "field_inspection_photos".inspection_id AND fi.company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')
    _enable_rls(bind, "field_inspection_findings", 'EXISTS (SELECT 1 FROM field_inspections fi WHERE fi.id = "field_inspection_findings".inspection_id AND fi.company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')
    _enable_rls(bind, "field_inspection_annotations", 'EXISTS (SELECT 1 FROM field_inspections fi WHERE fi.id = "field_inspection_annotations".inspection_id AND fi.company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')
    _enable_rls(bind, "field_inspection_legal_references", 'EXISTS (SELECT 1 FROM field_inspection_findings ff JOIN field_inspections fi ON fi.id = ff.inspection_id WHERE ff.id = "field_inspection_legal_references".finding_id AND fi.company_id = ANY(string_to_array(current_setting(\'app.allowed_company_ids\', true), \',\')::integer[]))')


def downgrade() -> None:
    # Rollback is deliberately explicit and opt-in; normal deploys never call
    # downgrade. New module tables can be removed in reverse FK order without
    # touching any legacy table.
    bind = op.get_bind()
    for table in ("field_inspection_actions", "field_inspection_legal_references", "field_inspection_annotations", "field_inspection_findings", "field_inspection_photos", "field_inspections", "field_inspection_equipment", "field_inspection_areas", "field_inspection_sites", "field_hazards", "field_hazard_categories"):
        if _table_exists(bind, table):
            op.drop_table(table)
