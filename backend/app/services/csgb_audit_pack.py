"""ÇSGB OSGB denetimi — müfettiş belge paketi hazırlık durumu.

ÇSGB / İSG Genel Müdürlüğü OSGB denetimlerinde sık istenen belge ve kayıt
kalemlerini sistemdeki verilerle eşleştirir; hazır / eksik / kısmi durumunu
raporlar. Hukuki dayanak özetleri bilgilendirme amaçlıdır.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AssignmentStatus,
    Company,
    DocumentCategory,
    DocumentRecord,
    Employee,
    HealthRecord,
    IncidentEvent,
    IsgProfessional,
    OsgbOrganization,
    RiskAssessment,
    ServiceContract,
    ServiceVisit,
    TrainingSession,
    WorkplaceAssignment,
)


def _item(
    code: str,
    title: str,
    legal: str,
    status: str,
    count: int = 0,
    detail: str = "",
    evidence: list[dict[str, Any]] | None = None,
    group: str = "genel",
    group_label: str = "Genel",
) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "legal": legal,
        "status": status,  # ready | partial | missing
        "count": count,
        "detail": detail,
        "evidence": evidence or [],
        "group": group,
        "group_label": group_label,
    }


# Kurulum / demo placeholder’ları “hazır” sayılmamalı
_PLACEHOLDER = {
    "1234567890",
    "1111111111",
    "0000000000",
    "9999999999",
    "osgb 001",
    "demo-osgb-001",
    "test-osgb-001",
    "global yönetici",
    "demo yönetici",
}


def _is_real_value(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    if not s:
        return False
    low = s.casefold()
    if low in _PLACEHOLDER:
        return False
    if low.startswith("demo") or low.startswith("test_") or low.startswith("test-"):
        return False
    return True


def _heal_osgb_links(db: Session, oid: int) -> None:
    """İşyerleri / profesyoneller / görevlendirmeler OSGB’ye bağlı değilse sayaçlar 0 kalır.

    Tek OSGB kurulumunda (canlı) Firma Ekle osgb_id yazmadığı için veri vardır ama
    paket ‘yok’ der. Mevcut kayıtları bu OSGB’ye bağlar.
    """
    osgb_n = db.scalar(select(func.count()).select_from(OsgbOrganization)) or 0
    if osgb_n != 1:
        # Çoklu OSGB: yalnız osgb_id boş işyerlerini ve görevlendirme ile bağlı olanları düzelt
        for c in db.scalars(select(Company).where(Company.osgb_id.is_(None))).all():
            c.osgb_id = oid
        linked = list(
            db.scalars(
                select(WorkplaceAssignment.company_id).where(WorkplaceAssignment.osgb_id == oid).distinct()
            ).all()
        )
        if linked:
            for c in db.scalars(select(Company).where(Company.id.in_(linked), Company.osgb_id.is_(None))).all():
                c.osgb_id = oid
        db.commit()
        return

    for c in db.scalars(select(Company).where(or_(Company.osgb_id.is_(None), Company.osgb_id != oid))).all():
        c.osgb_id = oid
    for p in db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id != oid)).all():
        p.osgb_id = oid
    for a in db.scalars(select(WorkplaceAssignment).where(WorkplaceAssignment.osgb_id != oid)).all():
        a.osgb_id = oid
    for c in db.scalars(select(ServiceContract).where(ServiceContract.osgb_id != oid)).all():
        c.osgb_id = oid
    db.commit()


def build_csgb_audit_pack(db: Session, osgb_id: int | None = None) -> dict[str, Any]:
    osgb = None
    if osgb_id:
        osgb = db.get(OsgbOrganization, osgb_id)
    if not osgb:
        osgb = db.scalar(select(OsgbOrganization).order_by(OsgbOrganization.id).limit(1))
    if not osgb:
        return {
            "osgb": None,
            "generated_at": date.today().isoformat(),
            "summary": {"ready": 0, "partial": 0, "missing": 1, "total": 1},
            "items": [
                _item(
                    "osgb_kayit",
                    "OSGB kayıt bilgileri",
                    "İşyeri Hekimi ve Diğer Sağlık Personeli ile İSG Uzmanlarının Görev, Yetki ve Sorumlulukları Hk. Yönetmelik / OSGB yönetmeliği",
                    "missing",
                    detail="Sistemde OSGB kaydı bulunamadı.",
                )
            ],
            "gaps": ["OSGB organizasyon kaydı oluşturulmalıdır."],
            "report_title": "ÇSGB OSGB Denetim Belge Paketi",
        }

    oid = osgb.id
    _heal_osgb_links(db, oid)

    companies = list(
        db.scalars(select(Company).where(Company.osgb_id == oid, Company.is_active.is_(True))).all()
    )
    company_ids = [c.id for c in companies]

    pros = list(db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == oid)).all())
    active_pros = [p for p in pros if p.is_active is not False]
    # Aktif görevlendirme: enum + string uyumu (PG/SQLite farkı)
    assignments = list(
        db.scalars(
            select(WorkplaceAssignment).where(
                WorkplaceAssignment.osgb_id == oid,
                or_(
                    WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
                    WorkplaceAssignment.status == "active",
                    WorkplaceAssignment.status == "ACTIVE",
                ),
            )
        ).all()
    )
    contracts = list(db.scalars(select(ServiceContract).where(ServiceContract.osgb_id == oid)).all())

    # Module counts scoped to OSGB companies
    def _count(model, *extra):
        if not company_ids:
            return 0
        return db.scalar(select(func.count()).select_from(model).where(model.company_id.in_(company_ids), *extra)) or 0

    risk_n = _count(RiskAssessment)
    plan_n = _count(AnnualPlanItem, AnnualPlanItem.deleted_at.is_(None))
    train_n = _count(TrainingSession)
    health_n = _count(HealthRecord, HealthRecord.deleted_at.is_(None))
    incident_n = _count(IncidentEvent)
    emp_n = _count(Employee)
    docs = []
    if company_ids:
        docs = list(
            db.scalars(
                select(DocumentRecord).where(
                    DocumentRecord.company_id.in_(company_ids),
                    DocumentRecord.is_active.is_(True),
                )
            ).all()
        )
    visit_n = (
        db.scalar(select(func.count()).select_from(ServiceVisit).where(ServiceVisit.osgb_id == oid)) or 0
    )

    items: list[dict[str, Any]] = []
    G_KURUM = ("kurumsal", "1. OSGB kurumsal")
    G_KADRO = ("kadro", "2. Kadro ve görevlendirme")
    G_SOZ = ("sozlesme", "3. Sözleşme ve süre")
    G_SAHA = ("saha", "4. Saha / hizmet kayıtları")

    # 1) Yetki belgesi / kimlik — placeholder (OSGB 001, 1234567890 vb.) hazır sayılmaz
    auth_ok = _is_real_value(osgb.authorization_number)
    items.append(
        _item(
            "yetki_belgesi",
            "OSGB yetki / ruhsat bilgisi",
            "OSGB Yönetmeliği — yetki belgesi",
            "ready" if auth_ok else "missing",
            count=1 if auth_ok else 0,
            detail=(
                f"Yetki no: {osgb.authorization_number}"
                if auth_ok
                else "Gerçek yetki / ruhsat numarası tanımlı değil (placeholder veya boş)."
            ),
            evidence=[{"field": "authorization_number", "value": osgb.authorization_number}] if auth_ok else [],
            group=G_KURUM[0],
            group_label=G_KURUM[1],
        )
    )

    # 2) OSGB kimlik kartı
    identity_fields = [
        ("name", osgb.name),
        ("tax_number", osgb.tax_number),
        ("responsible_manager", osgb.responsible_manager),
        ("address", osgb.address),
        ("email", osgb.email),
        ("phone", osgb.phone),
    ]
    filled = sum(1 for _, v in identity_fields if _is_real_value(v))
    id_status = "ready" if filled >= 5 else ("partial" if filled >= 2 else "missing")
    items.append(
        _item(
            "osgb_kimlik",
            "OSGB kimlik ve iletişim bilgileri",
            "OSGB Yönetmeliği — kuruluş bilgileri",
            id_status,
            count=filled,
            detail=f"{filled}/{len(identity_fields)} gerçek alan dolu (placeholder sayılmaz: unvan, vergi, sorumlu müdür, adres, e-posta, telefon).",
            evidence=[{"field": k, "value": v} for k, v in identity_fields if _is_real_value(v)],
            group=G_KURUM[0],
            group_label=G_KURUM[1],
        )
    )

    # 3) Profesyonel kadro + belgeler
    with_cert = [p for p in active_pros if p.certificate_number]
    if not active_pros:
        pro_status, pro_detail = "missing", "Aktif uzman / hekim / DSP kaydı yok."
    elif len(with_cert) < len(active_pros):
        pro_status = "partial"
        pro_detail = f"{len(active_pros)} aktif profesyonel; belgesi eksik: {len(active_pros) - len(with_cert)}."
    else:
        pro_status = "ready"
        pro_detail = f"{len(active_pros)} aktif profesyonel; tümünde belge no kayıtlı."
    items.append(
        _item(
            "profesyonel_kadro",
            "İSG profesyonel kadrosu ve belgeler",
            "6331 / İSG Hizmetleri Yönetmeliği — uzman, hekim, DSP yeterlilik",
            pro_status,
            count=len(active_pros),
            detail=pro_detail,
            evidence=[
                {
                    "id": p.id,
                    "name": p.full_name,
                    "type": p.professional_type.value,
                    "certificate_class": p.certificate_class,
                    "certificate_number": p.certificate_number,
                }
                for p in active_pros[:40]
            ],
            group=G_KADRO[0],
            group_label=G_KADRO[1],
        )
    )

    # 4) Hizmet sözleşmeleri
    active_contracts = [c for c in contracts if (c.status or "").lower() in ("active", "aktif", "")]
    if not companies:
        ctr_status, ctr_detail = "missing", "OSGB’ye bağlı aktif işyeri yok."
    elif not contracts:
        ctr_status, ctr_detail = "missing", f"{len(companies)} işyeri var; hizmet sözleşmesi kaydı yok."
    elif len(active_contracts) < len(companies):
        ctr_status = "partial"
        ctr_detail = f"{len(active_contracts)} sözleşme / {len(companies)} işyeri."
    else:
        ctr_status = "ready"
        ctr_detail = f"{len(active_contracts)} hizmet sözleşmesi kayıtlı."
    items.append(
        _item(
            "hizmet_sozlesmesi",
            "İşyeri hizmet sözleşmeleri",
            "OSGB Yönetmeliği — hizmet sözleşmesi",
            ctr_status,
            count=len(contracts),
            detail=ctr_detail,
            evidence=[
                {"id": c.id, "contract_number": c.contract_number, "company_id": c.company_id, "status": c.status}
                for c in contracts[:40]
            ],
            group=G_SOZ[0],
            group_label=G_SOZ[1],
        )
    )

    # 5) Görevlendirme / İSG-KATİP
    with_katip = [a for a in assignments if a.isg_katip_contract_number]
    if not assignments:
        asg_status, asg_detail = "missing", "Aktif görevlendirme yok."
    elif len(with_katip) < len(assignments):
        asg_status = "partial"
        asg_detail = (
            f"{len(assignments)} aktif görevlendirme; İSG-KATİP no eksik: "
            f"{len(assignments) - len(with_katip)}."
        )
    else:
        asg_status = "ready"
        asg_detail = f"{len(assignments)} aktif görevlendirme; İSG-KATİP no tamam."
    items.append(
        _item(
            "gorevlendirme_katip",
            "Görevlendirmeler ve İSG-KATİP bildirim no",
            "İSG-KATİP / görevlendirme bildirimi",
            asg_status,
            count=len(assignments),
            detail=asg_detail,
            evidence=[
                {
                    "id": a.id,
                    "company_id": a.company_id,
                    "professional_id": a.professional_id,
                    "isg_katip": a.isg_katip_contract_number,
                    "required_minutes": a.required_minutes_monthly,
                }
                for a in assignments[:40]
            ],
            group=G_KADRO[0],
            group_label=G_KADRO[1],
        )
    )

    # 6) Saha çalışma süreleri
    visit_status = "ready" if visit_n > 0 else "missing"
    items.append(
        _item(
            "saha_sure",
            "Saha çalışma / ziyaret süre kayıtları",
            "İSG Hizmetleri Yönetmeliği — asgari süre",
            visit_status if assignments else "missing",
            count=visit_n,
            detail=(
                f"{visit_n} saha ziyareti kaydı."
                if visit_n
                else "Saha ziyareti / süre kaydı bulunamadı (müfettiş asgari süre kanıtı ister)."
            ),
            group=G_SOZ[0],
            group_label=G_SOZ[1],
        )
    )

    # 7–12) Operasyonel kayıtlar
    def _mod(code, title, legal, n, empty_msg, ok_msg):
        st = "ready" if n > 0 else "missing"
        if not company_ids and st == "missing":
            detail = "Bağlı işyeri yok; kayıt üretilemez."
        else:
            detail = ok_msg.format(n=n) if n else empty_msg
        items.append(
            _item(code, title, legal, st, count=n, detail=detail, group=G_SAHA[0], group_label=G_SAHA[1])
        )

    _mod(
        "risk_degerlendirme",
        "Risk değerlendirme kayıtları",
        "6331 md. 10 — risk değerlendirmesi",
        risk_n,
        "Risk değerlendirme kaydı yok.",
        "{n} risk değerlendirme kaydı.",
    )
    _mod(
        "yillik_plan",
        "Yıllık çalışma planı",
        "İSG Hizmetleri Yönetmeliği — yıllık plan",
        plan_n,
        "Yıllık plan kalemi yok.",
        "{n} yıllık plan kalemi.",
    )
    _mod(
        "egitim",
        "İş sağlığı ve güvenliği eğitim kayıtları",
        "Çalışanların İSG Eğitimleri Yönetmeliği",
        train_n,
        "Eğitim oturumu kaydı yok.",
        "{n} eğitim oturumu.",
    )
    _mod(
        "saglik",
        "Sağlık gözetimi / muayene kayıtları",
        "6331 md. 15 — sağlık gözetimi",
        health_n,
        "Sağlık gözetimi kaydı yok.",
        "{n} sağlık kaydı.",
    )
    _mod(
        "olay",
        "İş kazası / ramak kala kayıtları",
        "6331 md. 14 — kayıt ve bildirim",
        incident_n,
        "Olay kaydı yok (sıfır olay da mümkündür; arşiv boşsa müfettişe açıklayın).",
        "{n} olay kaydı.",
    )
    # Olay için 0 = partial (bilinçli boş olabilir) — keep missing only if no companies
    if incident_n == 0 and company_ids:
        items[-1]["status"] = "partial"
        items[-1]["detail"] = "Sistemde olay kaydı yok; sıfır kaza ise yazılı beyan / defter hazırlayın."

    _mod(
        "personel",
        "İşyeri çalışan listeleri",
        "Denetim kimlik / kapsam doğrulama",
        emp_n,
        "Personel kaydı yok.",
        "{n} çalışan kaydı.",
    )

    # 13) Doküman arşivi (kategori özeti)
    by_cat: dict[str, int] = {}
    for d in docs:
        key = d.category.value if hasattr(d.category, "value") else str(d.category)
        by_cat[key] = by_cat.get(key, 0) + 1
    expected_cats = [c.value for c in DocumentCategory]
    present_cats = [c for c in expected_cats if by_cat.get(c)]
    if not docs:
        doc_status = "missing"
        doc_detail = "Doküman arşivinde aktif kayıt yok."
    elif len(present_cats) < 3:
        doc_status = "partial"
        doc_detail = f"{len(docs)} doküman; kategoriler: {', '.join(present_cats) or '—'}."
    else:
        doc_status = "ready"
        doc_detail = f"{len(docs)} doküman; {len(present_cats)} kategori dolu."
    items.append(
        _item(
            "dokuman_arsiv",
            "Doküman arşivi (yasal / risk / eğitim / sağlık…)",
            "OSGB denetim dosyası — destekleyici belgeler",
            doc_status,
            count=len(docs),
            detail=doc_detail,
            evidence=[{"category": k, "count": v} for k, v in sorted(by_cat.items())],
            group=G_SAHA[0],
            group_label=G_SAHA[1],
        )
    )

    ready = sum(1 for i in items if i["status"] == "ready")
    partial = sum(1 for i in items if i["status"] == "partial")
    missing = sum(1 for i in items if i["status"] == "missing")
    priority = [i for i in items if i["status"] in ("missing", "partial")]
    gaps = [f"{i['title']}: {i['detail']}" for i in priority]

    groups = []
    seen = set()
    for i in items:
        if i["group"] not in seen:
            seen.add(i["group"])
            groups.append({"id": i["group"], "label": i["group_label"]})

    return {
        "osgb": {
            "id": osgb.id,
            "name": osgb.name,
            "authorization_number": osgb.authorization_number,
            "tax_number": osgb.tax_number,
            "responsible_manager": osgb.responsible_manager,
            "address": osgb.address,
            "email": osgb.email,
            "phone": osgb.phone,
            "company_count": len(companies),
            "professional_count": len(active_pros),
            "assignment_count": len(assignments),
        },
        "generated_at": date.today().isoformat(),
        "legal_note": (
            "Sayaçlar yalnızca bu OSGB’ye bağlı kayıtlardan gelir: "
            "İşyerleri (companies.osgb_id), İSG Profesyonelleri, Görevlendirmeler. "
            "Bu sayfada veri girilmez; diğer menülerdeki gerçek kayıtlar okunur. "
            "Placeholder yetki/VKN (ör. OSGB 001, 1234567890) hazır sayılmaz."
        ),
        "summary": {
            "ready": ready,
            "partial": partial,
            "missing": missing,
            "total": len(items),
            "priority_count": len(priority),
            "readiness_pct": round(100 * (ready + 0.5 * partial) / len(items)) if items else 0,
        },
        "groups": groups,
        "items": items,
        "gaps": gaps,
        "report_title": f"ÇSGB OSGB Denetim Belge Paketi — {osgb.name}",
    }
