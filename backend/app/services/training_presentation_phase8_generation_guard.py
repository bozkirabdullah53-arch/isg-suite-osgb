"""Phase 8 render guard for traceable NACE presentation manifests.

Historical generated/approved files remain readable. When Phase 8 is active,
only a new render action is gated: draft/failed versions without valid 20/20
question-slide-source traceability are rejected before object-storage writes.

Phase 9 is installed from this already source-controlled startup hook so the
main application bootstrap stays unchanged. Phase 9 itself is separately
feature-gated and delegates to Phase 8 while disabled. Its final scope guard
keeps the v2 instructor marker only on fully reviewed five-topic profiles.
"""
from __future__ import annotations

import json
from functools import wraps

from app.services.training_presentation_phase8 import phase8_active, validate_manifest_traceability


def install_phase8_generation_guard() -> dict[str, str]:
    from app.api import training_presentation as api_module
    from app.services import training_presentation_generation as generation
    from app.services.training_presentation_phase9 import install_training_presentation_phase9
    from app.services.training_presentation_phase9_scope_guard import install_phase9_scope_guard

    phase9_status = install_training_presentation_phase9()
    phase9_scope_status = install_phase9_scope_guard()
    current = generation.generate_and_store_version
    if getattr(current, "_phase8_generation_guard_active", False):
        return {
            "generation_guard": "already-active",
            "enabled": str(phase8_active()).lower(),
            "phase9": str(phase9_status.get("enabled", "false")),
            "phase9_scope": str(phase9_scope_status.get("phase9_scope_guard", "already-active")),
        }

    @wraps(current)
    def guarded_generate(db, *, row, store=None):
        if phase8_active():
            try:
                manifest = json.loads(str(getattr(row, "manifest_json", "") or "{}"))
                validate_manifest_traceability(manifest)
            except (TypeError, json.JSONDecodeError, ValueError) as exc:
                raise generation.PresentationGenerationError(
                    "traceability_not_ready",
                    "Phase 8 aktifken yalnız 20/20 soru-slayt-kaynak izlenebilirliği taşıyan yeni sunum sürümü üretilebilir. Yeni sürüm oluşturun.",
                ) from exc
        return current(db, row=row, store=store)

    guarded_generate._phase8_generation_guard_active = True
    generation.generate_and_store_version = guarded_generate
    api_module.generate_and_store_version = guarded_generate
    return {
        "generation_guard": "active",
        "enabled": str(phase8_active()).lower(),
        "phase9": str(phase9_status.get("enabled", "false")),
        "phase9_scope": str(phase9_scope_status.get("phase9_scope_guard", "active")),
    }
