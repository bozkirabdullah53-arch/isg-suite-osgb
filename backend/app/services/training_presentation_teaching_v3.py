"""Grounded teaching enrichment for NACE presentation manifests.

The existing frozen manifest remains the source. This module only adds teaching
structure and vector-visual instructions derived from content that is already in
the manifest (topic, risk, hazard/control/safe-behaviour blocks). It does not
fetch web images or invent workplace-specific facts.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

TEACHING_V3_VERSION = "nace-training-teaching-v3"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _rehash(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest.pop("content_hash", None)
    manifest["content_hash"] = hashlib.sha256(_canonical_bytes(manifest)).hexdigest()
    return manifest


def _clean(value: object, limit: int = 700) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].rstrip()


def _first_value(blocks: list[dict[str, Any]], kinds: set[str]) -> str:
    for block in blocks:
        if str(block.get("type") or "") in kinds:
            value = _clean(block.get("value"))
            if value:
                return value
    return ""


def _all_values(blocks: list[dict[str, Any]], kinds: set[str]) -> list[str]:
    values: list[str] = []
    for block in blocks:
        if str(block.get("type") or "") not in kinds:
            continue
        value = _clean(block.get("value"))
        if value and value not in values:
            values.append(value)
    return values


def _append_once(blocks: list[dict[str, Any]], block: dict[str, Any]) -> None:
    kind = str(block.get("type") or "")
    value = _clean(block.get("value"))
    for current in blocks:
        if str(current.get("type") or "") == kind and _clean(current.get("value")) == value:
            return
    blocks.append(block)


def enrich_manifest_for_teaching_v3(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a new, hash-valid teaching manifest without changing the input."""
    result = deepcopy(manifest)
    slides = list(result.get("slides") or [])
    topics = [_clean(item, 300) for item in (result.get("training_topics") or []) if _clean(item, 300)]
    risks = [_clean(item, 160) for item in (result.get("technical_risk_tags") or []) if _clean(item, 160)]

    for slide in slides:
        blocks = [dict(item) for item in (slide.get("content_blocks") or []) if isinstance(item, dict)]
        section = str(slide.get("section_id") or "")
        title = _clean(slide.get("title"), 260) or "Eğitim konusu"

        if section == "work_specific_topics":
            hazard = _first_value(blocks, {"tehlike", "hazard"})
            controls = _all_values(blocks, {"kontrol_tedbiri", "control_measure"})
            safe_behavior = _first_value(blocks, {"guvenli_davranis", "safe_behavior"})
            _append_once(blocks, {
                "type": "learning_objective",
                "value": f"Katılımcı, {title} konusunda tehlikeyi tanıyıp uygun kontrolü ve güvenli davranışı açıklayabilmelidir.",
                "teaching_v3": True,
            })
            explanation = hazard or (
                f"Bu bölümde {title} konusu, işyerinin doğrulanmış NACE/risk kaydıyla birlikte ele alınır; "
                "işyerine özgü ayrıntılar eğitmen tarafından risk değerlendirmesiyle doğrulanır."
            )
            _append_once(blocks, {"type": "lesson_explanation", "value": explanation, "teaching_v3": True})
            scenario = (
                f"Vaka: Çalışma sırasında şu durum fark edildi: {hazard} Ne zaman çalışmayı durdurmalı, "
                "hangi kontrolü doğrulamalı ve kime bildirmelisiniz?"
                if hazard
                else f"Vaka: {title} ile ilgili sahada güvensiz bir durum fark ettiniz. Önce hangi tehlikeyi tanımlar, hangi kontrolü doğrularsınız?"
            )
            _append_once(blocks, {"type": "case_scenario", "value": scenario, "teaching_v3": True})
            _append_once(blocks, {
                "type": "check_question",
                "value": "Bu durumda tehlikeyi kaynağında azaltmak için ilk uygulanması gereken kontrol hangisidir?",
                "teaching_v3": True,
            })
            takeaway = safe_behavior or "Tehlikeyi tanı; kontrolün çalıştığını doğrula; güvensiz koşulda işi sürdürmeden bildir."
            _append_once(blocks, {"type": "key_takeaway", "value": takeaway, "teaching_v3": True})
            _append_once(blocks, {
                "type": "hazard_control_behavior_visual",
                "hazard": hazard or title,
                "controls": controls[:3],
                "safe_behavior": safe_behavior or takeaway,
                "teaching_v3": True,
            })

        elif section == "technical_risks":
            _append_once(blocks, {
                "type": "risk_map_visual",
                "values": risks[:8],
                "value": "Teknik risk haritası",
                "teaching_v3": True,
            })
        elif section == "control_measures":
            _append_once(blocks, {
                "type": "control_hierarchy_visual",
                "value": "Ortadan kaldırma → ikame/azaltma → mühendislik/toplu korunma → organizasyon → KKD",
                "teaching_v3": True,
            })
        elif section == "ppe":
            _append_once(blocks, {
                "type": "ppe_layers_visual",
                "value": "KKD, risk kontrol hiyerarşisinin son katmanıdır; seçim işyeri risk değerlendirmesiyle doğrulanır.",
                "teaching_v3": True,
            })
        elif section == "emergency":
            _append_once(blocks, {
                "type": "emergency_flow_visual",
                "value": "Tehlikeyi fark et → alarm/bildirim → güvenli tahliye → toplanma → sayım ve yetkili bildirimi",
                "teaching_v3": True,
            })
        elif section == "assessment":
            _append_once(blocks, {
                "type": "assessment_visual",
                "value": "5 temel + 15 işe özgü soru",
                "teaching_v3": True,
            })
        elif section == "summary":
            _append_once(blocks, {
                "type": "topic_map_visual",
                "values": topics[:5],
                "value": "Beş işe özgü konunun kapanış haritası",
                "teaching_v3": True,
            })

        slide["content_blocks"] = blocks

    result["slides"] = slides
    result["slide_count"] = len(slides)
    result["rendering"] = {
        **dict(result.get("rendering") or {}),
        "teaching_v3": True,
        "teaching_v3_version": TEACHING_V3_VERSION,
        "visual_layout": "vector-infographic",
        "instructor_editable_by_new_version": True,
    }
    result["teaching_v3"] = {
        "version": TEACHING_V3_VERSION,
        "grounding": "existing_manifest_only",
        "external_images": False,
        "visuals": [
            "hazard_control_behavior",
            "risk_map",
            "control_hierarchy",
            "ppe_layers",
            "emergency_flow",
            "assessment",
            "topic_map",
        ],
    }
    return _rehash(result)
