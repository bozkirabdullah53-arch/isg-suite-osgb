"""0.9.134 — Acil durum ekipleri yardımcı mantığı.

Uyarılar bilinçli olarak yumuşak dille yazılır ("... önerilir",
"... olabilir"). Kesin hukuki iddia / mevzuat hükmü ifadesi kullanılmaz;
amaç İSG uzmanına hatırlatma / kontrol listesi sunmaktır.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    EmergencyTeam,
    EmergencyTeamAssignment,
    EmergencyTeamTraining,
    EmergencyTeamType,
)
from app.schemas.emergency_teams import DEFAULT_TEAM_TYPES

CERT_WARN_DAYS = 30


# --------------------------------------------------------------------------- #
# Seed defaults
# --------------------------------------------------------------------------- #
def ensure_system_team_types(db: Session) -> list[EmergencyTeamType]:
    """6 sistem varsayılan ekip türünün (company_id NULL) varlığını sağlar."""
    existing = {
        t.code: t
        for t in db.scalars(
            select(EmergencyTeamType).where(EmergencyTeamType.company_id.is_(None))
        ).all()
    }
    created = False
    for code, name in DEFAULT_TEAM_TYPES:
        if code not in existing:
            row = EmergencyTeamType(
                company_id=None,
                code=code,
                name=name,
                is_system=True,
                min_members=2,
                is_active=True,
            )
            db.add(row)
            existing[code] = row
            created = True
    if created:
        db.commit()
    return list(
        db.scalars(
            select(EmergencyTeamType)
            .where(EmergencyTeamType.company_id.is_(None))
            .order_by(EmergencyTeamType.id)
        ).all()
    )


def ensure_default_teams(db: Session, company_id: int, user_id: int) -> list[EmergencyTeam]:
    """Firma için hiç ekip yoksa 6 varsayılan ekibi otomatik oluşturur."""
    count = db.scalar(
        select(func.count())
        .select_from(EmergencyTeam)
        .where(EmergencyTeam.company_id == company_id, EmergencyTeam.is_active.is_(True))
    ) or 0
    if count > 0:
        return []
    types = ensure_system_team_types(db)
    type_by_code = {t.code: t for t in types}
    created: list[EmergencyTeam] = []
    for code, name in DEFAULT_TEAM_TYPES:
        t = type_by_code.get(code)
        if not t:
            continue
        team = EmergencyTeam(
            company_id=company_id,
            type_id=t.id,
            name=name,
            min_members=t.min_members or 2,
            created_by_id=user_id,
        )
        db.add(team)
        created.append(team)
    if created:
        db.commit()
        for team in created:
            db.refresh(team)
    return created


# --------------------------------------------------------------------------- #
# Sertifika / eğitim durumu
# --------------------------------------------------------------------------- #
def latest_valid_until(trainings: list[EmergencyTeamTraining]) -> date | None:
    """Eğitimler içinden en geç geçerlilik tarihini döner."""
    dates: list[date] = []
    for t in trainings or []:
        if t.valid_until:
            dates.append(t.valid_until)
        if getattr(t, "first_aid_end", None):
            dates.append(t.first_aid_end)
    return max(dates) if dates else None


def cert_status(valid_until: date | None, today: date | None = None) -> str:
    """green: geçerli · yellow: 30 gün içinde · red: süresi geçmiş · grey: kayıt yok."""
    if not valid_until:
        return "grey"
    today = today or date.today()
    if valid_until < today:
        return "red"
    if valid_until <= today + timedelta(days=CERT_WARN_DAYS):
        return "yellow"
    return "green"


def cert_status_from_trainings(
    trainings: list[EmergencyTeamTraining], today: date | None = None
) -> tuple[str, date | None]:
    vu = latest_valid_until(trainings)
    return cert_status(vu, today), vu


# --------------------------------------------------------------------------- #
# Ekip durumu ve uyarılar (yumuşak dil)
# --------------------------------------------------------------------------- #
def team_status(active_members: int, min_members: int) -> dict:
    """Tam / Eksik / Kritik ekip durumu."""
    minimum = max(int(min_members or 0), 0)
    if minimum <= 0:
        minimum = 2
    if active_members == 0:
        return {"code": "kritik", "label": "Kritik", "tone": "danger"}
    if active_members >= minimum:
        return {"code": "tam", "label": "Tam", "tone": "ok"}
    if active_members <= max(1, minimum // 2):
        return {"code": "kritik", "label": "Kritik", "tone": "danger"}
    return {"code": "eksik", "label": "Eksik", "tone": "warn"}


def team_warnings(
    *,
    team: EmergencyTeam,
    active_members: int,
    asil_members: int,
    has_leader: bool,
    cert_counts: dict[str, int],
) -> list[str]:
    """Ekip düzeyinde yumuşak dilli hatırlatmalar."""
    warnings: list[str] = []
    minimum = max(int(team.min_members or 0), 0) or 2
    if active_members == 0:
        warnings.append("Bu ekibe henüz üye atanmamış — kontrol edilmesi önerilir.")
    elif asil_members < minimum:
        warnings.append(
            f"Asıl üye sayısı ({asil_members}) önerilen minimumun ({minimum}) "
            "altında olabilir — kontrol edilmesi önerilir."
        )
    if active_members > 0 and not has_leader:
        warnings.append("Ekip sorumlusu (lider) belirlenmemiş görünüyor — atanması önerilir.")
    red = cert_counts.get("red", 0)
    yellow = cert_counts.get("yellow", 0)
    grey = cert_counts.get("grey", 0)
    if red:
        warnings.append(
            f"{red} üyenin eğitim/sertifika geçerliliği dolmuş olabilir — güncelleme önerilir."
        )
    if yellow:
        warnings.append(
            f"{yellow} üyenin belgesi 30 gün içinde sona erebilir — yenileme planlanması önerilir."
        )
    if grey and active_members > 0:
        warnings.append(
            f"{grey} üye için eğitim/sertifika kaydı bulunmuyor — eklenmesi önerilir."
        )
    return warnings


def assignment_warnings(
    *,
    cert_state: str,
    active_team_count: int,
) -> list[str]:
    """Üye düzeyinde hatırlatmalar (iş yükü, belge)."""
    warnings: list[str] = []
    if cert_state == "red":
        warnings.append("Eğitim/sertifika geçerliliği dolmuş olabilir — güncelleme önerilir.")
    elif cert_state == "yellow":
        warnings.append("Belge 30 gün içinde sona erebilir — yenileme önerilir.")
    elif cert_state == "grey":
        warnings.append("Eğitim/sertifika kaydı bulunmuyor — eklenmesi önerilir.")
    if active_team_count >= 3:
        warnings.append(
            f"Bu personel {active_team_count} aktif ekipte görünüyor — "
            "iş yükü dağılımı kontrol edilmesi önerilir."
        )
    return warnings


def employee_active_team_counts(db: Session, company_id: int) -> dict[int, int]:
    """company içindeki her personelin kaç aktif ekipte olduğunu döner."""
    rows = db.execute(
        select(
            EmergencyTeamAssignment.employee_id,
            func.count(func.distinct(EmergencyTeamAssignment.team_id)),
        )
        .where(
            EmergencyTeamAssignment.company_id == company_id,
            EmergencyTeamAssignment.is_active.is_(True),
        )
        .group_by(EmergencyTeamAssignment.employee_id)
    ).all()
    return {emp_id: int(cnt or 0) for emp_id, cnt in rows}
