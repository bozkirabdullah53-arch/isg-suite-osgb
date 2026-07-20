from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.input_rules import (
    assert_date_order,
    assert_event_date,
    assert_meaningful_text,
    assert_person_name,
    clean_text,
)


class IncidentCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    event_type: str = Field(min_length=3, max_length=40)
    short_summary: str = Field(min_length=1, max_length=500)
    event_date: date
    event_time: str | None = Field(default=None, max_length=10)
    department: str | None = Field(default=None, max_length=160)
    location: str = Field(min_length=1, max_length=220)
    area: str | None = Field(default=None, max_length=160)
    work_being_done: str | None = Field(default=None, max_length=500)
    related_people: str | None = Field(default=None, max_length=2000)
    has_witness: bool = False
    witness_names: str | None = Field(default=None, max_length=2000)
    equipment_used: str | None = Field(default=None, max_length=500)
    chemical_used: str | None = Field(default=None, max_length=500)
    detail: str = Field(min_length=1, max_length=4000)
    classification: str = Field(min_length=2, max_length=160)
    injury_occurred: bool = False
    health_complaint: bool = False
    medical_intervention: bool = False
    work_incapacity_report: bool = False
    equipment_damage: bool = False
    would_have_injured: bool = False
    probability: int = Field(default=1, ge=0, le=5)
    severity: int = Field(default=1, ge=0, le=5)
    risk_analysis_status: str | None = Field(default=None, max_length=50)
    risk_analysis_note: str | None = Field(default=None, max_length=2000)
    emergency_relation: str | None = Field(default=None, max_length=160)
    emergency_note: str | None = Field(default=None, max_length=2000)
    evaluation_text: str | None = Field(default=None, max_length=4000)
    recorded_by_name: str | None = Field(default=None, max_length=160)
    safety_specialist: str | None = Field(default=None, max_length=160)
    workplace_physician: str | None = Field(default=None, max_length=160)
    employer_representative: str | None = Field(default=None, max_length=160)
    sgk_reported: bool = False
    sgk_report_date: date | None = None
    police_reported: bool = False
    accident_type: str | None = Field(default=None, max_length=120)
    injury_type: str | None = Field(default=None, max_length=220)
    intervention_detail: str | None = Field(default=None, max_length=2000)
    report_days: int = Field(default=0, ge=0, le=3650)
    status: str = Field(default="Aktif", max_length=40)

    @model_validator(mode="after")
    def type_ok(self):
        from app.services.incident_meta import EVENT_TYPES

        if self.event_type not in EVENT_TYPES:
            raise ValueError("Geçersiz olay tipi.")

        self.event_date = assert_event_date(self.event_date, label="Olay tarihi", allow_future_days=0)
        self.sgk_report_date = assert_event_date(
            self.sgk_report_date, label="SGK bildirim tarihi", required=False, allow_future_days=0
        )
        assert_date_order(
            self.event_date,
            self.sgk_report_date,
            earlier_label="Olay tarihi",
            later_label="SGK bildirim tarihi",
        )

        self.short_summary = assert_meaningful_text(
            self.short_summary, label="Kısa özet", min_len=20, required=True
        )
        self.detail = assert_meaningful_text(self.detail, label="Detay", min_len=30, required=True)
        self.location = assert_meaningful_text(self.location, label="Olay yeri", min_len=2, required=True)
        self.department = assert_meaningful_text(self.department, label="Departman", min_len=2, required=False)
        self.area = assert_meaningful_text(self.area, label="Alan", min_len=2, required=False)
        self.work_being_done = assert_meaningful_text(
            self.work_being_done, label="Yapılan iş", min_len=3, required=False
        )
        self.related_people = assert_meaningful_text(
            self.related_people, label="İlgili kişiler", min_len=2, required=False
        )
        self.equipment_used = assert_meaningful_text(
            self.equipment_used, label="Kullanılan ekipman", min_len=2, required=False
        )
        self.chemical_used = assert_meaningful_text(
            self.chemical_used, label="Kullanılan kimyasal", min_len=2, required=False
        )
        self.risk_analysis_note = assert_meaningful_text(
            self.risk_analysis_note, label="Risk analizi notu", min_len=5, required=False
        )
        self.emergency_note = assert_meaningful_text(
            self.emergency_note, label="Acil durum notu", min_len=5, required=False
        )
        self.evaluation_text = assert_meaningful_text(
            self.evaluation_text, label="Değerlendirme", min_len=10, required=False
        )
        self.intervention_detail = assert_meaningful_text(
            self.intervention_detail, label="Müdahale detayı", min_len=5, required=False
        )

        if self.has_witness:
            self.witness_names = assert_meaningful_text(
                self.witness_names, label="Şahit isimleri", min_len=3, required=True
            )
        else:
            self.witness_names = clean_text(self.witness_names)

        self.recorded_by_name = assert_person_name(self.recorded_by_name, label="Kaydeden")
        self.safety_specialist = assert_person_name(self.safety_specialist, label="İSG uzmanı")
        self.workplace_physician = assert_person_name(self.workplace_physician, label="İşyeri hekimi")
        self.employer_representative = assert_person_name(
            self.employer_representative, label="İşveren / vekili"
        )

        if self.sgk_reported and not self.sgk_report_date:
            raise ValueError("SGK bildirildi işaretliyse bildirim tarihi girilmelidir.")

        return self


class IncidentUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=40)
    short_summary: str | None = Field(default=None, min_length=1, max_length=500)
    event_date: date | None = None
    event_time: str | None = Field(default=None, max_length=10)
    department: str | None = Field(default=None, max_length=160)
    location: str | None = Field(default=None, max_length=220)
    area: str | None = Field(default=None, max_length=160)
    work_being_done: str | None = Field(default=None, max_length=500)
    related_people: str | None = Field(default=None, max_length=2000)
    has_witness: bool | None = None
    witness_names: str | None = Field(default=None, max_length=2000)
    equipment_used: str | None = Field(default=None, max_length=500)
    chemical_used: str | None = Field(default=None, max_length=500)
    detail: str | None = Field(default=None, max_length=4000)
    classification: str | None = Field(default=None, max_length=160)
    injury_occurred: bool | None = None
    health_complaint: bool | None = None
    medical_intervention: bool | None = None
    work_incapacity_report: bool | None = None
    equipment_damage: bool | None = None
    would_have_injured: bool | None = None
    probability: int | None = Field(default=None, ge=0, le=5)
    severity: int | None = Field(default=None, ge=0, le=5)
    risk_analysis_status: str | None = Field(default=None, max_length=50)
    risk_analysis_note: str | None = Field(default=None, max_length=2000)
    emergency_relation: str | None = Field(default=None, max_length=160)
    emergency_note: str | None = Field(default=None, max_length=2000)
    evaluation_text: str | None = Field(default=None, max_length=4000)
    recorded_by_name: str | None = Field(default=None, max_length=160)
    safety_specialist: str | None = Field(default=None, max_length=160)
    workplace_physician: str | None = Field(default=None, max_length=160)
    employer_representative: str | None = Field(default=None, max_length=160)
    sgk_reported: bool | None = None
    sgk_report_date: date | None = None
    police_reported: bool | None = None
    accident_type: str | None = Field(default=None, max_length=120)
    injury_type: str | None = Field(default=None, max_length=220)
    intervention_detail: str | None = Field(default=None, max_length=2000)
    report_days: int | None = Field(default=None, ge=0, le=3650)
    branch_id: int | None = None

    @model_validator(mode="after")
    def sanitize(self):
        if self.event_date is not None:
            self.event_date = assert_event_date(self.event_date, label="Olay tarihi", allow_future_days=0)
        if self.sgk_report_date is not None:
            self.sgk_report_date = assert_event_date(
                self.sgk_report_date, label="SGK bildirim tarihi", required=False, allow_future_days=0
            )
        assert_date_order(
            self.event_date,
            self.sgk_report_date,
            earlier_label="Olay tarihi",
            later_label="SGK bildirim tarihi",
        )
        if self.short_summary is not None:
            self.short_summary = assert_meaningful_text(
                self.short_summary, label="Kısa özet", min_len=20, required=True
            )
        if self.detail is not None:
            self.detail = assert_meaningful_text(self.detail, label="Detay", min_len=30, required=True)
        if self.location is not None:
            self.location = assert_meaningful_text(self.location, label="Olay yeri", min_len=2, required=True)
        for attr, label, mn in (
            ("department", "Departman", 2),
            ("area", "Alan", 2),
            ("work_being_done", "Yapılan iş", 3),
            ("related_people", "İlgili kişiler", 2),
            ("equipment_used", "Kullanılan ekipman", 2),
            ("chemical_used", "Kullanılan kimyasal", 2),
            ("risk_analysis_note", "Risk analizi notu", 5),
            ("emergency_note", "Acil durum notu", 5),
            ("evaluation_text", "Değerlendirme", 10),
            ("intervention_detail", "Müdahale detayı", 5),
            ("witness_names", "Şahit isimleri", 3),
        ):
            val = getattr(self, attr)
            if val is not None:
                setattr(self, attr, assert_meaningful_text(val, label=label, min_len=mn, required=False))
        for attr, label in (
            ("recorded_by_name", "Kaydeden"),
            ("safety_specialist", "İSG uzmanı"),
            ("workplace_physician", "İşyeri hekimi"),
            ("employer_representative", "İşveren / vekili"),
        ):
            val = getattr(self, attr)
            if val is not None:
                setattr(self, attr, assert_person_name(val, label=label))
        return self


class RootCauseUpsert(BaseModel):
    why_1: str | None = Field(default=None, max_length=2000)
    why_2: str | None = Field(default=None, max_length=2000)
    why_3: str | None = Field(default=None, max_length=2000)
    why_4: str | None = Field(default=None, max_length=2000)
    why_5: str | None = Field(default=None, max_length=2000)
    root_cause: str | None = Field(default=None, max_length=2000)
    root_cause_category: str | None = Field(default=None, max_length=160)
    systemic_gap: str | None = Field(default=None, max_length=2000)


class IncidentDofCreate(BaseModel):
    finding: str = Field(min_length=1, max_length=2000)
    root_cause: str | None = Field(default=None, max_length=2000)
    corrective_action: str = Field(min_length=1, max_length=2000)
    preventive_action: str = Field(min_length=1, max_length=2000)
    responsible_person: str = Field(min_length=1, max_length=160)
    term_date: date
    priority: str = Field(default="Orta", max_length=30)

    @model_validator(mode="after")
    def sanitize(self):
        self.finding = assert_meaningful_text(self.finding, label="Bulgu", min_len=10, required=True)
        self.corrective_action = assert_meaningful_text(
            self.corrective_action, label="Düzeltici faaliyet", min_len=10, required=True
        )
        self.preventive_action = assert_meaningful_text(
            self.preventive_action, label="Önleyici faaliyet", min_len=10, required=True
        )
        self.root_cause = assert_meaningful_text(
            self.root_cause, label="Kök neden", min_len=5, required=False
        )
        self.responsible_person = assert_person_name(
            self.responsible_person, label="Sorumlu kişi", required=True
        )
        self.term_date = assert_event_date(
            self.term_date, label="Termin tarihi", allow_future_days=3650, earliest=date(2000, 1, 1)
        )
        return self



class IncidentDofComplete(BaseModel):
    effectiveness_note: str | None = Field(default=None, max_length=2000)
    close_approval: str | None = Field(default=None, max_length=160)


class RootCauseResponse(BaseModel):
    id: int
    incident_id: int
    why_1: str | None
    why_2: str | None
    why_3: str | None
    why_4: str | None
    why_5: str | None
    root_cause: str | None
    root_cause_category: str | None
    systemic_gap: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentDofResponse(BaseModel):
    id: int
    dof_no: str
    incident_id: int
    finding: str
    root_cause: str | None
    corrective_action: str | None
    preventive_action: str | None
    responsible_person: str | None
    term_date: date | None
    priority: str
    status: str
    completion_date: date | None
    effectiveness_note: str | None
    close_approval: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class IncidentResponse(BaseModel):
    id: int
    form_no: str
    company_id: int
    branch_id: int | None
    event_type: str
    status: str
    recorded_by_name: str | None
    safety_specialist: str | None
    workplace_physician: str | None
    employer_representative: str | None
    department: str | None
    event_date: date
    event_time: str | None
    location: str | None
    area: str | None
    work_being_done: str | None
    related_people: str | None
    has_witness: bool
    witness_names: str | None
    equipment_used: str | None
    chemical_used: str | None
    short_summary: str
    detail: str | None
    classification: str | None
    injury_occurred: bool
    health_complaint: bool
    medical_intervention: bool
    work_incapacity_report: bool
    equipment_damage: bool
    would_have_injured: bool
    auto_warning: str | None
    probability: int
    severity: int
    risk_score: int
    risk_level: str | None
    risk_analysis_status: str | None
    risk_analysis_note: str | None
    emergency_relation: str | None
    emergency_note: str | None
    evaluation_text: str | None
    sgk_reported: bool
    sgk_report_date: date | None
    police_reported: bool
    accident_type: str | None
    injury_type: str | None
    intervention_detail: str | None
    report_days: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    root_cause: RootCauseResponse | None = None
    dofs: list[IncidentDofResponse] = []
    model_config = ConfigDict(from_attributes=True)
