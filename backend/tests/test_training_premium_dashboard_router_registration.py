from pathlib import Path


def test_premium_dashboard_router_is_registered_without_import_side_effects():
    main_text = Path("app/main.py").read_text(encoding="utf-8")
    assert "training_premium_dashboard_v1" in main_text
    assert "training_premium_dashboard_v1.router" in main_text
