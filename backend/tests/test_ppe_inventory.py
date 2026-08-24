"""KKD stok hareketleri ve süre durumları için yan etkisiz regresyon testleri."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.api.ppe import _stock_response
from app.schemas.ppe import PpeAssignmentAction, PpeInventoryCreate


def _item(**overrides):
    values = {
        "id": 1,
        "company_id": 7,
        "branch_id": None,
        "category": "Baş Koruyucular",
        "item_type": "Baret",
        "brand": "Test",
        "model": "M1",
        "size": None,
        "shelf_life_text": "36 ay",
        "expiry_date": date.today() + timedelta(days=90),
        "renewal_date": None,
        "min_stock": 2,
        "notes": None,
        "is_active": True,
        "created_by_id": 10,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_stock_balance_counts_inbound_issue_return_and_scrap():
    response = _stock_response(
        _item(),
        {"inbound": 12, "issue": 5, "return": 2, "scrap": 1},
    )

    assert response.received_quantity == 12
    assert response.issued_quantity == 5
    assert response.returned_quantity == 2
    assert response.scrapped_quantity == 1
    assert response.available_quantity == 8
    assert response.stock_state == "ok"


def test_stock_state_prioritizes_expiry_before_low_stock():
    response = _stock_response(
        _item(expiry_date=date.today() - timedelta(days=1), min_stock=100),
        {"inbound": 1},
    )

    assert response.stock_state == "expired"


def test_stock_state_also_tracks_renewal_date():
    response = _stock_response(
        _item(expiry_date=None, renewal_date=date.today() + timedelta(days=10)),
        {"inbound": 10},
    )

    assert response.stock_state == "due_soon"


def test_inventory_payload_validates_catalog_and_action_defaults_to_remaining_quantity():
    payload = PpeInventoryCreate(
        company_id=7,
        category="Baş Koruyucular",
        item_type="Baret",
        initial_quantity=10,
        min_stock=2,
    )
    action = PpeAssignmentAction(reason="Saha iadesi")

    assert payload.initial_quantity == 10
    assert payload.min_stock == 2
    assert action.quantity is None
