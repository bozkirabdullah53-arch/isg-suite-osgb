def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("health_records"):
        return
    columns = {column["name"] for column in inspector.get_columns("health_records")}
    indexes = {index["name"] for index in inspector.get_indexes("health_records")}
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("health_records")}
    with op.batch_alter_table("health_records") as batch:
        if "physician_professional_id" not in columns:
            batch.add_column(sa.Column("physician_professional_id", sa.Integer(), nullable=True))
        if "updated_at" not in columns:
            batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        if "version" not in columns:
            batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "fk_health_records_physician_professional" not in foreign_keys:
            batch.create_foreign_key(
                "fk_health_records_physician_professional",
                "isg_professionals",
                ["physician_professional_id"],
                ["id"],
            )
        if "ix_health_records_physician_professional_id" not in indexes:
            batch.create_index("ix_health_records_physician_professional_id", ["physician_professional_id"])
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("health_records")}
    if "updated_at" in columns:
        op.execute(sa.text("UPDATE health_records SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP) WHERE updated_at IS NULL"))
    with op.batch_alter_table("health_records") as batch:
        if "updated_at" in columns:
            batch.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)

    with op.batch_alter_table("health_records") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)

    if not sa.inspect(op.get_bind()).has_table("health_record_revisions"):
        op.create_table(
            "health_record_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("record_id", sa.Integer(), sa.ForeignKey("health_records.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("previous_hash", sa.String(64), nullable=True),
            sa.Column("entry_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("record_id", "version", name="uq_health_revision_record_version"),
            sa.UniqueConstraint("entry_hash", name="uq_health_revision_entry_hash"),
        )
        op.create_index("ix_health_record_revisions_company_id", "health_record_revisions", ["company_id"])
        op.create_index("ix_health_record_revisions_record_id", "health_record_revisions", ["record_id"])
        op.create_index("ix_health_record_revisions_actor_user_id", "health_record_revisions", ["actor_user_id"])
        op.create_index("ix_health_record_revisions_action", "health_record_revisions", ["action"])
        op.create_index("ix_health_record_revisions_created_at", "health_record_revisions", ["created_at"])

    if not sa.inspect(op.get_bind()).has_table("health_access_logs"):
        op.create_table(
            "health_access_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("record_id", sa.Integer(), sa.ForeignKey("health_records.id"), nullable=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("purpose", sa.String(160), nullable=False, server_default="occupational_health_service"),
            sa.Column("request_path", sa.String(500), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("previous_hash", sa.String(64), nullable=True),
            sa.Column("entry_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("entry_hash", name="uq_health_access_entry_hash"),
        )
        op.create_index("ix_health_access_logs_company_id", "health_access_logs", ["company_id"])
        op.create_index("ix_health_access_logs_record_id", "health_access_logs", ["record_id"])
        op.create_index("ix_health_access_logs_actor_user_id", "health_access_logs", ["actor_user_id"])
        op.create_index("ix_health_access_logs_action", "health_access_logs", ["action"])
        op.create_index("ix_health_access_logs_created_at", "health_access_logs", ["created_at"])

    _append_only_triggers("health_record_revisions")
    _append_only_triggers("health_access_logs")
    _clinical_rls("health_records")
    _clinical_rls("health_record_revisions")
    _clinical_rls("health_access_logs")


def downgrade() -> None:
    bind = op.get_bind()
    _restore_company_rls("health_records")
    for table in ("health_access_logs", "health_record_revisions"):
        if bind.dialect.name == "postgresql":
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}"))
            op.execute(sa.text(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation()"))
        elif bind.dialect.name == "sqlite":
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_no_update"))
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete"))
    op.drop_table("health_access_logs")
    op.drop_table("health_record_revisions")
    with op.batch_alter_table("health_records") as batch:
        batch.drop_index("ix_health_records_physician_professional_id")
        batch.drop_constraint("fk_health_records_physician_professional", type_="foreignkey")
        batch.drop_column("version")
        batch.drop_column("updated_at")
        batch.drop_column("physician_professional_id")
