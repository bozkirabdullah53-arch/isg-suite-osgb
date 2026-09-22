"""Tamper-evident audit zinciri doğrulaması (0122 ile gelen PG fonksiyonu).

Production PostgreSQL'de ``audit_chain_verify()`` set-tabanlı kontrolü çalıştırır:
- chain_breaks: prev_hash ↔ lag(event_hash) uyuşmazlığı (kayıt silme/ekleme/sıralama oynatma)
- hash_breaks: event_hash ↔ satır içeriğinden yeniden hesaplanan hash uyuşmazlığı (içerik tahrifatı)

SQLite (dev/test) veya migration henüz uygulanmadıysa güvenli biçimde
``supported: False`` döner; asla servis kesintisine yol açmaz.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session


def verify_audit_chain(db: Session) -> dict:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return {"supported": False, "reason": "postgresql_required"}
    try:
        row = db.execute(
            text("SELECT total, chain_breaks, hash_breaks FROM audit_chain_verify()")
        ).one()
    except ProgrammingError:
        db.rollback()
        return {"supported": False, "reason": "migration_0122_pending"}
    total, chain_breaks, hash_breaks = int(row[0]), int(row[1]), int(row[2])
    return {
        "supported": True,
        "total": total,
        "chain_breaks": chain_breaks,
        "hash_breaks": hash_breaks,
        "ok": chain_breaks == 0 and hash_breaks == 0,
    }


def audit_chain_health() -> dict:
    """Sağlık/release çıktısı için güvenli zincir durumu (kendi oturumunu açar).

    Denetim zinciri kontrolü hiçbir zaman çağıran akışı bozmaz.
    """
    try:
        from app.core.database import SessionLocal

        with SessionLocal() as db:
            return verify_audit_chain(db)
    except Exception as exc:  # pragma: no cover - savunmacı
        return {"supported": False, "reason": type(exc).__name__, "ok": None}
