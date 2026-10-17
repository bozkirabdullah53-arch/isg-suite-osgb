"""OSGB alacak yaşlandırma raporu: kurallar ve API sözleşmesi."""
from datetime import date

from app.services.finance_receivables import ReceivableRow, build_receivables_report
from test_faz0_security import client  # noqa: F401  (paylaşılan istemci ve tohum veri)

TODAY = date(2026, 10, 17)


def _row(id, amount, due, status="pending", kind="income", company_id=1):
    return ReceivableRow(
        id=id,
        company_id=company_id,
        amount=amount,
        due_date=due,
        status=status,
        transaction_type=kind,
        description=f"kayıt {id}",
    )


def test_only_open_income_counts_as_receivable():
    rows = [
        _row(1, 100, date(2026, 9, 1), status="pending"),
        _row(2, 200, date(2026, 9, 1), status="paid"),
        _row(3, 300, date(2026, 9, 1), status="cancelled"),
        _row(4, 400, date(2026, 9, 1), status="pending", kind="expense"),
    ]
    report = build_receivables_report(rows, TODAY)
    assert report["overdue_total"] == 100
    assert report["overdue_count"] == 1
    assert [item["id"] for item in report["items"]] == [1]


def test_aging_buckets_follow_days_overdue():
    rows = [
        _row(1, 10, date(2026, 10, 1)),  # 16 gün → 1-30
        _row(2, 20, date(2026, 8, 1)),  # 77 gün → 61-90
        _row(3, 30, date(2026, 7, 1)),  # 108 gün → 90+
        _row(4, 40, date(2026, 9, 1)),  # 46 gün → 31-60
    ]
    report = build_receivables_report(rows, TODAY)
    by_label = {bucket["label"]: bucket for bucket in report["aging"]}
    assert by_label["1-30 gün"] == {"label": "1-30 gün", "count": 1, "amount": 10}
    assert by_label["31-60 gün"] == {"label": "31-60 gün", "count": 1, "amount": 40}
    assert by_label["61-90 gün"] == {"label": "61-90 gün", "count": 1, "amount": 20}
    assert by_label["90+ gün"] == {"label": "90+ gün", "count": 1, "amount": 30}


def test_not_yet_due_is_separated_from_overdue():
    rows = [
        _row(1, 500, date(2026, 10, 30)),  # henüz vadesi gelmedi
        _row(2, 100, date(2026, 10, 1)),  # gecikmiş
    ]
    report = build_receivables_report(rows, TODAY)
    assert report["not_due_total"] == 500
    assert report["not_due_count"] == 1
    assert report["overdue_total"] == 100
    assert report["open_total"] == 600


def test_overdue_status_with_future_due_date_lands_in_first_bucket():
    rows = [_row(1, 250, date(2026, 11, 1), status="overdue")]
    report = build_receivables_report(rows, TODAY)
    assert report["overdue_count"] == 1
    assert report["items"][0]["days_overdue"] == 1
    assert report["items"][0]["aging_bucket"] == "1-30 gün"


def test_items_are_sorted_most_overdue_first_and_missing_due_date_is_not_overdue():
    rows = [
        _row(1, 10, date(2026, 10, 10)),
        _row(2, 10, date(2026, 7, 10)),
        _row(3, 10, None),
    ]
    report = build_receivables_report(rows, TODAY)
    assert [item["id"] for item in report["items"]] == [2, 1]
    assert report["not_due_count"] == 1
    assert report["not_due_total"] == 10


def test_empty_input_returns_zeroed_report():
    report = build_receivables_report([], TODAY)
    assert report["open_total"] == 0
    assert report["overdue_count"] == 0
    assert report["items"] == []
    assert [bucket["count"] for bucket in report["aging"]] == [0, 0, 0, 0]


def test_receivables_endpoint_scopes_and_reports_overdue(client):
    import app.core.database as dbmod
    from app.core.security import create_access_token, get_password_hash
    from datetime import timedelta
    from app.models.entities import FinanceTransaction, OsgbOrganization, User, UserRole

    with dbmod.SessionLocal() as db:
        osgb = db.query(OsgbOrganization).order_by(OsgbOrganization.id).first()
        admin = User(
            email="recv-admin@example.com",
            full_name="Tahsilat Yönetici",
            hashed_password=get_password_hash("RecvAdmin123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        admin_id = admin.id
        osgb_id = osgb.id
        db.add(
            FinanceTransaction(
                osgb_id=osgb_id,
                transaction_type="income",
                category="contract",
                amount=750,
                transaction_date=date.today() - timedelta(days=60),
                due_date=date.today() - timedelta(days=40),
                status="pending",
                description="Nisan hizmet bedeli",
            )
        )
        db.commit()

    token = create_access_token(str(admin_id))
    url = f"/api/v1/operations/finance/receivables?osgb_id={osgb_id}"
    anonymous = client.get(url)
    assert anonymous.status_code == 401

    result = client.get(url, headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["overdue_total"] >= 750
    assert any(item["description"] == "Nisan hizmet bedeli" and item["days_overdue"] == 40 for item in body["items"])
    assert body["aging"][1]["label"] == "31-60 gün"
