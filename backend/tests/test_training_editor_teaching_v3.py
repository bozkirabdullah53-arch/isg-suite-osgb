from __future__ import annotations

from copy import deepcopy
from datetime import date
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from app.services.training_document_consistency import (
    format_training_completion_date,
    normalize_safety_specialist_title,
    training_completion_date_code,
)
from app.services.training_exam_pdf import _training_exam_date_text
from app.services.training_presentation_editor import build_edited_manifest
from app.services.training_presentation_renderer import canonical_json_bytes, sha256_hex, verify_manifest
from app.services.training_presentation_teaching_renderer import render_teaching_presentation
from app.services.training_presentation_teaching_unicode_pdf import install_teaching_unicode_pdf
from app.services.training_presentation_teaching_v3 import enrich_manifest_for_teaching_v3

install_teaching_unicode_pdf()


def _hashed_manifest(slides):
    manifest = {
        "manifest_version": "test-v1",
        "contract_version": "test-contract-v1",
        "contract_hash": "a" * 64,
        "template_version": "test-template-v1",
        "training": {"training_id": 7, "company_id": 5, "start_date": "2026-08-01", "end_date": "2026-08-02"},
        "nace_snapshot": {"nace_code": "27.20.01", "nace_description": "Akümülatör imalatı", "hazard_class": "Çok Tehlikeli"},
        "training_topics": ["Kurşun maruziyeti", "Asitle çalışma", "Hidrojen", "Elektrik", "Acil durum"],
        "technical_risk_tags": ["lead", "sulfuric_acid", "hydrogen"],
        "special_risks": ["atex"],
        "source_registry": [{"source_id": "tr-law-6331", "title": "6331 sayılı Kanun"}],
        "slides": slides,
        "slide_count": len(slides),
        "approval": {"status": "specialist_review_required", "required_slide_positions": []},
        "rendering": {},
    }
    manifest["content_hash"] = sha256_hex(canonical_json_bytes(manifest))
    verify_manifest(manifest)
    return manifest


def test_exam_and_final_document_dates_use_training_end_date():
    training = SimpleNamespace(start_date=date(2026, 8, 1), end_date=date(2026, 8, 2))
    assert _training_exam_date_text(training) == "02.08.2026"
    assert format_training_completion_date(training) == "02.08.2026"
    assert training_completion_date_code(training) == "02082026"


def test_historical_record_falls_back_to_start_date_not_today():
    training = SimpleNamespace(start_date=date(2025, 3, 7), end_date=None)
    assert _training_exam_date_text(training) == "07.03.2025"
    assert format_training_completion_date(training) == "07.03.2025"


def test_legacy_certificate_title_is_normalized_without_changing_role_code():
    assert normalize_safety_specialist_title("A Sınıfı İSG Uzmanı") == "A Sınıfı İş Güvenliği Uzmanı"
    assert normalize_safety_specialist_title("") == "İş Güvenliği Uzmanı"


def test_editor_creates_copy_without_mutating_source_or_shifting_old_positions():
    source = _hashed_manifest([
        {"position": 1, "section_id": "cover", "title": "Kapak", "source_refs": ["tr-law-6331"], "content_blocks": [], "approval_required": False},
        {"position": 2, "section_id": "work_specific_topics", "title": "Hidrojen", "source_refs": ["tr-law-6331"], "content_blocks": [{"type": "tehlike", "value": "Hidrojen birikmesi"}], "approval_required": False},
    ])
    frozen = deepcopy(source)
    edited = build_edited_manifest(
        source,
        source_version_id=11,
        source_version=1,
        edited_by_id=9,
        slide_updates=[{
            "position": 2,
            "mode": "append",
            "lesson_points": ["Havalandırmayı doğrula"],
            "scenario": "Şarj alanında havalandırma durdu; ne yaparsınız?",
            "instructor_note": "Sahadaki şarj alanından örnek ver.",
        }],
        append_slides=[{
            "title": "Saha uygulaması",
            "lesson_points": ["Ateşleme kaynaklarını kontrol et"],
        }],
        change_note="Eğitmen saha örneği ekledi",
        auto_enrich_teaching_v3=True,
    )
    assert source == frozen
    assert [slide["position"] for slide in edited["slides"][:2]] == [1, 2]
    assert edited["slides"][-1]["position"] == 3
    assert edited["slides"][1]["approval_required"] is True
    assert edited["slides"][2]["approval_required"] is True
    assert {2, 3}.issubset(set(edited["approval"]["required_slide_positions"]))
    assert edited["editor"]["source_version_id"] == 11
    assert edited["rendering"]["teaching_v3"] is True
    verify_manifest(edited)


def test_teaching_v3_adds_real_visual_instruction_blocks_and_renders_files():
    base = _hashed_manifest([
        {"position": 1, "section_id": "cover", "title": "İş Güvenliği ve Akü üretimi eğitimi", "source_refs": ["tr-law-6331"], "content_blocks": [], "approval_required": False},
        {
            "position": 2,
            "section_id": "work_specific_topics",
            "title": "Akü şarjında hidrojen",
            "source_refs": ["tr-law-6331"],
            "content_blocks": [
                {"type": "tehlike", "value": "Şarj sırasında hidrojen birikmesi"},
                {"type": "kontrol_tedbiri", "value": "Yeterli havalandırma"},
                {"type": "guvenli_davranis", "value": "Ateşleme kaynaklarını uzak tut"},
            ],
            "approval_required": False,
        },
        {"position": 3, "section_id": "control_measures", "title": "Kontrol hiyerarşisi", "source_refs": ["tr-law-6331"], "content_blocks": [], "approval_required": False},
    ])
    enriched = enrich_manifest_for_teaching_v3(base)
    work_blocks = enriched["slides"][1]["content_blocks"]
    assert any(block.get("type") == "hazard_control_behavior_visual" for block in work_blocks)
    assert any(block.get("type") == "case_scenario" for block in work_blocks)
    assert any(block.get("type") == "control_hierarchy_visual" for block in enriched["slides"][2]["content_blocks"])
    assert enriched["approval"]["status"] == "specialist_review_required"
    assert set(enriched["approval"]["required_slide_positions"]) == {2, 3}
    assert enriched["teaching_v3"]["approval_required_for_enriched_positions"] == [2, 3]
    rendered = render_teaching_presentation(enriched)
    assert rendered.pptx_bytes.startswith(b"PK")
    assert rendered.pdf_bytes.startswith(b"%PDF")
    assert rendered.slide_count == 3

    reader = PdfReader(BytesIO(rendered.pdf_bytes))
    first = reader.pages[0]
    width = float(first.mediabox.width)
    height = float(first.mediabox.height)
    assert abs((width / height) - (16 / 9)) < 0.01
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "İş Güvenliği" in extracted
    assert "Akü şarjında hidrojen" in extracted
    assert "Şarj sırasında hidrojen birikmesi" in extracted
