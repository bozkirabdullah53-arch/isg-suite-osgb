"""Tenant backup domain serializers (format v3)."""
from types import SimpleNamespace

from app.services import archive_store as archive_store


def test_serialize_health_keeps_ciphertext():
    row = SimpleNamespace(
        id=1,
        company_id=9,
        employee_id=3,
        record_type=SimpleNamespace(value="periodic"),
        examination_date=None,
        next_examination_date=None,
        fitness_status=SimpleNamespace(value="fit"),
        physician_name="Dr",
        summary="enc:v1:abc",
        confidential_note="plain note",
        audiometry_date=None,
        audiometry_result=None,
        spirometry_date=None,
        spirometry_result=None,
        chest_xray_date=None,
        chest_xray_result=None,
        blood_lead_date=None,
        blood_lead_value=None,
        blood_lead_unit=None,
        blood_lead_ref=None,
        blood_lead_eval=None,
        suggested_tests=None,
        exposures=None,
        follow_up_note=None,
        other_biological_test=None,
        report_file_name=None,
        report_storage_path=None,
        deleted_at=None,
        created_at=None,
    )
    out = archive_store._serialize_health([row])
    assert out[0]["summary"] == "enc:v1:abc"
    assert out[0]["confidential_note"] == "plain note"


def test_serialize_trainings_shape():
    session = SimpleNamespace(
        id=1,
        company_id=9,
        title="Temel",
        training_type="Temel İSG",
        start_date=None,
        end_date=None,
        duration_hours=8,
        instructor_name="Ali",
        status=SimpleNamespace(value="planned"),
        verification_code="abc",
        created_at=None,
    )
    part = SimpleNamespace(
        id=2,
        training_id=1,
        employee_id=3,
        attended=True,
        score=80,
        successful=True,
        certificate_number="C1",
    )
    payload = archive_store._serialize_trainings([session], [part])
    assert len(payload["sessions"]) == 1
    assert len(payload["participants"]) == 1
