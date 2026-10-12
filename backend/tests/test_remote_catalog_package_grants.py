from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def test_catalog_grant_admin_guard_is_global_only():
    from app.api.remote_training import _require_global_catalog_admin
    from app.models.entities import UserRole

    _require_global_catalog_admin(SimpleNamespace(role=UserRole.GLOBAL_ADMIN))
    with pytest.raises(HTTPException) as denied:
        _require_global_catalog_admin(SimpleNamespace(role=UserRole.COMPANY_ADMIN))
    assert denied.value.status_code == 403


def test_grant_model_enforces_unique_package_and_osgb_pair():
    from app.core.database import Base
    from app.models import entities, remote_training  # noqa: F401
    from app.models.entities import OsgbOrganization
    from app.models.remote_training import RemoteTrainingCatalogPackage, RemoteTrainingCatalogPackageGrant

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        osgb = OsgbOrganization(name="Grant Test", is_active=True)
        package = RemoteTrainingCatalogPackage(code="grant-test", title="Grant test", status="published")
        db.add_all([osgb, package])
        db.flush()
        db.add(RemoteTrainingCatalogPackageGrant(package_id=package.id, osgb_id=osgb.id))
        db.commit()
        db.add(RemoteTrainingCatalogPackageGrant(package_id=package.id, osgb_id=osgb.id))
        with pytest.raises(Exception):
            db.commit()
