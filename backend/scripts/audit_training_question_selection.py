"""Read-only smoke audit for exact-NACE question-selection runtime wiring."""
from __future__ import annotations

import os

from app.services.training_question_selection_v2 import (
    STRICT_ENV,
    exact_nace_exam_strict_active,
    install_exact_nace_question_selection,
)
from app.services.training_runtime_patches import install_training_runtime_patches


def main() -> int:
    legacy = install_training_runtime_patches()
    exact = install_exact_nace_question_selection()
    print(
        {
            "legacy_runtime": legacy,
            "exact_nace_runtime": exact,
            "strict_env": STRICT_ENV,
            "strict_env_raw": os.getenv(STRICT_ENV),
            "strict_active": exact_nace_exam_strict_active(),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
