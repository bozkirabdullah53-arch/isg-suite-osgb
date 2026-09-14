from app.services.special_training_profiles import SPECIAL_TRAINING_PROFILES
from app.services.training_runtime_patches import install_training_runtime_patches


def test_height_profile_has_no_instructor_legal_note():
    install_training_runtime_patches()
    profile = SPECIAL_TRAINING_PROFILES["yuksekte_calisma"]
    assert "instructor_legal_note" not in profile
