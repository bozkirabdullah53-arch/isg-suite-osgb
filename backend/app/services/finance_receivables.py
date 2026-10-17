"""OSGB alacak (tahsilat) takibi: açık gelirleri vadeye göre yaşlandırır.

Tanımlar şirket özetiyle (company_overview) aynıdır:
- Alacak: gelir kaydı ve durumu "pending" veya "overdue".
- Vadesi geçmiş: durumu "overdue" olan ya da vadesi bugünden önce olan açık alacak.
Bu modül veritabanına bağımlı değildir; kayıtlar ReceivableRow olarak verilir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

OPEN_STATUSES = ("pending", "overdue")

AGING_BUCKETS = (
    (1, 30, "1-30 gün"),
    (31, 60, "31-60 gün"),
    (61, 90, "61-90 gün"),
    (91, None, "90+ gün"),
)


@dataclass(frozen=True)
class ReceivableRow:
    id: int
    company_id: int | None
    amount: int
    due_date: date | None
    status: str
    transaction_type: str
    description: str | None = None


def _days_overdue(row: ReceivableRow, today: date) -> int:
    if row.due_date is None or row.due_date >= today:
        return 0
    return (today - row.due_date).days


def _bucket_label(days: int) -> str:
    for low, high, label in AGING_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    return AGING_BUCKETS[0][2]


def build_receivables_report(rows: list[ReceivableRow], today: date) -> dict:
    """Açık gelirleri toplar, vade gününe göre yaşlandırır ve gecikenleri listeler."""
    open_rows = [r for r in rows if r.transaction_type == "income" and r.status in OPEN_STATUSES]

    aging = {label: {"label": label, "count": 0, "amount": 0} for _, _, label in AGING_BUCKETS}
    overdue_items: list[dict] = []
    not_due_total = 0
    not_due_count = 0

    for row in open_rows:
        days = _days_overdue(row, today)
        is_overdue = row.status == "overdue" or days > 0
        if not is_overdue:
            not_due_total += row.amount
            not_due_count += 1
            continue
        # Durumu "overdue" ama vadesi henüz gelmemiş kayıt, en düşük yaşlandırma grubuna girer.
        effective_days = max(days, 1)
        label = _bucket_label(effective_days)
        aging[label]["count"] += 1
        aging[label]["amount"] += row.amount
        overdue_items.append(
            {
                "id": row.id,
                "company_id": row.company_id,
                "amount": row.amount,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "days_overdue": effective_days,
                "aging_bucket": label,
                "description": row.description,
            }
        )

    overdue_items.sort(key=lambda item: (-item["days_overdue"], item["id"]))
    overdue_total = sum(item["amount"] for item in overdue_items)

    return {
        "as_of": today.isoformat(),
        "open_total": overdue_total + not_due_total,
        "overdue_total": overdue_total,
        "overdue_count": len(overdue_items),
        "not_due_total": not_due_total,
        "not_due_count": not_due_count,
        "aging": [aging[label] for _, _, label in AGING_BUCKETS],
        "items": overdue_items,
    }
