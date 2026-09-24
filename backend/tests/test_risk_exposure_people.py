from types import SimpleNamespace as N

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.services.risk_analytics import build_risk_analytics
from app.services.risk_personnel import personnel_exposure_match
from app.services.risk_exposure_roster import build_exposure_roster


def risk(i=1, **values):
    return N(**dict(dict(id=i, company_id=1, branch_id=None, risk_code=f'R-{i}', hazard_id=1,
        department_name='Asit dolum', activity='Asit aktarımı', risk_definition='Kimyasal sıçrama',
        risk_score=10, status='Açık', exposed_worker_count=None), **values))


def employee(i=1, **values):
    return N(**dict(dict(id=i, company_id=1, branch_id=None, full_name='Aynı İsim',
        department='Asit dolum', job_title='Dolum görevlisi', is_active=True), **values))


def roster(risks, employees, **scope):
    return build_exposure_roster(N(id=1, name='Test'), risks=risks, employees=employees,
        hazard_map={1: N(name='Asit sıçraması', category_id=1)},
        category_map={1: N(name='Kimyasal Riskler')}, **scope)


@pytest.mark.parametrize(('rd', 'activity', 'ed', 'job', 'expected'), [
    ('Jeneratör', 'Elektrik üretimi', 'İmalat', 'plaka üretim elemanı', 0),
    ('Şarj', 'Asit dolumu', 'Deşarj', 'Kontrol görevlisi', 0),
    ('Boya Üretim', 'Boya hazırlama', 'Gıda Üretim', 'Paketleme', 0),
    ('Elektrik Trafosu', 'Elektrik bakımı', 'Bakım', 'Elektrik teknisyeni', 1),
    ('Üretim', 'Kurşun oksit üretimi', 'Üretim Hattı', 'Operatör', 0),
    ('Oksit Üretim', 'Kurşun oksit üretimi', 'Oksit Üretim Hattı', 'Operatör', 1),
    ('Şarj Havuzları', 'Şarj işlemi', 'Şarjhane', 'Kontrol', 1),
])
def test_matching_is_specific_and_keeps_meaningful_variations(rd, activity, ed, job, expected):
    count, _, _ = personnel_exposure_match(risk(department_name=rd, activity=activity), [employee(department=ed, job_title=job)])
    assert count == expected


def test_empty_scope_does_not_crash_or_make_up_workers():
    row = risk(department_name='', activity='', risk_definition='')
    assert personnel_exposure_match(row, [employee()]) == (0, 'unmatched', set())
    result = build_risk_analytics(N(id=1), risks=[row], employees=[employee()])
    assert result['summary']['matched_worker_count'] == 0


def test_battery_lead_roles_match_without_matching_hr():
    row = risk(department_name='Üretim', activity='Kurşun oksit üretimi', risk_definition='Kurşun maruziyeti')
    workers = [
        employee(1, department='Üretim', job_title='Akü şarj operatörü'),
        employee(2, department='Şarjhane', job_title='Kurşun oksit operatörü'),
        employee(3, department='İK', job_title='İnsan kaynakları uzmanı'),
    ]
    count, source, matched = personnel_exposure_match(row, workers)
    assert source == 'personnel_match'
    assert count == 2
    assert {key[2] for key in matched} == {1, 2}


def test_roster_deduplicates_by_id_without_merging_same_names():
    out = roster([risk(), risk(2)], [employee(), employee(2)])
    assert out['summary']['matched_worker_count'] == 2
    assert len(out['employees']) == 2
    assert all(len(e['matches']) == 2 for e in out['employees'])
    assert all(e['matches'][0]['reasons'] for e in out['employees'])


def test_company_branch_active_and_cancelled_scopes_are_enforced():
    people = [employee(1, branch_id=3), employee(2, branch_id=9), employee(3),
              employee(4, company_id=2, branch_id=3), employee(5, branch_id=3, is_active=False)]
    out = roster([risk(branch_id=3), risk(2, status='İptal'), risk(3, company_id=2)], people)
    assert out['summary']['matched_worker_count'] == 1
    assert [e['id'] for e in out['employees'] if e['matches']] == [1]
    assert {e['id'] for e in out['employees']} == {1, 2, 3}
    assert len(out['risks']) == 1


def test_reported_numbers_never_invent_employee_identities():
    out = roster([risk(exposed_worker_count=5), risk(2, exposed_worker_count=5)], [employee()])
    assert out['summary']['matched_worker_count'] == 0
    assert out['summary']['reported_worker_count'] == 10
    assert out['summary']['reported_risk_count'] == 2
    assert out['employees'][0]['matches'] == []


def test_complete_roster_uses_risks_beyond_overview_limit_and_filters_exactly():
    rows = [risk(i) for i in range(1, 62)]
    out = roster(rows, [employee()], hazard_type='chemical')
    assert len(out['risks']) == 61
    assert len(out['employees'][0]['matches']) == 61
    assert roster(rows, [employee()], risk_id=61)['employees'][0]['matches'][0]['risk_id'] == 61
    assert roster(rows, [employee()], hazard_type='physical')['summary']['matched_worker_count'] == 0


def test_overview_and_named_roster_counts_agree_and_payload_is_minimal():
    rows, people = [risk(), risk(2)], [employee(), employee(2)]
    people[0].national_id_masked = 'must-not-leak'
    people[0].special_status = 'must-not-leak'
    kwargs = dict(hazard_map={1: N(name='Asit', category_id=1)}, category_map={1: N(name='Kimyasal Riskler')})
    overview = build_risk_analytics(N(id=1), risks=rows, employees=people, **kwargs)
    out = roster(rows, people)
    assert overview['risk_types'][0]['matched_worker_count'] == out['summary']['matched_worker_count']
    assert set(out['employees'][0]) == {'id', 'full_name', 'department', 'job_title', 'branch_id', 'matches'}


@pytest.fixture()
def endpoint(monkeypatch):
    from app.api import risks as api
    from app.api import company_access
    from app.models.entities import Base, Branch, Company, Employee, Hazard, HazardCategory, RiskAssessment, UserRole
    from app.core.tenant_context import clear_tenant

    clear_tenant()
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine, tables=[Company.__table__, Branch.__table__, Employee.__table__, Hazard.__table__, HazardCategory.__table__, RiskAssessment.__table__])
    db = Session(engine)
    db.add_all([Company(id=1, name='Yetkili firma'), Company(id=2, name='Başka firma'),
        HazardCategory(id=1, name='Kimyasal Riskler'), Hazard(id=1, category_id=1, name='Asit', code='K-1'),
        Employee(id=1, company_id=1, full_name='Yetkili Çalışan', department='Asit dolum', is_active=True),
        Employee(id=2, company_id=2, full_name='Başka Firmanın Çalışanı', department='Asit dolum', is_active=True),
        Employee(id=3, company_id=1, full_name='Pasif Çalışan', department='Asit dolum', is_active=False)])
    for cid in (1, 2):
        db.add(RiskAssessment(id=cid, company_id=cid, risk_code=f'R-{cid}', hazard_id=1, department_name='Asit dolum', activity='Asit aktarımı', risk_definition='Kimyasal sıçrama', probability=2, severity=3, risk_score=6, risk_level='Orta', created_by_id=1))
    db.commit()
    user = N(id=1, role=UserRole.SAFETY_SPECIALIST, company_id=None, osgb_id=1)
    monkeypatch.setattr(company_access, 'assigned_company_ids', lambda _db, _user: [1])
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: user
    app.dependency_overrides[api.get_db] = lambda: db
    with TestClient(app) as client:
        yield client, user
    db.close()
    engine.dispose()
    clear_tenant()


def test_endpoint_returns_only_authorized_active_people_with_no_store(endpoint):
    client, _ = endpoint
    response = client.get('/risks/analytics/exposures?company_id=1&hazard_type=chemical')
    assert response.status_code == 200, response.text
    assert [p['id'] for p in response.json()['employees']] == [1]
    assert response.headers['cache-control'] == 'private, no-store'
    assert client.get('/risks/analytics/exposures?company_id=2').status_code == 403
    assert client.get('/risks/analytics/exposures?company_id=1&risk_id=2').status_code == 404
    assert client.get('/risks/analytics/exposures?company_id=1&hazard_type=invalid').status_code == 422


@pytest.mark.parametrize('role', ['company_admin', 'other_health_personnel', 'read_only'])
def test_named_list_is_not_granted_to_osgb_or_other_roles(endpoint, role):
    client, user = endpoint
    user.role = role
    assert client.get('/risks/analytics/exposures?company_id=1').status_code == 403


def test_workplace_cannot_use_membership_to_cross_its_fixed_company(endpoint, monkeypatch):
    from app.api import company_access
    client, user = endpoint
    user.role, user.company_id = 'company_admin', 1
    monkeypatch.setattr(company_access, 'assigned_company_ids', lambda _db, _user: [1, 2])
    assert client.get('/risks/analytics/exposures?company_id=1').status_code == 200
    assert client.get('/risks/analytics/exposures?company_id=2').status_code == 403


def test_physician_can_read_but_does_not_gain_training_assignment_role(endpoint):
    client, user = endpoint
    user.role = 'workplace_physician'
    response = client.get('/risks/analytics/exposures?company_id=1')
    assert response.status_code == 200
    assert response.json()['can_assign_training'] is False


def test_risk_analytics_rejects_date_and_cross_company_branch_scope(endpoint):
    client, _ = endpoint
    assert client.get('/risks/analytics?company_id=1&date_from=2025-03-01&date_to=2025-02-01').status_code == 422
    assert client.get('/risks/analytics?company_id=1&branch_id=999').status_code == 404
