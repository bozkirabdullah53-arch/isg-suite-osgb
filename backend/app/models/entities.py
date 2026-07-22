import enum
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class UserRole(str, enum.Enum):
    GLOBAL_ADMIN = "global_admin"
    COMPANY_ADMIN = "company_admin"
    SAFETY_SPECIALIST = "safety_specialist"
    WORKPLACE_PHYSICIAN = "workplace_physician"
    OTHER_HEALTH_PERSONNEL = "other_health_personnel"
    READ_ONLY = "read_only"



class OsgbOrganization(Base):
    __tablename__ = "osgb_organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    authorization_number: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    tax_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    responsible_manager: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProfessionalType(str, enum.Enum):
    SAFETY_SPECIALIST = "safety_specialist"
    WORKPLACE_PHYSICIAN = "workplace_physician"
    OTHER_HEALTH_PERSONNEL = "other_health_personnel"


class IsgProfessional(Base):
    __tablename__ = "isg_professionals"
    __table_args__ = (UniqueConstraint("osgb_id", "certificate_number", name="uq_professional_osgb_certificate"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    professional_type: Mapped[ProfessionalType] = mapped_column(Enum(ProfessionalType), index=True)
    certificate_class: Mapped[str | None] = mapped_column(String(20), nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    certificate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"
    SUSPENDED = "suspended"


class WorkplaceAssignment(Base):
    __tablename__ = "workplace_assignments"
    __table_args__ = (UniqueConstraint("company_id", "professional_id", "professional_type", name="uq_company_professional_assignment"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("isg_professionals.id"), index=True)
    professional_type: Mapped[ProfessionalType] = mapped_column(Enum(ProfessionalType), index=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    required_minutes_monthly: Mapped[int] = mapped_column(Integer, default=0)
    planned_minutes_monthly: Mapped[int] = mapped_column(Integer, default=0)
    actual_minutes_monthly: Mapped[int] = mapped_column(Integer, default=0)
    isg_katip_contract_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contract_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(Enum(AssignmentStatus), default=AssignmentStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ServiceContract(Base):
    __tablename__ = "service_contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    contract_number: Mapped[str] = mapped_column(String(100), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    monthly_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    tax_number: Mapped[str | None] = mapped_column(String(20), nullable=True)  # legacy; UI'da yok
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)  # legacy; UI'da yok
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sgk_registry_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    authorized_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    site_verify_code: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    users: Mapped[list["User"]] = relationship(back_populates="company")
    branches: Mapped[list["Branch"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    employees: Mapped[list["Employee"]] = relationship(back_populates="company")

class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_branch_company_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    sgk_registry_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company: Mapped[Company] = relationship(back_populates="branches")
    employees: Mapped[list["Employee"]] = relationship(back_populates="branch")

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.READ_ONLY)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    failed_login_count: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mfa_recovery_hashes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company | None] = relationship(back_populates="users")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("company_id", "national_id_masked", name="uq_employee_company_national"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    national_id_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    special_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    company: Mapped[Company] = relationship(back_populates="employees")
    branch: Mapped[Branch | None] = relationship(back_populates="employees")


class IsgModule(str, enum.Enum):
    RISK = "risk"
    NEAR_MISS = "near_miss"
    ACCIDENT = "accident"
    CAPA = "capa"
    TRAINING = "training"


class RecordStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class IsgRecord(Base):
    __tablename__ = "isg_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    module: Mapped[IsgModule] = mapped_column(Enum(IsgModule), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[RecordStatus] = mapped_column(Enum(RecordStatus), default=RecordStatus.OPEN, index=True)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsible_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    probability: Mapped[int | None] = mapped_column(nullable=True)
    impact: Mapped[int | None] = mapped_column(nullable=True)
    risk_score: Mapped[int | None] = mapped_column(nullable=True)
    participant_count: Mapped[int | None] = mapped_column(nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HealthRecordType(str, enum.Enum):
    ENTRY_EXAM = "entry_exam"
    PERIODIC_EXAM = "periodic_exam"
    RETURN_EXAM = "return_exam"
    JOB_CHANGE = "job_change"
    NIGHT_WORK = "night_work"
    HEAVY_HAZARDOUS = "heavy_hazardous"
    LAB_TEST = "lab_test"
    VACCINATION = "vaccination"
    FITNESS_REPORT = "fitness_report"
    OTHER = "other"


class HealthFitnessStatus(str, enum.Enum):
    FIT = "fit"
    CONDITIONAL = "conditional"
    TRACKING = "tracking"
    UNFIT = "unfit"
    PENDING = "pending"


class HealthRecord(Base):
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    record_type: Mapped[HealthRecordType] = mapped_column(
        Enum(
            HealthRecordType,
            name="healthrecordtype",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=40,
        ),
        index=True,
    )
    examination_date: Mapped[date] = mapped_column(Date, index=True)
    next_examination_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    fitness_status: Mapped[HealthFitnessStatus] = mapped_column(
        Enum(
            HealthFitnessStatus,
            name="healthfitnessstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=40,
        ),
        default=HealthFitnessStatus.PENDING,
    )
    physician_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confidential_note: Mapped[str | None] = mapped_column(String(3000), nullable=True)
    # PRO tetkik takip alanları
    audiometry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    audiometry_result: Mapped[str | None] = mapped_column(String(240), nullable=True)
    spirometry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    spirometry_result: Mapped[str | None] = mapped_column(String(240), nullable=True)
    chest_xray_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    chest_xray_result: Mapped[str | None] = mapped_column(String(240), nullable=True)
    blood_lead_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    blood_lead_value: Mapped[float | None] = mapped_column(nullable=True)
    blood_lead_unit: Mapped[str | None] = mapped_column(String(20), nullable=True, default="µg/dL")
    blood_lead_ref: Mapped[float | None] = mapped_column(nullable=True)
    blood_lead_eval: Mapped[str | None] = mapped_column(String(40), nullable=True)
    suggested_tests: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    exposures: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    follow_up_note: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    other_biological_test: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    report_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    report_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentCategory(str, enum.Enum):
    GENERAL = "general"
    RISK = "risk"
    TRAINING = "training"
    HEALTH = "health"
    EMERGENCY = "emergency"
    LEGAL = "legal"
    ANNUAL_PLAN = "annual_plan"


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    category: Mapped[DocumentCategory] = mapped_column(Enum(DocumentCategory), index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnnualPlanStatus(str, enum.Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class AnnualPlanItem(Base):
    __tablename__ = "annual_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column()
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, default="yillik_calisma", index=True)
    activity: Mapped[str] = mapped_column(String(240), index=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    responsible_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[AnnualPlanStatus] = mapped_column(
        Enum(
            AnnualPlanStatus,
            name="annualplanstatus",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            validate_strings=True,
        ),
        default=AnnualPlanStatus.PLANNED,
    )
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    module: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SubscriptionPlan(str, enum.Enum):
    DEMO = "demo"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class CompanySubscription(Base):
    __tablename__ = "company_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True, index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), default=SubscriptionPlan.DEMO)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_users: Mapped[int] = mapped_column(default=3)
    max_employees: Mapped[int] = mapped_column(default=50)
    is_auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OsgbSubscriptionPlan(str, enum.Enum):
  STANDARD = "standard"


class PaymentChannel(str, enum.Enum):
    IYZICO = "iyzico"
    STRIPE = "stripe"
    BANK_TRANSFER = "bank_transfer"
    INVOICE = "invoice"


class OsgbApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class OsgbApplication(Base):
    __tablename__ = "osgb_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    authorization_number: Mapped[str] = mapped_column(String(80), index=True)
    tax_number: Mapped[str] = mapped_column(String(20), index=True)
    responsible_manager: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255), index=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    applicant_name: Mapped[str] = mapped_column(String(160))
    applicant_email: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    contract_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    personal_data_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[OsgbApplicationStatus] = mapped_column(
        Enum(OsgbApplicationStatus), default=OsgbApplicationStatus.PENDING, index=True
    )
    matched_osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    auto_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EisaPackage(Base):
    __tablename__ = "eisa_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price_monthly: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    price_yearly: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    max_users: Mapped[int] = mapped_column(default=50)
    max_workplaces: Mapped[int] = mapped_column(default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EisaPaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class EisaSubscriptionPayment(Base):
    __tablename__ = "eisa_subscription_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_no: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_subscriptions.id"), nullable=True, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="TRY")
    payment_method: Mapped[PaymentChannel | None] = mapped_column(Enum(PaymentChannel), nullable=True)
    payment_status: Mapped[EisaPaymentStatus] = mapped_column(
        Enum(EisaPaymentStatus), default=EisaPaymentStatus.COMPLETED, index=True
    )
    payment_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EisaNotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"


class EisaNotificationTarget(str, enum.Enum):
    ALL_OSGB = "all_osgb"
    SELECTED_OSGB = "selected_osgb"


class EisaNotificationDeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"


class EisaPlatformNotification(Base):
    __tablename__ = "eisa_platform_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[EisaNotificationChannel] = mapped_column(Enum(EisaNotificationChannel), index=True)
    target_scope: Mapped[EisaNotificationTarget] = mapped_column(Enum(EisaNotificationTarget))
    target_osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(String(2000))
    status: Mapped[EisaNotificationDeliveryStatus] = mapped_column(
        Enum(EisaNotificationDeliveryStatus), default=EisaNotificationDeliveryStatus.QUEUED, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EisaPlatformSetting(Base):
    __tablename__ = "eisa_platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    value: Mapped[str] = mapped_column(String(2000))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EisaErrorReportSource(str, enum.Enum):
    UI_CRASH = "ui_crash"
    API_ERROR = "api_error"
    USER_REPORT = "user_report"


class EisaErrorReportStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class EisaErrorReport(Base):
    """Kullanıcı / istemci hata ve destek raporları — EİSA panosu."""

    __tablename__ = "eisa_error_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    http_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    http_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(default=1)
    admin_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    admin_reply: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ArchiveKind(str, enum.Enum):
    TENANT_BACKUP = "tenant_backup"
    DELETED_FILE = "deleted_file"


class EisaArchiveRecord(Base):
    """Merkezi tarihli arşiv — EİSA her kaydı görür; kurum yalnızca kendi yedeklerini."""

    __tablename__ = "eisa_archive_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[ArchiveKind] = mapped_column(Enum(ArchiveKind), index=True)
    osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OsgbSubscription(Base):
    __tablename__ = "osgb_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), unique=True, index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("eisa_packages.id"), nullable=True, index=True)
    plan: Mapped[OsgbSubscriptionPlan] = mapped_column(
        Enum(OsgbSubscriptionPlan), default=OsgbSubscriptionPlan.STANDARD
    )
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.TRIAL)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_users: Mapped[int] = mapped_column(default=50)
    max_workplaces: Mapped[int] = mapped_column(default=100)
    last_payment_channel: Mapped[PaymentChannel | None] = mapped_column(Enum(PaymentChannel), nullable=True)
    payment_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationType(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType), default=NotificationType.INFO)
    title: Mapped[str] = mapped_column(String(220))
    message: Mapped[str] = mapped_column(String(1200))
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class VisitStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TrainingStatus(str, enum.Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrainingSession(Base):
    __tablename__ = "training_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(220), index=True)
    training_type: Mapped[str] = mapped_column(String(80), default="Temel İSG Eğitimi")
    delivery_method: Mapped[str] = mapped_column(String(40), default="Yüz yüze")
    location: Mapped[str | None] = mapped_column(String(220), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_training_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_hours: Mapped[int] = mapped_column(default=0)
    renewal_years: Mapped[int] = mapped_column(default=0)
    hazard_class: Mapped[str] = mapped_column(String(40))
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instructor_name: Mapped[str] = mapped_column(String(160))
    instructor_qualification: Mapped[str | None] = mapped_column(String(220), nullable=True)
    workplace_physician: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employer_representative: Mapped[str | None] = mapped_column(String(160), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stamp_text: Mapped[str | None] = mapped_column(String(400), nullable=True)
    evaluation_method: Mapped[str] = mapped_column(String(80), default="Sınav")
    passing_score: Mapped[int | None] = mapped_column(nullable=True)
    attendance_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    success_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    status: Mapped[TrainingStatus] = mapped_column(Enum(TrainingStatus), default=TrainingStatus.PLANNED, index=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    participants: Mapped[list["TrainingParticipant"]] = relationship(back_populates="training", cascade="all, delete-orphan")


class TrainingParticipant(Base):
    __tablename__ = "training_participants"
    __table_args__ = (UniqueConstraint("training_id", "employee_id", name="uq_training_employee"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    training_id: Mapped[int] = mapped_column(ForeignKey("training_sessions.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    attended: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int | None] = mapped_column(nullable=True)
    successful: Mapped[bool | None] = mapped_column(nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(30), nullable=True, unique=True)
    training: Mapped["TrainingSession"] = relationship(back_populates="participants")

class ServiceVisit(Base):
    __tablename__ = "service_visits"
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("isg_professionals.id"), index=True)
    visit_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    subject: Mapped[str] = mapped_column(String(220))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    notebook_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notebook_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notebook_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus), default=VisitStatus.PLANNED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CrmLead(Base):
    __tablename__ = "crm_leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(220), index=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stage: Mapped[str] = mapped_column(String(40), default="new", index=True)
    estimated_monthly_value: Mapped[int] = mapped_column(Integer, default=0)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int] = mapped_column(ForeignKey("osgb_organizations.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str] = mapped_column(String(80), default="service")
    amount: Mapped[int] = mapped_column(Integer, default=0)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --- Risk değerlendirme (İSG PRO 2026 risk modülünden) ---


class HazardCategory(Base):
    __tablename__ = "hazard_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True, default="bi-exclamation-triangle")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    hazards: Mapped[list["Hazard"]] = relationship(back_populates="category")


class Hazard(Base):
    __tablename__ = "hazards"
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("hazard_categories.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    risk_source: Mapped[str | None] = mapped_column(String(250), nullable=True)
    regulations: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    ai_suggestions: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    default_probability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    category: Mapped[HazardCategory] = relationship(back_populates="hazards")


class WorkplaceDepartment(Base):
    """İşyeri / fabrika bölümü (Üretim, Depo, Bakım vb.)."""

    __tablename__ = "workplace_departments"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_workplace_department_company_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskAssessmentStatus(str, enum.Enum):
    OPEN = "Açık"
    COMPLETED = "Tamamlandı"
    CANCELLED = "İptal"
    REVISED = "Revize"


class RiskAssessment(Base):
    """Firma bazlı risk kaydı — generic IsgRecord(module=risk) yerine."""

    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    risk_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("workplace_departments.id"), nullable=True, index=True)
    hazard_id: Mapped[int] = mapped_column(ForeignKey("hazards.id"), index=True)
    department_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    activity: Mapped[str] = mapped_column(String(500))
    risk_definition: Mapped[str] = mapped_column(String(2000))
    affected_people: Mapped[str | None] = mapped_column(String(500), nullable=True)
    affected_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    existing_measures: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    additional_measures: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    probability: Mapped[int] = mapped_column(Integer)
    severity: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    risk_level: Mapped[str] = mapped_column(String(50), index=True)
    term_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    term_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_suggested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    term_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(50), default="Açık", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    dofs: Mapped[list["RiskDof"]] = relationship(back_populates="risk", cascade="all, delete-orphan")
    media_files: Mapped[list["RiskMedia"]] = relationship(
        back_populates="risk", cascade="all, delete-orphan"
    )


class RiskMedia(Base):
    """Risk kaydına bağlı foto/medya (PRO MediaFile parity)."""
    __tablename__ = "risk_media"
    id: Mapped[int] = mapped_column(primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 0.9.121 — isteğe bağlı tehlike etiketi checklist (JSON)
    tags_json: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    risk: Mapped[RiskAssessment] = relationship(back_populates="media_files")


class RiskDof(Base):
    __tablename__ = "risk_dofs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dof_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(2000))
    responsible_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    responsible_department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    term_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="TRY")
    status: Mapped[str] = mapped_column(String(50), default="Açık", index=True)
    completion_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    risk: Mapped[RiskAssessment] = relationship(back_populates="dofs")


class IncidentEvent(Base):
    """Ramak kala / iş kazası / tehlike / acil durum — PRO OlayKayit uyarlaması."""

    __tablename__ = "incident_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    form_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="Aktif", index=True)
    recorded_by_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    safety_specialist: Mapped[str | None] = mapped_column(String(160), nullable=True)
    workplace_physician: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employer_representative: Mapped[str | None] = mapped_column(String(160), nullable=True)
    department: Mapped[str | None] = mapped_column(String(160), nullable=True)
    event_date: Mapped[date] = mapped_column(Date, index=True)
    event_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    location: Mapped[str | None] = mapped_column(String(220), nullable=True)
    area: Mapped[str | None] = mapped_column(String(160), nullable=True)
    work_being_done: Mapped[str | None] = mapped_column(String(500), nullable=True)
    related_people: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    has_witness: Mapped[bool] = mapped_column(Boolean, default=False)
    witness_names: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    equipment_used: Mapped[str | None] = mapped_column(String(500), nullable=True)
    chemical_used: Mapped[str | None] = mapped_column(String(500), nullable=True)
    short_summary: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(160), nullable=True)
    injury_occurred: Mapped[bool] = mapped_column(Boolean, default=False)
    health_complaint: Mapped[bool] = mapped_column(Boolean, default=False)
    medical_intervention: Mapped[bool] = mapped_column(Boolean, default=False)
    work_incapacity_report: Mapped[bool] = mapped_column(Boolean, default=False)
    equipment_damage: Mapped[bool] = mapped_column(Boolean, default=False)
    would_have_injured: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_warning: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    probability: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    risk_analysis_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_analysis_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    emergency_relation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    emergency_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    evaluation_text: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    sgk_reported: Mapped[bool] = mapped_column(Boolean, default=False)
    sgk_report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    police_reported: Mapped[bool] = mapped_column(Boolean, default=False)
    accident_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    injury_type: Mapped[str | None] = mapped_column(String(220), nullable=True)
    intervention_detail: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    report_days: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    root_cause: Mapped["IncidentRootCause | None"] = relationship(
        back_populates="incident", uselist=False, cascade="all, delete-orphan"
    )
    dofs: Mapped[list["IncidentDof"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentRootCause(Base):
    __tablename__ = "incident_root_causes"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incident_events.id", ondelete="CASCADE"), unique=True, index=True
    )
    why_1: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    why_2: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    why_3: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    why_4: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    why_5: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    root_cause_category: Mapped[str | None] = mapped_column(String(160), nullable=True)
    systemic_gap: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    incident: Mapped[IncidentEvent] = relationship(back_populates="root_cause")


class IncidentDof(Base):
    __tablename__ = "incident_dofs"
    id: Mapped[int] = mapped_column(primary_key=True)
    dof_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incident_events.id", ondelete="CASCADE"), index=True
    )
    finding: Mapped[str] = mapped_column(String(2000))
    root_cause: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    corrective_action: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    preventive_action: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    responsible_person: Mapped[str | None] = mapped_column(String(160), nullable=True)
    term_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(30), default="Orta")
    status: Mapped[str] = mapped_column(String(40), default="Açık", index=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effectiveness_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    close_approval: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    incident: Mapped[IncidentEvent] = relationship(back_populates="dofs")


class PpeAssignment(Base):
    """KKD zimmet / teslim kaydı (PRO kkd_takip parity)."""
    __tablename__ = "ppe_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    delivery_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(120))
    item_type: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size: Mapped[str | None] = mapped_column(String(60), nullable=True)
    serial_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    shelf_life_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    renewal_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="teslim", index=True)
    delivered_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    risk_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    photos: Mapped[list["PpeAssignmentPhoto"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class PpeAssignmentPhoto(Base):
    __tablename__ = "ppe_assignment_photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("ppe_assignments.id", ondelete="CASCADE"), index=True
    )
    storage_path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assignment: Mapped[PpeAssignment] = relationship(back_populates="photos")


class IntegrationDryRunLog(Base):
    """0.9.126 — İBYS/KATİP dry-run export kaydı (harici HTTP yok)."""

    __tablename__ = "integration_dry_run_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    osgb_id: Mapped[int | None] = mapped_column(ForeignKey("osgb_organizations.id"), nullable=True, index=True)
    adapter: Mapped[str] = mapped_column(String(20), index=True)  # ibys | katip
    status: Mapped[str] = mapped_column(String(40), default="dry_run", index=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ChemicalProduct(Base):
    """0.9.119 — SDS/PKD kimyasal ürün sicili (saha uzmanı)."""

    __tablename__ = "chemical_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(220), index=True)
    cas_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    has_sds_file: Mapped[bool] = mapped_column(Boolean, default=False)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_records.id"), nullable=True, index=True
    )
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    ghs_checklist_json: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
