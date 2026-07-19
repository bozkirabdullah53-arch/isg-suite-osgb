"""Yıllık plan API — İSG PRO 2026 Planlama Merkezi parity."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, effective_company_id, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import AnnualPlanItem, AnnualPlanStatus, Company, User, UserRole
from app.schemas.annual_plan import (
    AnnualPlanCreate,
    AnnualPlanGenerate,
    AnnualPlanResponse,
    AnnualPlanUpdate,
)

router = APIRouter(prefix="/annual-plans", tags=["Yıllık Planlar"])

EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)

CATEGORIES = {
    "yillik_calisma": "Yıllık Çalışma Planı",
    "egitim": "Eğitim",
    "saglik": "Sağlık",
    "periyodik": "Periyodik Kontrol",
    "tatbikat": "Tatbikat / Acil Durum",
    "kkd": "KKD",
    "diger": "Diğer",
}

# PRO planlama_template_items portu
TEMPLATE = [
    (1, "yillik_calisma", "Yıllık İSG çalışma planının oluşturulması", "İSG faaliyetlerinin yıl geneline dağıtılması", "İSG Uzmanı / İşveren", "Yıl başında plan hazırlanır."),
    (1, "egitim", "Yıllık eğitim planının hazırlanması", "Temel İSG, yangın, KKD ve işe özel eğitimlerin planlanması", "İSG Uzmanı", "Çalışan sayısı ve tehlike sınıfına göre revize edilir."),
    (2, "periyodik", "Elektrik tesisatı / topraklama kontrol planı", "Elektrik tesisatı, pano, topraklama ve paratoner kontrollerinin planlanması", "İdari İşler / Teknik Birim", "Yetkili kişi/kuruluş raporları dosyalanır."),
    (3, "tatbikat", "Yangın ve tahliye tatbikatı", "Acil durum ekipleriyle birlikte tahliye senaryosunun uygulanması", "İSG Uzmanı / Acil Durum Ekipleri", "Fotoğraflı tutanak alınır."),
    (4, "saglik", "Sağlık gözetimi takip kontrolü", "İşe giriş/periyodik muayene sürelerinin kontrolü", "İşyeri Hekimi", "Geciken muayeneler raporlanır."),
    (5, "periyodik", "Kaldırma ekipmanları kontrolü", "Forklift, vinç, caraskal, transpalet, platform kontrolleri", "Bakım / Teknik Birim", "Rapor PDF'leri Periyodik Kontroller modülüne yüklenir."),
    (6, "yillik_calisma", "Risk değerlendirmesi gözden geçirme", "Yeni faaliyet, ekipman, kaza veya değişiklikler bakımından risklerin gözden geçirilmesi", "İSG Uzmanı / İşveren", "Gerekirse revizyon yapılır."),
    (7, "kkd", "KKD zimmet ve uygunluk kontrolü", "Baret, gözlük, ayakkabı, eldiven, emniyet kemeri ve diğer KKD'lerin kontrolü", "İSG Uzmanı / Birim Sorumluları", "Eksik/hasarlı KKD yenilenir."),
    (8, "periyodik", "Raf sistemleri ve depo ekipmanları kontrolü", "Depo rafları, forklift yolları, istifleme ve yükleme alanlarının kontrolü", "Depo Sorumlusu", "Raf etiketi ve kapasite bilgileri kontrol edilir."),
    (9, "egitim", "Yenileme / işe özel eğitimlerin kontrolü", "Yüksekte çalışma, kimyasal, kaynak, elektrik, forklift gibi işe özel eğitimler", "İSG Uzmanı", "Eksik eğitimler tamamlanır."),
    (10, "tatbikat", "Acil durum planı ve ekip listesi kontrolü", "Ekip üyeleri, toplanma alanı, tahliye güzergâhı ve acil telefonlar", "İSG Uzmanı", "Plan revizyonu gerekiyorsa Acil Durum modülünde güncellenir."),
    (11, "yillik_calisma", "Yıl sonu veri toplama", "Eğitim, KKD, sağlık, periyodik kontrol, tespit ve ramak kala kayıtlarının toplanması", "İSG Uzmanı", "Yıllık değerlendirme raporuna hazırlık."),
    (12, "yillik_calisma", "Yıllık değerlendirme raporu", "Yıl boyunca yapılan İSG faaliyetlerinin değerlendirilmesi", "İSG Uzmanı / İşveren", "Yıl sonu raporu alınır."),
]


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


def _active_stmt():
    return select(AnnualPlanItem).where(AnnualPlanItem.deleted_at.is_(None))


def _refresh_delayed(db: Session, items: list[AnnualPlanItem]) -> None:
    today = date.today()
    changed = False
    for item in items:
        if item.status in (AnnualPlanStatus.COMPLETED, AnnualPlanStatus.CANCELLED):
            continue
        if item.target_date and item.target_date < today and item.status != AnnualPlanStatus.DELAYED:
            item.status = AnnualPlanStatus.DELAYED
            changed = True
    if changed:
        db.commit()
        for item in items:
            db.refresh(item)


@router.get("/meta")
def annual_plan_meta():
    return {
        "categories": [{"code": k, "label": v} for k, v in CATEGORIES.items()],
        "statuses": [
            {"code": s.value, "label": {
                "planned": "Planlandı",
                "in_progress": "Devam Ediyor",
                "completed": "Tamamlandı",
                "delayed": "Gecikti",
                "cancelled": "İptal",
            }.get(s.value, s.value)}
            for s in AnnualPlanStatus
        ],
    }


@router.get("/summary")
def annual_plan_summary(
    year: int | None = None,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    y = year or date.today().year
    effective = effective_company_id(db, user, company_id)
    items = list(
        db.scalars(
            _active_stmt().where(
                AnnualPlanItem.company_id == effective,
                AnnualPlanItem.year == y,
            )
        ).all()
    )
    _refresh_delayed(db, items)
    by_month = {m: 0 for m in range(1, 13)}
    for it in items:
        by_month[it.month] = by_month.get(it.month, 0) + 1
    return {
        "year": y,
        "company_id": effective,
        "total": len(items),
        "completed": sum(1 for i in items if i.status == AnnualPlanStatus.COMPLETED),
        "waiting": sum(
            1
            for i in items
            if i.status in (AnnualPlanStatus.PLANNED, AnnualPlanStatus.IN_PROGRESS)
        ),
        "delayed": sum(1 for i in items if i.status == AnnualPlanStatus.DELAYED),
        "cancelled": sum(1 for i in items if i.status == AnnualPlanStatus.CANCELLED),
        "by_month": by_month,
    }


@router.get("", response_model=list[AnnualPlanResponse])
def list_plan_items(
    year: int | None = None,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = _active_stmt().order_by(AnnualPlanItem.year.desc(), AnnualPlanItem.month, AnnualPlanItem.id)
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        query = query.where(AnnualPlanItem.company_id.in_(company_ids))
    if year:
        query = query.where(AnnualPlanItem.year == year)
    items = list(db.scalars(query).all())
    _refresh_delayed(db, items)
    return items


@router.post("", response_model=AnnualPlanResponse)
def create_plan_item(
    payload: AnnualPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    data = payload.model_dump()
    if not data.get("target_date"):
        data["target_date"] = date(payload.year, payload.month, 15)
    item = AnnualPlanItem(**data, created_by_id=user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/generate")
def generate_template(
    payload: AnnualPlanGenerate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """PRO /planlama/generate — aynı yıl için yoksa 6331 şablon maddelerini ekler."""
    ensure_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    existing = list(
        db.scalars(
            _active_stmt().where(
                AnnualPlanItem.company_id == payload.company_id,
                AnnualPlanItem.year == payload.year,
            )
        ).all()
    )
    existing_keys = {(i.month, (i.activity or "").strip().casefold()) for i in existing}
    created = 0
    for month, category, activity, description, responsible, notes in TEMPLATE:
        key = (month, activity.strip().casefold())
        if key in existing_keys:
            continue
        db.add(
            AnnualPlanItem(
                company_id=payload.company_id,
                year=payload.year,
                month=month,
                category=category,
                activity=activity,
                description=description,
                responsible_name=responsible,
                target_date=date(payload.year, month, 15),
                status=AnnualPlanStatus.PLANNED,
                notes=notes,
                created_by_id=user.id,
            )
        )
        created += 1
    db.commit()
    return {
        "company_id": payload.company_id,
        "year": payload.year,
        "created": created,
        "skipped_existing": len(TEMPLATE) - created,
        "template_size": len(TEMPLATE),
    }


@router.get("/export.txt")
def export_plan_txt(
    year: int | None = None,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    y = year or date.today().year
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    items = list(
        db.scalars(
            _active_stmt()
            .where(AnnualPlanItem.company_id == effective, AnnualPlanItem.year == y)
            .order_by(AnnualPlanItem.month, AnnualPlanItem.id)
        ).all()
    )
    lines = [
        "İSG Suite OSGB — Yıllık Çalışma Planı",
        f"Firma: {company.name if company else effective}",
        f"Yıl: {y}",
        f"Olusturma: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
        "-" * 72,
    ]
    for it in items:
        cat = CATEGORIES.get(it.category or "", it.category or "—")
        lines.append(
            f"{it.month:02d}. ay | {cat} | {it.activity} | "
            f"Sorumlu: {it.responsible_name or '—'} | "
            f"Hedef: {it.target_date or '—'} | Durum: {it.status.value}"
        )
        if it.description:
            lines.append(f"   Aciklama: {it.description}")
    body = "\n".join(lines) + "\n"
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="yillik-plan-{y}.txt"'},
    )


@router.patch("/{item_id}", response_model=AnnualPlanResponse)
def update_plan_item(
    item_id: int,
    payload: AnnualPlanUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    item = db.get(AnnualPlanItem, item_id)
    if not item or item.deleted_at:
        raise HTTPException(404, "Plan maddesi bulunamadı.")
    ensure_access(db, user, item.company_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_plan_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    item = db.get(AnnualPlanItem, item_id)
    if not item or item.deleted_at:
        raise HTTPException(404, "Plan maddesi bulunamadı.")
    ensure_access(db, user, item.company_id)
    item.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": item_id}
