from types import SimpleNamespace

from app.services.risk_nace_roadmap import TAG_LABELS
from app.services.risk_analytics import build_risk_analytics, classify_hazard_type


def _risk(risk_id, hazard_id, score, exposed, *, status="Açık"):
    return SimpleNamespace(
        id=risk_id,
        risk_code=f"RSK-{risk_id}",
        hazard_id=hazard_id,
        activity="Üretim faaliyeti",
        risk_definition="Tehlike kaynağına maruziyet",
        risk_score=score,
        risk_level="Yüksek",
        exposed_worker_count=exposed,
        status=status,
    )


def test_hazard_type_classifier_handles_turkish_terms():
    assert classify_hazard_type("Biyolojik Riskler", "Enfeksiyon") == "biological"
    assert classify_hazard_type("Kimyasal Riskler", "Solvent") == "chemical"
    assert classify_hazard_type("Fiziksel Riskler", "Gürültü") == "physical"


def test_battery_nace_candidate_labels_are_turkish():
    assert {
        key: TAG_LABELS[key]
        for key in (
            "lead_exposure",
            "sulfuric_acid",
            "hydrogen_gas",
            "chemical_spill",
            "health_surveillance",
            "lead_poisoning",
            "acid_burn",
            "hydrogen_explosion",
        )
    } == {
        "lead_exposure": "Kurşun maruziyeti",
        "sulfuric_acid": "Sülfürik asit",
        "hydrogen_gas": "Hidrojen gazı",
        "chemical_spill": "Kimyasal dökülme",
        "health_surveillance": "Sağlık gözetimi",
        "lead_poisoning": "Kurşun zehirlenmesi",
        "acid_burn": "Asit yanığı",
        "hydrogen_explosion": "Hidrojen patlaması",
    }


def test_build_risk_analytics_sorts_dominant_types_and_keeps_nace_candidates_separate():
    company = SimpleNamespace(
        id=17,
        name="Analitik Üretim A.Ş.",
        sgk_registry_no="",
        hazard_class="Tehlikeli",
    )
    categories = {
        1: SimpleNamespace(id=1, name="Fiziksel Riskler"),
        2: SimpleNamespace(id=2, name="Kimyasal Riskler"),
        3: SimpleNamespace(id=3, name="Biyolojik Riskler"),
    }
    hazards = {
        101: SimpleNamespace(id=101, code="FIZ-001", name="Gürültü", category_id=1),
        102: SimpleNamespace(id=102, code="KIM-001", name="Solvent", category_id=2),
        103: SimpleNamespace(id=103, code="BIO-001", name="Biyolojik etken", category_id=3),
    }
    roadmap = {
        "status": "verified",
        "status_label": "NACE doğrulandı",
        "entered_nace_code": "46.83.06",
        "exact_catalog_match": True,
        "identity": {
            "description": "Belirli ürünlerin toptan ticareti",
            "section_code": "G",
            "section_name": "Toptan ve perakende ticaret",
            "hazard_class": "Tehlikeli",
        },
        "workplace": {"nace_code": "46.83.06", "nace_source": "company"},
        "technical_risk_tags": [
            {"key": "noise", "label": "Gürültü", "category": "Fiziksel Riskler"},
        ],
        "special_risks": [
            {"key": "solvent", "label": "Solvent kullanımı", "category": "Kimyasal Riskler"},
        ],
        "warnings": [],
    }
    risks = [
        _risk(1, 101, 5, 2),
        _risk(2, 102, 20, 3),
        _risk(3, 103, 2, 10),
        _risk(4, 102, 99, 99, status="İptal"),
    ]

    result = build_risk_analytics(
        company,
        risks=risks,
        hazard_map=hazards,
        category_map=categories,
        nace_roadmap=roadmap,
        active_employee_count=25,
    )

    assert result["nace"]["code"] == "46.83.06"
    assert result["summary"]["risk_record_count"] == 3
    assert result["summary"]["exposed_worker_count_total"] == 15
    assert result["summary"]["dominant_type"] == "Kimyasal"
    assert result["summary"]["dominant_risk"] == "Solvent"
    assert result["risk_types"][0]["key"] == "chemical"
    assert result["risk_types"][0]["percentage"] == 66.7
    assert result["dominant_risks"][0]["label"] == "Solvent"
    assert len(result["potential_hazards"]) == 2
    assert result["potential_hazards"][0]["source"] == "NACE"
    assert all(row["status"] != "İptal" for row in result["observed_risks"])


def test_missing_exposure_count_is_explicit_and_does_not_drop_risk():
    company = SimpleNamespace(id=1, name="Eksik Veri", hazard_class=None)
    risk = _risk(1, 11, 8, None)
    result = build_risk_analytics(
        company,
        risks=[risk],
        hazard_map={11: SimpleNamespace(id=11, code="F-1", name="Gürültü", category_id=1)},
        category_map={1: SimpleNamespace(id=1, name="Fiziksel Riskler")},
        active_employee_count=4,
    )

    assert result["summary"]["risk_record_count"] == 1
    assert result["summary"]["exposure_records_missing"] == 1
    assert result["observed_risks"][0]["exposure_count_reported"] is False
    assert result["observed_risks"][0]["dominance_score"] == 8
