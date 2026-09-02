"""Görsel saha denetimi AI adaptörü.

Bu katman fail-closed çalışır: açıkça etkinleştirilmiş, veri işleme izni
verilmiş ve anahtarı tanımlanmış bir provider yoksa dışarı çağrı yapmaz.
Provider çıktısı yalnızca uzman taslağıdır; bu servis risk/uygunsuzluk onayı
vermez ve doğrulanmamış mevzuat maddesi üretmez.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import settings
from app.services.field_inspection_ai_prompt import FIELD_AI_PROMPT_VERSION, build_field_ai_system_prompt
from app.services.field_inspection_catalog import FIELD_HAZARD_CATEGORIES, FIELD_LEGAL_CATALOG, legal_entry

logger = logging.getLogger(__name__)


class FieldAiNotConfigured(RuntimeError):
    """AI çağrısı için güvenli ve açık yapılandırma bulunmadı."""


class FieldAiProviderError(RuntimeError):
    """Provider çağrısı veya çıktısı beklenen sözleşmeye uymadı."""


FIELD_AI_SYSTEM_PROMPT = build_field_ai_system_prompt(
    hazard_categories=FIELD_HAZARD_CATEGORIES,
    legal_catalog=tuple(str(item["name"]) for item in FIELD_LEGAL_CATALOG),
)

_CONFIDENCE_LABELS = {
    "very_high": 0.92,
    "high": 0.78,
    "medium": 0.55,
    "low": 0.28,
}
_CONFIRMED_EVIDENCE_CLASSES = {"directly_observed", "strongly_supported"}
_PRIORITY_COLORS = {"critical": "#7f1d1d", "high": "#b91c1c", "medium": "#d97706", "low": "#64748b"}


def _field_ai_api_key() -> str:
    """Return the new pilot key, with a safe bridge to the legacy vision key.

    The visual field-inspection flow was introduced after the legacy
    ``VISION_*`` flow.  Keeping the fallback here lets an existing production
    secret continue to be used without copying or exposing it, while the new
    FIELD_AI feature flags still remain the only gates for this flow.
    """
    return str(
        getattr(settings, "field_ai_api_key", None)
        or getattr(settings, "vision_api_key", None)
        or ""
    ).strip()


def field_ai_is_configured() -> bool:
    if bool(getattr(settings, "field_ai_force_off", False)):
        return False
    provider = str(getattr(settings, "field_ai_provider", "openai_compatible") or "").strip().lower()
    return bool(
        provider in {"openai_compatible", "openai"}
        and getattr(settings, "field_ai_enabled", False)
        and getattr(settings, "field_ai_data_processing_allowed", False)
        and _field_ai_api_key()
        and str(getattr(settings, "field_ai_api_url", "") or "").strip()
        and str(getattr(settings, "field_ai_model", "") or "").strip()
    )


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean[:limit] if clean else None


def _number(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bbox(value: Any) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    values = [_number(value.get(key)) for key in ("x", "y", "width", "height")]
    if any(item is None for item in values):
        return None
    x, y, width, height = (max(0.0, min(1.0, float(item))) for item in values)
    if width <= 0 or height <= 0:
        return None
    # Kutu ekran dışına taşmasın; provider hatası güvenli biçimde daraltılır.
    return {"x": x, "y": y, "width": min(width, 1.0 - x), "height": min(height, 1.0 - y)}


def _parse_date(value: Any) -> str | None:
    raw = _text(value, 20)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        return None


def _photo_index(value: Any, *, photo_count: int) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        index = 0
    return max(0, min(max(photo_count - 1, 0), index))


def _confidence(item: dict[str, Any]) -> float | None:
    numeric = _number(item.get("confidence"))
    if numeric is not None:
        return max(0.0, min(1.0, numeric))
    label = str(item.get("confidence_label") or "").strip().lower().replace(" ", "_")
    mapped = _CONFIDENCE_LABELS.get(label)
    return mapped


def _evidence_class(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "a": "directly_observed",
        "directlyobserved": "directly_observed",
        "b": "strongly_supported",
        "stronglysupported": "strongly_supported",
        "c": "possible_requires_verification",
        "possible": "possible_requires_verification",
        "requires_verification": "possible_requires_verification",
        "d": "not_assessable",
        "notassessable": "not_assessable",
        "e": "no_visible_nonconformity",
        "no_visible_nonconformity_identified": "no_visible_nonconformity",
    }
    normalized = aliases.get(raw, raw)
    if normalized in {
        "directly_observed",
        "strongly_supported",
        "possible_requires_verification",
        "not_assessable",
        "no_visible_nonconformity",
    }:
        return normalized
    return None


def _priority(value: Any, default: str = "medium") -> str:
    priority = str(value or default).strip().lower()
    return priority if priority in {"low", "medium", "high", "critical"} else default


def _annotation_label(item: dict[str, Any], *, finding_no: int | None = None) -> str:
    hazard = _text(item.get("hazard_name") or item.get("title"), 50) or "Bulgu"
    code = _text(item.get("annotation_label") or item.get("finding_code"), 40)
    if finding_no is not None:
        body = code or hazard
        if body.startswith(f"#{finding_no}"):
            return body[:80]
        return f"#{finding_no} {body}"[:80]
    return (code or f"OHS {hazard}")[:80]


def _legal_references(item: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for reference in item.get("legal_references") or item.get("legal_refs") or []:
        if not isinstance(reference, dict):
            continue
        name = _text(reference.get("regulation_name") or reference.get("name"), 300)
        entry = legal_entry(name)
        if not entry:
            warnings.append("AI çıktısındaki katalog dışı mevzuat atfı saklanmadı.")
            continue
        references.append({
            "regulation_name": name,
            "article": None,
            "paragraph": None,
            "source_url": entry.get("source_url"),
            "source_version": entry.get("version") or "resmî kaynak uzman kontrolü",
            "relation_explanation": _text(reference.get("relation_explanation") or reference.get("explanation"), 2000),
            "verification_status": "needs_expert_review",
        })
    return references


def _verification_items(raw: Any, *, photo_count: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(raw[:30], start=1):
        if not isinstance(item, dict):
            continue
        reason = _text(item.get("reason") or item.get("what_cannot_be_verified") or item.get("description"), 2000)
        if not reason:
            continue
        items.append({
            "verification_id": _text(item.get("verification_id"), 20) or f"VER-{index:03d}",
            "reason": reason,
            "what_cannot_be_verified": _text(item.get("what_cannot_be_verified"), 2000),
            "required_check": _text(item.get("required_check") or item.get("required_field_document_check"), 2000),
            "priority": _priority(item.get("priority"), "medium"),
            "photo_index": _photo_index(item.get("photo_index", 0), photo_count=photo_count),
        })
    return items


def _critical_alerts_to_findings(raw: Any, *, photo_count: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    converted: list[dict[str, Any]] = []
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        copy.setdefault("suggested_priority", "critical")
        copy.setdefault("evidence_class", "directly_observed")
        copy.setdefault("finding_code", copy.get("finding_id") or "CRIT")
        copy["photo_index"] = _photo_index(copy.get("photo_index", 0), photo_count=photo_count)
        converted.append(copy)
    return converted


def _parse_provider_json(payload: dict[str, Any]) -> Any:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise FieldAiProviderError("AI yanıtında choices bulunamadı.")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise FieldAiProviderError("AI yanıtında JSON içerik bulunamadı.")
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.startswith("json"):
            clean = clean[4:].lstrip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as exc:
        raise FieldAiProviderError("AI yanıtı geçerli JSON değil.") from exc


def _normalize(raw: Any, *, photo_count: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise FieldAiProviderError("AI çıktısı nesne olmalıdır.")
    findings_raw = raw.get("findings")
    if not isinstance(findings_raw, list):
        findings_raw = []
    findings_raw = list(findings_raw) + _critical_alerts_to_findings(raw.get("critical_alerts"), photo_count=photo_count)
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, int]] = set()
    for item in findings_raw[:60]:
        if not isinstance(item, dict):
            continue
        evidence = _text(item.get("visual_evidence") or item.get("observed_condition") or item.get("evidence"), 4000)
        nonconformity = _text(
            item.get("nonconformity_description")
            or item.get("observed_condition")
            or item.get("description"),
            4000,
        )
        hazard_name = _text(item.get("hazard_name") or item.get("title"), 220)
        # Kanıt ve açıklama yoksa provider'ın tahmini sonuç olarak saklanmaz.
        if not evidence or not nonconformity or not hazard_name:
            continue
        evidence_class = _evidence_class(item.get("evidence_class"))
        if evidence_class and evidence_class not in _CONFIRMED_EVIDENCE_CLASSES:
            warnings.append("Doğrulama gerektiren veya yetersiz kanıtlı AI taslağı confirmed bulgu olarak saklanmadı.")
            continue
        confidence = _confidence(item)
        if confidence is not None and confidence < 0.45:
            warnings.append("Düşük güvenli AI taslağı confirmed bulgu olarak saklanmadı; uzman doğrulaması gerekir.")
            continue
        box = _bbox(item.get("bbox") or item.get("bounding_box"))
        if box is None:
            warnings.append("AI çıktısındaki bulgu geçerli bir işaret koordinatı içermedi; taslak saklanmadı.")
            continue
        photo_index = _photo_index(item.get("photo_index", 0), photo_count=photo_count)
        category = _text(item.get("category_name") or item.get("category"), 180)
        if category not in FIELD_HAZARD_CATEGORIES:
            category = None
        priority = _priority(item.get("suggested_priority") or item.get("priority") or item.get("visual_priority"))
        key = (hazard_name.casefold(), evidence.casefold(), photo_index)
        if key in seen:
            continue
        seen.add(key)
        harm = _text(item.get("possible_harm") or item.get("potential_consequence") or item.get("harm"), 3000)
        cause = _text(item.get("possible_cause") or item.get("hazard_mechanism") or item.get("cause"), 3000)
        urgent = _text(item.get("urgent_action") or item.get("immediate_temporary_control"), 3000)
        corrective = _text(item.get("corrective_action") or item.get("permanent_corrective_action"), 3000)
        uncertainty = _text(item.get("uncertainty_note") or item.get("uncertainty") or item.get("location_in_image"), 2000)
        if evidence_class:
            class_note = "Doğrudan gözlenen görsel kanıt." if evidence_class == "directly_observed" else "Güçlü görsel destek; saha teyidi önerilir."
            uncertainty = " ".join(part for part in (class_note, uncertainty) if part)[:2000]
        findings.append({
            "photo_index": photo_index,
            "hazard_name": hazard_name,
            "category_name": category,
            "visual_evidence": evidence,
            "nonconformity_description": nonconformity,
            "possible_cause": cause,
            "possible_harm": harm,
            "possible_accident_or_disease": _text(item.get("possible_accident_or_disease") or item.get("accident"), 3000),
            "suggested_priority": priority,
            "priority_reason": _text(item.get("priority_reason"), 2000),
            "confidence": confidence,
            "uncertainty_note": uncertainty,
            "urgent_action": urgent,
            "corrective_action": corrective,
            "preventive_action": _text(item.get("preventive_action"), 3000),
            "engineering_control": _text(item.get("engineering_control"), 3000),
            "administrative_control": _text(item.get("administrative_control"), 3000),
            "training_need": _text(item.get("training_need"), 2000),
            "required_ppe": _text(item.get("required_ppe"), 2000),
            "suggested_responsible_role": _text(item.get("suggested_responsible_role") or item.get("responsible_role"), 180),
            "suggested_term_date": _parse_date(item.get("suggested_term_date")),
            "annotation_label": _annotation_label(item),
            "bbox": box,
            "legal_references": _legal_references(item, warnings),
        })
    warning_parts = [
        _text(raw.get("warning"), 3000),
        _text(raw.get("limitations"), 2000),
        *_text_list(raw.get("verification_items"), photo_count=photo_count),
        *dict.fromkeys(warnings),
    ]
    warning = " ".join(part for part in warning_parts if part)[:4000] or None
    assessment = _compose_general_assessment(raw)
    return {
        "general_assessment": assessment,
        "warning": warning,
        "findings": findings,
    }


def _text_list(raw: Any, *, photo_count: int) -> list[str]:
    notes: list[str] = []
    for item in _verification_items(raw, photo_count=photo_count):
        bits = [item.get("verification_id"), item.get("reason"), item.get("required_check")]
        notes.append("Doğrulama: " + " — ".join(part for part in bits if part))
    return notes


def _compose_general_assessment(raw: dict[str, Any]) -> str | None:
    parts = [
        _text(raw.get("general_assessment") or raw.get("summary"), 3500),
        _text(raw.get("scene_inventory"), 1500),
    ]
    quality = _text(raw.get("image_quality"), 40)
    status = _text(raw.get("overall_visual_safety_status"), 80)
    if quality:
        parts.append(f"Görüntü kalitesi: {quality}.")
    if status:
        parts.append(f"Görsel güvenlik durumu (taslak): {status}.")
    positives = raw.get("positive_observations")
    if isinstance(positives, list):
        clean = [text for text in (_text(item, 240) for item in positives[:8]) if text]
        if clean:
            parts.append("Olumlu gözlemler: " + "; ".join(clean) + ".")
    combined = " ".join(part for part in parts if part)
    return combined[:5000] if combined else None


def analyze_field_images(*, context: dict[str, Any], photos: list[tuple[Any, bytes]]) -> dict[str, Any]:
    """Provider'a optimize kopyaları gönderip güvenli, normalize edilmiş taslak döndürür."""
    if not field_ai_is_configured():
        raise FieldAiNotConfigured(
            "Görsel AI yapılandırılmamış veya kapalı. Anahtar, veri işleme izni ve feature flag birlikte açılmalıdır."
        )
    if not photos:
        raise FieldAiProviderError("Analiz için en az bir fotoğraf gereklidir.")
    descriptions = {
        "company": context.get("company_name"),
        "site": context.get("site_name"),
        "area": context.get("area_name"),
        "equipment": context.get("equipment_name"),
        "workplace_type": context.get("site_type"),
        "nace_code": context.get("nace_code"),
        "hazard_class": context.get("hazard_class"),
        "selected_categories": context.get("selected_categories") or [],
        "selected_hazards": context.get("selected_hazards") or [],
        "gps_status": context.get("gps_status"),
        "inspection_date": context.get("inspection_date"),
        "photo_context": context.get("photo_context") or [],
    }
    user_content: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            "Aşağıdaki bağlamı yalnızca yardımcı veri olarak kullan; görsel kanıtı aşma. "
            "Bağlam fotoğrafta görünmeyen tehlikeyi kanıtlamaz. Seçili kategoriler diğer görünür tehlikeleri dışlamaz. "
            "Madde/fıkra numarası, ölçüm değeri ve hukuki ihlal kararı üretme. "
            "Yalnızca doğrudan gözlenen veya güçlü desteklenen, bbox'lu bulguları findings'e koy. "
            "COUNTRY=Türkiye. BAĞLAM:\n" + json.dumps(descriptions, ensure_ascii=False)
        ),
    }]
    for index, (photo, data) in enumerate(photos):
        content_type = str(getattr(photo, "content_type", "image/jpeg") or "image/jpeg")
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            content_type = "image/jpeg"
        encoded = base64.b64encode(data).decode("ascii")
        user_content.append({"type": "text", "text": f"FOTOĞRAF {index + 1} (photo_index={index})"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}})
    request_body = {
        "model": str(getattr(settings, "field_ai_model", "") or ""),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": FIELD_AI_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {_field_ai_api_key()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=float(getattr(settings, "field_ai_timeout_seconds", 60))) as client:
            response = client.post(str(settings.field_ai_api_url).strip(), headers=headers, json=request_body)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise FieldAiProviderError(f"AI sağlayıcısı yanıt vermedi: {exc}") from exc
    return _normalize(_parse_provider_json(payload), photo_count=len(photos))


def run_visual_field_analysis_job(inspection_id: int) -> dict[str, Any]:
    """İş kuyruğu handler'ı: bir denetimin AI taslağını üretir.

    Handler top-level ve import edilebilir tutulur; Redis worker başka process'te
    de aynı davranışı sürdürebilir. Hata durumunda DB'ye açık hata yazılır ve
    hiçbir varsayımsal bulgu eklenmez.
    """
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.database import SessionLocal
    from app.models.field_inspection import (
        FieldHazardCategory,
        FieldHazard,
        FieldInspection,
        FieldInspectionArea,
        FieldInspectionEquipment,
        FieldInspectionAnnotation,
        FieldInspectionFinding,
        FieldInspectionLegalReference,
        FieldInspectionSite,
    )
    from app.models.entities import Company, User
    from app.services.audit import add_audit_log
    from app.services.field_inspection_media import render_marked_photo
    from app.services.object_store import get_object_store

    db = SessionLocal()
    inspection = None
    try:
        inspection = db.scalar(
            select(FieldInspection)
            .options(selectinload(FieldInspection.photos))
            .where(FieldInspection.id == int(inspection_id), FieldInspection.deleted_at.is_(None))
        )
        if not inspection:
            return {"status": "missing", "inspection_id": inspection_id}
        inspection.ai_status = "running"
        inspection.ai_error = None
        db.commit()
        if not field_ai_is_configured():
            raise FieldAiNotConfigured(
                "Görsel AI yapılandırılmamış veya kapalı. Bulgular oluşturulmadı."
            )
        active_photos = [photo for photo in inspection.photos if photo.deleted_at is None]
        if not active_photos:
            raise FieldAiProviderError("Analiz için aktif fotoğraf bulunmuyor.")
        company = db.get(Company, inspection.company_id)
        site = db.get(FieldInspectionSite, inspection.site_id)
        area = db.get(FieldInspectionArea, inspection.area_id)
        equipment = db.get(FieldInspectionEquipment, inspection.equipment_id) if inspection.equipment_id else None
        categories = list(db.scalars(select(FieldHazardCategory).where(FieldHazardCategory.is_active.is_(True))).all())
        category_map = {row.id: row for row in categories}
        try:
            selected_ids = json.loads(inspection.selected_category_ids_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            selected_ids = []
        try:
            selected_hazard_ids = json.loads(inspection.selected_hazard_ids_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            selected_hazard_ids = []
        hazards = list(db.scalars(select(FieldHazard).where(FieldHazard.id.in_(selected_hazard_ids))).all()) if selected_hazard_ids else []
        context = {
            "company_name": getattr(company, "name", None),
            "site_name": getattr(site, "name", None),
            "site_type": getattr(site, "site_type", None),
            "area_name": getattr(area, "name", None),
            "equipment_name": getattr(equipment, "name", None) if equipment else None,
            "nace_code": getattr(company, "nace_code", None),
            "hazard_class": getattr(company, "hazard_class", None),
            "selected_categories": [category_map[item].name for item in selected_ids if item in category_map],
            "selected_hazards": [item.name for item in hazards],
            "gps_status": inspection.gps_status,
            "inspection_date": inspection.inspection_date.isoformat() if inspection.inspection_date else None,
        }
        photo_context = []
        for index, photo in enumerate(active_photos):
            photo_site = db.get(FieldInspectionSite, photo.site_id) if photo.site_id else None
            photo_area = db.get(FieldInspectionArea, photo.area_id) if photo.area_id else None
            photo_equipment = db.get(FieldInspectionEquipment, photo.equipment_id) if photo.equipment_id else None
            photo_context.append({
                "photo_index": index,
                "site": getattr(photo_site, "name", None),
                "area": getattr(photo_area, "name", None),
                "equipment": getattr(photo_equipment, "name", None),
                "gps_lat": photo.gps_lat,
                "gps_lng": photo.gps_lng,
                "gps_accuracy_m": photo.gps_accuracy_m,
                "gps_status": photo.gps_status,
            })
        context["photo_context"] = photo_context
        store = get_object_store()
        inputs = [(photo, store.get_bytes(photo.analysis_storage_path)) for photo in active_photos]
        result = analyze_field_images(context=context, photos=inputs)
        old_drafts = list(db.scalars(select(FieldInspectionFinding).where(
            FieldInspectionFinding.inspection_id == inspection.id,
            FieldInspectionFinding.source == "ai",
            FieldInspectionFinding.status.in_(["ai_draft", "under_review"]),
        )).all())
        for old in old_drafts:
            old.status = "superseded"
        current_max = max((int(row.finding_no or 0) for row in inspection.findings), default=0)
        for item in result.get("findings", []):
            current_max += 1
            photo_index = int(item.get("photo_index", 0))
            photo = active_photos[min(max(photo_index, 0), len(active_photos) - 1)]
            category = next((row for row in categories if row.name == item.get("category_name")), None)
            finding = FieldInspectionFinding(
                inspection_id=inspection.id,
                photo_id=photo.id,
                field_category_id=category.id if category else None,
                finding_no=current_max,
                category_name=category.name if category else item.get("category_name"),
                hazard_name=item["hazard_name"],
                area_name=getattr(area, "name", None),
                equipment_name=getattr(equipment, "name", None) if equipment else None,
                visual_evidence=item["visual_evidence"],
                nonconformity_description=item["nonconformity_description"],
                possible_cause=item.get("possible_cause"),
                possible_harm=item.get("possible_harm"),
                possible_accident_or_disease=item.get("possible_accident_or_disease"),
                suggested_priority=item.get("suggested_priority") or "medium",
                priority_reason=item.get("priority_reason"),
                confidence=item.get("confidence"),
                uncertainty_note=item.get("uncertainty_note"),
                urgent_action=item.get("urgent_action"),
                corrective_action=item.get("corrective_action"),
                preventive_action=item.get("preventive_action"),
                engineering_control=item.get("engineering_control"),
                administrative_control=item.get("administrative_control"),
                training_need=item.get("training_need"),
                required_ppe=item.get("required_ppe"),
                suggested_responsible_role=item.get("suggested_responsible_role"),
                suggested_term_date=(date.fromisoformat(item["suggested_term_date"]) if item.get("suggested_term_date") else None),
                status="ai_draft",
                source="ai",
                ai_model_name=str(getattr(settings, "field_ai_model", "") or "")[:120],
                ai_model_version=str(getattr(settings, "field_ai_model_version", "") or "")[:80],
                ai_prompt_version=str(getattr(settings, "field_ai_prompt_version", None) or FIELD_AI_PROMPT_VERSION)[:40],
                created_by_id=inspection.created_by_id,
            )
            db.add(finding)
            db.flush()
            for reference in item.get("legal_references", []):
                db.add(FieldInspectionLegalReference(finding_id=finding.id, **reference))
            box = item.get("bbox")
            if box:
                annotation = FieldInspectionAnnotation(
                    inspection_id=inspection.id, photo_id=photo.id, finding_id=finding.id,
                    shape_type="rectangle", x=box["x"], y=box["y"], width=box["width"], height=box["height"],
                    label=_annotation_label(item, finding_no=finding.finding_no)[:80],
                    color=_PRIORITY_COLORS.get(finding.suggested_priority, "#d97706"),
                    source="ai", created_by_id=inspection.created_by_id,
                )
                db.add(annotation)
        db.flush()
        for photo in active_photos:
            annotations = list(db.scalars(select(FieldInspectionAnnotation).where(
                FieldInspectionAnnotation.photo_id == photo.id,
                FieldInspectionAnnotation.is_deleted.is_(False),
            )).all())
            if annotations:
                marked = render_marked_photo(analysis_bytes=store.get_bytes(photo.analysis_storage_path), annotations=annotations)
                store.put_bytes(photo.marked_storage_path, marked)
        inspection.ai_status = "completed"
        inspection.ai_analysis_at = datetime.utcnow()
        inspection.ai_model_name = str(getattr(settings, "field_ai_model", "") or "")[:120]
        inspection.ai_model_version = str(getattr(settings, "field_ai_model_version", "") or "")[:80]
        inspection.ai_prompt_version = str(getattr(settings, "field_ai_prompt_version", None) or FIELD_AI_PROMPT_VERSION)[:40]
        inspection.ai_general_assessment = result.get("general_assessment")
        inspection.ai_warning = result.get("warning")
        inspection.status = "in_review"
        add_audit_log(db, user=db.get(User, inspection.created_by_id), action="field_ai_completed", entity_type="field_inspection", entity_id=str(inspection.id), description=f"Görsel AI taslağı tamamlandı; {len(result.get('findings', []))} bulgu uzman onayı bekliyor.", module="field_inspection")
        db.commit()
        return {"status": "completed", "inspection_id": inspection.id, "finding_count": len(result.get("findings", []))}
    except FieldAiNotConfigured as exc:
        if inspection:
            inspection.ai_status = "not_configured"
            inspection.ai_error = str(exc)[:4000]
            inspection.status = "draft"
            db.commit()
        return {"status": "failed", "inspection_id": inspection_id, "error": str(exc)}
    except Exception as exc:
        logger.exception("Visual field analysis failed: inspection_id=%s", inspection_id)
        if inspection:
            db.rollback()
            inspection = db.get(FieldInspection, inspection_id)
            if inspection:
                inspection.ai_status = "failed"
                inspection.ai_error = "AI analizi başarısız oldu; sahte bulgu oluşturulmadı. " + str(exc)[:3800]
                inspection.status = "draft"
                db.commit()
        return {"status": "failed", "inspection_id": inspection_id, "error": str(exc)}
    finally:
        db.close()
