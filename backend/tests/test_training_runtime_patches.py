from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from app.services import training_pdfs
from app.services.training_runtime_patches import (
    NEW_HEADING,
    OLD_HEADINGS,
    _replace_heading,
    install_training_runtime_patches,
)


def test_premium_renderer_installation_is_idempotent():
    install_training_runtime_patches()
    installed = training_pdfs._draw_certificate_page
    assert getattr(installed, "_premium_renderer_active", False) is True

    status = install_training_runtime_patches()
    assert training_pdfs._draw_certificate_page is installed
    assert status["premium_certificate"] == "already-active"


def test_fourth_topic_heading_is_normalized():
    assert _replace_heading(OLD_HEADINGS[0]) == NEW_HEADING
    assert _replace_heading([OLD_HEADINGS[1]]) == [NEW_HEADING]


def test_compatibility_script_does_not_rewrite_training_source():
    backend_root = Path(__file__).resolve().parents[1]
    target = backend_root / "app" / "services" / "training_pdfs.py"
    script = backend_root / "scripts" / "activate_premium_training_pdf.py"
    before = target.read_bytes()

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=backend_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert target.read_bytes() == before
    assert "no build rewrite required" in result.stdout
