"""Acil durum planı hazırlık ve mevzuat kontrol yardımcıları.

Bu modül hukuki uygunluk kararı vermez. Planın, İşyerlerinde Acil Durumlar
Hakkında Yönetmelik'te sayılan asgari başlıkları ne ölçüde belgelediğini ve
eksik kalan uygulama adımlarını görünür kılar.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterable


EMERGENCY_SCENARIOS: tuple[dict[str, str], ...] = (
    {"code": "yangin", "label": "Yangın"},
    {"code": "patlama", "label": "Patlama / parlama"},
    {"code": "chemical_release", "label": "Tehlikeli kimyasal yayılımı / sızıntı"},
    {"code": "biological", "label": "Biyolojik etken / salgın"},
    {"code": "natural_disaster", "label": "Deprem / doğal afet"},
    {"code": "flood_storm", "label": "Sel / fırtına / yıldırım"},
    {"code": "sabotage", "label": "Sabotaj / şiddet / güvenlik olayı"},
    {"code": "work_accident", "label": "İş kazası / tıbbi acil durum"},
    {"code": "power_gas", "label": "Elektrik / gaz acil durumu"},
    {"code": "other", "label": "Diğer"},
)

SCENARIO_LABELS = {item["code"]: item["label"] for item in EMERGENCY_SCENARIOS}
MANDATORY_TEAM_CODES = ("sondurme", "kurtarma", "koruma", "ilk_yardim")
MANDATORY_TEAM_LABELS = {
    "sondurme": "Söndürme",
    "kurtarma": "Kurtarma",
    "koruma": "Koruma",
    "ilk_yardim": "İlk yardım",
}
SUPPORT_TEAM_CODES = ("sondurme", "kurtarma", "koruma")


def default_plan_details() -> dict[str, Any]:
    """Yeni kayıtlar için güvenli ve açık bir başlangıç şablonu."""
    return {
        "version": 1,
        "emergency_types": [],
        "preventive_measures": "",
        "measurement_evaluation": "",
        "equipment_inventory": "",
        "response_methods": "",
        "special_risk_mode": "not_evaluated",
        "special_risk_areas": "",
        "energy_controls_mode": "not_evaluated",
        "energy_shutoff_points": "",
        "special_groups": "",
        "visitors_included": True,
        "temporary_workers_included": True,
        "shared_workplace": False,
        "shared_workplace_note": "",
        "approval_status": "not_confirmed",
        "posted_confirmed": False,
        "employees_informed": False,
        "last_drill_date": "",
        "next_drill_date": "",
        "drill_record_ref": "",
        "external_contacts": [
            {"name": "112 Acil Çağrı Merkezi", "phone": "112", "note": "Ulusal acil çağrı"}
        ],
    }


def _clean_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def normalize_plan_details(raw: Any) -> dict[str, Any]:
    """JSON alanını whitelist ederek normalize eder.

    Kullanıcının gönderdiği bilinmeyen anahtarları saklamamak, rapor çıktısında
    kontrol dışı veri taşınmasını ve gelecekteki şema çakışmalarını önler.
    """
    defaults = default_plan_details()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}

    emergency_types = raw.get("emergency_types")
    if not isinstance(emergency_types, list):
        emergency_types = []
    normalized_types: list[str] = []
    for value in emergency_types:
        code = _clean_text(value, 60)
        if code and code not in normalized_types:
            normalized_types.append(code)
    defaults["emergency_types"] = normalized_types[:20]

    for key, limit in (
        ("preventive_measures", 6000),
        ("measurement_evaluation", 4000),
        ("equipment_inventory", 4000),
        ("response_methods", 6000),
        ("special_risk_areas", 4000),
        ("energy_shutoff_points", 4000),
        ("special_groups", 2000),
        ("shared_workplace_note", 2000),
        ("last_drill_date", 10),
        ("next_drill_date", 10),
        ("drill_record_ref", 120),
    ):
        defaults[key] = _clean_text(raw.get(key), limit)

    for key in ("special_risk_mode", "energy_controls_mode"):
        value = _clean_text(raw.get(key), 30)
        defaults[key] = value if value in {"not_evaluated", "not_applicable", "present"} else "not_evaluated"

    for key in ("visitors_included", "temporary_workers_included", "shared_workplace"):
        defaults[key] = bool(raw.get(key, defaults[key]))
    approval_status = _clean_text(raw.get("approval_status"), 30)
    defaults["approval_status"] = approval_status if approval_status in {"not_confirmed", "employer_signed", "secure_esign"} else "not_confirmed"
    for key in ("posted_confirmed", "employees_informed"):
        defaults[key] = bool(raw.get(key, defaults[key]))

    contacts = raw.get("external_contacts")
    if not isinstance(contacts, list):
        contacts = defaults["external_contacts"]
    normalized_contacts: list[dict[str, str]] = []
    for contact in contacts[:30]:
        if not isinstance(contact, dict):
            continue
        name = _clean_text(contact.get("name"), 160)
        phone = _clean_text(contact.get("phone"), 60)
        note = _clean_text(contact.get("note"), 240)
        if name or phone or note:
            normalized_contacts.append({"name": name, "phone": phone, "note": note})
    defaults["external_contacts"] = normalized_contacts
    return defaults


def parse_plan_details(raw: Any) -> dict[str, Any]:
    return normalize_plan_details(raw)


def scene_summary(floors: Iterable[Any]) -> dict[str, Any]:
    """Kat krokilerindeki nesneleri mevzuat başlıkları için özetler."""
    counts: dict[str, int] = {}
    floor_summaries: list[dict[str, Any]] = []
    for floor in floors or []:
        raw = getattr(floor, "scene_json", None)
        try:
            scene = json.loads(raw) if raw else {}
        except (TypeError, ValueError):
            scene = {}
        objects = scene.get("objects") if isinstance(scene, dict) else []
        objects = objects if isinstance(objects, list) else []
        local: dict[str, int] = {}
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            kind = _clean_text(obj.get("type"), 80)
            if not kind:
                continue
            counts[kind] = counts.get(kind, 0) + 1
            local[kind] = local.get(kind, 0) + 1
        floor_summaries.append(
            {
                "id": getattr(floor, "id", None),
                "name": getattr(floor, "name", None) or "Kat",
                "has_background": bool(getattr(floor, "background_storage_path", None)),
                "objects": local,
            }
        )

    exits = counts.get("exit", 0) + counts.get("door_exit", 0)
    fire_equipment = sum(counts.get(code, 0) for code in ("extinguisher", "hose", "alarm"))
    geometry = counts.get("wall", 0) + counts.get("room", 0)
    has_background = any(item["has_background"] for item in floor_summaries)
    return {
        "symbol_counts": counts,
        "floor_summaries": floor_summaries,
        "floor_count": len(floor_summaries),
        "exits": exits,
        "routes": counts.get("route", 0),
        "assemblies": counts.get("assembly", 0),
        "first_aid": counts.get("firstaid", 0),
        "fire_equipment": fire_equipment,
        "you_are_here": counts.get("youarehere", 0),
        "geometry": geometry,
        "has_background": has_background,
    }


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has_text(value: Any, minimum: int = 1) -> bool:
    return len(str(value or "").strip()) >= minimum


def _review_years(hazard_class: Any) -> int | None:
    value = str(hazard_class or "").lower()
    if not value:
        return None
    if "cok" in value or "çok" in value or "heavy" in value:
        return 2
    if "tehlikeli" in value and "az" not in value:
        return 4
    if "az" in value or "less" in value:
        return 6
    return None


def support_team_threshold(hazard_class: Any) -> int | None:
    """Md. 11/3'teki söndürme-kurtarma-koruma çalışan kademesini döndürür."""
    value = str(hazard_class or "").lower()
    if "cok" in value or "çok" in value or "heavy" in value:
        return 30
    if "tehlikeli" in value and "az" not in value:
        return 40
    if "az" in value or "less" in value:
        return 50
    return None


def support_team_required_count(employee_count: Any, hazard_class: Any) -> int | None:
    """Destek elemanı sayısını hesaplar; ilk yardım sayısını hesaplamaz.

    Yönetmelik, 10'dan az çalışanı olan işyerlerinde söndürme, kurtarma ve
    koruma görevlerinin tamamı için bir kişinin yeterli olabileceğini söyler.
    İlk yardım sayısı ise İlkyardım Yönetmeliği'ne göre ayrıca belirlenir.
    """
    try:
        count = max(int(employee_count or 0), 0)
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    if count < 10:
        return 1
    threshold = support_team_threshold(hazard_class)
    return ((count + threshold - 1) // threshold) if threshold else None


def _add_years(value: Any, years: int) -> date | None:
    if not value:
        return None
    try:
        current = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
        return current.replace(year=current.year + years)
    except (TypeError, ValueError):
        # 29 Şubat için son geçerli gün kullanılır.
        try:
            return current.replace(year=current.year + years, day=28)  # type: ignore[has-type]
        except (UnboundLocalError, TypeError, ValueError):
            return None


def _check(
    checks: list[dict[str, Any]],
    *,
    code: str,
    label: str,
    ok: bool,
    detail: str,
    required: bool = True,
    warning: bool = False,
    reference: str = "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
) -> None:
    checks.append(
        {
            "id": code,
            "label": label,
            "status": "ok" if ok else ("warn" if warning else "error"),
            "detail": detail,
            "required": required,
            "reference": reference,
        }
    )


def calculate_plan_readiness(
    plan: Any,
    company: Any,
    details: dict[str, Any] | None,
    floors: Iterable[Any],
    team_summary: dict[str, Any] | None = None,
    drill_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Planı belge kapsamına göre puanlar; hukuki uygunluk beyanı üretmez."""
    details = normalize_plan_details(details)
    map_data = scene_summary(floors)
    company_name = _value(company, "name", "")
    company_address = _value(company, "address", "")
    employer = _value(company, "authorized_person", "")
    team_summary = team_summary or {}
    drill_summary = drill_summary or {}
    team_codes = set(team_summary.get("team_codes") or [])
    missing_team_codes = [code for code in MANDATORY_TEAM_CODES if code not in team_codes]
    empty_team_codes = list(team_summary.get("empty_team_codes") or [])

    checks: list[dict[str, Any]] = []
    identity_missing = [
        label
        for label, value in (
            ("işyeri adresi", company_address),
            ("işveren / vekil bilgisi", employer),
        )
        if not _has_text(value)
    ]
    _check(
        checks,
        code="workplace_identity",
        label="İşyeri künyesi",
        ok=not identity_missing and _has_text(company_name),
        detail=("İşyeri adı, adres ve işveren/vekil bilgisi mevcut." if not identity_missing and _has_text(company_name)
                else f"Eksik: {', '.join(identity_missing or ['işyeri adı'])}."),
        reference="Md. 12/1-a",
    )
    _check(
        checks,
        code="plan_dates",
        label="Plan ve yenileme tarihleri",
        ok=bool(_value(plan, "plan_date") and _value(plan, "next_review_date")),
        detail=("Plan tarihi ve bir sonraki gözden geçirme tarihi girilmiş."
                if _value(plan, "plan_date") and _value(plan, "next_review_date")
                else "Plan tarihi ve gözden geçirme tarihi birlikte girilmeli."),
        reference="Md. 12/1-c, Md. 14",
    )
    review_years = _review_years(_value(company, "hazard_class"))
    review_limit = _add_years(_value(plan, "plan_date"), review_years) if review_years else None
    cadence_known = review_limit is not None and _value(plan, "next_review_date") is not None
    cadence_ok = bool(cadence_known and _value(plan, "next_review_date") <= review_limit)
    _check(
        checks,
        code="review_cadence",
        label="Tehlike sınıfına göre yenileme aralığı",
        ok=cadence_ok if review_years else False,
        detail=(f"Azami {review_years} yıllık aralık içinde." if cadence_ok else
                ("Firma tehlike sınıfı kartta tanımlı değil; yenileme aralığı doğrulanmalı." if not review_years else
                 f"Gözden geçirme tarihi tehlike sınıfı için azami {review_years} yılı aşmamalı.")),
        required=bool(review_years),
        warning=not bool(review_years),
        reference="Md. 14",
    )
    selected_types = [code for code in details.get("emergency_types", []) if code]
    selected_labels = [SCENARIO_LABELS.get(code, code) for code in selected_types]
    _check(
        checks,
        code="emergency_scenarios",
        label="Acil durum senaryoları",
        ok=bool(selected_types),
        detail=(f"{len(selected_types)} senaryo seçildi: {', '.join(selected_labels[:4])}."
                if selected_types else "Risk değerlendirmesine göre en az bir senaryo seçilmeli."),
        reference="Md. 5, Md. 7, Md. 8",
    )
    _check(
        checks,
        code="preventive_measures",
        label="Önleyici ve sınırlandırıcı tedbirler",
        ok=_has_text(details.get("preventive_measures"), 20),
        detail=("Tedbirler yazılı."
                if _has_text(details.get("preventive_measures"), 20)
                else "Senaryolara göre uygulanacak tedbirleri açıklayın."),
        reference="Md. 5/1-b, Md. 12/1-d",
    )
    _check(
        checks,
        code="measurement_evaluation",
        label="Ölçüm ve değerlendirme",
        ok=_has_text(details.get("measurement_evaluation"), 10),
        detail=("Acil durum etkilerine ilişkin ölçüm / değerlendirme notu mevcut."
                if _has_text(details.get("measurement_evaluation"), 10)
                else "Gerekli ölçüm ve değerlendirmelerin yapıldığını veya uygulanamaz olduğunu açıklayın."),
        reference="Md. 5/1-c",
    )
    _check(
        checks,
        code="equipment_inventory",
        label="Acil durum ekipmanı ve KKD",
        ok=_has_text(details.get("equipment_inventory"), 10),
        detail=("Acil durum ekipmanı / KKD listesi mevcut."
                if _has_text(details.get("equipment_inventory"), 10)
                else "Yangın, ilk yardım, kurtarma ve gerekiyorsa KKD ekipmanlarını listeleyin."),
        reference="Md. 5/1-g, Md. 12/1-f-1/2",
    )
    _check(
        checks,
        code="response_methods",
        label="Müdahale ve tahliye yöntemleri",
        ok=_has_text(details.get("response_methods"), 20),
        detail=("Müdahale, haberleşme ve tahliye yöntemi yazılı."
                if _has_text(details.get("response_methods"), 20)
                else "İhbar, ilk yardım, yangınla mücadele ve tahliye adımlarını açıklayın."),
        reference="Md. 10, Md. 12/1-e",
    )
    map_ok = bool(
        map_data["floor_count"]
        and map_data["exits"]
        and map_data["routes"]
        and map_data["assemblies"]
        and (map_data["geometry"] or map_data["has_background"])
    )
    _check(
        checks,
        code="evacuation_map",
        label="Tahliye krokisi",
        ok=map_ok,
        detail=(f"{map_data['floor_count']} kat için çıkış, kaçış yönü ve toplanma alanı işaretlenmiş."
                if map_ok else "En az bir katta plan zemini, acil çıkış, kaçış yönü ve toplanma alanı birlikte bulunmalı."),
        reference="Md. 10/1, Md. 12/1-f",
    )
    equipment_ok = bool(map_data["first_aid"] and map_data["fire_equipment"])
    _check(
        checks,
        code="emergency_equipment",
        label="Acil durum ekipmanları",
        ok=equipment_ok,
        detail=("İlk yardım ve yangınla mücadele ekipmanları krokide gösterilmiş."
                if equipment_ok else "İlk yardım malzemeleri ile yangınla mücadele ekipmanlarını krokide gösterin."),
        reference="Md. 5/1-g, Md. 12/1-f-1/2",
    )
    teams_ok = not missing_team_codes and not empty_team_codes
    team_detail = "Zorunlu dört ekipte aktif görevlendirme görünüyor."
    if missing_team_codes:
        team_detail = "Eksik ekip türleri: " + ", ".join(MANDATORY_TEAM_LABELS[c] for c in missing_team_codes) + "."
    elif empty_team_codes:
        team_detail = "Üyesiz ekip türleri: " + ", ".join(MANDATORY_TEAM_LABELS.get(c, c) for c in empty_team_codes) + "."
    _check(
        checks,
        code="emergency_teams",
        label="Acil durum ekipleri / destek elemanları",
        ok=teams_ok,
        detail=team_detail,
        reference="Md. 11, Md. 12/1-f-4",
    )
    under_minimum = list(team_summary.get("under_minimum_codes") or [])
    capacity_check_known = bool(team_summary.get("capacity_check_known"))
    capacity_check_present = any(
        key in team_summary for key in ("employee_count", "required_support_members", "capacity_check_known")
    )
    required_support_members = team_summary.get("required_support_members")
    if not capacity_check_present:
        capacity_ok = not under_minimum
        capacity_detail = (
            "Tanımlı ekip üyeleri mevcut; vardiya ve eğitim geçerliliği ayrıca doğrulanmalı."
            if capacity_ok else
            "Kontrol edilen ekiplerde tanımlı destek elemanı sayısı eksik."
        )
    elif not capacity_check_known:
        capacity_ok = False
        capacity_detail = "Aktif çalışan sayısı veya tehlike sınıfı kayıtlı olmadığından Md. 11 sayısı hesaplanamadı."
    else:
        capacity_ok = not under_minimum
        capacity_detail = (
            f"Söndürme, kurtarma ve koruma için çalışan kademesi ({required_support_members}) karşılanıyor; "
            "vardiya ve eğitim geçerliliği ayrıca doğrulanmalı."
            if capacity_ok else
            "Kontrol edilen söndürme, kurtarma veya koruma ekiplerinde Md. 11 destek elemanı sayısı eksik: "
            + ", ".join(MANDATORY_TEAM_LABELS.get(code, code) for code in under_minimum) + "."
        )
    _check(
        checks,
        code="team_capacity",
        label="Destek elemanı sayısı ve sürekliliği",
        ok=capacity_ok,
        detail=capacity_detail,
        required=False,
        warning=True,
        reference="Md. 5/1-d, Md. 11",
    )
    contacts = [c for c in details.get("external_contacts", []) if c.get("name") and c.get("phone")]
    only_112 = len(contacts) == 1 and contacts[0].get("phone") == "112"
    _check(
        checks,
        code="external_contacts",
        label="Ulusal / yerel acil iletişim",
        ok=bool(contacts) and not only_112,
        detail=("Acil iletişim listesi mevcut; yerel birim ve tesis irtibatlarını ayrıca doğrulayın."
                if contacts else "112 ve işyerine uygun yerel acil iletişimleri ekleyin."),
        warning=bool(contacts),
        reference="Md. 12/1-f-5",
    )
    special_mode = details.get("special_risk_mode")
    special_ok = special_mode == "not_applicable" or (
        special_mode == "present" and _has_text(details.get("special_risk_areas"), 10)
    )
    _check(
        checks,
        code="special_risks",
        label="Özel risk alanları",
        ok=special_ok,
        detail=("Özel risk alanları / uygulanamazlık beyanı işlenmiş."
                if special_ok else "Kimyasal, patlama, biyolojik ve benzeri özel riskleri değerlendirin."),
        reference="Md. 8, Md. 12/1-f-6",
    )
    energy_mode = details.get("energy_controls_mode")
    energy_ok = energy_mode == "not_applicable" or (
        energy_mode == "present" and _has_text(details.get("energy_shutoff_points"), 10)
    )
    _check(
        checks,
        code="energy_controls",
        label="Enerji kesme / vana noktaları",
        ok=energy_ok,
        detail=("Enerji kesme ve vana bilgisi işlenmiş."
                if energy_ok else "Elektrik, gaz ve diğer tehlikeli sistemlerin kesme noktalarını değerlendirin."),
        reference="Md. 5/1-f, Md. 12/1-f-7",
    )
    approval_ok = details.get("approval_status") in {"employer_signed", "secure_esign"}
    posting_ok = bool(details.get("posted_confirmed"))
    _check(
        checks,
        code="document_control",
        label="Onay, imza ve görünür yerde bulundurma",
        ok=approval_ok and posting_ok,
        detail=("Onay / imza durumu ve krokilerin görünür yerde bulundurulduğu kaydı mevcut."
                if approval_ok and posting_ok
                else "İşveren onay / imza durumunu ve krokilerin görünür yerde bulundurulmasını doğrulayın."),
        reference="Md. 12/2-3",
    )
    drill_date = drill_summary.get("last_date") or details.get("last_drill_date")
    drill_age = None
    if drill_date:
        try:
            parsed_drill_date = drill_date if isinstance(drill_date, date) else date.fromisoformat(str(drill_date)[:10])
            drill_age = (date.today() - parsed_drill_date).days
        except (TypeError, ValueError):
            drill_age = None
    drill_ok = drill_age is not None and 0 <= drill_age <= 366
    if drill_ok:
        drill_detail = f"Son tamamlanmış tatbikat {drill_age} gün önce kayıtlı."
    elif drill_age is not None and drill_age > 366:
        drill_detail = "Son tatbikatın üzerinden bir yıldan fazla süre geçmiş."
    elif drill_age is not None and drill_age < 0:
        drill_detail = "Tatbikat tarihi ileri tarihli olamaz."
    else:
        drill_detail = "Tamamlanmış tatbikat kaydı bulunamadı; yıllık tatbikat planlayın ve tutanağı saklayın."
    _check(
        checks,
        code="drill_currency",
        label="Tatbikat güncelliği",
        ok=drill_ok,
        detail=drill_detail,
        reference="Md. 5/1-ç, Md. 13",
    )

    _check(
        checks,
        code="people_needing_support",
        label="Özel desteğe ihtiyaç duyan kişiler",
        ok=_has_text(details.get("special_groups"), 5),
        detail=("Özel destek ihtiyacı olan kişiler için yöntem not edilmiş."
                if _has_text(details.get("special_groups"), 5)
                else "Engelli, yaşlı, gebe, çocuk veya desteğe ihtiyaç duyan kişiler için yöntemi yazın."),
        required=False,
        warning=True,
        reference="Md. 10/2",
    )
    _check(
        checks,
        code="visitors_and_temporary_workers",
        label="Ziyaretçi ve geçici çalışan kapsamı",
        ok=bool(details.get("visitors_included") and details.get("temporary_workers_included")),
        detail=("Ziyaretçi ve geçici çalışanlar plana dahil edilmiş."
                if details.get("visitors_included") and details.get("temporary_workers_included")
                else "Ziyaretçi / geçici çalışan bilgilendirmesini ayrıca işaretleyin."),
        required=False,
        warning=True,
        reference="Md. 5/1-e, Md. 15",
    )
    _check(
        checks,
        code="employee_information",
        label="Çalışan bilgilendirmesi",
        ok=bool(details.get("employees_informed")),
        detail=("Çalışan bilgilendirmesi tamamlandı olarak işaretlendi."
                if details.get("employees_informed") else "Tüm çalışanların ve yeni / geçici çalışanların bilgilendirildiğini doğrulayın."),
        required=False,
        warning=True,
        reference="Md. 15",
    )
    coordination_ok = not details.get("shared_workplace") or _has_text(details.get("shared_workplace_note"), 10)
    _check(
        checks,
        code="shared_workplace_coordination",
        label="Ortak işyeri koordinasyonu",
        ok=coordination_ok,
        detail=("Ortak işyeri / birden fazla işveren koordinasyon notu mevcut."
                if coordination_ok else "Ortak saha koordinasyonunu, ana işveren ve diğer işveren sorumluluklarını yazın."),
        required=False,
        warning=True,
        reference="Md. 17, Md. 18",
    )

    required_checks = [item for item in checks if item["required"]]
    passed = sum(1 for item in required_checks if item["status"] == "ok")
    total = len(required_checks)
    pct = round((passed / total) * 100) if total else 0
    errors = [item for item in checks if item["status"] == "error"]
    warnings = [item for item in checks if item["status"] == "warn"]
    if not errors:
        status = "ready" if not warnings else "review"
        label = "Hazır" if not warnings else "Son kontrol gerekli"
    elif passed == 0:
        status = "draft"
        label = "Taslak"
    else:
        status = "action"
        label = "İyileştirme gerekli"
    missing = [item["detail"] for item in checks if item["status"] != "ok"]
    return {
        "version": "emergency-plan-compliance-v1",
        "pct": pct,
        "score": passed,
        "max_score": total,
        "status": status,
        "label": label,
        "checks": checks,
        "missing": missing,
        "required_total": total,
        "required_passed": passed,
        "summary": f"{passed}/{total} zorunlu kontrol tamamlandı.",
        "map": map_data,
        "team_summary": team_summary,
        "drill_summary": drill_summary,
    }
