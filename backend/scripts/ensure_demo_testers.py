"""
4 sabit demo test kullanıcısı oluşturur / şifresini günceller.

  EİSA global_admin
  OSGB company_admin (osgb_id bağlı, company_id yok)
  İş güvenliği uzmanı + İSG profesyonel kaydı
  İşyeri hekimi + İSG profesyonel kaydı

Çalıştırma (backend klasöründen):
  python scripts/ensure_demo_testers.py

Şifre tüm hesaplarda aynıdır (aşağıda DEMO_PASSWORD).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)

DEMO_PASSWORD = "DemoIsgSuite2026!"
MARKER = "[DEMO_TEST]"

USERS = [
    {
        "email": "demo.eisa@example.com",
        "full_name": f"{MARKER} EİSA Global Yönetici",
        "role": UserRole.GLOBAL_ADMIN,
        "need_osgb": False,
        "need_company": False,
        "pro_type": None,
    },
    {
        "email": "demo.osgb@example.com",
        "full_name": f"{MARKER} OSGB Yöneticisi",
        "role": UserRole.COMPANY_ADMIN,
        "need_osgb": True,
        "need_company": False,
        "pro_type": None,
    },
    {
        "email": "demo.uzman@example.com",
        "full_name": f"{MARKER} İş Güvenliği Uzmanı",
        "role": UserRole.SAFETY_SPECIALIST,
        "need_osgb": True,
        "need_company": True,
        "pro_type": ProfessionalType.SAFETY_SPECIALIST,
    },
    {
        "email": "demo.hekim@example.com",
        "full_name": f"{MARKER} İşyeri Hekimi",
        "role": UserRole.WORKPLACE_PHYSICIAN,
        "need_osgb": True,
        "need_company": True,
        "pro_type": ProfessionalType.WORKPLACE_PHYSICIAN,
    },
]


def _ensure_osgb(db) -> OsgbOrganization:
    org = db.scalar(
        select(OsgbOrganization)
        .where(OsgbOrganization.name == f"{MARKER} Demo OSGB")
        .limit(1)
    )
    if org:
        org.is_active = True
        return org
    # Mevcut aktif OSGB varsa onu kullan (canlıda gereksiz yeni tenant açmamak için)
    existing = db.scalar(
        select(OsgbOrganization)
        .where(OsgbOrganization.is_active.is_(True))
        .order_by(OsgbOrganization.id)
        .limit(1)
    )
    if existing:
        return existing
    org = OsgbOrganization(
        name=f"{MARKER} Demo OSGB",
        authorization_number="DEMO-YETKI-001",
        tax_number="1234567890",
        responsible_manager=f"{MARKER} Sorumlu",
        email="demo.osgb@example.com",
        phone="05550001111",
        address="Demo Adres",
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org


def _ensure_company(db, osgb: OsgbOrganization) -> Company:
    company = db.scalar(
        select(Company)
        .where(Company.name == f"{MARKER} Demo İşyeri", Company.osgb_id == osgb.id)
        .limit(1)
    )
    if company:
        company.is_active = True
        return company
    company = Company(
        name=f"{MARKER} Demo İşyeri",
        hazard_class="Tehlikeli",
        sgk_registry_no="DEMO-SGK-001",
        address="Demo İşyeri Adresi",
        phone="05550002222",
        authorized_person="Demo Yetkili",
        osgb_id=osgb.id,
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def _upsert_user(
    db,
    *,
    email: str,
    full_name: str,
    role: UserRole,
    osgb_id: int | None,
    company_id: int | None,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    hashed = get_password_hash(DEMO_PASSWORD)
    if user:
        user.full_name = full_name
        user.role = role
        user.hashed_password = hashed
        user.is_active = True
        user.osgb_id = osgb_id
        user.company_id = company_id
    else:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed,
            role=role,
            osgb_id=osgb_id,
            company_id=company_id,
            is_active=True,
        )
        db.add(user)
    db.flush()
    return user


def _ensure_professional(
    db,
    *,
    osgb: OsgbOrganization,
    company: Company,
    email: str,
    full_name: str,
    ptype: ProfessionalType,
) -> IsgProfessional:
    pro = db.scalar(
        select(IsgProfessional).where(
            IsgProfessional.osgb_id == osgb.id,
            IsgProfessional.email == email,
        )
    )
    if not pro:
        pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name=full_name,
            email=email,
            phone="05550003333",
            professional_type=ptype,
            certificate_class="A" if ptype == ProfessionalType.SAFETY_SPECIALIST else None,
            certificate_number=f"DEMO-{ptype.value[:3].upper()}-001",
            certificate_date=date(2022, 1, 1),
            is_active=True,
        )
        db.add(pro)
        db.flush()
    else:
        pro.full_name = full_name
        pro.professional_type = ptype
        pro.is_active = True
        db.flush()

    assign = db.scalar(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.osgb_id == osgb.id,
            WorkplaceAssignment.company_id == company.id,
            WorkplaceAssignment.professional_id == pro.id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    if not assign:
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                professional_type=ptype,
                start_date=date(2025, 1, 1),
                required_minutes_monthly=480,
                planned_minutes_monthly=480,
                actual_minutes_monthly=0,
                isg_katip_contract_number=f"DEMO-KATIP-{pro.id}",
                status=AssignmentStatus.ACTIVE,
            )
        )
        db.flush()
    return pro


def main() -> int:
    db = SessionLocal()
    try:
        osgb = _ensure_osgb(db)
        company = _ensure_company(db, osgb)
        rows = []
        for spec in USERS:
            oid = osgb.id if spec["need_osgb"] else None
            # EİSA global: osgb bağlanmaz
            if spec["role"] == UserRole.GLOBAL_ADMIN:
                oid = None
            cid = company.id if spec["need_company"] else None
            # OSGB yöneticisi: company_id bilinçli olarak None
            if spec["role"] == UserRole.COMPANY_ADMIN:
                cid = None
            user = _upsert_user(
                db,
                email=spec["email"],
                full_name=spec["full_name"],
                role=spec["role"],
                osgb_id=oid,
                company_id=cid,
            )
            if spec["pro_type"] is not None:
                _ensure_professional(
                    db,
                    osgb=osgb,
                    company=company,
                    email=spec["email"],
                    full_name=spec["full_name"],
                    ptype=spec["pro_type"],
                )
            rows.append((spec["role"].value, spec["email"], user.id))
        db.commit()
        print("OK demo test kullanicilari hazir.")
        print(f"OSGB: #{osgb.id} {osgb.name}")
        print(f"Isyeri: #{company.id} {company.name}")
        print(f"Sifre (hepsi): {DEMO_PASSWORD}")
        print("---")
        for role, email, uid in rows:
            print(f"{role}\t{email}\tid={uid}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"HATA: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
