"""audit_logs.user_agent kolonu (güvenli, additive).

Denetimde "hangi cihaz/tarayıcı" sorusunun merkezî trail'den cevaplanabilmesi
için ``user_agent`` kolonu eklenir.

GÜVENLİ ROLLOUT NOTU
--------------------
Bu migration yalnızca kolonu ekler; mevcut hash zincirine (0121/0122) ve
``audit_chain_verify()`` fonksiyonuna DOKUNMAZ. Böylece deploy sırasında
audit_logs tablosu yeniden yazılmaz, kilit/timeout riski oluşmaz ve mevcut
kayıtların hash'leri geçerli kalır.

``user_agent`` alanını hash zincirine dahil etmek isteyen operatör, bunu
bakım penceresinde ayrı bir araçla yapar:

    python -m scripts.rebuild_audit_chain --dry-run
    python -m scripts.rebuild_audit_chain --apply

Revision ID: 0126
Revises: 0125
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0126"
down_revision: Union[str, None] = "0125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("audit_logs")}
    if "user_agent" in columns:
        return

    if bind.dialect.name == "postgresql":
        op.add_column("audit_logs", sa.Column("user_agent", sa.String(255), nullable=True))
    else:
        with op.batch_alter_table("audit_logs") as batch:
            batch.add_column(sa.Column("user_agent", sa.String(255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("audit_logs")}
    if "user_agent" not in columns:
        return

    if bind.dialect.name == "postgresql":
        op.drop_column("audit_logs", "user_agent")
    else:
        with op.batch_alter_table("audit_logs") as batch:
            batch.drop_column("user_agent")
