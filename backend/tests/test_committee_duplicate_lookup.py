from app.api.committee_professional import _find_duplicate_member_id
from app.core.database import SessionLocal


class _ScalarResult:
    def scalar(self):
        return None


class _RecordingSession:
    def __init__(self):
        self.statement = None
        self.params = None

    def execute(self, statement, params):
        self.statement = str(statement)
        self.params = params
        return _ScalarResult()


def test_duplicate_lookup_does_not_bind_untyped_null_identifiers():
    db = _RecordingSession()

    result = _find_duplicate_member_id(
        db,
        company_id=118,
        identity_key="employer:118:118",
        employee_id=None,
        user_id=None,
    )

    assert result is None
    assert db.params == {"company_id": 118, "identity_key": "employer:118:118"}
    assert "employee_id = :employee_id" not in db.statement
    assert "user_id = :user_id" not in db.statement


def test_duplicate_lookup_executes_with_null_optional_ids_on_configured_database():
    """Runs on SQLite smoke and PostgreSQL CI; PostgreSQL previously raised AmbiguousParameter."""
    with SessionLocal() as db:
        result = _find_duplicate_member_id(
            db,
            company_id=2_147_483_647,
            identity_key="test:null-safe:committee-duplicate-lookup",
            employee_id=None,
            user_id=None,
        )

    assert result is None
