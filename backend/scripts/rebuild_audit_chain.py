"""audit_logs hash zincirini user_agent dahil edecek şekilde yeniden kurar.

NEDEN AYRI BİR ARAÇ?
--------------------
Zincir yeniden kurulumu O(n) bir işlemdir (her satırın hash'i bir öncekine
bağlıdır) ve ``audit_logs`` üzerindeki append-only trigger'ın geçici olarak
kaldırılmasını gerektirir. Bu işlemin canlı deploy migration'ına bağlanması
büyük tablolarda kilit/timeout riski taşır. Bu nedenle 0125 migration'ı yalnızca
``user_agent`` kolonunu ekler; zinciri hash'e dahil etmek isteyen operatör bu
aracı **bakım penceresinde** çalıştırır.

KULLANIM
--------
    python -m scripts.rebuild_audit_chain --dry-run    # sadece rapor, değişiklik yok
    python -m scripts.rebuild_audit_chain --apply      # zinciri yeniden kur

Güvenlik:
- Yalnızca PostgreSQL'de çalışır (hash zinciri oraya özgüdür).
- ``--apply`` olmadan hiçbir şey değişmez.
- İşlem tek bir set-tabanlı ifadeyle (recursive CTE) yapılır; satır satır
  döngü yoktur.
- İşlem sonunda zincir yeniden doğrulanır ve sonuç JSON olarak basılır.
- Herhangi bir adım başarısız olursa trigger'lar geri kurulur.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.services.audit_chain import verify_audit_chain  # noqa: E402

# user_agent, ip_address'ten sonra ve module'den önce yer alır.
_CANONICAL_INSERT = """concat_ws('|',
    coalesce(NEW.id::text, ''),
    coalesce(NEW.action, ''),
    coalesce(NEW.entity_type, ''),
    coalesce(NEW.entity_id, ''),
    coalesce(NEW.description, ''),
    coalesce(NEW.ip_address, ''),
    coalesce(NEW.user_agent, ''),
    coalesce(NEW.module, ''),
    coalesce(NEW.old_value, ''),
    coalesce(NEW.new_value, ''),
    coalesce(NEW.created_at::text, ''),
    coalesce(previous_hash, '')
)"""

_CANONICAL_VERIFY = """concat_ws('|',
    coalesce(id::text, ''),
    coalesce(action, ''),
    coalesce(entity_type, ''),
    coalesce(entity_id, ''),
    coalesce(description, ''),
    coalesce(ip_address, ''),
    coalesce(user_agent, ''),
    coalesce(module, ''),
    coalesce(old_value, ''),
    coalesce(new_value, ''),
    coalesce(created_at::text, ''),
    coalesce(prev_hash, '')
)"""

_HASH_FN = """
CREATE OR REPLACE FUNCTION audit_logs_hash_on_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    previous_hash TEXT;
    canonical TEXT;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('isgsuite.audit_logs.chain'));
    SELECT event_hash INTO previous_hash FROM audit_logs ORDER BY id DESC LIMIT 1;
    NEW.prev_hash := previous_hash;
    canonical := """ + _CANONICAL_INSERT + """;
    NEW.event_hash := encode(digest(canonical, 'sha256'), 'hex');
    RETURN NEW;
END;
$$;
"""

_GUARD_FN = """
CREATE OR REPLACE FUNCTION audit_logs_append_only_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_logs is append-only: DELETE is forbidden';
    END IF;

    IF (NEW.user_id IS NULL OR NEW.user_id = OLD.user_id)
       AND (NEW.company_id IS NULL OR NEW.company_id = OLD.company_id)
       AND (NEW.user_id IS DISTINCT FROM OLD.user_id
            OR NEW.company_id IS DISTINCT FROM OLD.company_id)
       AND NEW.id = OLD.id
       AND NEW.action IS NOT DISTINCT FROM OLD.action
       AND NEW.entity_type IS NOT DISTINCT FROM OLD.entity_type
       AND NEW.entity_id IS NOT DISTINCT FROM OLD.entity_id
       AND NEW.description IS NOT DISTINCT FROM OLD.description
       AND NEW.ip_address IS NOT DISTINCT FROM OLD.ip_address
       AND NEW.user_agent IS NOT DISTINCT FROM OLD.user_agent
       AND NEW.module IS NOT DISTINCT FROM OLD.module
       AND NEW.old_value IS NOT DISTINCT FROM OLD.old_value
       AND NEW.new_value IS NOT DISTINCT FROM OLD.new_value
       AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
       AND NEW.prev_hash IS NOT DISTINCT FROM OLD.prev_hash
       AND NEW.event_hash IS NOT DISTINCT FROM OLD.event_hash
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
      'audit_logs is append-only: only FK detach (user_id/company_id -> NULL) updates are permitted';
END;
$$;
"""

_VERIFY_FN = """
CREATE OR REPLACE FUNCTION audit_chain_verify()
RETURNS TABLE(total bigint, chain_breaks bigint, hash_breaks bigint)
LANGUAGE sql
STABLE
AS $$
    WITH ordered AS (
        SELECT
            id,
            event_hash,
            prev_hash,
            lag(event_hash) OVER (ORDER BY id) AS expected_prev,
            encode(digest(""" + _CANONICAL_VERIFY + """, 'sha256'), 'hex') AS expected_hash
        FROM audit_logs
    )
    SELECT
        count(*),
        count(*) FILTER (WHERE prev_hash IS DISTINCT FROM expected_prev),
        count(*) FILTER (WHERE event_hash IS DISTINCT FROM expected_hash)
    FROM ordered;
$$;
"""

# Set-tabanlı zincir kurulumu: satır satır döngü yerine tek recursive CTE.
_REBUILD = """
WITH RECURSIVE ordered AS (
    SELECT
        id,
        action, entity_type, entity_id, description,
        ip_address, user_agent, module, old_value, new_value, created_at,
        row_number() OVER (ORDER BY id) AS rn
    FROM audit_logs
),
chain AS (
    SELECT
        o.rn,
        o.id,
        encode(digest(concat_ws('|',
            coalesce(o.id::text, ''),
            coalesce(o.action, ''),
            coalesce(o.entity_type, ''),
            coalesce(o.entity_id, ''),
            coalesce(o.description, ''),
            coalesce(o.ip_address, ''),
            coalesce(o.user_agent, ''),
            coalesce(o.module, ''),
            coalesce(o.old_value, ''),
            coalesce(o.new_value, ''),
            coalesce(o.created_at::text, ''),
            coalesce(NULL::text, '')
        ), 'sha256'), 'hex') AS event_hash,
        NULL::text AS prev_hash
    FROM ordered o
    WHERE o.rn = 1
    UNION ALL
    SELECT
        o.rn,
        o.id,
        encode(digest(concat_ws('|',
            coalesce(o.id::text, ''),
            coalesce(o.action, ''),
            coalesce(o.entity_type, ''),
            coalesce(o.entity_id, ''),
            coalesce(o.description, ''),
            coalesce(o.ip_address, ''),
            coalesce(o.user_agent, ''),
            coalesce(o.module, ''),
            coalesce(o.old_value, ''),
            coalesce(o.new_value, ''),
            coalesce(o.created_at::text, ''),
            coalesce(c.event_hash, '')
        ), 'sha256'), 'hex') AS event_hash,
        c.event_hash AS prev_hash
    FROM ordered o
    JOIN chain c ON o.rn = c.rn + 1
)
UPDATE audit_logs a
   SET prev_hash = c.prev_hash,
       event_hash = c.event_hash
  FROM chain c
 WHERE a.id = c.id;
"""


def _row_count(db) -> int:
    return int(db.execute(text("SELECT count(*) FROM audit_logs")).scalar() or 0)


def _is_postgres(db) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def rebuild(*, apply: bool = False) -> dict:
    """Zinciri yeniden kurar. ``apply=False`` iken yalnızca rapor üretir."""
    with SessionLocal() as db:
        if not _is_postgres(db):
            return {
                "status": "unsupported",
                "reason": "postgresql_required",
                "dry_run": not apply,
                "detail": "Hash zinciri yalnızca PostgreSQL'de bulunur; değişiklik yapılmadı.",
            }

        before = verify_audit_chain(db)
        rows = _row_count(db)
        report: dict = {
            "status": "dry-run" if not apply else "ok",
            "row_count": rows,
            "before": before,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        if not apply:
            report["action"] = "Değişiklik yapılmadı. Uygulamak için --apply kullanın."
            return report

        triggers_dropped = False
        try:
            db.execute(text("DROP TRIGGER IF EXISTS trg_audit_logs_hash_on_insert ON audit_logs"))
            db.execute(text("DROP TRIGGER IF EXISTS trg_audit_logs_append_only_guard ON audit_logs"))
            triggers_dropped = True

            db.execute(text(_HASH_FN))
            db.execute(text(_GUARD_FN))
            db.execute(text(_VERIFY_FN))

            db.execute(text(_REBUILD))

            db.execute(text(
                """
                CREATE TRIGGER trg_audit_logs_hash_on_insert
                BEFORE INSERT ON audit_logs
                FOR EACH ROW
                EXECUTE FUNCTION audit_logs_hash_on_insert();
                """
            ))
            db.execute(text(
                """
                CREATE TRIGGER trg_audit_logs_append_only_guard
                BEFORE UPDATE OR DELETE ON audit_logs
                FOR EACH ROW
                EXECUTE FUNCTION audit_logs_append_only_guard();
                """
            ))
            db.commit()
            triggers_dropped = False
        except Exception as exc:  # noqa: BLE001 - trigger'lar geri kurulmalı
            db.rollback()
            if triggers_dropped:
                try:
                    db.execute(text(
                        """
                        CREATE TRIGGER trg_audit_logs_hash_on_insert
                        BEFORE INSERT ON audit_logs
                        FOR EACH ROW
                        EXECUTE FUNCTION audit_logs_hash_on_insert();
                        """
                    ))
                    db.execute(text(
                        """
                        CREATE TRIGGER trg_audit_logs_append_only_guard
                        BEFORE UPDATE OR DELETE ON audit_logs
                        FOR EACH ROW
                        EXECUTE FUNCTION audit_logs_append_only_guard();
                        """
                    ))
                    db.commit()
                except Exception:  # pragma: no cover - en iyi çaba
                    db.rollback()
            report["status"] = "error"
            report["error_class"] = type(exc).__name__
            report["error"] = str(exc)[:400]
            return report

        report["after"] = verify_audit_chain(db)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description="audit_logs hash zincirini yeniden kur")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Yalnızca rapor üret")
    group.add_argument("--apply", action="store_true", help="Zinciri yeniden kur")
    parser.add_argument("--out", type=Path, default=None, help="Kanıt JSON yolu")
    args = parser.parse_args()

    report = rebuild(apply=bool(args.apply))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report.get("status") == "error":
        return 1
    if report.get("status") == "ok":
        after = report.get("after") or {}
        return 0 if after.get("ok") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
