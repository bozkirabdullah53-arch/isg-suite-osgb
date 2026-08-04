"""Compatibility entrypoint for the source-controlled premium renderer.

Historically this script rewrote ``training_pdfs.py`` during Render builds.
The approved renderer is now installed by ``training_runtime_patches`` without
modifying tracked source files. The entrypoint remains temporarily so existing
Render service build commands stay backward compatible.
"""
from __future__ import annotations

from pathlib import Path

REQUIRED_FILES = (
    Path(__file__).resolve().parents[1] / "app" / "services" / "training_pdf_premium.py",
    Path(__file__).resolve().parents[1] / "app" / "services" / "training_runtime_patches.py",
)


def main() -> None:
    missing = [str(path) for path in REQUIRED_FILES if not path.is_file()]
    if missing:
        raise RuntimeError(f"Premium eğitim renderer kaynakları eksik: {', '.join(missing)}")
    print("premium training certificate renderer is source-controlled; no build rewrite required")


if __name__ == "__main__":
    main()
