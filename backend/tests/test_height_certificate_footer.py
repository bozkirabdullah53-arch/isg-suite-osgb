from pathlib import Path


def test_height_certificate_does_not_render_instructor_suitability_footer():
    source = Path("app/services/training_height_2026.py").read_text(encoding="utf-8")
    assert 'c.drawString(ml, 11.7 * mm, "Eğitici Uygunluğu:")' not in source
