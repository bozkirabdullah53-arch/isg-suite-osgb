from types import SimpleNamespace

from app.services.risk_responsible import rank_responsible_candidates


def test_risk_responsible_candidates_prioritize_matching_branch_department_and_role():
    employees = [
        SimpleNamespace(
            id=1,
            full_name="Genel Ofis",
            branch_id=1,
            department="İnsan Kaynakları",
            job_title="Uzman",
        ),
        SimpleNamespace(
            id=2,
            full_name="Bakım Sorumlusu",
            branch_id=2,
            department="Bakım",
            job_title="Bakım Sorumlusu",
        ),
    ]

    ranked = rank_responsible_candidates(
        employees,
        branch_id=2,
        department_name="Bakım",
        activity="Elektrik panosu bakımı",
        risk_definition="Elektrik çarpması",
        hazard_name="Elektrik",
        category_name="Elektrik ve Enerji",
    )

    assert ranked[0][0].id == 2
    assert ranked[0][1] > ranked[1][1]
    assert any("eşleşen departman" in reason for reason in ranked[0][2])


def test_risk_responsible_ranking_is_deterministic_for_equal_candidates():
    employees = [
        SimpleNamespace(id=2, full_name="Zeynep", branch_id=None, department=None, job_title=None),
        SimpleNamespace(id=1, full_name="Ali", branch_id=None, department=None, job_title=None),
    ]

    ranked = rank_responsible_candidates(employees, activity="Genel iş")

    assert [employee.id for employee, _, _ in ranked] == [1, 2]
