"""Branch, active-state and search filters preserve workplace access boundaries."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import company_access, employees, exports
from app.api.deps import get_current_user
from app.core.database import Base, get_db
from app.core.tenant_context import clear_tenant
from app.models.entities import Branch, Company, Employee, UserRole


@pytest.fixture()
def client(monkeypatch):
    clear_tenant()
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Company(id=1, name='Assigned Workplace'), Company(id=2, name='Other Workplace')])
        db.flush()
        db.add_all([Branch(id=11, company_id=1, name='Production'), Branch(id=12, company_id=1, name='Warehouse'), Branch(id=21, company_id=2, name='Other')])
        db.flush()
        db.add_all([
            Employee(id=1, company_id=1, branch_id=11, full_name='Alice', department='Welding', is_active=True),
            Employee(id=2, company_id=1, branch_id=12, full_name='Bob', department='Welding', is_active=True),
            Employee(id=3, company_id=1, branch_id=11, full_name='Archived', department='Welding', is_active=False),
            Employee(id=4, company_id=1, branch_id=None, full_name='No Branch', is_active=True),
            Employee(id=5, company_id=2, branch_id=21, full_name='Outside Scope', is_active=True),
        ])
        db.commit()
        user = SimpleNamespace(id=1, role=UserRole.COMPANY_ADMIN, company_id=1, osgb_id=None, email='fixture@example.invalid', full_name='Test')
        monkeypatch.setattr(company_access, 'assigned_company_ids', lambda _db, _user: [1])
        monkeypatch.setattr(exports, 'assigned_company_ids', lambda _db, _user: [1])
        app = FastAPI()
        app.include_router(employees.router)
        app.include_router(exports.router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as value:
            yield value
    engine.dispose()
    clear_tenant()


def test_branch_active_and_search_filters_apply_together(client):
    response = client.get('/employees?company_id=1&branch_id=11&active=true&q=Welding')
    assert response.status_code == 200
    assert [row['id'] for row in response.json()] == [1]
    archive = client.get('/employees?company_id=1&branch_id=11&active=false')
    assert [row['id'] for row in archive.json()] == [3]
    all_branches = client.get('/employees?company_id=1&active=true')
    assert {row['id'] for row in all_branches.json()} == {1, 2, 4}


def test_excel_report_matches_filtered_list(client):
    response = client.get('/exports/employees.xlsx?company_id=1&branch_id=11&active=true&q=Welding')
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), read_only=True)
    names = [row[1] for row in list(workbook.active.values)[1:]]
    assert names == ['Alice']
    workbook.close()


def test_pdf_report_accepts_the_same_filter_scope(client):
    response = client.get('/exports/employees.pdf?company_id=1&branch_id=11&active=false&q=Archived')
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')


@pytest.mark.parametrize('path', ['/employees', '/exports/employees.xlsx', '/exports/employees.pdf'])
@pytest.mark.parametrize('query, status', [
    ('company_id=1&branch_id=21', 422),
    ('company_id=2&branch_id=21', 403),
    ('company_id=1&branch_id=999', 422),
    ('company_id=1&branch_id=0', 422),
])
def test_branch_filter_never_crosses_company_access(client, path, query, status):
    assert client.get(f'{path}?{query}').status_code == status
