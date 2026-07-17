import enum
from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
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
    tax_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hazard_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped[Company | None] = relationship(back_populates="users")

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
    LAB_TEST = "lab_test"
    VACCINATION = "vaccination"
    FITNESS_REPORT = "fitness_report"


class HealthFitnessStatus(str, enum.Enum):
    FIT = "fit"
    CONDITIONAL = "conditional"
    UNFIT = "unfit"
    PENDING = "pending"


class HealthRecord(Base):
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    record_type: Mapped[HealthRecordType] = mapped_column(Enum(HealthRecordType), index=True)
    examination_date: Mapped[date] = mapped_column(Date, index=True)
    next_examination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fitness_status: Mapped[HealthFitnessStatus] = mapped_column(
        Enum(HealthFitnessStatus), default=HealthFitnessStatus.PENDING
    )
    physician_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    confidential_note: Mapped[str | None] = mapped_column(String(3000), nullable=True)
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


class AnnualPlanItem(Base):
    __tablename__ = "annual_plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    year: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column()
    activity: Mapped[str] = mapped_column(String(240), index=True)
    responsible_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[AnnualPlanStatus] = mapped_column(
        Enum(AnnualPlanStatus), default=AnnualPlanStatus.PLANNED
    )
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1500), nullable=True)
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
