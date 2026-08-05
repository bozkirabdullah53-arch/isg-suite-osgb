"""ÇSGB readiness advice must be actionable without fabricating evidence."""
from app.services.csgb_readiness_advice import build_csgb_readiness_advice


def _gaps():
    return [
        {
            "code": "risk_degerlendirme",
            "title": "Risk değerlendirme kayıtları",
            "status": "missing",
            "detail": "Risk değerlendirme kaydı yok.",
        },
        {
            "code": "isg_kurulu",
            "title": "İSG kurulu / çalışan temsilcisi",
            "status": "missing",
            "detail": "Kurul üye / toplantı kaydı yok.",
        },
    ]


def test_under_fifty_employees_flags_committee_for_context_review_without_changing_score():
    result = build_csgb_readiness_advice(
        missing_items=_gaps(),
        active_employees=2,
        company_count=1,
    )

    assert result["advice_version"] == "csgb-advice-v1"
    assert result["priority_count"] == 2
    assert result["score_changed"] is False
    assert result["contextual_review_count"] == 1
    assert "50 çalışan eşiğine" in result["contextual_notes"][0]["detail"]
    assert "altı aydan fazla" in result["contextual_notes"][0]["detail"]

    by_code = {item["code"]: item for item in result["priority_items"]}
    assert by_code["risk_degerlendirme"]["action_module"] == "risk"
    assert by_code["isg_kurulu"]["context_review"] is True
    assert by_code["isg_kurulu"]["action_module"] == "isg_kurulu"


def test_fifty_or_more_employees_does_not_apply_threshold_exception():
    result = build_csgb_readiness_advice(
        missing_items=_gaps(),
        active_employees=50,
        company_count=1,
    )

    assert result["contextual_review_count"] == 0
    assert result["contextual_notes"] == []
    by_code = {item["code"]: item for item in result["priority_items"]}
    assert by_code["isg_kurulu"].get("context_review") is not True
    assert result["score_changed"] is False


def test_action_map_covers_operational_gap_destinations():
    gaps = [
        {"code": "periyodik_kontrol", "title": "Periyodik kontrol", "status": "missing", "detail": "Yok"},
        {"code": "acil_durum_plani", "title": "Acil durum planı", "status": "missing", "detail": "Yok"},
        {"code": "ortam_olcum", "title": "Ortam ölçümü", "status": "missing", "detail": "Yok"},
        {"code": "egitim", "title": "Eğitim", "status": "missing", "detail": "Yok"},
    ]
    result = build_csgb_readiness_advice(
        missing_items=gaps,
        active_employees=2,
        company_count=1,
    )
    modules = {item["code"]: item["action_module"] for item in result["priority_items"]}
    assert modules == {
        "periyodik_kontrol": "periyodik_kontrol",
        "acil_durum_plani": "acil_plan",
        "ortam_olcum": "ortam_olcum",
        "egitim": "training",
    }
