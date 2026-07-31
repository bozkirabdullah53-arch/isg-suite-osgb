"""Pro 2026 risk parity — revision / media / roles / DOF excel."""
from types import SimpleNamespace

from app.api import risks as risks_api
from app.models.entities import UserRole
from app.services.risk_reports import build_dof_excel


def test_risk_edit_roles_exclude_company_admin():
    assert UserRole.SAFETY_SPECIALIST in risks_api.EDIT_ROLES
    assert UserRole.GLOBAL_ADMIN in risks_api.EDIT_ROLES
    assert UserRole.COMPANY_ADMIN not in risks_api.EDIT_ROLES


def test_media_file_type_mapping():
    assert risks_api._media_file_type(".jpg") == "photo"
    assert risks_api._media_file_type(".pdf") == "pdf"
    assert risks_api._media_file_type(".mp4") == "video"
    assert risks_api._media_file_type(".docx") == "drawing"


def test_build_dof_excel_empty_ok():
    company = SimpleNamespace(name="Test OSGB", id=1)
    data = build_dof_excel(company=company, risks=[], hazard_map={})
    assert data[:2] == b"PK"  # zip/xlsx


def test_revision_fields_cover_core_assessment():
    for key in ("activity", "risk_definition", "probability", "severity", "status"):
        assert key in risks_api.REVISION_FIELDS
