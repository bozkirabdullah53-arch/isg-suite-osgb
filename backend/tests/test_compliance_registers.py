"""6331 compliance register smoke tests."""
from datetime import date, timedelta
from types import SimpleNamespace

from app.api.incidents import _apply_sgk_process
from app.api.compliance_registers import PERIODIC_CATEGORIES, MEASUREMENT_TYPES, COMMITTEE_ROLES


def test_meta_catalogs_nonempty():
    assert any(c["code"] == "yangin_tup" for c in PERIODIC_CATEGORIES)
    assert any(t["code"] == "gurultu" for t in MEASUREMENT_TYPES)
    assert any(r["code"] == "calisan_temsilcisi" for r in COMMITTEE_ROLES)


def test_sgk_process_sets_due_for_accident():
    row = SimpleNamespace(
        event_type="is_kazasi",
        event_date=date(2026, 7, 1),
        sgk_reported=False,
        sgk_due_date=None,
        sgk_notification_status=None,
    )
    _apply_sgk_process(row)
    assert row.sgk_due_date == date(2026, 7, 4)
    assert row.sgk_notification_status in ("bekliyor", "gecikti")


def test_sgk_process_completed_when_reported():
    row = SimpleNamespace(
        event_type="is_kazasi",
        event_date=date.today() - timedelta(days=1),
        sgk_reported=True,
        sgk_due_date=None,
        sgk_notification_status=None,
    )
    _apply_sgk_process(row)
    assert row.sgk_notification_status == "tamamlandi"


def test_import_compliance_routers():
    from app.api import compliance_registers

    assert compliance_registers.pc_router.prefix == "/periodic-controls"
    assert compliance_registers.ep_router.prefix == "/emergency-plans"
    assert compliance_registers.wm_router.prefix == "/workplace-measurements"
    assert compliance_registers.oc_router.prefix == "/ohs-committee"
    assert compliance_registers.da_router.prefix == "/document-approvals"
