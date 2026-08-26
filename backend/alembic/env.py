from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import personnel_profile  # noqa: F401
from app.models import personnel_profile_document  # noqa: F401
from app.models import training_nace  # noqa: F401
from app.models import training_presentation  # noqa: F401
from app.models import training_presentation_approval  # noqa: F401
from app.models import field_inspection  # noqa: F401
from app.services.personnel_profile_osgb_scope import install_osgb_profile_metadata_scope

install_osgb_profile_metadata_scope()

config = context.config

# Ensure psycopg (v3) is used with PostgreSQL URLs
_db_url = settings.database_url
if _db_url.startswith("postgresql://") and "+psycopg" not in _db_url:
    _db_url = _db_url.replace("postgresql://", "postgresql+psycopg://", 1)

config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
