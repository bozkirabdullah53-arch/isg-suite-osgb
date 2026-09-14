import inspect

from app.services.training_height_2026 import draw_height_certificate_page


def test_height_certificate_employer_box_leaves_signature_body_blank():
    source = inspect.getsource(draw_height_certificate_page)

    assert '("İşveren / İşveren Vekili", "", "", NAVY)' in source
    assert 'Kaşe / İmza' not in source
