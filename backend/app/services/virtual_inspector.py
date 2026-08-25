"""Sanal Müfettiş — mevzuat uyum denetimi ve olası ceza tahmini (0.9.245).

HSE Radar "Sanal Müfettiş" özelliğine benzer, ancak İSG Suite'in risk/sağlık/
eğitim/doküman verisine entegre çalışır. Ücretli AI API gerektirmez; kural
tabanlı mevzuat kontrolü + uyum skorlaması.

6331 sayılı Kanun ve alt yönetmeliklere dayalı kontrol maddeleri. Çıktı:
- uyum skoru (0-100)
- tespit edilen ihlaller (kritik/orta/düşük)
- olası idari para cezası aralığı (md.26/27 referans)
- önerilen düzeltici aksiyonlar
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

INSPECTOR_ENGINE = "rule-v1-6331"

# 6331 md.26/27 idari para cezası referans aralıkları (TL, 2024 güncel tahmini).
# Gerçek ceza, ihlalin niteliğine ve YİBYS'deki puana göre belirlenir; burada
# sadece bilgilendirme amaçlı tahmini aralıklar verilir.
_PENALTY_RANGES = {
    "kritik": (50_000, 600_000),      # işveren, ağır ihlal (md.26/27)
    "orta": (15_000, 100_000),
    "dusuk": (3_000, 25_000),
}


@dataclass
class InspectionFinding:
    code: str
    title: str
    severity: str  # kritik | orta | dusuk
    regulation_ref: str
    detail: str
    suggested_action: str


@dataclass
class InspectionReport:
    engine: str = INSPECTOR_ENGINE
    company_id: int | None = None
    inspection_date: str = ""
    compliance_score: int = 100  # 0-100 (100 = tam uyumlu)
    findings: list[InspectionFinding] = field(default_factory=list)
    penalty_estimate: dict[str, int] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "company_id": self.company_id,
            "inspection_date": self.inspection_date,
            "compliance_score": self.compliance_score,
            "findings": [
                {
                    "code": f.code,
                    "title": f.title,
                    "severity": f.severity,
                    "regulation_ref": f.regulation_ref,
                    "detail": f.detail,
                    "suggested_action": f.suggested_action,
                }
                for f in self.findings
            ],
            "penalty_estimate": self.penalty_estimate,
            "summary": self.summary,
        }


def _days_since(d: date | datetime | None) -> int | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    return (date.today() - d).days


def inspect_company(db, company_id: int) -> InspectionReport:
    """Bir işyerinin İSG mevzuat uyumunu denetler.

    db: SQLAlchemy session
    company_id: denetlenecek işyeri
    """
    from sqlalchemy import select

    from app.models.entities import (
        RiskAssessment,
        TrainingSession,
        HealthRecord,
        EmergencyPlan,
    )

    report = InspectionReport(
        engine=INSPECTOR_ENGINE,
        company_id=company_id,
        inspection_date=date.today().isoformat(),
    )

    findings: list[InspectionFinding] = []

    # --- 1. Risk değerlendirme (6331 md.10) ---
    risk = db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.company_id == company_id)
        .order_by(RiskAssessment.id.desc())
    )
    if risk is None:
        findings.append(InspectionFinding(
            code="RISK-001",
            title="Risk değerlendirmesi yapılmamış",
            severity="kritik",
            regulation_ref="6331 md.10",
            detail="İşyerinde risk değerlendirmesi kaydı bulunamadı.",
            suggested_action="Acil olarak risk değerlendirmesi yapın ve kayıt altına alın.",
        ))
    else:
        last_risk = _days_since(getattr(risk, "created_at", None))
        if last_risk is not None and last_risk > 365:
            findings.append(InspectionFinding(
                code="RISK-002",
                title="Risk değerlendirmesi güncel değil",
                severity="orta",
                regulation_ref="6331 md.10.4",
                detail=f"Son risk değerlendirmesi {last_risk} gün önce yapılmış (1 yılı aşmış).",
                suggested_action="Risk değerlendirmesini yenileyin; makine/değişiklik varsa güncelleyin.",
            ))

    # --- 2. Eğitim (6331 md.17) ---
    trainings = db.scalars(
        select(TrainingSession)
        .where(TrainingSession.company_id == company_id)
        .order_by(TrainingSession.id.desc())
        .limit(1)
    ).all()
    if not trainings:
        findings.append(InspectionFinding(
            code="EDU-001",
            title="İSG eğitimi kaydı yok",
            severity="kritik",
            regulation_ref="6331 md.17",
            detail="Çalışanlara yönelik İSG eğitimi kaydı bulunamadı.",
            suggested_action="İşe başlama ve periyodik İSG eğitimleri planlayın ve kaydedin.",
        ))

    # --- 3. Sağlık gözetimi (6331 md.15) ---
    health = db.scalar(
        select(HealthRecord)
        .where(HealthRecord.company_id == company_id)
        .order_by(HealthRecord.id.desc())
    )
    if health is None:
        findings.append(InspectionFinding(
            code="HEA-001",
            title="Periyodik sağlık muayenesi kaydı yok",
            severity="kritik",
            regulation_ref="6331 md.15",
            detail="Çalışan periyodik sağlık muayenesi kaydı bulunamadı.",
            suggested_action="Çalışanların periyodik sağlık muayenelerini planlayın ve kaydedin.",
        ))

    # --- 4. Acil durum planı (6331 md.11) ---
    emergency = db.scalar(
        select(EmergencyPlan)
        .where(EmergencyPlan.company_id == company_id)
        .order_by(EmergencyPlan.id.desc())
    )
    if emergency is None:
        findings.append(InspectionFinding(
            code="EME-001",
            title="Acil durum planı kaydı yok",
            severity="orta",
            regulation_ref="6331 md.11",
            detail="Acil durum planı ve tahliye prosedürü kaydı bulunamadı.",
            suggested_action="Acil durum planı hazırlayın, tatbikat yapın ve kaydedin.",
        ))

    # --- Uyum skoru hesaplama ---
    kritik = sum(1 for f in findings if f.severity == "kritik")
    orta = sum(1 for f in findings if f.severity == "orta")
    dusuk = sum(1 for f in findings if f.severity == "dusuk")
    total_weight = kritik * 25 + orta * 10 + dusuk * 3
    score = max(0, 100 - total_weight)
    report.compliance_score = score

    # --- Ceza tahmini ---
    low, high = 0, 0
    for f in findings:
        pl, ph = _PENALTY_RANGES.get(f.severity, (0, 0))
        low += pl
        high += ph
    report.penalty_estimate = {
        "min_tl": low,
        "max_tl": high,
        "note": "Tahmini aralık; gerçek ceza YİBYS puanına ve ihlal niteliğine göre değişir.",
    }

    # --- Özet ---
    if score >= 80:
        verdict = "İSG mevzuatına büyük ölçüde uyumlu."
    elif score >= 60:
        verdict = "Uyumda eksiklikler var; düzeltici aksiyon gerekiyor."
    elif score >= 40:
        verdict = "Ciddi uyum eksiklikleri mevcut; acil düzeltme gerekli."
    else:
        verdict = "Kritik ihlaller mevcut; derhal müdahale edilmeli."
    report.findings = findings
    report.summary = (
        f"{verdict} Uyum skoru: {score}/100. "
        f"{kritik} kritik, {orta} orta, {dusuk} düşük bulgu. "
        f"Tahmini ceza riski: {low:,}–{high:,} TL."
    )
    return report
