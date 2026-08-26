"""Görsel saha denetimi retention bakım işi.

Retention uygulaması uygulama başlangıcında veya normal CRUD isteklerinde
çalıştırılmaz. Böylece mevcut kayıtlar ve raporlar beklenmedik biçimde
silinmez. Operasyon ekibi, ``FIELD_INSPECTION_RETENTION_DAYS`` değerini
belirleyip bu işi açıkça planladığında eski kayıtları geri alınabilir soft
archive durumuna alabilir.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AuditLog
from app.models.field_inspection import FieldInspection


def archive_expired_field_inspections(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 500,
    include_approved: bool = False,
    dry_run: bool = False,
) -> int:
    """Eski denetimleri soft-archive yapar ve etkilenen sayıyı döndürür.

    Onaylı raporlar ayrıca ``include_approved=True`` verilmedikçe korunur.
    Nesne depolamasındaki orijinal/analiz/işaretli dosyalar silinmez; bu bakım
    işi veri kaybını önlemek için yalnızca DB görünürlüğünü arşivler.
    """
    days = int(getattr(settings, "field_inspection_retention_days", 0) or 0)
    if days <= 0:
        return 0
    cutoff = (now or datetime.utcnow()) - timedelta(days=days)
    stmt = (
        select(FieldInspection)
        .where(FieldInspection.deleted_at.is_(None), FieldInspection.created_at < cutoff)
        .order_by(FieldInspection.created_at)
        .limit(max(1, min(int(limit or 500), 5000)))
    )
    if not include_approved:
        stmt = stmt.where(FieldInspection.status != "approved")
    rows = list(db.scalars(stmt).all())
    if dry_run or not rows:
        return len(rows)
    archived_at = now or datetime.utcnow()
    for row in rows:
        row.deleted_at = archived_at
        row.status = "archived"
        db.add(AuditLog(
            user_id=None,
            company_id=row.company_id,
            action="field_inspection_retention_archived",
            entity_type="field_inspection",
            entity_id=str(row.id),
            description=f"Retention bakımı ile {days} günlük süresi dolan görsel denetim arşivlendi.",
            module="field_inspection",
        ))
    db.commit()
    return len(rows)
