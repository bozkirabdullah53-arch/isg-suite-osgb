from app.services.training_question_selection_v2 import exact_nace_exam_strict_active


def test_exact_nace_strict_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("TRAINING_EXACT_NACE_EXAM_STRICT", raising=False)
    assert exact_nace_exam_strict_active() is False


def test_exact_nace_strict_flag_accepts_explicit_true(monkeypatch):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    assert exact_nace_exam_strict_active() is True
