"""Acil durum ekiplerinin çalışan sayısına bağlı asgarileri ve kontrol uyarıları.

Asgari kişi hesabında ilgili yönetmelik maddesi belirtilir; eğitim ve ekip
organizasyonu uyarıları uzman için kontrol listesi sunar.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    EmergencyTeam,
    EmergencyTeamAssignment,
    EmergencyTeamTraining,
    EmergencyTeamType,
)
from app.schemas.emergency_teams import DEFAULT_TEAM_TYPES
from app.services.capacity_engine import normalize_hazard
from app.services.emergency_plan_compliance import support_team_required_count, support_team_threshold
from app.services.first_aid_compliance import required_first_aiders

CERT_WARN_DAYS = 30

SUPPORT_TEAM_CODES = {"sondurme", "kurtarma", "koruma"}


def emergency_team_today() -> date:
    """Ekiplerin takvim günü; sunucunun saat diliminden bağımsız Türkiye tarihi."""
    return datetime.now(ZoneInfo("Europe/Istanbul")).date()


def team_minimum_requirement(
    type_code: str | None,
    employee_count: int,
    hazard_class: str | None,
    configured_minimum: int = 0,
) -> dict:
    """Çalışan sayısına bağlı asgariyi kayıtlı eski sabit hedeften ayrı hesaplar.

    İADY m.11/3-5 ve İlkyardım Yönetmeliği m.19 esas alınır. Bina kullanımı,
    ziyaretçiler ve vardiya düzeni için ayrıca acil durum planı değerlendirilir.
    """
    hazard_key = " ".join(str(hazard_class or "").split()).casefold().replace("\u0307", "")
    hazard = normalize_hazard(hazard_key)
    if type_code in {"tahliye", "haberlesme"}:
        return {
            "required_members": None,
            "minimum_source": "risk_assessment",
            "minimum_basis": "İşyerine özgü acil durum planı",
            "minimum_note": "Sabit bir yasal kişi oranı yoktur; sayı, risk değerlendirmesi ve acil durum planıyla belirlenir.",
        }
    if type_code not in SUPPORT_TEAM_CODES | {"ilk_yardim"}:
        return {
            "required_members": max(int(configured_minimum or 0), 0),
            "minimum_source": "workplace",
            "minimum_basis": "İşyerinin belirlediği hedef",
            "minimum_note": "Bu sayı işyerinin tanımladığı hedeftir.",
        }

    first_aid = type_code == "ilk_yardim"
    basis = "İlkyardım Yönetmeliği m.19; İADY m.11/5" if first_aid else "İADY m.11/3"
    minimum = None
    if employee_count > 0:
        minimum = (
            required_first_aiders(employee_count, hazard)
            if first_aid else support_team_required_count(employee_count, hazard)
        )
    if minimum is None:
        return {
            "required_members": None,
            "minimum_source": "incomplete",
            "minimum_basis": basis,
            "minimum_note": (
                "Hesap için bu işyerinin aktif çalışan kayıtları gerekli."
                if employee_count <= 0 else "Hesap için işyerinin tehlike sınıfı gerekli."
            ),
        }
    if not first_aid and employee_count < 10:
        basis = "İADY m.11/4"
        note = "10’dan az çalışan: aynı eğitimli destek elemanı söndürme, kurtarma ve koruma görevlerinin tamamını üstlenebilir."
    else:
        per = {"Az Tehlikeli": 20, "Tehlikeli": 15, "Çok Tehlikeli": 10}.get(hazard) if first_aid else support_team_threshold(hazard)
        note = f"{employee_count} çalışan; her {per} çalışana kadar 1 kişi → {minimum} kişi (yukarı yuvarlanır)."
        if first_aid:
            note += " İlkyardımcı belgesi geçerli olmalıdır."
    return {
        "required_members": minimum,
        "minimum_source": "legal",
        "minimum_basis": basis,
        "minimum_note": note,
    }


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
    """Firma için 6 varsayılan ekip kartının her zaman aktif kalmasını sağlar.

    Ekip kartı geçmiş bir sürümde yanlışlıkla pasife alınmışsa aynı kaydı ve ona
    bağlı üyeleri yeniden etkinleştirir. Böylece ekip bölümü silinmez; kullanıcı
    yalnızca ekip içindeki üye/görevlendirmeleri kaldırabilir.
    """
    types = ensure_system_team_types(db)
    type_by_code = {t.code: t for t in types}
    default_type_ids = [t.id for code, _ in DEFAULT_TEAM_TYPES if (t := type_by_code.get(code))]

    existing_teams = list(
        db.scalars(
            select(EmergencyTeam).where(
                EmergencyTeam.company_id == company_id,
                EmergencyTeam.type_id.in_(default_type_ids),
            )
        ).all()
    ) if default_type_ids else []

    by_type: dict[int, list[EmergencyTeam]] = {}
    for team in existing_teams:
        by_type.setdefault(team.type_id, []).append(team)

    now = datetime.utcnow()
    changed = False
    ensured: list[EmergencyTeam] = []

    for code, name in DEFAULT_TEAM_TYPES:
        t = type_by_code.get(code)
        if not t:
            continue

        candidates = by_type.get(t.id, [])
        active = next((team for team in candidates if team.is_active), None)
        if active:
            ensured.append(active)
            continue

        if candidates:
            # Eski sürümde karttan yapılan "Sil" işlemi soft-delete idi. En son
            # kaydı geri aç ve aynı işlemde pasife alınan üyeleri de geri getir.
            team = max(candidates, key=lambda row: row.id)
            team.is_active = True
            team.updated_at = now
            for assignment in team.assignments or []:
                assignment.is_active = True
                assignment.updated_at = now
            ensured.append(team)
            changed = True
            continue

        team = EmergencyTeam(
            company_id=company_id,
            type_id=t.id,
            name=name,
            min_members=t.min_members or 2,
            created_by_id=user_id,
        )
        db.add(team)
        ensured.append(team)
        changed = True

    if changed:
        db.commit()
        for team in ensured:
            if team.id is not None:
                db.refresh(team)
    return ensured


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
    today = today or emergency_team_today()
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
def team_status(active_members: int, min_members: int | None) -> dict:
    """Tam / Eksik / Kritik ekip durumu."""
    if min_members is None:
        return {"code": "veri_eksik", "label": "Hesaplanamadı", "tone": "muted"}
    minimum = max(int(min_members or 0), 0)
    if minimum <= 0:
        return {"code": "planlama", "label": "Plana göre", "tone": "muted"}
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
    minimum: int | None,
) -> list[str]:
    """Ekip düzeyinde yumuşak dilli hatırlatmalar."""
    warnings: list[str] = []
    if minimum is not None and minimum > 0 and active_members == 0:
        warnings.append("Bu ekibe henüz üye atanmamış — kontrol edilmesi önerilir.")
    elif minimum is not None and asil_members < minimum:
        warnings.append(
            f"Asıl üye sayısı {asil_members}; gerekli sayı {minimum}. "
            f"{minimum - asil_members} asıl üye görevlendirmesi eksik."
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
