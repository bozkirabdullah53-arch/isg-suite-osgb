"""CI Postgres parity — alembic head + kritik şema/kısıt kontrolleri (P1-08)."""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, inspect, text


def _url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL required")
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def main() -> int:
    url = _url()
    if "sqlite" in url.lower():
        print("SKIP: sqlite URL — bu script Postgres için")
        return 0

    engine = create_engine(url, pool_pre_ping=True)
    insp = inspect(engine)

    required_tables = [
        "alembic_version",
        "companies",
        "users",
        "osgb_organizations",
        "token_denylist",
        "site_qr_sessions",
        "health_records",
    ]
    missing = [t for t in required_tables if not insp.has_table(t)]
    if missing:
        print("FAIL: missing tables:", ", ".join(missing))
        return 1

    with engine.connect() as conn:
        ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        print(f"alembic_version={ver}")
        if not ver:
            print("FAIL: alembic_version empty")
            return 1

        # companies: name tek başına unique olmamalı; (osgb_id, name) unique olmalı
        uqs = insp.get_unique_constraints("companies")
        indexes = insp.get_indexes("companies")
        name_only_unique = False
        for uq in uqs:
            cols = list(uq.get("column_names") or [])
            if cols == ["name"]:
                name_only_unique = True
        for ix in indexes:
            if ix.get("unique") and list(ix.get("column_names") or []) == ["name"]:
                name_only_unique = True
        if name_only_unique:
            print("FAIL: companies.name still globally unique")
            return 1

        scoped = False
        for uq in uqs:
            cols = set(uq.get("column_names") or [])
            if cols == {"osgb_id", "name"} or uq.get("name") == "uq_company_osgb_name":
                scoped = True
        for ix in indexes:
            cols = set(ix.get("column_names") or [])
            if ix.get("unique") and cols == {"osgb_id", "name"}:
                scoped = True
        if not scoped:
            print("FAIL: uq_company_osgb_name / (osgb_id, name) missing")
            print(" unique_constraints=", uqs)
            print(" indexes=", indexes)
            return 1

        # token_version kolonu
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "token_version" not in user_cols:
            print("FAIL: users.token_version missing")
            return 1

    print("OK: postgres parity checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
