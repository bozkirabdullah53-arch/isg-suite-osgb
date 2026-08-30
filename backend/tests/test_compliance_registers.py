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
    assert row.sgk_due_date == date(2026, 7, 6)
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


def test_emergency_readiness_separates_required_fields_from_legal_opinion():
    from app.services.emergency_plan_compliance import calculate_plan_readiness

    plan = SimpleNamespace(plan_date=date(2026, 1, 1), next_review_date=date(2030, 1, 1))
    company = SimpleNamespace(name="Örnek İşyeri", address="Adres", authorized_person="İşveren", hazard_class="az_tehlikeli")
    floor = SimpleNamespace(
        id=1,
        name="Zemin",
        background_storage_path=None,
        scene_json=(
            '{"objects":['
            '{"type":"room"},{"type":"exit"},{"type":"route"},'
            '{"type":"assembly"},{"type":"firstaid"},{"type":"extinguisher"}'
            ']}'
        ),
    )
    details = {
        "emergency_types": ["yangin"],
        "preventive_measures": "Yanıcı malzemeler kontrollü depolanır ve alarm sistemi izlenir.",
        "measurement_evaluation": "Mevcut ortam ölçümleri ve risk değerlendirmesi incelenmiştir.",
        "equipment_inventory": "Yangın tüpleri, ilk yardım çantası ve gerekli KKD listelenmiştir.",
        "response_methods": "İhbar, ilk müdahale, tahliye, toplanma ve yoklama sırası uygulanır.",
        "special_risk_mode": "not_applicable",
        "energy_controls_mode": "not_applicable",
        "external_contacts": [
            {"name": "İtfaiye", "phone": "110", "note": "Yerel irtibat"},
        ],
        "special_groups": "Refakat planı saha sorumlusu tarafından yürütülür.",
        "visitors_included": True,
        "temporary_workers_included": True,
        "approval_status": "secure_esign",
        "posted_confirmed": True,
        "employees_informed": True,
        "last_drill_date": date.today().isoformat(),
    }
    result = calculate_plan_readiness(
        plan,
        company,
        details,
        [floor],
        {"team_codes": ["sondurme", "kurtarma", "koruma", "ilk_yardim"], "empty_team_codes": []},
    )

    assert result["pct"] == 100
    assert result["status"] == "ready"
    assert result["version"] == "emergency-plan-compliance-v1"


def test_emergency_support_staff_thresholds_follow_hazard_class():
    from app.services.emergency_plan_compliance import support_team_required_count

    assert support_team_required_count(9, "az tehlikeli") == 1
    assert support_team_required_count(50, "az tehlikeli") == 1
    assert support_team_required_count(51, "az tehlikeli") == 2
    assert support_team_required_count(31, "çok tehlikeli") == 2
    assert support_team_required_count(41, "tehlikeli") == 2
    assert support_team_required_count(41, "") is None
