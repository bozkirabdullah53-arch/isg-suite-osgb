"""Append-only instructor editing for NACE training presentations.

An instructor never mutates an existing generated/approved presentation. Every
edit creates a new draft version that keeps the original source snapshot and
historical files intact. This preserves auditability and makes rollback a simple
matter of using the previous version.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.training_presentation import TrainingPresentationVersion
from app.services.training_presentation_renderer import verify_manifest
from app.services.training_presentation_teaching_v3 import enrich_manifest_for_teaching_v3


class PresentationEditError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _rehash(manifest: dict[str, Any]) -> None:
    manifest.pop("content_hash", None)
    payload = _canonical_json(manifest).encode("utf-8")
    manifest["content_hash"] = hashlib.sha256(payload).hexdigest()


def _clean(value: object, *, max_len: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) > max_len:
        raise PresentationEditError("editor_text_too_long", f"Sunum düzenleme metni {max_len} karakteri aşamaz.")
    return text


def _custom_blocks(update: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lesson_points = update.get("lesson_points") or []
    if not isinstance(lesson_points, list):
        raise PresentationEditError("invalid_lesson_points", "Ders anlatım maddeleri liste olmalıdır.")
    for value in lesson_points[:8]:
        text = _clean(value, max_len=420)
        if text:
            blocks.append({"type": "lesson_point", "value": text, "editor_authored": True})
    for field, kind, limit in (
        ("scenario", "case_scenario", 900),
        ("key_takeaway", "key_takeaway", 500),
        ("instructor_note", "instructor_note", 1400),
    ):
        text = _clean(update.get(field), max_len=limit)
        if text:
            blocks.append({"type": kind, "value": text, "editor_authored": True})
    if not blocks:
        raise PresentationEditError("empty_slide_edit", "En az bir ders maddesi, vaka, ana mesaj veya eğitmen notu girilmelidir.")
    return blocks


def _source_refs_for_new_slide(manifest: dict[str, Any]) -> list[str]:
    for slide in manifest.get("slides") or []:
        if str(slide.get("section_id") or "") == "work_specific_topics":
            refs = [str(item) for item in (slide.get("source_refs") or []) if str(item).strip()]
            if refs:
                return refs
    return [
        str(item.get("source_id"))
        for item in (manifest.get("source_registry") or [])
        if isinstance(item, dict) and item.get("source_id")
    ][:4]


def build_edited_manifest(
    source_manifest: dict[str, Any],
    *,
    source_version_id: int,
    source_version: int,
    edited_by_id: int | None,
    slide_updates: list[dict[str, Any]] | None = None,
    append_slides: list[dict[str, Any]] | None = None,
    change_note: str | None = None,
    auto_enrich_teaching_v3: bool = False,
) -> dict[str, Any]:
    """Copy and edit a manifest while preserving old slide positions."""
    try:
        verify_manifest(source_manifest)
    except ValueError as exc:
        raise PresentationEditError("invalid_source_manifest", str(exc)) from exc

    manifest = deepcopy(source_manifest)
    slides = [dict(item) for item in (manifest.get("slides") or [])]
    by_position = {int(slide.get("position") or 0): slide for slide in slides}
    if set(by_position) != set(range(1, len(slides) + 1)):
        raise PresentationEditError("invalid_slide_positions", "Kaynak sunum slayt sırası kesintisiz değil.")

    edited_positions: list[int] = []
    for update in slide_updates or []:
        position = int(update.get("position") or 0)
        slide = by_position.get(position)
        if slide is None:
            raise PresentationEditError("slide_not_found", f"{position}. slayt bulunamadı.")
        mode = str(update.get("mode") or "append").strip().lower()
        if mode not in {"append", "replace"}:
            raise PresentationEditError("invalid_edit_mode", "Düzenleme modu append veya replace olmalıdır.")
        title = _clean(update.get("title"), max_len=220)
        if title:
            slide["title"] = title
        blocks = _custom_blocks(update)
        original = deepcopy(slide.get("content_blocks") or [])
        if mode == "replace":
            # Original evidence remains inside the new version for audit/rollback,
            # while the displayed lesson blocks become instructor-authored.
            slide["editor_original_content_blocks"] = original
            slide["content_blocks"] = blocks
        else:
            slide["content_blocks"] = original + blocks
        slide["approval_required"] = True
        slide["editor_revision"] = {
            "mode": mode,
            "edited_by_id": edited_by_id,
            "source_version_id": source_version_id,
        }
        edited_positions.append(position)

    refs = _source_refs_for_new_slide(manifest)
    for addition in append_slides or []:
        blocks = _custom_blocks(addition)
        title = _clean(addition.get("title"), max_len=220)
        if not title:
            raise PresentationEditError("new_slide_title_required", "Yeni slayt için başlık zorunludur.")
        position = len(slides) + 1
        slide = {
            "position": position,
            "section_id": "work_specific_topics",
            "title": title,
            "source_refs": refs,
            "content_blocks": blocks,
            "speaker_notes_required": True,
            "approval_required": True,
            "editor_revision": {
                "mode": "new_slide",
                "edited_by_id": edited_by_id,
                "source_version_id": source_version_id,
            },
        }
        slides.append(slide)
        by_position[position] = slide
        edited_positions.append(position)

    if not edited_positions and not auto_enrich_teaching_v3:
        raise PresentationEditError("no_changes", "Yeni sunum sürümünde uygulanacak değişiklik bulunmuyor.")

    manifest["slides"] = slides
    manifest["slide_count"] = len(slides)
    approval = dict(manifest.get("approval") or {})
    required = {int(value) for value in (approval.get("required_slide_positions") or []) if int(value) > 0}
    required.update(edited_positions)
    approval["status"] = "specialist_review_required"
    approval["required_slide_positions"] = sorted(required)
    manifest["approval"] = approval
    manifest["editor"] = {
        "mode": "append_only_versioning",
        "source_version_id": int(source_version_id),
        "source_version": int(source_version),
        "edited_by_id": edited_by_id,
        "edited_positions": sorted(edited_positions),
        "change_note": _clean(change_note, max_len=800) or None,
        "edited_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }

    if auto_enrich_teaching_v3:
        manifest = enrich_manifest_for_teaching_v3(manifest)
    else:
        _rehash(manifest)

    try:
        verify_manifest(manifest)
    except ValueError as exc:
        raise PresentationEditError("edited_manifest_invalid", str(exc)) from exc
    return manifest


def create_edited_draft_version(
    db: Session,
    *,
    source_row: TrainingPresentationVersion,
    created_by_id: int | None,
    slide_updates: list[dict[str, Any]] | None = None,
    append_slides: list[dict[str, Any]] | None = None,
    change_note: str | None = None,
    auto_enrich_teaching_v3: bool = False,
) -> TrainingPresentationVersion:
    """Persist one new draft; source version and old files are never modified."""
    if not nace_training_presentation_active(getattr(source_row, "company_id", None)):
        raise PresentationEditError("pilot_access_denied", "NACE eğitim sunumu bu şirket için kontrollü pilot erişimine açık değildir.")
    try:
        source_manifest = json.loads(str(source_row.manifest_json or "{}"))
    except json.JSONDecodeError as exc:
        raise PresentationEditError("invalid_source_manifest", "Kaynak sunum manifesti okunamadı.") from exc

    manifest = build_edited_manifest(
        source_manifest,
        source_version_id=int(source_row.id),
        source_version=int(source_row.version),
        edited_by_id=created_by_id,
        slide_updates=slide_updates,
        append_slides=append_slides,
        change_note=change_note,
        auto_enrich_teaching_v3=auto_enrich_teaching_v3,
    )
    current_max = db.scalar(
        select(func.max(TrainingPresentationVersion.version)).where(
            TrainingPresentationVersion.training_id == source_row.training_id
        )
    )
    row = TrainingPresentationVersion(
        training_id=int(source_row.training_id),
        company_id=int(source_row.company_id),
        branch_id=source_row.branch_id,
        nace_snapshot_id=source_row.nace_snapshot_id,
        version=int(current_max or 0) + 1,
        status="draft",
        contract_version=str(manifest.get("contract_version") or source_row.contract_version),
        contract_hash=str(manifest.get("contract_hash") or source_row.contract_hash),
        template_version=str(manifest.get("template_version") or source_row.template_version),
        manifest_version=str(manifest.get("manifest_version") or source_row.manifest_version),
        manifest_json=_canonical_json(manifest),
        manifest_hash=str(manifest["content_hash"]),
        catalog_key=source_row.catalog_key,
        nace_code=source_row.nace_code,
        nace_description=source_row.nace_description,
        hazard_class=source_row.hazard_class,
        content_profile_code=source_row.content_profile_code,
        catalog_version=source_row.catalog_version,
        catalog_hash=source_row.catalog_hash,
        source_snapshot_json=source_row.source_snapshot_json,
        training_topics_json=source_row.training_topics_json,
        technical_risk_tags_json=source_row.technical_risk_tags_json,
        special_risks_json=source_row.special_risks_json,
        output_formats_json=source_row.output_formats_json,
        primary_output_format=source_row.primary_output_format,
        created_by_id=created_by_id,
    )
    db.add(row)
    db.flush()
    return row
