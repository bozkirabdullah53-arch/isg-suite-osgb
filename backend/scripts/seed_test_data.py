"""
TEST_ işaretli örnek veri oluşturma / temizleme.

Kullanım (yalnızca yerel / test DB — üretimde dikkat):
  cd backend
  .venv\\Scripts\\python.exe scripts/seed_test_data.py
  .venv\\Scripts\\python.exe scripts/seed_test_data.py --cleanup

Tüm firma adları "TEST_" ile başlar; e-postalar @example.com ve test. önekli.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    Branch,
    Company,
    CompanySubscription,
    DocumentCategory,
    DocumentRecord,
    Employee,
    FinanceTransaction,
    HealthFitnessStatus,
    HealthRecord,
    HealthRecordType,
    IsgModule,
    IsgProfessional,
    IsgRecord,
    Notification,
    NotificationType,
    OsgbOrganization,
    ProfessionalType,
    RecordStatus,
    ServiceContract,
    ServiceVisit,
    SubscriptionPlan,
    SubscriptionStatus,
    TrainingParticipant,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
    VisitStatus,
    WorkplaceAssignment,
    CrmLead,
)

TEST_PREFIX = "TEST_"
TEST_PASSWORD = "TestPass12345!"
MARKER = "[TEST_DATA]"


def _hash():
    return get_password_hash(TEST_PASSWORD)


def cleanup(db) -> dict:
    """TEST_ firmaları ve bağlı kayıtları temizler."""
    companies = list(db.scalars(select(Company).where(Company.name.like(f"{TEST_PREFIX}%"))).all())
    company_ids = [c.id for c in companies]
    osgbs = list(db.scalars(select(OsgbOrganization).where(OsgbOrganization.name.like(f"{TEST_PREFIX}%"))).all())
    osgb_ids = [o.id for o in osgbs]
    counts = {"companies": len(company_ids), "osgb": len(osgb_ids)}

    if company_ids:
        trainings = list(db.scalars(select(TrainingSession).where(TrainingSession.company_id.in_(company_ids))).all())
        tid = [t.id for t in trainings]
        if tid:
            db.execute(delete(TrainingParticipant).where(TrainingParticipant.training_id.in_(tid)))
        for model in (
            TrainingSession,
            IsgRecord,
            HealthRecord,
            DocumentRecord,
            AnnualPlanItem,
            CompanySubscription,
            Notification,
            FinanceTransaction,
            ServiceVisit,
            WorkplaceAssignment,
            ServiceContract,
            CrmLead,
            Employee,
            Branch,
        ):
            if hasattr(model, "company_id"):
                q = delete(model).where(model.company_id.in_(company_ids))
                db.execute(q)
        db.execute(delete(User).where(User.company_id.in_(company_ids)))
        db.execute(delete(Company).where(Company.id.in_(company_ids)))

    if osgb_ids:
        db.execute(delete(IsgProfessional).where(IsgProfessional.osgb_id.in_(osgb_ids)))
        db.execute(delete(User).where(User.osgb_id.in_(osgb_ids), User.email.like("test.%@example.com")))
        db.execute(delete(OsgbOrganization).where(OsgbOrganization.id.in_(osgb_ids)))

    # orphan test users (global)
    db.execute(delete(User).where(User.email.like("test.%@example.com")))
    db.commit()
    return counts


def seed(db) -> dict:
    # Idempotent: cleanup first for TEST_
    cleanup(db)

    osgb = OsgbOrganization(
        name=f"{TEST_PREFIX}OSGB Denetim Merkezi",
        authorization_number="TEST-OSGB-001",
        tax_number="9990000001",
        responsible_manager=f"{MARKER} Test OSGB Müdürü",
        email="test.osgb@example.com",
        phone="05550000001",
        address=f"{MARKER} Test OSGB Adresi, Ankara",
        is_active=True,
    )
    db.add(osgb)
    db.flush()

    firms = [
        ("TEST_ Firma Az Tehlikeli A.Ş.", "Az Tehlikeli", "62.01", 8),
        ("TEST_ Firma Tehlikeli Ltd.", "Tehlikeli", "25.11", 25),
        ("TEST_ Firma Cok Tehlikeli San.", "Çok Tehlikeli", "41.20", 60),
    ]
    company_map = {}
    for name, hazard, nace, emp_count in firms:
        c = Company(
            name=name,
            tax_number=f"999{abs(hash(name)) % 10000000:07d}"[:10],
            nace_code=nace,
            hazard_class=hazard,
            sgk_registry_no=f"TEST-ISYERI-{abs(hash(name)) % 1000000:06d}",
            is_active=True,
            osgb_id=osgb.id,
        )
        db.add(c)
        db.flush()
        b = Branch(
            company_id=c.id,
            name=f"{TEST_PREFIX}Merkez Şube",
            city="Ankara",
            sgk_registry_no=f"TEST-SGK-{c.id}",
            address=f"{MARKER} Test adres {c.id}",
            is_active=True,
        )
        db.add(b)
        db.flush()
        company_map[hazard] = (c, b, emp_count)

    # Subscriptions: active / trial / suspended (süresi dolmuş simülasyonu)
    plans = [
        (company_map["Az Tehlikeli"][0], SubscriptionPlan.STARTER, SubscriptionStatus.ACTIVE, None, 30),
        (company_map["Tehlikeli"][0], SubscriptionPlan.PROFESSIONAL, SubscriptionStatus.TRIAL, 7, None),
        (company_map["Çok Tehlikeli"][0], SubscriptionPlan.ENTERPRISE, SubscriptionStatus.SUSPENDED, None, -10),
    ]
    for company, plan, status, trial_days, period_days in plans:
        db.add(
            CompanySubscription(
                company_id=company.id,
                plan=plan,
                status=status,
                trial_ends_at=(datetime.utcnow() + timedelta(days=trial_days)) if trial_days is not None else None,
                current_period_ends_at=(datetime.utcnow() + timedelta(days=period_days)) if period_days is not None else None,
                max_users=20,
                max_employees=200,
                is_auto_renew=False,
            )
        )

    users_spec = []
    # Global admin test
    users_spec.append(
        dict(email="test.global.admin@example.com", full_name=f"{MARKER} Global Admin", role=UserRole.GLOBAL_ADMIN, company_id=None, osgb_id=osgb.id)
    )
    # Per-company roles
    for hazard, (c, b, _) in company_map.items():
        slug = "az" if "Az" in hazard else ("teh" if hazard == "Tehlikeli" else "cok")
        users_spec.extend(
            [
                dict(email=f"test.{slug}.admin@example.com", full_name=f"{MARKER} Firma Admin {slug}", role=UserRole.COMPANY_ADMIN, company_id=c.id, osgb_id=osgb.id),
                dict(email=f"test.{slug}.uzman@example.com", full_name=f"{MARKER} ISG Uzmani {slug}", role=UserRole.SAFETY_SPECIALIST, company_id=c.id, osgb_id=osgb.id),
                dict(email=f"test.{slug}.hekim@example.com", full_name=f"{MARKER} Isyeri Hekimi {slug}", role=UserRole.WORKPLACE_PHYSICIAN, company_id=c.id, osgb_id=osgb.id),
                dict(email=f"test.{slug}.dsp@example.com", full_name=f"{MARKER} DSP {slug}", role=UserRole.OTHER_HEALTH_PERSONNEL, company_id=c.id, osgb_id=osgb.id),
                dict(email=f"test.{slug}.readonly@example.com", full_name=f"{MARKER} Salt Okunur {slug}", role=UserRole.READ_ONLY, company_id=c.id, osgb_id=osgb.id),
            ]
        )
    # Inactive / unauthorized
    users_spec.append(
        dict(email="test.inactive@example.com", full_name=f"{MARKER} Pasif Kullanici", role=UserRole.READ_ONLY, company_id=company_map["Az Tehlikeli"][0].id, osgb_id=osgb.id, is_active=False)
    )

    created_users = []
    for u in users_spec:
        row = User(
            email=u["email"],
            full_name=u["full_name"],
            hashed_password=_hash(),
            role=u["role"],
            company_id=u.get("company_id"),
            osgb_id=u.get("osgb_id"),
            is_active=u.get("is_active", True),
        )
        db.add(row)
        created_users.append(u["email"])
    db.flush()

    # Professionals
    pros = []
    for ptype, name, cert in [
        (ProfessionalType.SAFETY_SPECIALIST, f"{MARKER} Profesyonel Uzman", "TEST-UZM-001"),
        (ProfessionalType.WORKPLACE_PHYSICIAN, f"{MARKER} Profesyonel Hekim", "TEST-HEK-001"),
        (ProfessionalType.OTHER_HEALTH_PERSONNEL, f"{MARKER} Profesyonel DSP", "TEST-DSP-001"),
    ]:
        p = IsgProfessional(
            osgb_id=osgb.id,
            full_name=name,
            email=f"test.pro.{ptype.value}@example.com",
            phone="05550000999",
            professional_type=ptype,
            certificate_class="A",
            certificate_number=cert,
            certificate_date=date(2020, 1, 1),
            is_active=True,
        )
        db.add(p)
        db.flush()
        pros.append(p)

    admin_user = db.scalar(select(User).where(User.email == "test.global.admin@example.com"))

    # Employees + records per company
    for hazard, (c, b, emp_count) in company_map.items():
        emps = []
        for i in range(1, emp_count + 1):
            e = Employee(
                company_id=c.id,
                branch_id=b.id,
                full_name=f"{MARKER} Calisan {hazard[:3]} {i:02d}",
                national_id_masked=f"100{c.id:02d}{i:06d}"[:11],
                job_title="Operatör" if i % 2 else "Teknisyen",
                department="Üretim",
                start_date=date(2024, 1, 15),
                is_active=True,
            )
            db.add(e)
            emps.append(e)
        db.flush()

        for p in pros:
            db.add(
                WorkplaceAssignment(
                    osgb_id=osgb.id,
                    company_id=c.id,
                    professional_id=p.id,
                    professional_type=p.professional_type,
                    start_date=date(2025, 1, 1),
                    required_minutes_monthly=480,
                    planned_minutes_monthly=480,
                    actual_minutes_monthly=120,
                    isg_katip_contract_number=f"TEST-KATIP-{c.id}-{p.id}",
                    status=AssignmentStatus.ACTIVE,
                )
            )
        db.add(
            ServiceContract(
                osgb_id=osgb.id,
                company_id=c.id,
                contract_number=f"TEST-SOZ-{c.id}",
                start_date=date(2025, 1, 1),
                end_date=date(2026, 12, 31),
                monthly_fee=15000,
                status="active",
            )
        )
        db.add(
            ServiceVisit(
                osgb_id=osgb.id,
                company_id=c.id,
                professional_id=pros[0].id,
                visit_date=date.today(),
                start_time="09:00",
                end_time="12:00",
                duration_minutes=180,
                subject=f"{MARKER} Saha ziyareti",
                notes=MARKER,
                status=VisitStatus.PLANNED,
            )
        )
        db.add(
            CrmLead(
                osgb_id=osgb.id,
                company_name=f"{TEST_PREFIX}CRM Firsat {c.id}",
                contact_name=f"{MARKER} Kontak",
                phone="05550000111",
                email=f"test.crm.{c.id}@example.com",
                employee_count=10,
                hazard_class=hazard,
                stage="new",
                estimated_monthly_value=5000,
                notes=MARKER,
            )
        )
        db.add(
            FinanceTransaction(
                osgb_id=osgb.id,
                company_id=c.id,
                transaction_type="income",
                category="service",
                amount=15000,
                transaction_date=date.today(),
                status="paid",
                description=f"{MARKER} Test tahsilat",
            )
        )

        # ISG modules
        for module, title in [
            (IsgModule.RISK, f"{MARKER} Risk kaydi"),
            (IsgModule.NEAR_MISS, f"{MARKER} Ramak kala"),
            (IsgModule.ACCIDENT, f"{MARKER} Is kazasi"),
            (IsgModule.CAPA, f"{MARKER} DOF"),
        ]:
            db.add(
                IsgRecord(
                    company_id=c.id,
                    branch_id=b.id,
                    module=module,
                    title=title,
                    description=MARKER,
                    status=RecordStatus.OPEN,
                    severity="orta",
                    event_date=date.today(),
                    due_date=date.today() + timedelta(days=30),
                    responsible_name=f"{MARKER} Sorumlu",
                    probability=3 if module == IsgModule.RISK else None,
                    impact=4 if module == IsgModule.RISK else None,
                    risk_score=12 if module == IsgModule.RISK else None,
                    created_by_id=admin_user.id,
                )
            )

        if emps:
            db.add(
                HealthRecord(
                    company_id=c.id,
                    employee_id=emps[0].id,
                    record_type=HealthRecordType.PERIODIC_EXAM,
                    examination_date=date.today(),
                    next_examination_date=date.today() + timedelta(days=365),
                    fitness_status=HealthFitnessStatus.FIT,
                    physician_name=f"{MARKER} Hekim",
                    summary=MARKER,
                    confidential_note=f"{MARKER} gizli not",
                    created_by_id=admin_user.id,
                )
            )

        db.add(
            DocumentRecord(
                company_id=c.id,
                branch_id=b.id,
                category=DocumentCategory.TRAINING,
                title=f"{MARKER} Test Dokuman",
                file_name="test_dokuman.pdf",
                description=MARKER,
                version="1.0",
                is_active=True,
                created_by_id=admin_user.id,
            )
        )
        db.add(
            AnnualPlanItem(
                company_id=c.id,
                year=date.today().year,
                month=date.today().month,
                activity=f"{MARKER} Yillik plan maddesi",
                responsible_name=f"{MARKER} Plan sorumlu",
                status=AnnualPlanStatus.PLANNED,
                created_by_id=admin_user.id,
            )
        )
        db.add(
            Notification(
                company_id=c.id,
                user_id=None,
                type=NotificationType.INFO,
                title=f"{MARKER} Bildirim",
                message=MARKER,
                is_read=False,
            )
        )

        # Training with participants
        tr = TrainingSession(
            company_id=c.id,
            branch_id=b.id,
            title=f"{MARKER} Temel ISG Egitimi",
            training_type="Temel İSG Eğitimi",
            delivery_method="Yüz yüze",
            location=f"{MARKER} Egitim salonu",
            start_date=date.today(),
            hazard_class=hazard,
            duration_hours={"Az Tehlikeli": 8, "Tehlikeli": 12, "Çok Tehlikeli": 16}[hazard],
            renewal_years={"Az Tehlikeli": 3, "Tehlikeli": 2, "Çok Tehlikeli": 1}[hazard],
            next_training_date=date.today() + timedelta(days=365),
            sector="genel_uretim",
            instructor_name=f"{MARKER} Egitmen",
            instructor_qualification="A Sınıfı İSG Uzmanı",
            evaluation_method="Sınav",
            passing_score=70,
            attendance_verified=True,
            success_verified=True,
            verification_code=f"TESTVERIF{c.id:04d}",
            status=TrainingStatus.PLANNED,
            notes=MARKER,
            created_by_id=admin_user.id,
        )
        db.add(tr)
        db.flush()
        for e in emps[: min(5, len(emps))]:
            db.add(
                TrainingParticipant(
                    training_id=tr.id,
                    employee_id=e.id,
                    attended=True,
                    certificate_number=f"TEST-EGT-{tr.id}-{e.id}",
                )
            )

    # --- İkinci OSGB (çapraz tenant IDOR testleri için) ---
    osgb2 = OsgbOrganization(
        name=f"{TEST_PREFIX}OSGB Rakip Merkez",
        authorization_number="TEST-OSGB-002",
        tax_number="9990000002",
        responsible_manager=f"{MARKER} Test OSGB2 Muduru",
        email="test.osgb2@example.com",
        phone="05550000002",
        address=f"{MARKER} Test OSGB2 Adresi, Istanbul",
        is_active=True,
    )
    db.add(osgb2)
    db.flush()
    c2 = Company(
        name=f"{TEST_PREFIX} Firma Yabanci OSGB Ltd.",
        tax_number="9988776655",
        nace_code="41.20",
        hazard_class="Tehlikeli",
        sgk_registry_no="TEST-ISYERI-OSGB2",
        is_active=True,
        osgb_id=osgb2.id,
    )
    db.add(c2)
    db.flush()
    db.add(
        Branch(
            company_id=c2.id,
            name=f"{TEST_PREFIX}OSGB2 Merkez",
            city="Istanbul",
            sgk_registry_no=f"TEST-SGK-OSGB2-{c2.id}",
            address=f"{MARKER} OSGB2 adres",
            is_active=True,
        )
    )
    e2 = Employee(
        company_id=c2.id,
        full_name=f"{MARKER} Yabanci Personel",
        job_title="Operator",
        department="Uretim",
        is_active=True,
    )
    db.add(e2)
    u2 = User(
        email="test.osgb2.admin@example.com",
        full_name=f"{MARKER} OSGB2 Firma Admin",
        hashed_password=_hash(),
        role=UserRole.COMPANY_ADMIN,
        company_id=c2.id,
        osgb_id=osgb2.id,
        is_active=True,
    )
    db.add(u2)
    created_users.append(u2.email)

    db.commit()
    return {
        "osgb": osgb.name,
        "osgb2": osgb2.name,
        "companies": [n for n, *_ in firms] + [c2.name],
        "users": created_users,
        "password": TEST_PASSWORD,
        "marker": MARKER,
        "cross_osgb": {
            "osgb1_company": company_map["Az Tehlikeli"][0].name,
            "osgb2_company": c2.name,
            "osgb2_admin": "test.osgb2.admin@example.com",
        },
    }


def main():
    Base.metadata.create_all(bind=engine)
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.cleanup:
            out = {"cleaned": cleanup(db)}
        else:
            out = seed(db)
    # Windows konsol (cp1252) icin guvenli JSON
    sys.stdout.buffer.write((json.dumps(out, ensure_ascii=True, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
