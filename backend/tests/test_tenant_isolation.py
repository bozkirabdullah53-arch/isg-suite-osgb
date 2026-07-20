from app.api.tenant_access import user_in_admin_scope
from app.models.entities import User, UserRole


def test_null_company_admins_are_not_same_tenant():
    a = User(id=1, email="a@x.com", full_name="A", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=1)
    b = User(id=2, email="b@x.com", full_name="B", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=2)
    # Without DB company lookup, different osgb_id must fail
    class DummyDB:
        def get(self, *_a, **_k):
            return None

    assert user_in_admin_scope(DummyDB(), a, b) is False
    assert user_in_admin_scope(DummyDB(), a, a) is True


def test_same_osgb_admins_share_scope():
    a = User(id=1, email="a@x.com", full_name="A", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=5)
    b = User(id=2, email="b@x.com", full_name="B", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=5)

    class DummyDB:
        def get(self, *_a, **_k):
            return None

    assert user_in_admin_scope(DummyDB(), a, b) is True


def test_company_admin_null_without_osgb_cannot_manage():
    a = User(id=1, email="a@x.com", full_name="A", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=None)
    b = User(id=2, email="b@x.com", full_name="B", hashed_password="x", role=UserRole.COMPANY_ADMIN, company_id=None, osgb_id=None)

    class DummyDB:
        def get(self, *_a, **_k):
            return None

    assert user_in_admin_scope(DummyDB(), a, b) is False
