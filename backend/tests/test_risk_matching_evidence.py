"""Semantic regressions from the risk-personnel audit; synthetic identities only."""
from types import SimpleNamespace as N

import pytest

from app.services.risk_analytics import build_risk_analytics, classify_hazard_type
from app.services.risk_exposure_roster import build_exposure_roster
from app.services.risk_personnel import personnel_exposure_match


def person(department="Genel", job="İş Güvenliği Uzmanı"):
    return N(id=1, company_id=1, branch_id=None, is_active=True,
             full_name="Test Çalışanı", department=department, job_title=job)


def risk(**overrides):
    values = dict(id=1, risk_code="R-1", company_id=1, branch_id=None, hazard_id=1,
                  department_name="Genel Alan", activity="Elle taşıma",
                  risk_definition="Risk unsuru: Ağır yük\nTehlike: Yanlış kaldırma\nOlası sonuç: Bel fıtığı",
                  status="Açık", risk_score=10, exposed_worker_count=None)
    return N(**(values | overrides))


@pytest.mark.parametrize("department", ["Genel", "Genel Alan", "Ortak Alan", "Tüm Alanlar", "Üretim", "İmalat"])
def test_generic_department_alone_cannot_establish_an_exposure_candidate(department):
    assert personnel_exposure_match(risk(department_name=department), [person(department)])[0] == 0


def test_public_relations_does_not_match_public_health_or_consequence_text():
    worker = person("İletişim Tasarımı Uzmanı", "Reklam ve Halkla İlişkiler Personeli")
    row = risk(department_name="Hava Kontrol", activity="Hijyen",
               risk_definition="Risk unsuru: Asitli el/giysi\nTehlike: İkincil maruziyet\nOlası sonuç: Halk sağlığı riski")
    assert personnel_exposure_match(row, [worker])[0] == 0
    # Even an identical occupational word in a consequence is not task evidence.
    row.risk_definition = "Olası sonuç: Elektrik teknisyeninin yaralanması"
    assert personnel_exposure_match(row, [person("Ofis", "Elektrik teknisyeni")])[0] == 0


@pytest.mark.parametrize(("job", "activity", "expected"), [
    ("Kaynakçı", "Metal kaynak işlemi", 1),
    ("Temizlik personeli", "Zemin yıkama", 1),
    ("Elektrik teknisyeni", "Elektrik pano bakımı", 1),
    ("İş Güvenliği Uzmanı", "Elle taşıma", 0),
    ("Reklam ve halkla ilişkiler", "Halk sağlığı", 0),
    ("Elektrik bakım teknisyeni", "Mekanik bakım", 0),
])
def test_task_aliases_have_positive_and_negative_controls(job, activity, expected):
    assert personnel_exposure_match(risk(department_name="", activity=activity), [person("", job)])[0] == expected


def test_specialist_is_not_blacklisted_when_specific_workplace_scope_is_present():
    assert personnel_exposure_match(risk(department_name="Asit dolum"), [person("Asit dolum")])[0] == 1


def test_different_named_departments_do_not_match_a_shared_word():
    assert personnel_exposure_match(risk(department_name="Elektrik Bakım", activity=""),
                                    [person("Mekanik Bakım", "Kontrol görevlisi")])[0] == 0


def test_hygiene_does_not_override_a_chemical_category():
    assert classify_hazard_type("Kimyasal Riskler", "İkincil maruziyet", "Hijyen",
                               "Risk unsuru: Asitli el/giysi\nOlası sonuç: Halk sağlığı riski") == "chemical"


@pytest.mark.parametrize("label", ["Yapıştırıcı kullanımı", "Reaktör", "Kurşun maruziyeti", "Sülfürik asit"])
def test_turkish_chemical_terms_use_the_same_normalization(label):
    assert classify_hazard_type(None, label) == "chemical"


def test_generic_hygiene_is_not_biological_agent_evidence():
    assert classify_hazard_type(None, "Hijyen", "Yemekhane girişi") == "other"


def test_classifier_does_not_confuse_scaffolding_skeleton_or_acid_assistant():
    assert classify_hazard_type("Ergonomik Riskler", "Kas-iskelet hastalığı") == "ergonomic"
    assert classify_hazard_type(None, "Asistan") == "other"
    assert classify_hazard_type("Fiziksel Riskler", "İskelede düşme") == "physical"


def test_conflicting_lead_category_is_flagged_in_both_analytics_and_roster():
    row = risk(activity="Yemekhane girişi", risk_definition="Risk unsuru: İş elbisesiyle giriş\nOlası sonuç: Halk sağlığı riski")
    kwargs = dict(risks=[row], employees=[person()],
                  hazard_map={1: N(name="Kurşun transferi", category_id=1)},
                  category_map={1: N(name="Biyolojik Riskler")})
    overview = build_risk_analytics(N(id=1), **kwargs)
    roster = build_exposure_roster(N(id=1, name="Test"), **kwargs, hazard_type="other")
    assert overview["summary"]["classification_review_count"] == 1
    for item in (overview["observed_risks"][0], roster["risks"][0]):
        assert item["hazard_type"] == "other"
        assert item["classification_status"] == "review_required"
        assert set(item["classification_candidates"]) == {"chemical", "biological"}
        assert "Biyolojik" in item["classification_note"]
    assert overview["classification_reviews"][0]["risk_code"] == "R-1"
    assert overview["summary"]["matched_worker_count"] == roster["summary"]["matched_worker_count"] == 0


def test_candidates_do_not_amplify_dominance_and_unknown_is_not_zero_exposure():
    row = risk(department_name="Asit dolum")
    people = [person("Asit dolum") for _ in range(3)]
    for i, employee in enumerate(people):
        employee.id = i + 1
    kwargs = dict(risks=[row], hazard_map={1: N(name="Asit sıçraması", category_id=1)},
                  category_map={1: N(name="Kimyasal Riskler")})
    found = build_risk_analytics(N(id=1), employees=people, **kwargs)
    missing = build_risk_analytics(N(id=1), employees=[], **kwargs)
    assert found["summary"]["matched_worker_count"] == 3
    assert found["observed_risks"][0]["dominance_score"] == missing["observed_risks"][0]["dominance_score"] == 10
    assert missing["summary"]["exposure_records_unmatched"] == 1
    assert missing["observed_risks"][0]["exposed_worker_count"] == 0
    assert missing["observed_risks"][0]["dominance_weight"] == 1
