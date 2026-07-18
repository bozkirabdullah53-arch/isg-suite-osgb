from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.entities import TrainingStatus


class TrainingCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    title: str = Field(min_length=3, max_length=220)
    training_type: str = Field(default="Temel İSG Eğitimi", max_length=80)
    delivery_method: str = Field(default="Yüz yüze", max_length=40)
    location: str | None = Field(default=None, max_length=220)
    start_date: date
    end_date: date | None = None
    hazard_class: str
    sector: str | None = Field(default=None, max_length=120)
    instructor_name: str = Field(min_length=3, max_length=160)
    instructor_qualification: str | None = Field(default=None, max_length=220)
    workplace_physician: str | None = Field(default=None, max_length=160)
    employer_representative: str | None = Field(default=None, max_length=160)
    stamp_text: str | None = Field(default=None, max_length=400)
    evaluation_method: str = Field(default="Sınav", max_length=80)
    passing_score: int | None = Field(default=None, ge=0, le=100)
    attendance_verified: bool = False
    success_verified: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    participant_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def dates_valid(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")
        if not self.participant_ids:
            raise ValueError(
                "En az bir katılımcı seçmelisiniz (Excel veya personel listesi). Belge/imza formu için zorunludur."
            )
        return self


class TrainingUpdate(BaseModel):
    status: TrainingStatus | None = None
    attendance_verified: bool | None = None
    success_verified: bool | None = None
    workplace_physician: str | None = Field(default=None, max_length=160)
    employer_representative: str | None = Field(default=None, max_length=160)
    stamp_text: str | None = Field(default=None, max_length=400)
    notes: str | None = Field(default=None, max_length=2000)


class ParticipantResponse(BaseModel):
    id: int
    employee_id: int
    attended: bool
    score: int | None
    successful: bool | None
    certificate_number: str | None
    model_config = ConfigDict(from_attributes=True)


class TrainingResponse(BaseModel):
    id: int
    company_id: int
    branch_id: int | None
    title: str
    training_type: str
    delivery_method: str
    location: str | None
    start_date: date
    end_date: date | None
    next_training_date: date | None
    hazard_class: str
    duration_hours: int
    renewal_years: int
    sector: str | None
    instructor_name: str
    instructor_qualification: str | None
    workplace_physician: str | None = None
    employer_representative: str | None = None
    logo_path: str | None = None
    stamp_text: str | None = None
    evaluation_method: str
    passing_score: int | None
    attendance_verified: bool
    success_verified: bool
    verification_code: str
    status: TrainingStatus
    notes: str | None
    created_at: datetime
    participants: list[ParticipantResponse] = []
    model_config = ConfigDict(from_attributes=True)


class TrainingVerifyResponse(BaseModel):
    valid: bool
    verification_code: str
    title: str | None = None
    company_name: str | None = None
    start_date: date | None = None
    hazard_class: str | None = None
    duration_hours: int | None = None
    instructor_name: str | None = None
    workplace_physician: str | None = None
    employer_representative: str | None = None
    participant_count: int = 0
    participants: list[dict] = Field(default_factory=list)
    message: str | None = None
