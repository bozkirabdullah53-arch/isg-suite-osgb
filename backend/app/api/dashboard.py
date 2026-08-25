from datetime import date
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Employee,
    IncidentDof,
    RiskAssessment,
    RiskDof,
    User,
    UserRole,
)
from app.api.company_access import assigned_company_ids, find_professional_for_user
from app.services.capacity_engine import build_capacity_overview
from app.services.professional_duty import build_my_duty_board, format_duty_report_txt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Panel"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    field_roles = {
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    }
    if user.role == UserRole.GLOBAL_ADMIN:
        cc = db.scalar(select(func.count()).select_from(Company).where(Company.is_active.is_(True))) or 0
        bc = db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))) or 0
        ec = db.scalar(select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))) or 0
        uc = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
        open_risks = db.scalar(
            select(func.count()).select_from(RiskAssessment).where(RiskAssessment.status == "Açık")
        ) or 0
        open_capa = (
            db.scalar(
                select(func.count()).select_from(IncidentDof).where(IncidentDof.status != "Tamamlandı")
            )
            or 0
        ) + (
            db.scalar(
                select(func.count()).select_from(RiskDof).where(RiskDof.is_completed.is_(False))
            )
            or 0
        )
    elif user.role in field_roles:
        ids = assigned_company_ids(db, user)
        cc = len(ids)
        bc = (
            db.scalar(
                select(func.count()).select_from(Branch).where(Branch.company_id.in_(ids), Branch.is_active.is_(True))
            )
            or 0
        ) if ids else 0
        ec = (
            db.scalar(
                select(func.count())
                .select_from(Employee)
                .where(Employee.company_id.in_(ids), Employee.is_active.is_(True))
            )
            or 0
        ) if ids else 0
        uc = 0
        open_risks = 0
        open_capa = 0
        if ids:
            open_risks = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskAssessment)
                    .where(RiskAssessment.company_id.in_(ids), RiskAssessment.status == "Açık")
                )
                or 0
            )
            open_capa = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskDof)
                    .where(
                        RiskDof.is_completed.is_(False),
                        RiskDof.risk_id.in_(
                            select(RiskAssessment.id).where(RiskAssessment.company_id.in_(ids))
                        ),
                    )
                )
                or 0
            )
    else:
        cid = user.company_id
        cc = 1 if cid else 0
        bc = (
            db.scalar(
                select(func.count()).select_from(Branch).where(Branch.company_id == cid, Branch.is_active.is_(True))
            )
            or 0
        )
        ec = (
            db.scalar(
                select(func.count())
                .select_from(Employee)
                .where(Employee.company_id == cid, Employee.is_active.is_(True))
            )
            or 0
        )
        uc = (
            db.scalar(
                select(func.count()).select_from(User).where(User.company_id == cid, User.is_active.is_(True))
            )
            or 0
        )
        open_risks = 0
        open_capa = 0
        if cid:
            open_risks = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskAssessment)
                    .where(RiskAssessment.company_id == cid, RiskAssessment.status == "Açık")
                )
                or 0
            )
            open_capa = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskDof)
                    .where(
                        RiskDof.is_completed.is_(False),
                        RiskDof.risk_id.in_(
                            select(RiskAssessment.id).where(RiskAssessment.company_id == cid)
                        ),
                    )
                )
                or 0
            )

    return {
        "company_count": cc,
        "branch_count": bc,
        "employee_count": ec,
        "user_count": uc,
        "open_risks": open_risks,
        "open_capa": open_capa,
        "role": user.role.value,
    }


@router.get("/my-duties")
def my_duties(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Uzman / hekim / DSP — kişisel sorumluluk uyarı paneli."""
    try:
        return build_my_duty_board(db, user)
    except Exception:
        logger.warning("my-duties board failed user_id=%s", getattr(user, "id", None), exc_info=True)
        try:
            db.rollback()
        except Exception:
            logger.warning("my-duties rollback failed", exc_info=True)
        # Panel hiç açılmasın diye kontrollü boş cevap
        return {
            "supported": True,
            "role": user.role.value,
            "role_label": user.role.value,
            "full_name": user.full_name,
            "professional": None,
            "period": {"today": date.today().isoformat(), "approaching_days": 14},
            "workplace_count": 0,
            "workplace_ids": [],
            "check_catalog": [],
            "summary": {"overdue": 0, "due_soon": 0, "missing": 0, "done": 0, "total": 0, "completion_pct": 0},
            "alerts": {"overdue": [], "due_soon": [], "missing": [], "done": [], "all": []},
            "email_notifications": {"enabled": False, "planned": True, "note": ""},
            "error": "Sorumluluk paneli yüklenirken hata oluştu. Yenile’ye basın; devam ederse OSGB yönetimine bildirin.",
        }


@router.get("/my-capacity")
def my_capacity(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Uzman/hekim için yalnızca kendi aylık görevlendirme kapasitesi."""
    allowed_roles = {
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
    }
    if user.role not in allowed_roles:
        raise HTTPException(403, "Bu kapasite görünümü yalnızca iş güvenliği uzmanı ve işyeri hekimi içindir.")

    professional = find_professional_for_user(db, user)
    expected_type = {
        UserRole.SAFETY_SPECIALIST: "safety_specialist",
        UserRole.WORKPLACE_PHYSICIAN: "workplace_physician",
    }[user.role]
    # find_professional_for_user mevcut güvenli eşleştirmeyi yapar; ek tip
    # kontrolü, hatalı/legacy e-posta eşleşmesinde başka rolün verisini
    # kişisel panele taşımamasını garanti eder.
    if professional and getattr(professional.professional_type, "value", professional.professional_type) != expected_type:
        professional = None

    overview = build_capacity_overview(
        db,
        osgb_id=professional.osgb_id if professional else user.osgb_id,
        professional_id=professional.id if professional else 0,
    )
    overview["professional"] = (
        {
            "professional_id": professional.id,
            "full_name": professional.full_name,
            "professional_type": expected_type,
            "role_label": "İSG Uzmanı" if expected_type == "safety_specialist" else "İşyeri Hekimi",
            "certificate_class": professional.certificate_class,
        }
        if professional
        else None
    )
    if not professional:
        overview["error"] = "Kullanıcı aktif bir uzman/hekim kaydıyla eşleşmiyor; kişisel süre verisi bulunamadı."
    return overview


@router.get("/my-duties/export.txt")
def my_duties_export_txt(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Uzman / hekim / DSP — ana sayfa görev durum raporu (TXT)."""
    if user.role not in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        raise HTTPException(403, "Bu rapor yalnızca İSG profesyonelleri içindir.")
    board = build_my_duty_board(db, user)
    body = format_duty_report_txt(board)
    fname = f"gorev-durum-{date.today().isoformat()}.txt"
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
