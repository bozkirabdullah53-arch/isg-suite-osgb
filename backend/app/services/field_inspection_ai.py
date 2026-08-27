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
from app.services.field_inspection_catalog import FIELD_HAZARD_CATEGORIES, legal_entry

logger = logging.getLogger(__name__)


class FieldAiNotConfigured(RuntimeError):
    """AI çağrısı için güvenli ve açık yapılandırma bulunmadı."""


class FieldAiProviderError(RuntimeError):
    """Provider çağrısı veya çıktısı beklenen sözleşmeye uymadı."""


FIELD_AI_SYSTEM_PROMPT = """
Sen bir iş güvenliği uzmanına yardımcı olan görsel kanıt asistanısın. Yalnızca
fotoğrafta açıkça görülen, makul biçimde desteklenen unsurları yaz. Fotoğrafta
görünmeyen bir ekipman, ölçüm, kişi davranışı, mevzuat maddesi veya tehlikeyi
varsayma. Belirsizliği açıkça belirt. Nihai risk seviyesi, hukuki karar ve
uygunsuzluk onayı verme; tüm bulgular uzman onayı bekleyen taslaktır.

Yanıt yalnızca JSON olsun:
{
  "general_assessment": "...",
  "warning": "...",
  "findings": [
    {
      "photo_index": 0,
      "hazard_name": "...",
      "category_name": "katalogdaki tam ad veya null",
      "visual_evidence": "fotoğrafta görülen kanıt",
      "nonconformity_description": "uzman kontrolüne sunulan açıklama",
      "possible_cause": "...",
      "possible_harm": "...",
      "possible_accident_or_disease": "...",
      "suggested_priority": "low|medium|high|critical",
      "priority_reason": "...",
      "confidence": 0.0,
      "uncertainty_note": "...",
      "urgent_action": "...",
      "corrective_action": "...",
      "preventive_action": "...",
      "engineering_control": "...",
      "administrative_control": "...",
      "training_need": "...",
      "required_ppe": "...",
      "suggested_responsible_role": "...",
      "suggested_term_date": "YYYY-MM-DD veya null",
      "bbox": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
      "legal_references": [
        {"regulation_name": "başlık", "article": null, "paragraph": null, "relation_explanation": "..."}
      ]
    }
  ]
}

Madde numarası uydurma: article ve paragraph alanlarını yalnızca kesin
doğrulanmış bir kaynağın açıkça verdiği durumda doldur; aksi hâlde null.
Katalogdaki başlıkları aynen kullan, katalog dışı mevzuat ekleme.
""".strip()


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
    findings: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for item in findings_raw[:60]:
        if not isinstance(item, dict):
            continue
        evidence = _text(item.get("visual_evidence") or item.get("evidence"), 4000)
        nonconformity = _text(item.get("nonconformity_description") or item.get("description"), 4000)
        hazard_name = _text(item.get("hazard_name") or item.get("title"), 220)
        # Kanıt ve açıklama yoksa provider'ın tahmini sonuç olarak saklanmaz.
        if not evidence or not nonconformity or not hazard_name:
            continue
        box = _bbox(item.get("bbox") or item.get("bounding_box"))
        if box is None:
            warnings.append("AI çıktısındaki bulgu geçerli bir işaret koordinatı içermedi; taslak saklanmadı.")
            continue
        try:
            photo_index = int(item.get("photo_index", 0))
        except (TypeError, ValueError):
            photo_index = 0
        photo_index = max(0, min(max(photo_count - 1, 0), photo_index))
        category = _text(item.get("category_name") or item.get("category"), 180)
        if category not in FIELD_HAZARD_CATEGORIES:
            category = None
        priority = str(item.get("suggested_priority") or item.get("priority") or "medium").strip().lower()
        if priority not in {"low", "medium", "high", "critical"}:
            priority = "medium"
        confidence = _number(item.get("confidence"))
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
        key = (hazard_name.casefold(), evidence.casefold())
        if key in seen:
            continue
        seen.add(key)
        references: list[dict[str, Any]] = []
        for reference in item.get("legal_references") or item.get("legal_refs") or []:
            if not isinstance(reference, dict):
                continue
            name = _text(reference.get("regulation_name") or reference.get("name"), 300)
            entry = legal_entry(name)
            if not entry:
                warnings.append("AI çıktısındaki katalog dışı mevzuat atfı saklanmadı.")
                continue
            # Provider madde numarasını hiçbir durumda otomatik doğrulanmış
            # kabul etmiyoruz. Uzman daha sonra ayrı inceleme ile doldurabilir.
            references.append({
                "regulation_name": name,
                "article": None,
                "paragraph": None,
                "source_url": entry.get("source_url"),
                "source_version": entry.get("version") or "resmî kaynak uzman kontrolü",
                "relation_explanation": _text(reference.get("relation_explanation") or reference.get("explanation"), 2000),
                "verification_status": "needs_expert_review",
            })
        findings.append({
            "photo_index": photo_index,
            "hazard_name": hazard_name,
            "category_name": category,
            "visual_evidence": evidence,
            "nonconformity_description": nonconformity,
            "possible_cause": _text(item.get("possible_cause") or item.get("cause"), 3000),
            "possible_harm": _text(item.get("possible_harm") or item.get("harm"), 3000),
            "possible_accident_or_disease": _text(item.get("possible_accident_or_disease") or item.get("accident"), 3000),
            "suggested_priority": priority,
            "priority_reason": _text(item.get("priority_reason"), 2000),
            "confidence": confidence,
            "uncertainty_note": _text(item.get("uncertainty_note") or item.get("uncertainty"), 2000),
            "urgent_action": _text(item.get("urgent_action"), 3000),
            "corrective_action": _text(item.get("corrective_action"), 3000),
            "preventive_action": _text(item.get("preventive_action"), 3000),
            "engineering_control": _text(item.get("engineering_control"), 3000),
            "administrative_control": _text(item.get("administrative_control"), 3000),
            "training_need": _text(item.get("training_need"), 2000),
            "required_ppe": _text(item.get("required_ppe"), 2000),
            "suggested_responsible_role": _text(item.get("suggested_responsible_role"), 180),
            "suggested_term_date": _parse_date(item.get("suggested_term_date")),
            "bbox": box,
            "legal_references": references,
        })
    warning = _text(raw.get("warning"), 3000)
    if warnings:
        warning = " ".join(item for item in [warning, *dict.fromkeys(warnings)] if item)
    return {
        "general_assessment": _text(raw.get("general_assessment") or raw.get("summary"), 5000),
        "warning": warning,
        "findings": findings,
    }


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
            "Seçili kategoriler diğer görünür tehlikeleri dışlamaz. BAĞLAM:\n" + json.dumps(descriptions, ensure_ascii=False)
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
                ai_prompt_version=str(getattr(settings, "field_ai_prompt_version", "") or "")[:40],
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
                    label=f"#{finding.finding_no}", color="#b91c1c" if finding.suggested_priority in {"high", "critical"} else "#d97706",
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
        inspection.ai_prompt_version = str(getattr(settings, "field_ai_prompt_version", "") or "")[:40]
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
