"""6331 compliance register smoke tests."""
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.api.incidents import _apply_sgk_process
from app.api.compliance_registers import (
    COMMITTEE_ROLES,
    MEASUREMENT_TYPES,
    PERIODIC_CATEGORIES,
    _ep_enrich,
)
from app.schemas.compliance import EmergencyPlanCreate


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


def test_emergency_scene_parse_and_empty():
    from app.api.compliance_registers import EMPTY_SCENE, _parse_scene

    empty = _parse_scene(None)
    assert empty["objects"] == []
    assert empty["paths"] == []
    parsed = _parse_scene(EMPTY_SCENE)
    assert parsed["version"] == 1
    rich = _parse_scene('{"version":1,"objects":[{"id":"a","type":"exit","x":1,"y":2}],"paths":[]}')
    assert len(rich["objects"]) == 1
    assert rich["objects"][0]["type"] == "exit"


def test_kroki_symbol_catalog_meta():
    from app.api.compliance_registers import ep_meta
    from types import SimpleNamespace

    meta = ep_meta(user=SimpleNamespace())
    assert meta["engine"] == "emergency-kroki-v2.2"
    assert "exit" in meta["symbols"]
    assert "extinguisher" in meta["symbols"]


def test_emergency_plan_create_rejects_legacy_invalid_date():
    with pytest.raises(ValidationError):
        EmergencyPlanCreate(
            company_id=1,
            title="Acil Durum Planı",
            plan_date=date(1111, 1, 1),
        )


def test_emergency_plan_list_enrichment_allows_legacy_invalid_date():
    legacy = SimpleNamespace(
        id=7,
        company_id=1,
        title="Eski Acil Durum Planı",
        revision_no="00",
        plan_date=date(1111, 1, 1),
        next_review_date=None,
        assembly_areas=None,
        scenario_summary=None,
        kroki_file_name=None,
        kroki_storage_path=None,
        document_id=None,
        status="Aktif",
        notes=None,
        locked_at=None,
        is_active=True,
        created_by_id=1,
        created_at=date(2026, 1, 1),
        updated_at=date(2026, 1, 1),
    )

    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    response = _ep_enrich(db, legacy)

    assert response.id == 7
    assert response.plan_date == date(1111, 1, 1)
    assert response.floor_count == 0
