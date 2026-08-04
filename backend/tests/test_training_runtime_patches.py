from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from app.services import training_pdfs, training_question_bank, training_topics
from app.services.training_runtime_patches import (
    NEW_HEADING,
    OLD_HEADINGS,
    _replace_heading,
    install_training_runtime_patches,
)


def test_training_runtime_installation_is_idempotent():
    install_training_runtime_patches()
    renderer = training_pdfs._draw_certificate_page
    resolver = training_topics.sektor_kodu_cozumle
    candidate_builder = training_question_bank._candidate_buckets

    assert getattr(renderer, "_premium_renderer_active", False) is True
    assert getattr(resolver, "_source_controlled_sector_resolver_active", False) is True
    assert getattr(
        candidate_builder,
        "_source_controlled_candidate_buckets_active",
        False,
    ) is True

    status = install_training_runtime_patches()
    assert training_pdfs._draw_certificate_page is renderer
    assert training_topics.sektor_kodu_cozumle is resolver
    assert training_question_bank._candidate_buckets is candidate_builder
    assert status["sector_profiles"] == "already-active"
    assert status["question_candidates"] == "already-active"
    assert status["premium_certificate"] == "already-active"


def test_battery_nace_resolves_to_approved_profile():
    install_training_runtime_patches()
    assert training_topics.sektor_kodu_cozumle("27.20.01") == "aku_uretimi"
    assert training_topics.SEKTOR_PROFIL["nace_27_20_01"] == "aku_uretimi"
    assert training_topics.SEKTOREL_EGITIM_KONULARI["aku_uretimi"]


def test_sector_question_alias_fills_missing_bucket(monkeypatch):
    install_training_runtime_patches()
    rows = [SimpleNamespace(id=index) for index in range(1, 7)]
    primary_context = {
        "hazard": "Tehlikeli",
        "sector": "elektronik",
        "sector_code": "elektronik",
        "nace": "26.12.01",
    }

    monkeypatch.setattr(
        training_question_bank,
        "_published_questions_for_training",
        lambda _db, _training: rows,
    )
    monkeypatch.setattr(
        training_question_bank,
        "_context",
        lambda _training: primary_context,
    )

    def fake_buckets(_rows, context):
        if context["sector_code"] == "elektronik":
            return {"common": [], "technical": [], "sector": [rows[0]]}
        if context["sector_code"] == "enerji_jenerator_trafo":
            return {"common": [], "technical": [], "sector": rows[1:]}
        return {"common": [], "technical": [], "sector": []}

    monkeypatch.setattr(training_question_bank, "_buckets_for_context", fake_buckets)
    result = training_question_bank._candidate_buckets(None, object())

    assert len(result["sector"]) == training_question_bank.BUCKET_TARGETS["sector"]
    assert len({row.id for row in result["sector"]}) == len(result["sector"])


def test_fourth_topic_heading_is_normalized():
    assert _replace_heading(OLD_HEADINGS[0]) == NEW_HEADING
    assert _replace_heading([OLD_HEADINGS[1]]) == [NEW_HEADING]


def test_compatibility_scripts_do_not_rewrite_training_sources():
    backend_root = Path(__file__).resolve().parents[1]
    targets = (
        backend_root / "app" / "services" / "training_pdfs.py",
        backend_root / "app" / "services" / "training_topics.py",
        backend_root / "app" / "services" / "training_question_bank.py",
        backend_root / "app" / "api" / "trainings.py",
    )
    before = {target: target.read_bytes() for target in targets}

    premium_result = subprocess.run(
        [sys.executable, str(backend_root / "scripts" / "activate_premium_training_pdf.py")],
        cwd=backend_root,
        check=True,
        capture_output=True,
        text=True,
    )
    exam_result = subprocess.run(
        [sys.executable, str(backend_root / "scripts" / "activate_training_exam.py")],
        cwd=backend_root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert {target: target.read_bytes() for target in targets} == before
    assert "no build rewrite required" in premium_result.stdout
    assert "no build rewrite required" in exam_result.stdout
