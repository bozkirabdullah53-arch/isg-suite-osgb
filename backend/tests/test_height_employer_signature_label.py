import inspect

from app.services.training_height_2026 import draw_height_certificate_page


def test_height_certificate_employer_box_uses_stamp_signature_label():
    source = inspect.getsource(draw_height_certificate_page)

    assert '("İşveren / İşveren Vekili", "Kaşe / İmza", "İşveren / İşveren Vekili", NAVY)' in source
