from io import BytesIO
import logging
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.company_access import accessible_company_ids_or_empty, ensure_company_access, resolve_employee_company_id
from app.api.deps import get_current_user, is_workplace_manager_account, require_roles
from app.core.database import get_db
from app.models.entities import Branch, Employee, User, UserRole
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_excel import build_import_template_xlsx, parse_employees_workbook
from app.services.capacity_engine import sync_company_service_requirements
from app.services.national_id_format import normalize_national_id
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/employees", tags=["Personel"])
logger = logging.getLogger(__name__)
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


def resolve_create_company_id(db: Session, user: User, requested_company_id: int | None) -> int:
    """Personel oluşturma tenant kapsamını backend'de kesinleştirir.

    İşyeri yetkilisi (company_admin + company_id) için firma kimliği istemciden
    belirlenmez; hesabın bağlı olduğu tek işyeri kullanılır. İstemci yabancı bir
    firma kimliği gönderirse istek açıkça 403 ile reddedilir.
    """
    if is_workplace_manager_account(user):
        own_company_id = int(user.company_id)
        if requested_company_id is not None and int(requested_company_id) != own_company_id:
            raise HTTPException(403, "Bu işyerine bağlı hesap yalnızca kendi işyerine personel ekleyebilir.")
        check_company(db, user, own_company_id)
        return own_company_id

    if requested_company_id is None:
        raise HTTPException(422, "Firma seçilmelidir.")
    check_company(db, user, int(requested_company_id))
    return int(requested_company_id)


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
    cid = resolve_create_company_id(db, user, payload.company_id)
    validate_branch(db, cid, payload.branch_id)
    values = payload.model_dump()
    values["company_id"] = cid
    values["national_id_masked"] = normalize_national_id(values.get("national_id_masked")) or None
    obj = Employee(**values)
    db.add(obj)
    try:
        sync_company_service_requirements(db, cid, commit=False)
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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu işyerinde aynı maskeli T.C. kimlik numarasına sahip başka bir personel var.") from exc
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


@router.post("/bulk-purge")
def bulk_purge_inactive_employees(
    employee_ids: list[int] = Body(..., embed=True),
    company_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Kalıcı olarak seçili ve bağlantısız personelleri aktif/pasif ayrımı olmadan siler."""
    check_company(db, user, company_id)
    ids = sorted({int(x) for x in employee_ids if int(x) > 0})
    if not ids:
        raise HTTPException(422, "Kalıcı silinecek personel seçilmedi.")
    if len(ids) > 1000:
        raise HTTPException(422, "Tek işlemde en fazla 1000 personel kalıcı silinebilir.")

    rows = list(
        db.scalars(
            select(Employee).where(
                Employee.id.in_(ids),
                Employee.company_id == company_id,
            )
        ).all()
    )
    found_ids = {row.id for row in rows}
    if len(found_ids) != len(ids):
        raise HTTPException(409, "Seçilen personellerden bazıları bu işyerine ait değil veya bulunamadı.")

    deleted = 0
    linked_skipped = 0
    for row in rows:
        try:
            with db.begin_nested():
                db.delete(row)
                db.flush()
            deleted += 1
        except IntegrityError:
            linked_skipped += 1

    db.commit()
    message = f"{deleted} personel kalıcı olarak silindi."
    if linked_skipped:
        message += f" {linked_skipped} bağlı sağlık/eğitim kaydı bulunduğu için korundu."
    return {
        "message": message,
        "deleted": deleted,
        "linked_skipped": linked_skipped,
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
    except (BadZipFile, InvalidFileException, OSError) as exc:
        raise HTTPException(
            422,
            "Excel dosyası açılamadı. Dosyayı Microsoft Excel'de .xlsx biçiminde yeniden kaydedip tekrar yükleyin.",
        ) from exc
    except Exception as exc:
        logger.exception("Personel Excel dosyası okunamadı: %s", file.filename)
        raise HTTPException(
            422,
            "Excel dosyası okunamadı. Güncel personel şablonunu indirip bilgileri bu şablona aktarın.",
        ) from exc
    if not rows:
        raise HTTPException(
            422,
            "Excel'de personel satırı bulunamadı. Şablonu indirip Adı Soyadı sütununu doldurun.",
        )

    created = 0
    updated = 0
    reactivated = 0
    errors: list[str] = []
    for row_no, data in enumerate(rows, start=2):
        national_id = data.get("national_id_masked")
        existing = None
        if national_id:
            existing = db.scalar(
                select(Employee).where(
                    Employee.company_id == company_id,
                    Employee.national_id_masked == national_id,
                )
            )

        if existing is not None:
            was_inactive = not existing.is_active
            existing.branch_id = branch_id
            existing.full_name = data["full_name"]
            existing.job_title = data.get("job_title")
            existing.department = data.get("department")
            existing.start_date = data.get("start_date")
            existing.special_status = data.get("special_status")
            existing.is_active = True
            updated += 1
            if was_inactive:
                reactivated += 1
            continue

        obj = Employee(
            company_id=company_id,
            branch_id=branch_id,
            full_name=data["full_name"],
            national_id_masked=national_id,
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
        except IntegrityError as exc:
            logger.warning(
                "Personel satırı eklenemedi: company_id=%s row=%s name=%s error=%s",
                company_id,
                row_no,
                data["full_name"],
                exc.orig,
            )
            errors.append(
                f"Satır {row_no} ({data['full_name']}): TC kimlik başka bir kayıtla çakışıyor"
            )
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Personel Excel kayıtları veritabanına yazılamadı: company_id=%s", company_id)
        raise HTTPException(
            409,
            "Personeller kaydedilemedi. Dosyada mükerrer veya geçersiz kayıt olup olmadığını kontrol edin.",
        ) from exc

    warning = None
    try:
        sync_company_service_requirements(db, company_id, commit=True)
    except Exception:
        db.rollback()
        logger.exception("Personel yüklemesi sonrası hizmet süresi senkronizasyonu başarısız: company_id=%s", company_id)
        warning = "Personeller yüklendi; hizmet süresi hesaplaması daha sonra yenilenecek."

    return {
        "created": created,
        "updated": updated,
        "reactivated": reactivated,
        "errors": errors[:50],
        "error_count": len(errors),
        "count": len(rows),
        "warning": warning,
    }
