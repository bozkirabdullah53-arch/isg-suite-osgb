from __future__ import annotations


def test_ohs_committee_residuals_are_deleted_child_first():
    from app.services.osgb_purge import _purge_osgb_ohs_committee_residuals

    class FakeSession:
        def __init__(self):
            self.calls: list[tuple[str, dict[str, int]]] = []
            self.flushed = False

        def execute(self, stmt, params):
            self.calls.append((str(stmt), dict(params)))

        def flush(self):
            self.flushed = True

    db = FakeSession()
    _purge_osgb_ohs_committee_residuals(db, 35)

    assert [
        "ohs_committee_signature_steps",
        "ohs_committee_meeting_versions",
        "ohs_committee_duplicate_reports",
    ] == [
        next(
            name
            for name in (
                "ohs_committee_signature_steps",
                "ohs_committee_meeting_versions",
                "ohs_committee_duplicate_reports",
            )
            if name in sql
        )
        for sql, _params in db.calls
    ]
    assert all(params == {"osgb_id": 35} for _sql, params in db.calls)
    assert db.flushed is True
