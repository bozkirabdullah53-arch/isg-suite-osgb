"""Formatted XLSX exports for professional performance.

Legacy CSV routes in app.api.osgb remain unchanged for backward compatibility.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import reject_company_bound_admin_from_osgb_internal, require_roles
from app.core.database import get_db
from app.models.entities import IsgProfessional, User, UserRole
from app.services.professional_performance_detail_excel import (
    build_professional_performance_detail_xlsx_safe,
)
from app.services.professional_performance_excel import (
    XLSX_MEDIA_TYPE,
    build_professional_performance_roster_xlsx,
)

router = APIRouter(
    prefix="/osgb",
    tags=["OSGB Yönetimi"],
    dependencies=[Depends(reject_company_bound_admin_from_osgb_internal)],
)
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)


def _resolve_osgb_scope(user: User, osgb_id: int | None) -> int | None:
    """Apply the same OSGB boundary as the existing CSV endpoints."""
    from app.core.tenant_context import assert_osgb_access, current_tenant

    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil.")
        return user.osgb_id

    if osgb_id is not None:
        if current_tenant() is not None:
            assert_osgb_access(osgb_id)
        elif user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != osgb_id:
            raise HTTPException(403, "Bu OSGB kaydına erişim yetkiniz yok.")
    return osgb_id


@router.get("/professionals/performance/export.xlsx")
def professional_performance_roster_xlsx(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """OSGB genel profesyonel performans raporu — biçimlendirilmiş gerçek Excel."""
    target_osgb_id = _resolve_osgb_scope(user, osgb_id)
    data, filename = build_professional_performance_roster_xlsx(db, osgb_id=target_osgb_id)
    return StreamingResponse(
        iter([data]),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/professionals/{professional_id}/performance/export.xlsx")
def professional_performance_detail_xlsx(
    professional_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Seçili profesyonelin özet, eksik, tamamlanan ve firma checklist Excel'i."""
    professional = db.get(IsgProfessional, professional_id)
    if not professional:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id or professional.osgb_id != user.osgb_id:
            raise HTTPException(403, "Bu profesyonelin performansına erişemezsiniz.")
    else:
        _resolve_osgb_scope(user, professional.osgb_id)
    try:
        data, filename = build_professional_performance_detail_xlsx_safe(db, professional_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return StreamingResponse(
        iter([data]),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
