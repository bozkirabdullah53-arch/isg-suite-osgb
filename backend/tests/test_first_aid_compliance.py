from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.entities import (
    Base, Company, EmergencyTeam, EmergencyTeamAssignment, EmergencyTeamTraining,
    EmergencyTeamType, Employee, User, UserRole,
)
from app.services.first_aid_compliance import (
    build_first_aid_compliance, first_aid_alerts, required_first_aiders,
)

TODAY = date(2026, 10, 6)


@pytest.fixture()
def context():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        company = Company(name="İlk Yardım Firma", hazard_class="Çok Tehlikeli", is_active=True)
        other = Company(name="Diğer Firma", hazard_class="Çok Tehlikeli", is_active=True)
        user = User(email="first-aid@example.com", full_name="Uzman", hashed_password="unused",
                    role=UserRole.GLOBAL_ADMIN, is_active=True)
        team_type = EmergencyTeamType(code="ilk_yardim", name="İlk Yardım", is_system=True)
        db.add_all([company, other, user, team_type])
        db.flush()
        team = EmergencyTeam(company_id=company.id, type_id=team_type.id, name="İlk Yardım",
                             created_by_id=user.id)
        db.add(team)
        db.flush()
        yield SimpleNamespace(db=db, company=company, other=other, user=user, team=team,
                              team_type=team_type)
    engine.dispose()


def _staff(context, count):
    employees = [Employee(company_id=context.company.id, full_name=f"Çalışan {index}",
                          is_active=True) for index in range(count)]
    context.db.add_all(employees)
    context.db.flush()
    return employees


def _assign(context, employee, **overrides):
    fields = dict(company_id=context.company.id, employee_id=employee.id, team_id=context.team.id,
                  membership="asil", assign_start=TODAY, is_active=True, created_by_id=context.user.id)
    fields.update(overrides)
    assignment = EmergencyTeamAssignment(**fields)
    context.db.add(assignment)
    context.db.flush()
    return assignment


def _summary(context):
    context.db.flush()
    return build_first_aid_compliance(context.db, context.company, today=TODAY)


def test_required_first_aiders_boundary_values():
    assert required_first_aiders(1, "Çok Tehlikeli") == 1
    assert required_first_aiders(10, "Çok Tehlikeli") == 1
    assert required_first_aiders(11, "Çok Tehlikeli") == 2
    assert required_first_aiders(15, "Tehlikeli") == 1
    assert required_first_aiders(16, "Tehlikeli") == 2
    assert required_first_aiders(20, "Az Tehlikeli") == 1
    assert required_first_aiders(21, "Az Tehlikeli") == 2
    assert required_first_aiders(10, "Bilinmiyor") is None


def test_first_aid_status_helpers_keep_expiring_documents_currently_valid():
    from app.services.first_aid_compliance import _status

    assert _status(date.today(), date.today())[0] == "expiring_soon"


def test_nine_assignments_are_complete_and_missing_certificates_are_visible(context):
    employees = _staff(context, 88)
    for employee in employees[:9]:
        _assign(context, employee)

    result = _summary(context)
    assert result["required_count"] == result["assigned_primary_count"] == 9
    assert result["assignment_complete"] is True
    assert result["assignment_missing_count"] == 0
    assert result["record_count"] == result["incomplete_count"] == 9
    assert result["valid_count"] == 0
    assert result["missing_count"] == 9
    assert {row["employee_id"] for row in result["people"]} == {e.id for e in employees[:9]}
    assert all(row["membership"] == "asil" for row in result["people"])
    alerts = first_aid_alerts(result)
    assert len(alerts) == 1
    assert "tamamlandı (9/9 asıl)" in alerts[0]["text"]
    assert "9 kişinin belge bilgisi eksik" in alerts[0]["text"]
    assert "İlkyardımcı sayısı yetersiz" not in alerts[0]["text"]


def test_certificate_add_and_remove_updates_compliance_without_losing_assignment(context):
    employee = _staff(context, 1)[0]
    assignment = _assign(context, employee)
    assert _summary(context)["incomplete_count"] == 1
    certificate = EmergencyTeamTraining(assignment_id=assignment.id, first_aid_cert_no="İY-001",
                                       first_aid_start=TODAY, first_aid_end=TODAY + timedelta(days=365))
    context.db.add(certificate)
    context.db.flush()
    context.db.expire_all()
    result = _summary(context)
    assert result["valid_count"] == 1
    assert result["missing_count"] == result["incomplete_count"] == 0
    assert result["people"][0]["certificate_no"] == "İY-001"
    assert first_aid_alerts(result) == []

    context.db.delete(certificate)
    context.db.flush()
    context.db.expire_all()
    result = _summary(context)
    assert result["assignment_complete"] is True
    assert result["incomplete_count"] == result["missing_count"] == 1


@pytest.mark.parametrize("excluded", [
    "employee_inactive", "employee_future", "employee_exited", "assignment_inactive",
    "assignment_future", "assignment_ended", "team_inactive", "foreign_employee",
    "foreign_assignment", "foreign_team",
])
def test_inactive_out_of_date_and_foreign_records_are_excluded(context, excluded):
    employee = _staff(context, 1)[0]
    fields = {}
    if excluded == "employee_inactive":
        employee.is_active = False
    elif excluded == "employee_future":
        employee.start_date = TODAY + timedelta(days=1)
    elif excluded == "employee_exited":
        employee.exit_date = TODAY
    elif excluded == "assignment_inactive":
        fields["is_active"] = False
    elif excluded == "assignment_future":
        fields["assign_start"] = TODAY + timedelta(days=1)
    elif excluded == "assignment_ended":
        fields["assign_end"] = TODAY - timedelta(days=1)
    elif excluded == "team_inactive":
        context.team.is_active = False
    elif excluded == "foreign_employee":
        employee.company_id = context.other.id
    elif excluded == "foreign_assignment":
        fields["company_id"] = context.other.id
    elif excluded == "foreign_team":
        context.team.company_id = context.other.id
    assignment = _assign(context, employee, **fields)
    context.db.add(EmergencyTeamTraining(assignment_id=assignment.id, first_aid_cert_no="İY-002",
                                       first_aid_end=TODAY + timedelta(days=365)))
    result = _summary(context)
    assert result["assigned_count"] == result["record_count"] == result["valid_count"] == 0
    assert result["people"] == []


def test_current_date_boundaries_match_emergency_team_cards(context):
    employee = _staff(context, 1)[0]
    employee.start_date = TODAY
    employee.exit_date = TODAY + timedelta(days=1)
    _assign(context, employee, assign_end=TODAY)
    result = _summary(context)
    assert result["active_employee_count"] == result["assigned_primary_count"] == 1


def test_duplicate_people_and_reserves_do_not_fill_primary_assignment_requirement(context):
    employees = _staff(context, 11)
    duplicate_team = EmergencyTeam(company_id=context.company.id, type_id=context.team_type.id,
                                   name="Diğer Vardiya", created_by_id=context.user.id)
    context.db.add(duplicate_team)
    context.db.flush()
    _assign(context, employees[0])
    _assign(context, employees[0], team_id=duplicate_team.id)
    _assign(context, employees[0], membership="yedek", team_id=duplicate_team.id)
    _assign(context, employees[1], membership="yedek")
    result = _summary(context)
    assert result["required_count"] == result["assigned_count"] == result["record_count"] == 2
    assert result["assigned_primary_count"] == result["assigned_reserve_count"] == 1
    assert result["assignment_missing_count"] == 1
    assert result["assignment_complete"] is False


@pytest.mark.parametrize("training_type,expected_valid", [
    (None, 1), ("İlk yardım", 1), ("İlkyardım eğitimi", 1), ("Sertifika belgesi", 1),
    ("Yangın eğitimi", 0), ("Temel İSG eğitimi", 0),
])
def test_generic_certificate_fields_are_limited_to_first_aid_context(context, training_type, expected_valid):
    assignment = _assign(context, _staff(context, 1)[0])
    context.db.add(EmergencyTeamTraining(assignment_id=assignment.id, training_type=training_type,
                                       certificate_no="S-001", valid_until=TODAY + timedelta(days=90)))
    result = _summary(context)
    assert result["valid_count"] == expected_valid
    assert result["incomplete_count"] == 1 - expected_valid
    assert result["expiring_soon_count"] == expected_valid


def test_other_team_generic_certificate_is_not_a_first_aid_certificate(context):
    context.team_type.code = "sondurme"
    assignment = _assign(context, _staff(context, 1)[0])
    context.db.add(EmergencyTeamTraining(assignment_id=assignment.id, certificate_no="Y-001",
                                       valid_until=TODAY + timedelta(days=365)))
    result = _summary(context)
    assert result["valid_count"] == result["assigned_count"] == result["record_count"] == 0


def test_expired_and_future_certificates_do_not_clear_document_warning(context):
    employees = _staff(context, 2)
    expired = _assign(context, employees[0])
    future = _assign(context, employees[1])
    context.db.add_all([
        EmergencyTeamTraining(assignment_id=expired.id, first_aid_cert_no="İY-ESKİ",
                              first_aid_end=TODAY - timedelta(days=1)),
        EmergencyTeamTraining(assignment_id=future.id, first_aid_cert_no="İY-GELECEK",
                              first_aid_start=TODAY + timedelta(days=1),
                              first_aid_end=TODAY + timedelta(days=365)),
    ])
    result = _summary(context)
    assert result["assignment_complete"] is True
    assert result["valid_count"] == 0
    assert result["expired_count"] == result["incomplete_count"] == result["missing_count"] == 1
