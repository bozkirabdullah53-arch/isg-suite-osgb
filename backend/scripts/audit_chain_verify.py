"""Denetim zinciri periyodik doğrulama (İBYS Veritabanı Değişiklik Prosedürü §8).

``audit_chain_verify()`` fonksiyonunu çalıştırır, sonucu JSON basar ve zincir
bozuksa exit code 1 döndürür. Zincir bozuksa global yöneticilere bildirim üretir.

Kullanım:
  python -m scripts.audit_chain_verify
  python -m scripts.audit_chain_verify --out docs/qa/logs/audit-chain-verify.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.services.audit_chain import verify_audit_chain  # noqa: E402

logger = logging.getLogger(__name__)


def _notify_admins(chain_breaks: int, hash_breaks: int) -> int:
    """Zincir bozulduğunda global yöneticilere kritik bildirim gönderir."""
    from sqlalchemy import select

    from app.models.entities import Notification, NotificationType, User, UserRole

    sent = 0
    try:
        with SessionLocal() as db:
            admins = list(
                db.scalars(
                    select(User).where(User.role == UserRole.GLOBAL_ADMIN, User.is_active.is_(True))
                ).all()
            )
            for admin in admins:
                db.add(
                    Notification(
                        user_id=admin.id,
                        company_id=None,
                        type=NotificationType.CRITICAL,
                        title="Denetim zinciri bütünlüğü bozuldu",
                        message=(
                            f"audit_logs hash zincirinde {chain_breaks} sıra kırığı ve "
                            f"{hash_breaks} hash uyuşmazlığı tespit edildi. "
                            "Kayıtlar değiştirilmiş veya zincir bozulmuş olabilir; derhal inceleyin."
                        ),
                        entity_type="audit_chain",
                        entity_id=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    )
                )
            db.commit()
            sent = len(admins)
    except Exception:  # pragma: no cover - alarm asla doğrulamayı bozmaz
        logger.exception("Denetim zinciri bildirimi gönderilemedi")
    return sent


def run_verify(*, out: Path | None = None, notify: bool = True) -> dict:
    with SessionLocal() as db:
        result = verify_audit_chain(db)
    result["ran_at"] = datetime.now(timezone.utc).isoformat()
    result["ok"] = bool(result.get("ok"))
    if not result["ok"] and result.get("supported"):
        if notify:
            result["notified_admins"] = _notify_admins(
                int(result.get("chain_breaks") or 0),
                int(result.get("hash_breaks") or 0),
            )
    result["exit_code"] = 0 if result["ok"] else 1
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Periyodik denetim zinciri doğrulaması")
    parser.add_argument("--out", type=Path, default=None, help="Kanıt JSON yolu")
    parser.add_argument("--no-notify", action="store_true", help="Bildirim gönderme")
    args = parser.parse_args()
    result = run_verify(out=args.out, notify=not args.no_notify)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
