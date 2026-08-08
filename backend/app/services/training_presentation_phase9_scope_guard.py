"""Final Phase 9 manifest scope guard.

The Phase 9 compatibility layer is installed after Phase 8 and may evaluate any
new traceable manifest while the global Phase 9 flag is enabled. This guard
ensures that the v2 instructor UI marker and curated slide source references are
retained only when all five training topics belong to the reviewed Phase 9
coverage pack. Existing Phase 8-only profiles remain v1.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable

from app.services.training_presentation_phase9 import (
    INSTRUCTOR_UI_VERSION,
    phase9_active,
    phase9_coverage_readiness,
    resolve_phase9_topic_knowledge,
)


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_refs(pack: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for source in pack.get("sources") or []:
        if not isinstance(source, dict):
            value = str(source or "").strip()
        else:
            value = str(source.get("url") or source.get("title") or "").strip()
        if value and value not in refs:
            refs.append(value)
    return refs


def finalize_phase9_manifest_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(manifest)
    topics = list(result.get("training_topics") or [])
    coverage = phase9_coverage_readiness(topics)
    rendering = dict(result.get("rendering") or {})

    if not coverage["phase9_full_profile"]:
        result.pop("coverage_v2", None)
        rendering.pop("instructor_mode_ui", None)
        rendering.pop("coverage_v2_active", None)
        result["rendering"] = rendering
        result.pop("content_hash", None)
        result["content_hash"] = _canonical_hash(result)
        return result

    work_slides = [
        slide for slide in result.get("slides") or []
        if str(slide.get("section_id") or "") == "work_specific_topics"
    ]
    if len(work_slides) != 5:
        raise ValueError(f"Phase 9 için beş işe özgü slayt bekleniyor; bulunan: {len(work_slides)}")

    for topic, slide in zip(topics, work_slides, strict=True):
        pack = resolve_phase9_topic_knowledge(topic)
        if pack is None:
            raise ValueError(f"Phase 9 kaynak paketi bulunamadı: {topic}")
        refs = _source_refs(pack)
        if not refs:
            raise ValueError(f"Phase 9 kaynak referansı bulunamadı: {topic}")
        slide["source_refs"] = refs
        slide["coverage_v2_source_controlled"] = True

    rendering["instructor_mode_ui"] = INSTRUCTOR_UI_VERSION
    rendering["coverage_v2_active"] = True
    result["rendering"] = rendering
    result["coverage_v2"] = coverage
    result.pop("content_hash", None)
    result["content_hash"] = _canonical_hash(result)
    return result


def install_phase9_scope_guard() -> dict[str, str]:
    from app.services import training_presentation_phase8 as phase8

    current: Callable[..., dict[str, Any]] = phase8.enrich_manifest_with_traceability
    if getattr(current, "_phase9_scope_guard_active", False):
        return {"phase9_scope_guard": "already-active", "enabled": str(phase9_active()).lower()}

    original = current

    def scoped_enricher(manifest: dict[str, Any], snapshot: Any) -> dict[str, Any]:
        result = original(manifest, snapshot)
        if not phase9_active():
            return result
        result = finalize_phase9_manifest_scope(result)
        phase8.validate_manifest_traceability(result)
        return result

    scoped_enricher._phase9_scope_guard_active = True
    phase8.enrich_manifest_with_traceability = scoped_enricher
    return {"phase9_scope_guard": "active", "enabled": str(phase9_active()).lower()}
