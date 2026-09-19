from datetime import date
from io import BytesIO
import logging
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, inspect, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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
logger = logging.getLogger(__name__)
EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)

# Employee rows are intentionally protected when a historical/operational
# record still points at them.  Keep the labels here in one place so the purge
# response describes the actual FK blocker instead of treating every
# IntegrityError as a generic "health/education" record.
_EMPLOYEE_LINK_LABELS = {
    "health_records": ("health", "sağlık kaydı"),
    "prescriptions": ("health", "reçete kaydı"),
    "training_participants": ("training", "eğitim kaydı"),
    "remote_training_assignments": ("training", "uzaktan eğitim ataması"),
    "remote_training_assignment_sectors": ("training", "uzaktan eğitim kapsam kaydı"),
    "remote_training_video_progress": ("training", "uzaktan eğitim ilerleme kaydı"),
    "remote_training_events": ("training", "uzaktan eğitim olay kaydı"),
    "remote_training_exam_attempts": ("training", "uzaktan eğitim sınav kaydı"),
    "remote_training_checkpoint_answers": ("training", "uzaktan eğitim cevap kaydı"),
    "remote_training_certificates": ("training", "eğitim katılım belgesi"),
    "ppe_assignments": ("ppe", "KKD zimmet kaydı"),
    "emergency_team_assignments": ("emergency", "acil durum ekibi kaydı"),
    "work_permit_employees": ("work_permit", "çalışma izni kaydı"),
    "personnel_profiles": ("profile", "personel profil kaydı"),
}


def _employee_linked_records(
    db: Session, employee_ids: set[int]
) -> dict[int, list[dict[str, int | str]]]:
    """Return the non-cascading records that protect an employee from purge.

    Health records are append-only and are soft-deleted with ``deleted_at``.
    They must therefore be counted even when they are not visible in the
    active health list.  Other employee FKs are discovered from the mapped
    schema so a newly added protected table cannot silently fall back to the
    misleading legacy message.
    """
    bind = db.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    links_by_employee: dict[int, list[dict[str, int | str]]] = {}
    if not employee_ids:
        return links_by_employee

    for table in Employee.metadata.tables.values():
        if table.name not in existing_tables:
            continue
        employee_fk = next(
            (
                fk
                for fk in table.foreign_keys
                if fk.target_fullname == "employees.id"
                and (fk.ondelete or "").upper() not in {"CASCADE", "SET NULL"}
            ),
            None,
        )
        if employee_fk is None:
            continue
        column = table.c.get(employee_fk.parent.name)
        if column is None:
            continue

        category, label = _EMPLOYEE_LINK_LABELS.get(
            table.name, ("other", "bağlı kayıt")
        )
        count_rows = db.execute(
            select(column, func.count().label("total"))
            .select_from(table)
            .where(column.in_(employee_ids))
            .group_by(column)
        ).all()
        active_by_employee: dict[int, int] = {}
        deleted_at = table.c.get("deleted_at")
        if table.name == "health_records" and deleted_at is not None:
            active_rows = db.execute(
                select(column, func.count().label("active"))
                .select_from(table)
                .where(column.in_(employee_ids), deleted_at.is_(None))
                .group_by(column)
            ).all()
            active_by_employee = {int(employee_id): int(active) for employee_id, active in active_rows}

        for employee_id, total in count_rows:
            total = int(total or 0)
            if total <= 0:
                continue
            employee_id = int(employee_id)
            detail: dict[str, int | str] = {
                "table": table.name,
                "category": category,
                "label": label,
                "count": total,
            }
            if table.name == "health_records" and deleted_at is not None:
                active = active_by_employee.get(employee_id, 0)
                detail["active_count"] = active
                detail["historical_count"] = total - active
            links_by_employee.setdefault(employee_id, []).append(detail)
    return links_by_employee


def _purge_blocker_message(
    protected_count: int,
    blocked_details: list[dict[str, object]],
) -> str:
    """Build a user-facing message that distinguishes active/history links."""
    grouped: dict[tuple[str, str], dict[str, int]] = {}
    for item in blocked_details:
        for link in item.get("links", []):
            category = str(link.get("category") or "other")
            label = str(link.get("label") or "bağlı kayıt")
            key = (category, label)
            counts = grouped.setdefault(key, {"count": 0, "active": 0, "historical": 0})
            counts["count"] += int(link.get("count") or 0)
            counts["active"] += int(link.get("active_count") or 0)
            counts["historical"] += int(link.get("historical_count") or 0)

    reasons: list[str] = []
    for (category, label), counts in grouped.items():
        if category == "health":
            active = counts["active"]
            historical = counts["historical"]
            if historical and not active:
                reasons.append(f"{historical} arşivlenmiş/geçmiş sağlık kaydı")
            elif active and historical:
                reasons.append(
                    f"{counts['count']} sağlık kaydı ({active} aktif, {historical} arşivlenmiş)"
                )
            elif active:
                reasons.append(f"{active} aktif sağlık kaydı")
            else:
                reasons.append(f"{counts['count']} {label}")
        else:
            reasons.append(f"{counts['count']} {label}")

    if not reasons:
        reasons.append("bağlı kayıt")
    message = (
        f"{protected_count} personel, "
        + ", ".join(reasons)
        + " bulunduğu için korundu."
    )
    if any(
        int(link.get("historical_count") or 0)
        for item in blocked_details
        for link in item.get("links", [])
    ):
        message += " Arşivlenmiş sağlık kayıtları aktif sağlık listesinde gösterilmez."
    return message


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
    values = payload.model_dump(exclude={"hire_date"})
    if values.get("exit_date") is not None:
        values["is_active"] = False
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
    values = payload.model_dump(exclude_unset=True, exclude={"hire_date"})
    if values.get("exit_date") is not None and values.get("is_active") is not True:
        values["is_active"] = False
    if values.get("is_active") is True and "exit_date" not in values:
        values["exit_date"] = None
    if values.get("is_active") is True and values.get("exit_date") is not None:
        raise HTTPException(422, "Aktif personel için işten çıkış tarihi kaldırılmalıdır.")
    for k, v in values.items():
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
    exit_date: date | None = Body(None, embed=True),
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

    if exit_date is not None:
        invalid = next(
            (row for row in rows if row.start_date and exit_date < row.start_date),
            None,
        )
        if invalid is not None:
            raise HTTPException(
                422,
                f"{invalid.full_name} için işten çıkış tarihi işe giriş tarihinden önce olamaz.",
            )

    changed = 0
    for row in rows:
        if row.is_active:
            row.is_active = False
            if exit_date is not None:
                row.exit_date = exit_date
            changed += 1
    sync_company_service_requirements(db, company_id, commit=False)
    db.commit()
    return {
        "message": f"{changed} personel pasife alındı.",
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
    blocked_details: list[dict[str, object]] = []
    links_by_employee = _employee_linked_records(db, set(ids))
    for row in rows:
        links = links_by_employee.get(row.id, [])
        if links:
            linked_skipped += 1
            blocked_details.append(
                {
                    "employee_id": row.id,
                    "employee_name": row.full_name,
                    "links": links,
                }
            )
            continue
        try:
            with db.begin_nested():
                db.delete(row)
                db.flush()
            deleted += 1
        except IntegrityError:
            linked_skipped += 1
            blocked_details.append(
                {
                    "employee_id": row.id,
                    "employee_name": row.full_name,
                    "links": [
                        {
                            "category": "other",
                            "label": "bağlı kayıt",
                            "count": 1,
                        }
                    ],
                }
            )

    db.commit()
    message = f"{deleted} personel kalıcı olarak silindi."
    if linked_skipped:
        message += " " + _purge_blocker_message(linked_skipped, blocked_details)
    return {
        "message": message,
        "deleted": deleted,
        "linked_skipped": linked_skipped,
        "requested": len(ids),
        "blocked_details": blocked_details,
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
            existing.exit_date = data.get("exit_date")
            existing.special_status = data.get("special_status")
            existing.is_active = data.get("exit_date") is None
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
            exit_date=data.get("exit_date"),
            special_status=data.get("special_status"),
            is_active=data.get("exit_date") is None,
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
