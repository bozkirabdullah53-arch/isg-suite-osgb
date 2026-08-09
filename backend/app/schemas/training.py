from datetime import date, datetime
from math import ceil
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.entities import TrainingStatus
from app.services.special_training_profiles import (
    SPECIAL_INSTRUCTOR_ROLES,
    SPECIAL_TRAINING_PROFILES,
    resolve_special_duration_hours,
    resolve_special_profile_key,
)
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api

# Bir takvim gününde makul üst ders saati (1 günde 16 saat olmaz)
MAX_TRAINING_HOURS_PER_DAY = 8
HAZARD_HOURS = {"Az Tehlikeli": 8, "Tehlikeli": 12, "Çok Tehlikeli": 16}


def resolve_training_hours(*, training_type: str, title: str, notes: str | None, hazard_class: str) -> int:
    """Tek kaynaklı süre politikası: işe başlama 2 saat, tekrar 8 saat,
    temel eğitim tehlike sınıfı saati, özel profil ise katalog saati."""
    text = f"{training_type or ''} {title or ''}".casefold()
    if 'işe başlama' in text or 'ise baslama' in text:
        return 2
    if 'bilgi yenileme' in text or 'bilgi tazeleme' in text:
        return {'Az Tehlikeli': 2, 'Tehlikeli': 3, 'Çok Tehlikeli': 4}.get(hazard_class, 2)
    if 'tekrar' in text or 'yenileme eğitimi' in text or 'yenileme egitimi' in text:
        return 8
    special = resolve_special_duration_hours(
        SimpleNamespace(training_type=training_type, title=title, notes=notes or "")
    )
    if special:
        return int(special)
    return int(HAZARD_HOURS.get(hazard_class, 8))


class TrainingCreate(BaseModel):
    company_id: int
    branch_id: int | None = None
    title: str = Field(min_length=3, max_length=220)
    training_type: str = Field(default="Temel İSG Eğitimi", max_length=80)
    delivery_method: str = Field(default="Yüz yüze", max_length=40)
    location: str | None = Field(default=None, max_length=220)
    start_date: date
    end_date: date
    hazard_class: str
    sector: str = Field(min_length=4, max_length=140)
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
        from app.core.input_rules import (
            assert_date_order,
            assert_event_date,
            assert_meaningful_text,
            assert_person_name,
        )

        self.start_date = assert_event_date(self.start_date, label="Başlangıç tarihi", allow_future_days=365)
        self.end_date = assert_event_date(self.end_date, label="Bitiş tarihi", allow_future_days=730)
        assert_date_order(
            self.start_date,
            self.end_date,
            earlier_label="Başlangıç tarihi",
            later_label="Bitiş tarihi",
        )
        if self.end_date < self.start_date:
            raise ValueError("Bitiş tarihi başlangıç tarihinden önce olamaz.")
        self.title = assert_meaningful_text(self.title, label="Eğitim başlığı", min_len=3, required=True)
        self.location = assert_meaningful_text(self.location, label="Eğitim yeri", min_len=2, required=False)
        self.instructor_name = assert_person_name(self.instructor_name, label="Eğitmen", required=True)
        self.workplace_physician = assert_person_name(self.workplace_physician, label="İşyeri hekimi")
        self.employer_representative = assert_person_name(
            self.employer_representative, label="İşveren / vekili"
        )
        self.notes = assert_meaningful_text(self.notes, label="Notlar", min_len=3, required=False)

        special_key = resolve_special_profile_key(
            SimpleNamespace(
                training_type=self.training_type,
                title=self.title,
                notes=self.notes or "",
            )
        )
        if special_key:
            # Özel profiller temel eğitimden bağımsızdır; kullanıcıdan ayrıca NACE
            # seçmesini istemeyiz. Belge içeriğinde sektör basılmaz. Veri modelinin
            # geriye dönük zorunlu alanı için katalogdan güvenli, doğrulanabilir bir
            # teknik varsayılan kullanılır; temel eğitimlerde NACE yine zorunludur.
            try:
                classification = resolve_exact_nace(self.sector)
            except ValueError:
                fallback = next(
                    (str(row.get("code") or "") for row in sectors_list_for_api() if str(row.get("code") or "").startswith("nace_")),
                    "",
                )
                if not fallback:
                    raise ValueError("Özel eğitim için teknik NACE varsayılanı bulunamadı.")
                classification = resolve_exact_nace(fallback)
            self.sector = str(classification.catalog_key)
            self.hazard_class = str(classification.hazard_class)
            if not self.participant_ids:
                raise ValueError("Özel eğitim kaydı için en az bir gerçek katılımcı seçilmelidir.")
            qualification = str(self.instructor_qualification or "").strip().casefold()
            if not qualification:
                raise ValueError("Özel eğitim için doğrulanmış eğitici unvanı / yeterliliği zorunludur.")
            allowed_labels = [
                str(meta.get("label") or "").casefold()
                for meta in SPECIAL_INSTRUCTOR_ROLES.values()
                if special_key in (meta.get("profiles") or [])
            ]
            if allowed_labels and not any(label and label in qualification for label in allowed_labels):
                raise ValueError("Seçilen özel eğitim profili için yetkili eğitici yeterliliği doğrulanamadı.")
            required_method = str(SPECIAL_TRAINING_PROFILES.get(special_key, {}).get("training_method") or "").casefold()
            if required_method and "yüz yüze" in required_method and "yüz yüze" not in str(self.delivery_method or "").casefold():
                raise ValueError("Bu özel eğitim profili yüz yüze ve uygulamalı yürütülmelidir.")
        else:
            # Temel eğitimlerde tam NACE kimliği zorunludur.
            classification = resolve_exact_nace(self.sector)
            self.sector = str(classification.catalog_key)
            self.hazard_class = str(classification.hazard_class)

        policy_text = f"{self.training_type or ''} {self.title or ''}".casefold()
        is_record_only = (
            'işe başlama' in policy_text
            or 'ise baslama' in policy_text
            or 'bilgi yenileme' in policy_text
            or 'bilgi tazeleme' in policy_text
        )
        if is_record_only:
            self.evaluation_method = 'Katılım yeterlidir'
            self.passing_score = None
        else:
            evaluation_text = str(self.evaluation_method or '').casefold()
            if not any(token in evaluation_text for token in ('sınav', 'sinav', 'yazılı', 'yazili')):
                raise ValueError(
                    'Bu eğitim türünde değerlendirme yöntemi Sınav veya Yazılı değerlendirme olmalıdır.'
                )
            if self.passing_score is None:
                self.passing_score = 60

        hours = resolve_training_hours(
            training_type=self.training_type,
            title=self.title,
            notes=self.notes,
            hazard_class=self.hazard_class,
        )
        calendar_days = (self.end_date - self.start_date).days + 1
        min_days = max(1, ceil(hours / MAX_TRAINING_HOURS_PER_DAY))
        if calendar_days < min_days:
            raise ValueError(
                f"{hours} saatlik eğitim en az {min_days} güne yayılmalıdır "
                f"(günde en fazla {MAX_TRAINING_HOURS_PER_DAY} ders saati). "
                f"Başlangıç–bitiş aralığını genişletin."
            )
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
    # Gönderilirse katılımcı listesinin tamamını değiştirir (PDF'ler bu listeyi basar).
    participant_ids: list[int] | None = None


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
    end_date: date | None = None
    hazard_class: str | None = None
    duration_hours: int | None = None
    instructor_name: str | None = None
    workplace_physician: str | None = None
    employer_representative: str | None = None
    participant_count: int = 0
    participants: list[dict] | None = None
    message: str | None = None
