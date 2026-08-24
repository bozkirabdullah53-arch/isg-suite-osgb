"""Isolated models for the Basic Occupational Health and Safety remote course.

The existing training, examination, certificate and employee tables are kept
unchanged.  These tables are an additive content/attendance layer and carry
their own company scope so that PostgreSQL RLS and the application access
checks can be applied independently.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


REMOTE_TRAINING_TYPE = "Basic Occupational Health and Safety Training"
REMOTE_CERTIFICATE_TRAINING_TYPE = "Uzaktan Eğitim"

PROGRAM_STATUSES = ("draft", "ready_for_review", "published", "unpublished", "archived")
VIDEO_STATUSES = (
    "draft",
    "uploading",
    "processing",
    "processing_failed",
    "ready_for_review",
    "published",
    "unpublished",
    "archived",
)
ASSIGNMENT_STATUSES = ("not_started", "in_progress", "completed", "failed", "expired", "revoked")
PROGRESS_STATUSES = ("not_started", "in_progress", "completed")
ASSET_TYPES = ("thumbnail", "subtitle", "supporting_document")

# The remote Basic OHS catalog is intentionally explicit.  Keeping the
# identifiers stable lets a company select a sector once and keeps the same
# scope attached to employee assignments and exam questions.
REMOTE_SECTOR_CATALOG = (
    ("common", "Temel Ortak İSG", "Tüm sektörlerde ortak temel iş sağlığı ve güvenliği içeriği."),
    ("construction", "İnşaat", "İnşaat işleri ve saha riskleriyle ilgili dersler."),
    (
        "battery",
        "Akü, Pil ve Enerji Depolama",
        "Akü, pil, batarya ve enerji depolama üretimi, servisi ve güvenliğiyle ilgili dersler.",
    ),
    ("foundry", "Döküm", "Dökümhane, ergitme ve sıcak metal çalışma riskleriyle ilgili dersler."),
    ("metal", "Metal", "Metal işleme, kesme, kaynak ve ilgili çalışma riskleriyle ilgili dersler."),
    ("logistics", "Lojistik", "Depolama, yükleme, taşıma ve lojistik çalışma riskleriyle ilgili dersler."),
    ("food", "Gıda", "Gıda üretimi, işleme, hijyen ve tesis güvenliğiyle ilgili dersler."),
    ("chemical", "Kimyasal/Boya", "Kimyasal ve boya faaliyetlerinde maruziyet, depolama ve proses güvenliği dersleri."),
    ("mining", "Maden/Agrega", "Maden, taş ocağı ve agrega faaliyetlerindeki saha ve ekipman riskleriyle ilgili dersler."),
    ("road", "Yol/Asfalt/Altyapı", "Yol, asfalt, altyapı ve saha trafik güvenliğiyle ilgili dersler."),
    ("office", "Ofis/Genel İşyerleri", "Ofis ve genel işyerlerinde ergonomi, acil durum ve çalışma güvenliği dersleri."),
    (
        "health",
        "Hastaneler ve Sağlık Hizmetleri",
        "Hastane ve insan sağlığı hizmetlerinde biyolojik, kimyasal, radyasyon, ergonomi ve acil durum risklerine yönelik dersler.",
    ),
    (
        "education_universities",
        "Eğitim Kurumları ve Üniversiteler",
        "Okul, kampüs, laboratuvar, atölye ve üniversite yerleşkelerindeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "public_municipalities",
        "Kamu Kurumları ve Belediyeler",
        "Kamu hizmet binaları, belediye birimleri, saha ekipleri ve yerel hizmetlerdeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "agriculture_livestock_forestry",
        "Tarım, Hayvancılık ve Ormancılık",
        "Tarım, hayvancılık, seracılık, orman işleri ve tarımsal makine kullanımındaki risklere yönelik dersler.",
    ),
    (
        "hospitality_tourism_restaurants",
        "Konaklama, Turizm ve Restoran",
        "Otel, konaklama, turizm tesisi, mutfak ve restoran faaliyetlerindeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "trade_retail_markets",
        "Ticaret, Perakende ve Marketler",
        "Mağaza, market, perakende, ticaret ve müşteri hizmetleri faaliyetlerindeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "energy_electricity_gas",
        "Enerji, Elektrik ve Doğalgaz",
        "Elektrik üretimi ve dağıtımı, enerji tesisleri ve doğalgaz faaliyetlerindeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "water_sewerage_waste",
        "Su, Kanalizasyon ve Atık Yönetimi",
        "Su temini, kanalizasyon, arıtma, atık toplama ve atık yönetimi faaliyetlerindeki risklere yönelik dersler.",
    ),
    (
        "textile_clothing_leather",
        "Tekstil, Giyim ve Deri",
        "Tekstil, hazır giyim, konfeksiyon ve deri üretimindeki makine, kimyasal, ergonomi ve yangın risklerine yönelik dersler.",
    ),
    (
        "plastic_rubber",
        "Plastik ve Kauçuk",
        "Plastik ve kauçuk üretimindeki proses, makine, kimyasal, sıcak yüzey ve yangın risklerine yönelik dersler.",
    ),
    (
        "wood_furniture",
        "Ağaç ve Mobilya",
        "Ağaç işleme, mobilya, marangozluk, toz, kesim ve makine kullanımındaki risklere yönelik dersler.",
    ),
    (
        "ceramic_glass_marble",
        "Seramik, Cam ve Mermer",
        "Seramik, cam, mermer ve taş işleme faaliyetlerindeki kesilme, toz, sıcak yüzey, kaldırma ve makine risklerine yönelik dersler.",
    ),
    (
        "building_cleaning_security",
        "Bina, Temizlik ve Güvenlik Hizmetleri",
        "Bina yönetimi, temizlik, bakım, özel güvenlik ve saha hizmetlerindeki iş sağlığı ve güvenliği risklerine yönelik dersler.",
    ),
    (
        "automotive_vehicle_services",
        "Otomotiv ve Araç Servisleri",
        "Araç bakım, onarım, servis, lastik, kaporta, boya ve otomotiv saha faaliyetlerindeki risklere yönelik dersler.",
    ),
    ("working_at_height", "Yüksekte Çalışma", "Yüksekte çalışma, düşmeyi önleme, ekipman kullanımı ve kurtarma planlaması dersleri."),
)
REMOTE_SECTOR_CODES = frozenset(item[0] for item in REMOTE_SECTOR_CATALOG)
REMOTE_SECTOR_LABELS = {item[0]: item[1] for item in REMOTE_SECTOR_CATALOG}

# A central package is a reusable curriculum, but its copied sections still
# need a stable sector identity inside the company-scoped snapshot.  Without
# this mapping every catalog section was copied as ``common`` and a selected
# sector displayed zero lessons/videos even though the package was complete.
# Unknown/future packages intentionally fall back to common so older or custom
# catalog entries keep their existing behavior until they receive an explicit
# sector mapping.
REMOTE_CATALOG_PACKAGE_SECTOR_CODES = {
    "common-basic-ohs": "common",
    "construction-ohs": "construction",
    "metal-machine-ohs": "metal",
    "battery-production-ohs": "battery",
    "food-production-ohs": "food",
    "logistics-warehouse-transport-ohs": "logistics",
    "chemical-paint-production-ohs": "chemical",
    "open-mine-quarry-aggregate-ohs": "mining",
    "road-asphalt-infrastructure-ohs": "road",
    "office-general-ohs": "office",
    "health-services-ohs": "health",
    "working-at-height-ohs": "working_at_height",
}


def catalog_package_sector_code(package_code: str | None) -> str:
    normalized = str(package_code or "").strip().lower()
    return REMOTE_CATALOG_PACKAGE_SECTOR_CODES.get(normalized, "common")


# Merkezi katalog kayıtları firma seçilmeden hazırlanır.  ``sections`` yalnızca
# hazır müfredatı olan paketlerde başlangıç bölümlerini oluşturur; boş bırakılan
# paketler yönetici ekranından sonradan bölüm eklenmesine hazırdır. Paket sırası
# kullanıcıya gösterilen iş akışıdır; yeni bir paket eklenirse listenin sonuna
# eklenir.
REMOTE_CATALOG_PACKAGE_SPECS = (
    {
        "code": "common-basic-ohs",
        "title": "Ortak Temel İSG",
        "description": "Tüm sektörlerde ortak kullanılacak temel iş sağlığı ve güvenliği eğitimi.",
        "sections": (
            ("D01", "Mevzuat ve çalışan hakları"),
            ("D02", "İş kazaları ve meslek hastalıkları"),
            ("D03", "Acil durumlar ve tahliye"),
            ("D04", "Sağlık, hijyen, ergonomi ve güvenlik kültürü"),
            ("D05", "Teknik güvenlik, KKD ve iş ekipmanları"),
            ("D06", "Uzaktan eğitim akışı ve değerlendirme"),
        ),
    },
    {
        "code": "construction-ohs",
        "title": "İnşaat",
        "description": "Şantiye, yapı işleri ve inşaat sahasına özgü iş sağlığı ve güvenliği dersleri.",
        "sections": (
            ("İNŞ-01", "Şantiye organizasyonu"),
            ("İNŞ-02", "Kazı, göçük ve altyapı"),
            ("İNŞ-03", "Yüksekte çalışma"),
            ("İNŞ-04", "Kalıp, donatı ve betonarme"),
            ("İNŞ-05", "İş makineleri ve kaldırma"),
            ("İNŞ-06", "Şantiye elektriği"),
            ("İNŞ-07", "Vinçler ve askıda yükler"),
            ("İNŞ-08", "İskeleler ve çalışma platformları"),
            ("İNŞ-09", "Sıcak işler ve yangın"),
            ("İNŞ-10", "Kimyasallar ve tozlar"),
            ("İNŞ-11", "Kapalı alanlar ve kurtarma"),
            ("İNŞ-12", "Şantiye düzeni ve acil durum"),
        ),
    },
    {
        "code": "metal-machine-ohs",
        "title": "Metal-Makine",
        "description": "Metal işleme, makine imalatı, kaynak, kesim ve otomasyon risklerine yönelik dersler.",
        "sections": (
            ("MET-01", "Genel metal ve makine güvenliği"),
            ("MET-02", "Makine ve ekipman güvenliği"),
            ("MET-03", "Pres, kesim ve sıkıştırma"),
            ("MET-04", "Kaynak, taşlama ve sıcak işler"),
            ("MET-05", "CNC ve otomasyon"),
            ("MET-06", "Kimyasallar ve yüzey işlemleri"),
            ("MET-07", "Kaldırma, taşıma ve forklift"),
            ("MET-08", "KKD kullanımı ve bakımı"),
            ("MET-09", "Acil durum, yangın ve tahliye"),
            ("MET-10", "Ramak kala, kaza bildirimi ve ilk yardım farkındalığı"),
        ),
    },
    {
        "code": "battery-production-ohs",
        "title": "Akü-Batarya",
        "description": "Akü ve batarya üretiminde kimyasal, elektriksel ve proses güvenliği dersleri.",
        "sections": (
            ("AKÜ-01", "Temel İSG ve hidrojen riski"),
            ("AKÜ-02", "Kurşun maruziyeti ve hijyen"),
            ("AKÜ-03", "Sülfürik asit ve dökülmeler"),
            ("AKÜ-04", "Hidrojen ve patlama önleme"),
            ("AKÜ-05", "Makineler, taşıma ve ergonomi"),
            ("AKÜ-06", "Şarj, elektrik ve enerji güvenliği"),
            ("AKÜ-07", "Kimyasal depolama ve atıklar"),
            ("AKÜ-08", "Havalandırma ve maruziyet ölçümleri"),
            ("AKÜ-09", "Acil durum ve kimyasal müdahale"),
            ("AKÜ-10", "Akü üretiminde kaza önleme ve ilk yardım farkındalığı"),
        ),
    },
    {
        "code": "food-production-ohs",
        "title": "Gıda",
        "description": "Gıda üretim tesislerinde makine, hijyen, kimyasal ve acil durum güvenliği.",
        "sections": (),
    },
    {
        "code": "logistics-warehouse-transport-ohs",
        "title": "Lojistik",
        "description": "Depo, sevkiyat, yükleme-boşaltma ve taşıma faaliyetlerine özel paket.",
        "sections": (),
    },
    {
        "code": "chemical-paint-production-ohs",
        "title": "Kimyasal/Boya",
        "description": "Kimyasal ve boya üretiminde maruziyet, depolama, proses ve yangın güvenliği.",
        "sections": (),
    },
    {
        "code": "open-mine-quarry-aggregate-ohs",
        "title": "Maden/Agrega",
        "description": "Açık maden, taş ocağı ve agrega faaliyetlerine özel paket.",
        "sections": (),
    },
    {
        "code": "road-asphalt-infrastructure-ohs",
        "title": "Yol/Asfalt/Altyapı",
        "description": "Yol, asfalt ve altyapı çalışmalarında saha, trafik ve ekipman güvenliği paketi.",
        "sections": (),
    },
    {
        "code": "office-general-ohs",
        "title": "Ofis/Genel İşyerleri",
        "description": "Ofisler ve genel işyerleri için ergonomi, acil durum ve çalışma güvenliği paketi.",
        "sections": (),
    },
    {
        "code": "health-services-ohs",
        "title": "Hastaneler ve Sağlık Hizmetleri",
        "description": "Hastane, klinik ve sağlık kuruluşlarında biyolojik, kimyasal, radyasyon, ergonomi, tıbbi ekipman ve acil durum güvenliği.",
        "sections": (
            ("SAG-01", "Hastane İSG organizasyonu ve işveren sorumluluğu"),
            ("SAG-02", "Biyolojik riskler ve enfeksiyonlardan korunma"),
            ("SAG-03", "Kesici-delici aletler ve kan/vücut sıvısı maruziyeti"),
            ("SAG-04", "Kimyasal maddeler, dezenfeksiyon ve sterilizasyon"),
            ("SAG-05", "Sitotoksik ilaçlar ve laboratuvar güvenliği"),
            ("SAG-06", "İyonlaştırıcı radyasyon ve görüntüleme birimleri"),
            ("SAG-07", "Hasta taşıma, ergonomi ve kas-iskelet riskleri"),
            ("SAG-08", "Şiddet, vardiya ve psikososyal riskler"),
            ("SAG-09", "Tıbbi atıklar, gaz tüpleri ve ekipman güvenliği"),
            ("SAG-10", "Hastane yangın, tahliye ve acil durum planı"),
        ),
    },
    {
        "code": "working-at-height-ohs",
        "title": "Yüksekte Çalışma İSG Paketi",
        "description": "Yüksekte çalışma, düşmeyi önleme, ekipman kullanımı ve kurtarma planlamasına yönelik paket.",
        "sections": (
            ("YÜK-01", "Yüksekte çalışma esasları ve mevzuat"),
            ("YÜK-02", "Tehlike tanımlama ve işe özel risk değerlendirmesi"),
            ("YÜK-03", "Çalışmaktan kaçınma ve toplu korunma tedbirleri"),
            ("YÜK-04", "İskeleler, platformlar ve güvenli geçişler"),
            ("YÜK-05", "Merdivenler ve erişim sistemleri"),
            ("YÜK-06", "Kişisel düşüş durdurma sistemleri ve KKD"),
            ("YÜK-07", "Ankraj, yaşam hattı ve bağlantı elemanları"),
            ("YÜK-08", "Çatı, kırılgan yüzeyler ve malzeme düşmesi"),
            ("YÜK-09", "Hava şartları, kaldırma ekipmanları ve çevresel riskler"),
            ("YÜK-10", "Kurtarma planı, acil durum ve askıda kalma"),
        ),
    },
)


class RemoteTrainingProgram(Base):
    __tablename__ = "remote_training_programs"
    __table_args__ = (
        Index("ix_remote_training_programs_company_status", "company_id", "status"),
        Index("ix_remote_training_programs_branch", "branch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Optional immutable source link.  Existing company programs remain NULL
    # and therefore keep the legacy behavior.
    source_catalog_package_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_catalog_packages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_catalog_code: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    source_catalog_revision_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(
        String(220), default="Basic Occupational Health and Safety Training"
    )
    training_type: Mapped[str] = mapped_column(
        String(120), default=REMOTE_TRAINING_TYPE, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructor_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    instructor_qualification: Mapped[str | None] = mapped_column(String(220), nullable=True)
    total_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_threshold_percent: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    attempt_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    requires_final_exam: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # ``legacy`` is deliberately the migration default.  Only catalog
    # materialization creates ``strict`` programs.
    policy_mode: Mapped[str] = mapped_column(String(24), default="legacy", nullable=False)
    sequence_enforced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exam_gate_enforced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingProgramSector(Base):
    """Sector scope selected for a company training program."""

    __tablename__ = "remote_training_program_sectors"
    __table_args__ = (
        UniqueConstraint("program_id", "sector_code", name="uq_remote_program_sector"),
        Index("ix_remote_program_sectors_company", "company_id"),
        Index("ix_remote_program_sectors_program_enabled", "program_id", "is_enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sector_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingSection(Base):
    __tablename__ = "remote_training_sections"
    __table_args__ = (
        UniqueConstraint("program_id", "order_index", name="uq_remote_section_program_order"),
        Index("ix_remote_training_sections_program", "program_id"),
        Index("ix_remote_training_sections_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sector_code: Mapped[str] = mapped_column(
        String(64), default="common", server_default="common", nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingVideo(Base):
    __tablename__ = "remote_training_videos"
    __table_args__ = (
        Index("ix_remote_training_videos_program_status", "program_id", "status"),
        Index("ix_remote_training_videos_section_order", "section_id", "order_index"),
        Index("ix_remote_training_videos_company", "company_id"),
        Index("ix_remote_training_videos_current", "program_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(80), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    processing_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingCatalogPackage(Base):
    """Firma atamasından bağımsız merkezi uzaktan eğitim paketi."""

    __tablename__ = "remote_training_catalog_packages"
    __table_args__ = (
        UniqueConstraint("osgb_id", "code", name="uq_remote_catalog_package_scope_code"),
        Index("ix_remote_catalog_packages_scope_status", "osgb_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(96), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_type: Mapped[str] = mapped_column(
        String(120), default=REMOTE_TRAINING_TYPE, nullable=False
    )
    total_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requires_final_exam: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    completion_threshold_percent: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    attempt_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    policy_mode: Mapped[str] = mapped_column(String(24), default="strict", nullable=False)
    sequence_enforced: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exam_gate_enforced: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingCatalogSection(Base):
    """Merkezi paketin firma seçilmeden video yüklenebilen bölümü."""

    __tablename__ = "remote_training_catalog_sections"
    __table_args__ = (
        UniqueConstraint("package_id", "code", name="uq_remote_catalog_section_package_code"),
        UniqueConstraint("package_id", "order_index", name="uq_remote_catalog_section_package_order"),
        Index("ix_remote_catalog_sections_package", "package_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingCatalogVideo(Base):
    """Merkezi pakete dosyadan yüklenen, firma bağımsız video."""

    __tablename__ = "remote_training_catalog_videos"
    __table_args__ = (
        Index("ix_remote_catalog_videos_package_status", "package_id", "status"),
        Index("ix_remote_catalog_videos_section_order", "section_id", "order_index"),
        Index("ix_remote_catalog_videos_current", "package_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_catalog_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_catalog_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_catalog_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(80), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    processing_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingAsset(Base):
    __tablename__ = "remote_training_assets"
    __table_args__ = (
        Index("ix_remote_training_assets_video_type", "video_id", "asset_type"),
        Index("ix_remote_training_assets_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingAssignment(Base):
    __tablename__ = "remote_training_assignments"
    __table_args__ = (
        UniqueConstraint("program_id", "employee_id", name="uq_remote_assignment_program_employee"),
        Index("ix_remote_training_assignments_company_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    workplace_name_snapshot: Mapped[str | None] = mapped_column(String(220), nullable=True)
    sgk_registration_number_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nace_code_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_description_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hazard_class_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    employee_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_started", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    assigned_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingAssignmentSector(Base):
    """Immutable sector-scope snapshot captured when an assignment is made."""

    __tablename__ = "remote_training_assignment_sectors"
    __table_args__ = (
        UniqueConstraint("assignment_id", "sector_code", name="uq_remote_assignment_sector"),
        Index("ix_remote_assignment_sectors_company", "company_id"),
        Index("ix_remote_assignment_sectors_assignment_employee", "assignment_id", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sector_code: Mapped[str] = mapped_column(String(64), nullable=False)
    sector_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingVideoProgress(Base):
    __tablename__ = "remote_training_video_progress"
    __table_args__ = (
        UniqueConstraint("assignment_id", "video_id", name="uq_remote_progress_assignment_video"),
        Index("ix_remote_progress_company_status", "company_id", "status"),
        Index("ix_remote_progress_employee", "employee_id"),
        Index("ix_remote_progress_program", "program_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    last_position_seconds: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    watched_duration_seconds: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    watched_percentage: Mapped[float] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    # Merged watched intervals, e.g. [[0, 12.4], [18, 32.1]].  It prevents a
    # worker from replaying the same five seconds after seeking backwards and
    # farming completion with repeated API calls.
    coverage_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="not_started", index=True)
    viewing_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingEvent(Base):
    __tablename__ = "remote_training_events"
    __table_args__ = (
        Index("ix_remote_training_events_company_created", "company_id", "created_at"),
        Index("ix_remote_training_events_assignment", "assignment_id"),
        Index("ix_remote_training_events_video", "video_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    position_seconds: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    watched_seconds: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingQuestion(Base):
    __tablename__ = "remote_training_questions"
    __table_args__ = (
        Index("ix_remote_training_questions_program", "program_id"),
        Index("ix_remote_training_questions_video", "video_id"),
        Index("ix_remote_training_questions_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sector_code: Mapped[str] = mapped_column(
        String(64), default="common", server_default="common", nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Catalog-derived programs receive ten approved, immutable final-exam
    # snapshots here.  Existing rows remain video/checkpoint questions.
    is_final_exam: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    # Eğitim öncesi ilk test soruları final sınavı ve video içi sorulardan ayrıdır.
    is_pre_assessment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingPreAssessmentAttempt(Base):
    """Immutable, one-time baseline result recorded before remote training."""

    __tablename__ = "remote_training_pre_assessment_attempts"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_remote_pre_assessment_assignment"),
        Index("ix_remote_pre_assessment_attempts_company", "company_id"),
        Index("ix_remote_pre_assessment_attempts_assignment", "assignment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RemoteTrainingCheckpointAnswer(Base):
    __tablename__ = "remote_training_checkpoint_answers"
    __table_args__ = (
        Index("ix_remote_checkpoint_answers_assignment", "assignment_id"),
        Index("ix_remote_checkpoint_answers_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingProgramQuestion(Base):
    __tablename__ = "remote_training_program_questions"
    __table_args__ = (
        UniqueConstraint("program_id", "question_id", name="uq_remote_program_question"),
        UniqueConstraint("program_id", "position", name="uq_remote_program_question_position"),
        Index("ix_remote_program_questions_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("training_questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sector_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingExamAttempt(Base):
    __tablename__ = "remote_training_exam_attempts"
    __table_args__ = (
        UniqueConstraint("assignment_id", "attempt_no", name="uq_remote_exam_assignment_attempt"),
        Index("ix_remote_exam_attempts_company_status", "company_id", "passed"),
        Index("ix_remote_exam_attempts_assignment", "assignment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    question_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RemoteTrainingCertificate(Base):
    __tablename__ = "remote_training_certificates"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_remote_certificate_assignment"),
        UniqueConstraint("certificate_number", name="uq_remote_certificate_number"),
        UniqueConstraint("verification_code", name="uq_remote_certificate_verification"),
        Index("ix_remote_certificates_company", "company_id"),
        Index("ix_remote_certificates_employee", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    company_name_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    workplace_name_snapshot: Mapped[str | None] = mapped_column(String(220), nullable=True)
    sgk_registration_number_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nace_code_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_description_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hazard_class_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    training_name: Mapped[str] = mapped_column(String(220), nullable=False)
    training_type: Mapped[str] = mapped_column(String(120), default=REMOTE_TRAINING_TYPE)
    training_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_date: Mapped[date] = mapped_column(Date, nullable=False)
    instructor_name_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    instructor_qualification_snapshot: Mapped[str | None] = mapped_column(String(220), nullable=True)
    workplace_physician_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    employer_representative_snapshot: Mapped[str | None] = mapped_column(String(160), nullable=True)
    examination_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(80), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingEmployeeAccess(Base):
    __tablename__ = "remote_training_employee_access"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_remote_employee_access_user"),
        UniqueConstraint("employee_id", name="uq_remote_employee_access_employee"),
        Index("ix_remote_employee_access_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingAuditLog(Base):
    __tablename__ = "remote_training_audit_logs"
    __table_args__ = (
        Index("ix_remote_training_audit_company_created", "company_id", "created_at"),
        Index("ix_remote_training_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
