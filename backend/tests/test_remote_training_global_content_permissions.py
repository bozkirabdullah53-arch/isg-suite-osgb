"""Exercise global content ownership through the actual authenticated API."""
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from test_remote_basic_ohs_video_training import remote_client  # noqa: F401


@pytest.fixture()
def content_scope(remote_client, monkeypatch):
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.entities import (
        Branch, Company, Employee, IsgProfessional, OsgbOrganization,
        ProfessionalType, User, UserRole, WorkplaceAssignment,
    )
    from app.models.remote_training import (
        RemoteTrainingCatalogPackage, RemoteTrainingCatalogSection,
        RemoteTrainingCatalogVideo, RemoteTrainingEmployeeAccess,
        RemoteTrainingProgram, RemoteTrainingSection, RemoteTrainingVideo,
    )
    from app.services.object_store import get_object_store, reset_object_store_for_tests

    monkeypatch.setattr(settings, "object_storage_backend", "local")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_force_off", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_package_codes", "common-basic-ohs")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")
    reset_object_store_for_tests()
    store = get_object_store()
    data = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    with SessionLocal() as db:
        osgb = OsgbOrganization(name="Content Owner OSGB", is_active=True)
        foreign_osgb = OsgbOrganization(name="Foreign Content OSGB", is_active=True)
        db.add_all([osgb, foreign_osgb])
        db.flush()
        company = Company(name="Authorized Firma", osgb_id=osgb.id, is_active=True)
        foreign_company = Company(name="Foreign Firma", osgb_id=foreign_osgb.id, is_active=True)
        db.add_all([company, foreign_company])
        db.flush()
        branch = Branch(company_id=company.id, name="Merkez", is_active=True)
        employee = Employee(company_id=company.id, branch=branch, full_name="Atanan Çalışan", is_active=True)
        foreign_employee = Employee(company_id=foreign_company.id, full_name="Diğer Çalışan", is_active=True)
        db.add_all([branch, employee, foreign_employee])
        users = {}
        professional_roles = {
            UserRole.SAFETY_SPECIALIST: ProfessionalType.SAFETY_SPECIALIST,
            UserRole.WORKPLACE_PHYSICIAN: ProfessionalType.WORKPLACE_PHYSICIAN,
            UserRole.OTHER_HEALTH_PERSONNEL: ProfessionalType.OTHER_HEALTH_PERSONNEL,
        }
        for role in UserRole:
            user = User(
                email=f"{role.value}@global-content.test", full_name=role.value,
                hashed_password="unused", role=role, is_active=True,
                osgb_id=None if role == UserRole.GLOBAL_ADMIN else osgb.id,
                company_id=company.id if role == UserRole.READ_ONLY else None,
                password_change_required=False,
            )
            db.add(user)
            db.flush()
            users[role.value] = user
            if role in professional_roles:
                pro = IsgProfessional(
                    osgb_id=osgb.id, full_name=user.full_name, email=user.email,
                    professional_type=professional_roles[role], is_active=True,
                )
                db.add(pro)
                db.flush()
                db.add(WorkplaceAssignment(
                    osgb_id=osgb.id, company_id=company.id, professional_id=pro.id,
                    professional_type=pro.professional_type, start_date=date(2020, 1, 1),
                ))
        workplace = User(
            email="workplace@global-content.test", full_name="İşyeri Yetkilisi",
            hashed_password="unused", role=UserRole.COMPANY_ADMIN,
            osgb_id=osgb.id, company_id=company.id, is_active=True,
            password_change_required=False,
        )
        db.add(workplace)
        db.flush()
        users["workplace"] = workplace
        shared = RemoteTrainingCatalogPackage(
            osgb_id=None, code="common-basic-ohs", title="Merkezi Eğitim",
            status="published", requires_final_exam=False, total_duration_seconds=10,
            published_at=datetime.utcnow(),
        )
        legacy = RemoteTrainingCatalogPackage(
            osgb_id=osgb.id, code="legacy-package", title="Mevcut OSGB Paketi", status="draft",
        )
        db.add_all([shared, legacy])
        db.flush()
        section = RemoteTrainingCatalogSection(
            package_id=shared.id, code="GEN-01", title="Merkezi Ders", order_index=1,
        )
        program = RemoteTrainingProgram(
            osgb_id=osgb.id, company_id=company.id, source_catalog_package_id=shared.id,
            source_catalog_code=shared.code, source_catalog_revision_no=shared.revision_no,
            title=shared.title, status="published", requires_final_exam=False,
            total_duration_seconds=10, workplace_assignment_allowed=True,
        )
        db.add_all([section, program])
        db.flush()
        catalog_video = RemoteTrainingCatalogVideo(
            package_id=shared.id, section_id=section.id, title="Global Video", order_index=1,
            storage_key=store.put_bytes("catalog/global/lesson.mp4", data),
            original_file_name="lesson.mp4", content_type="video/mp4",
            file_size_bytes=len(data), duration_seconds=10, status="published", is_current=True,
        )
        program_section = RemoteTrainingSection(
            osgb_id=osgb.id, company_id=company.id, program_id=program.id,
            title="Merkezi Ders", sector_code="common", order_index=1,
        )
        db.add_all([catalog_video, program_section])
        db.flush()
        program_video = RemoteTrainingVideo(
            osgb_id=osgb.id, company_id=company.id, program_id=program.id,
            section_id=program_section.id, title="Firma Video", order_index=1,
            storage_key=store.put_bytes("company/lesson.mp4", data),
            original_file_name="lesson.mp4", content_type="video/mp4",
            file_size_bytes=len(data), duration_seconds=10, status="published", is_current=True,
        )
        db.add(program_video)
        db.add(RemoteTrainingEmployeeAccess(
            osgb_id=osgb.id, company_id=company.id, employee_id=employee.id,
            user_id=users["read_only"].id, is_active=True,
        ))
        db.commit()
        result = {
            "company": company.id, "foreign_company": foreign_company.id,
            "employee": employee.id, "foreign_employee": foreign_employee.id,
            "package": shared.id, "legacy": legacy.id, "section": section.id,
            "video": catalog_video.id, "program": program.id,
            "program_section": program_section.id, "program_video": program_video.id,
            "headers": {key: {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
                        for key, user in users.items()},
        }
    yield result
    reset_object_store_for_tests()


@pytest.mark.parametrize("role", [
    "company_admin", "safety_specialist", "workplace_physician",
    "other_health_personnel", "workplace", "read_only",
])
def test_lower_roles_cannot_mutate_catalog_or_company_video_content(remote_client, content_scope, role):
    scope = content_scope
    base = "/api/v1/trainings/remote"
    package, section, video = scope["package"], scope["section"], scope["video"]
    program, program_section, program_video = scope["program"], scope["program_section"], scope["program_video"]
    requests = [
        ("POST", "/catalog/packages", {"title": "Yeni Eğitim", "sector_code": "common"}),
        ("PATCH", f"/catalog/packages/{package}", {"title": "Yetkisiz Değişiklik"}),
        ("DELETE", f"/catalog/packages/{package}", None),
        ("POST", f"/catalog/packages/{package}/fork", None),
        ("POST", f"/catalog/packages/{package}/sections", {"code": "GEN-02", "title": "Yeni Bölüm"}),
        ("PATCH", f"/catalog/packages/{package}/sections/order", {"section_ids": [section]}),
        ("PATCH", f"/catalog/sections/{section}", {"title": "Yetkisiz Bölüm"}),
        ("DELETE", f"/catalog/sections/{section}", None),
        ("POST", f"/catalog/sections/{section}/archive", None),
        ("PATCH", f"/catalog/videos/{video}", {"title": "Yetkisiz Video"}),
        ("DELETE", f"/catalog/videos/{video}", None),
        ("POST", "/programs", {"company_id": scope["company"], "title": "Yeni Program"}),
        ("PATCH", f"/programs/{program}", {"title": "Değişen Program"}),
        ("POST", f"/programs/{program}/sections", {"title": "Yeni Ders"}),
        ("PUT", f"/programs/{program}/sectors", {"sector_codes": ["common"]}),
        ("PATCH", f"/sections/{program_section}", {"title": "Değişen Ders"}),
        ("POST", f"/sections/{program_section}/archive", None),
        ("PATCH", f"/videos/{program_video}", {"title": "Değişen Video"}),
        ("DELETE", f"/videos/{program_video}", None),
        ("POST", f"/programs/{program}/checkpoint-questions", {
            "question_text": "Yetkisiz soru?", "options": {"A": "Bir", "B": "İki", "C": "Üç", "D": "Dört"}, "correct_option": "A",
        }),
        ("POST", f"/programs/{program}/exam/questions", {"question_id": 1}),
        ("PATCH", f"/programs/{program}/final-exam-questions/1", {
            "question_text": "Yetkisiz soru?", "options": {"A": "Bir", "B": "İki", "C": "Üç", "D": "Dört"}, "correct_option": "A",
        }),
        ("DELETE", f"/programs/{program}/exam/questions/1", None),
    ]
    for action in ["ready-for-review", "publish", "unpublish", "archive", "restore"]:
        requests.append(("POST", f"/catalog/packages/{package}/{action}", None))
    for action in ["publish", "unpublish", "archive", "retry-processing"]:
        requests.extend([
            ("POST", f"/catalog/videos/{video}/{action}", None),
            ("POST", f"/videos/{program_video}/{action}", None),
        ])
    for action in ["ready-for-review", "publish", "unpublish", "archive"]:
        requests.append(("POST", f"/programs/{program}/{action}", None))
    for method, path, payload in requests:
        response = remote_client.request(method, base + path, headers=scope["headers"][role], json=payload)
        assert response.status_code == 403, (role, method, path, response.text)
    for path in [f"/catalog/sections/{section}/videos", f"/sections/{program_section}/videos"]:
        response = remote_client.post(
            base + path, headers=scope["headers"][role], data={"title": "Yetkisiz Yükleme"},
            files={"file": ("video.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16, "video/mp4")},
        )
        assert response.status_code == 403, (role, path, response.text)


def test_global_admin_creates_shared_packages_and_manages_existing_osgb_content(remote_client, content_scope):
    from app.core.database import SessionLocal
    from app.models.remote_training import RemoteTrainingCatalogPackage

    base = "/api/v1/trainings/remote"
    headers = content_scope["headers"]["global_admin"]
    created = remote_client.post(base + "/catalog/packages", headers=headers, json={
        "title": "Global Yeni Eğitim", "sector_code": "common",
    })
    assert created.status_code == 201, created.text
    assert created.json()["is_shared"] is True
    package_id = created.json()["id"]
    section = remote_client.post(f"{base}/catalog/packages/{package_id}/sections", headers=headers, json={
        "code": "EK-01", "title": "Global Yeni Ders",
    })
    assert section.status_code == 201, section.text
    for package_id in [content_scope["package"], content_scope["legacy"]]:
        response = remote_client.patch(f"{base}/catalog/packages/{package_id}", headers=headers, json={
            "title": f"Global Düzenlenen {package_id}",
        })
        assert response.status_code == 200, response.text
    rows = remote_client.get(base + "/catalog/packages", headers=headers)
    assert rows.status_code == 200, rows.text
    assert created.json()["id"] in [row["id"] for row in rows.json()]
    assert content_scope["legacy"] in [row["id"] for row in rows.json()]
    with SessionLocal() as db:
        package = db.get(RemoteTrainingCatalogPackage, content_scope["package"])
        assert package.title == f"Global Düzenlenen {package.id}"
        assert db.get(RemoteTrainingCatalogPackage, created.json()["id"]).osgb_id is None


@pytest.mark.parametrize("role", ["company_admin", "safety_specialist", "workplace_physician", "other_health_personnel"])
def test_lower_operators_keep_company_and_employee_assignment_without_content_writes(remote_client, content_scope, role):
    from app.core.database import SessionLocal
    from app.models.remote_training import RemoteTrainingCatalogPackage, RemoteTrainingCatalogSection

    base = "/api/v1/trainings/remote"
    headers = content_scope["headers"][role]
    with SessionLocal() as db:
        before = (db.scalar(select(func.count()).select_from(RemoteTrainingCatalogPackage)),
                  db.scalar(select(func.count()).select_from(RemoteTrainingCatalogSection)))
    meta = remote_client.get(base + "/meta", headers=headers).json()
    assert meta["can_manage"] is True
    assert meta["can_edit_content"] is False
    assert meta["can_edit_shared_content"] is False
    rows = remote_client.get(base + "/catalog/packages", headers=headers)
    assert rows.status_code == 200, rows.text
    assert [row["id"] for row in rows.json()] == [content_scope["package"]]
    with SessionLocal() as db:
        after = (db.scalar(select(func.count()).select_from(RemoteTrainingCatalogPackage)),
                 db.scalar(select(func.count()).select_from(RemoteTrainingCatalogSection)))
    assert after == before
    materialized = remote_client.post(
        f"{base}/catalog/packages/{content_scope['package']}/materialize", headers=headers,
        json={"company_id": content_scope["company"]},
    )
    assert materialized.status_code == 201, materialized.text
    program_id = materialized.json()["id"]
    assigned = remote_client.post(f"{base}/programs/{program_id}/assign", headers=headers, json={
        "employee_ids": [content_scope["employee"]],
    })
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["created_count"] == 1
    assignments = remote_client.get(f"{base}/programs/{program_id}/assignments", headers=headers)
    assert assignments.status_code == 200, assignments.text
    assert assignments.json()[0]["employee_id"] == content_scope["employee"]
    certificates = remote_client.get(base + "/certificates", headers=headers, params={"company_id": content_scope["company"]})
    assert certificates.status_code == 200, certificates.text
    forbidden = remote_client.post(
        f"{base}/catalog/packages/{content_scope['package']}/materialize", headers=headers,
        json={"company_id": content_scope["foreign_company"]},
    )
    assert forbidden.status_code == 403, forbidden.text
    forbidden_employee = remote_client.post(f"{base}/programs/{program_id}/assign", headers=headers, json={
        "employee_ids": [content_scope["foreign_employee"]],
    })
    assert forbidden_employee.status_code == 422, forbidden_employee.text


def test_global_custom_package_is_shared_after_publication_and_drafts_are_private(remote_client, content_scope):
    from app.core.database import SessionLocal
    from app.models.remote_training import RemoteTrainingCatalogPackage

    base = "/api/v1/trainings/remote/catalog/packages"
    created = remote_client.post(base, headers=content_scope["headers"]["global_admin"], json={
        "title": "Tüm OSGBlere Eğitim", "sector_code": "common",
    })
    assert created.status_code == 201, created.text
    package_id = created.json()["id"]
    headers = content_scope["headers"]["company_admin"]
    assert remote_client.get(f"{base}/{package_id}", headers=headers).status_code == 404
    assert package_id not in [row["id"] for row in remote_client.get(base, headers=headers).json()]
    with SessionLocal() as db:
        db.get(RemoteTrainingCatalogPackage, package_id).status = "published"
        db.commit()
    assert package_id in [row["id"] for row in remote_client.get(base, headers=headers).json()]


def test_global_deletion_survives_catalog_refresh_and_preserves_company_history(remote_client, content_scope):
    from app.core.database import SessionLocal
    from app.models.remote_training import RemoteTrainingCatalogPackage, RemoteTrainingProgram, RemoteTrainingVideo

    base = "/api/v1/trainings/remote/catalog/packages"
    headers = content_scope["headers"]["global_admin"]
    deleted = remote_client.delete(f"{base}/{content_scope['package']}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["history_preserved"] is True
    for _ in range(2):
        rows = remote_client.get(base, headers=headers)
        assert rows.status_code == 200, rows.text
        assert "common-basic-ohs" not in [row["code"] for row in rows.json()]
    with SessionLocal() as db:
        assert db.get(RemoteTrainingCatalogPackage, content_scope["package"]) is None
        program = db.get(RemoteTrainingProgram, content_scope["program"])
        assert program.source_catalog_package_id is None
        assert program.status == "published"
        assert db.get(RemoteTrainingVideo, content_scope["program_video"]).status == "published"
