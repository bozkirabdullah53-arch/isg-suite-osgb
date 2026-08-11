from io import BytesIO

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import accessible_company_ids_or_empty, ensure_company_access, resolve_employee_company_id
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, Employee, User, UserRole
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_excel import build_import_template_xlsx, parse_employees_workbook
from app.services.capacity_engine import sync_company_service_requirements
from app.services.national_id_format import normalize_national_id
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/employees", tags=["Personel"])
EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)


def check_company(db: Session, user: User, cid: int):
    ensure_company_access(db, user, cid)


def validate_branch(db: Session, cid: int, bid: int | None):
    if bid:
        branch = db.get(Branch, bid)
        if not branch or branch.company_id != cid:
            raise HTTPException(422, "Şube firma ile uyumlu değil.")


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    company_id: int | None = Query(None),
    q: str | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cid = resolve_employee_company_id(db, user, company_id)
    stmt = select(Employee).order_by(Employee.full_name)
    if cid == -1:
        return []
    if cid is not None:
        stmt = stmt.where(Employee.company_id == cid)
    else:
        ids = accessible_company_ids_or_empty(db, user)
        if not ids:
            return []
        stmt = stmt.where(Employee.company_id.in_(ids))
    if q:
        stmt = stmt.where(
            or_(
                Employee.full_name.ilike(f"%{q}%"),
                Employee.job_title.ilike(f"%{q}%"),
                Employee.department.ilike(f"%{q}%"),
            )
        )
    if active is not None:
        stmt = stmt.where(Employee.is_active == active)
    return list(db.scalars(stmt).all())


@router.get("/import-template.xlsx")
def download_employee_import_template(user: User = Depends(get_current_user)):
    """Kullanıcıya personel Excel şablonu (Adı Soyadı / TC / Görev / İşe giriş / Özel durum)."""
    _ = user
    data = build_import_template_xlsx()
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="personel-aktarim-sablonu.xlsx"'},
    )


@router.post("", response_model=EmployeeResponse)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    check_company(db, user, payload.company_id)
    validate_branch(db, payload.company_id, payload.branch_id)
    values = payload.model_dump()
    values["national_id_masked"] = normalize_national_id(values.get("national_id_masked")) or None
    obj = Employee(**values)
    db.add(obj)
    try:
        sync_company_service_requirements(db, payload.company_id, commit=False)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu personel kaydı zaten mevcut olabilir.")
    db.refresh(obj)
    return obj


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    obj = db.get(Employee, employee_id)
    if not obj:
        raise HTTPException(404, "Personel bulunamadı.")
    check_company(db, user, obj.company_id)
    validate_branch(db, obj.company_id, payload.branch_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k == "national_id_masked":
            v = normalize_national_id(v) or None
        setattr(obj, k, v)
    sync_company_service_requirements(db, obj.company_id, commit=False)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{employee_id}")
def deactivate_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    obj = db.get(Employee, employee_id)
    if not obj:
        raise HTTPException(404, "Personel bulunamadı.")
    check_company(db, user, obj.company_id)
    obj.is_active = False
    sync_company_service_requirements(db, obj.company_id, commit=False)
    db.commit()
    return {"message": "Personel pasife alındı."}


@router.post("/bulk-delete")
def bulk_deactivate_employees(
    employee_ids: list[int] = Body(..., embed=True),
    company_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Seçilen işyerindeki personelleri toplu olarak pasife alır.

    Kalıcı veri kaybını önlemek için kayıtlar fiziksel olarak silinmez; aktif
    personel listesinden kaldırılır. Başka işyerine ait kimlikler işleme alınmaz.
    """
    check_company(db, user, company_id)
    ids = sorted({int(x) for x in employee_ids if int(x) > 0})
    if not ids:
        raise HTTPException(422, "Silinecek personel seçilmedi.")
    if len(ids) > 1000:
        raise HTTPException(422, "Tek işlemde en fazla 1000 personel silinebilir.")

    rows = list(
        db.scalars(
            select(Employee).where(
                Employee.id.in_(ids),
                Employee.company_id == company_id,
            )
        ).all()
    )
    found_ids = {row.id for row in rows}
    missing = [employee_id for employee_id in ids if employee_id not in found_ids]
    if missing:
        raise HTTPException(409, "Seçilen personellerden bazıları bu işyerine ait değil veya bulunamadı.")

    changed = 0
    for row in rows:
        if row.is_active:
            row.is_active = False
            changed += 1
    sync_company_service_requirements(db, company_id, commit=False)
    db.commit()
    return {
        "message": f"{changed} personel silindi.",
        "deleted": changed,
        "requested": len(ids),
    }


@router.post("/import-excel")
async def import_excel(
    company_id: int,
    branch_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    check_company(db, user, company_id)
    validate_branch(db, company_id, branch_id)
    name = (file.filename or "").lower()
    if not name.endswith(".xlsx"):
        raise HTTPException(422, "Yalnızca .xlsx dosyası yükleyebilirsiniz.")
    content = await file.read()
    assert_safe_upload(content, ".xlsx", file.filename or "")
    try:
        rows = parse_employees_workbook(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not rows:
        raise HTTPException(
            422,
            "Excel'de personel satırı bulunamadı. Şablonu indirip Adı Soyadı sütununu doldurun.",
        )

    created = 0
    errors: list[str] = []
    for row_no, data in enumerate(rows, start=2):
        obj = Employee(
            company_id=company_id,
            branch_id=branch_id,
            full_name=data["full_name"],
            national_id_masked=data.get("national_id_masked"),
            job_title=data.get("job_title"),
            department=data.get("department"),
            start_date=data.get("start_date"),
            special_status=data.get("special_status"),
            is_active=True,
        )
        try:
            with db.begin_nested():
                db.add(obj)
                db.flush()
            created += 1
        except IntegrityError:
            errors.append(f"Satır {row_no} ({data['full_name']}): mükerrer veya geçersiz kayıt")
    sync_company_service_requirements(db, company_id, commit=False)
    db.commit()
    return {"created": created, "errors": errors[:50], "count": len(rows)}
