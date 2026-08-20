from types import SimpleNamespace

from app.api.trainings import is_training_package_manager
from app.models.entities import UserRole


def test_classic_training_package_requires_osgb_scope():
    assert is_training_package_manager(
        SimpleNamespace(role=UserRole.GLOBAL_ADMIN, osgb_id=None, company_id=None)
    )
    assert is_training_package_manager(
        SimpleNamespace(role=UserRole.COMPANY_ADMIN, osgb_id=7, company_id=None)
    )
    assert not is_training_package_manager(
        SimpleNamespace(role=UserRole.COMPANY_ADMIN, osgb_id=7, company_id=42)
    )
    assert not is_training_package_manager(
        SimpleNamespace(role=UserRole.SAFETY_SPECIALIST, osgb_id=7, company_id=None)
    )
