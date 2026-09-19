from types import SimpleNamespace

from app.services.health_meta import (
    LEAD_DEFAULT_BINDING_LIMIT,
    LEAD_DEFAULT_MEDICAL_SURVEILLANCE_LIMIT,
    build_analysis_payload,
    evaluate_blood_lead,
    lead_status_label,
)


def test_default_blood_lead_thresholds_match_turkish_annex_2():
    assert LEAD_DEFAULT_BINDING_LIMIT == 70
    assert LEAD_DEFAULT_MEDICAL_SURVEILLANCE_LIMIT == 40
    assert evaluate_blood_lead(40) == "normal"
    assert evaluate_blood_lead(40.1) == "izlem"
    assert evaluate_blood_lead(70) == "izlem"
    assert evaluate_blood_lead(70.1) == "yuksek"
    assert evaluate_blood_lead(105.1) == "kritik"


def test_lead_labels_use_record_reference_without_hard_coded_old_values():
    assert lead_status_label(50)[0] == "Tıbbi gözetim"
    assert lead_status_label(71)[0] == "Sınır aşıldı"
    assert lead_status_label(31, 30)[0] == "Sınır aşıldı"


def test_analysis_exposes_binding_limit_and_warning_lists():
    records = [
        SimpleNamespace(
            id=1,
            employee_id=10,
            blood_lead_date=None,
            blood_lead_value=72,
            blood_lead_unit="µg/dL",
            blood_lead_ref=None,
            blood_lead_eval="yuksek",
            examination_date=None,
            fitness_status=None,
            next_examination_date=None,
            audiometry_result=None,
            audiometry_date=None,
            spirometry_result=None,
            spirometry_date=None,
            chest_xray_result=None,
            chest_xray_date=None,
            exposures="Kurşun",
            suggested_tests="Kanda kurşun",
            other_biological_test=None,
            report_storage_path=None,
        ),
    ]
    employee = SimpleNamespace(
        id=10,
        full_name="Örnek Çalışan",
        job_title="Akü operatörü",
        department="Üretim",
        is_active=True,
        start_date=None,
    )
    result = build_analysis_payload(records, {10: employee}, all_employees=[employee])
    assert result["lead_limits"]["binding_limit"] == 70
    assert len(result["over_limit"]) == 1
    assert len(result["over_medical"]) == 1
    assert result["over_limit"][0]["blood_lead_exceeds_limit"] is True
