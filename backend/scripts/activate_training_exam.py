"""Compatibility validator for source-controlled training exam behavior.

Historically this script rewrote training topic, question-bank and API modules
during Render builds and application startup. The approved behavior now lives
in ``training_runtime_patches.py`` and the exam endpoint is tracked directly in
``trainings.py``. This entrypoint remains temporarily for compatibility and
never writes to source files.
"""
from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SNIPPETS = {
    BACKEND_ROOT / "app" / "services" / "training_runtime_patches.py": (
        "_patch_sector_profile_resolution",
        "_patch_question_bank_candidates",
        "SECTOR_QUESTION_ALIASES",
    ),
    BACKEND_ROOT / "app" / "api" / "trainings.py": (
        'from app.services.training_exam_pdf import build_exam_pdf',
        '@router.get("/{training_id}/exam.pdf")',
        "db=db",
        "created_by_id=user.id",
    ),
}


def main() -> None:
    for path, snippets in REQUIRED_SNIPPETS.items():
        if not path.is_file():
            raise RuntimeError(f"Eğitim sınavı kaynağı eksik: {path}")
        source = path.read_text(encoding="utf-8")
        missing = [snippet for snippet in snippets if snippet not in source]
        if missing:
            raise RuntimeError(
                f"Eğitim sınavı kaynak kontrolü eksik ({path.name}): {', '.join(missing)}"
            )
    print("training exam features are source-controlled; no build rewrite required")


if __name__ == "__main__":
    main()
