"""Premium employee validity wording for the 2026 training rules.

This is a read-only calculation wrapper. It corrects the old assumption that a
Basic İSG record itself must exist before the employee starts. The premium rule
is: Work Start before actual work, Basic İSG as soon as possible and in all cases
within three months after start. Existing persisted training rows are untouched.
"""
from __future__ import annotations

import calendar
from datetime import date
from functools import wraps

from app.services.training_lifecycle_v2 import premium_lifecycle_active

_original_evaluate_employee = None


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def no_basic_training_state(*, hire_date: date | None, today: date | None = None) -> dict:
    now = today or date.today()
    if hire_date is None:
        return {
            "status": "never",
            "status_label": "Temel eğitim kaydı yok",
            "days_left": None,
            "last_training_end": None,
            "next_due": None,
            "message": (
                "Temel İSG eğitimi kaydı yok. İşe başlama eğitimi ayrı olarak fiilen işe başlamadan önce; "
                "Temel İSG eğitimi ise işe başladıktan sonra en kısa sürede ve en geç üç ay içinde tamamlanmalıdır."
            ),
        }

    due = add_months(hire_date, 3)
    days_left = (due - now).days
    if days_left < 0:
        message = (
            f"Temel İSG eğitimi kaydı yok. İşe başlama tarihi {hire_date.strftime('%d.%m.%Y')}; "
            f"Temel eğitimin en geç {due.strftime('%d.%m.%Y')} tarihinde tamamlanması gerekiyordu "
            f"({abs(days_left)} gün gecikmiş). İşe Başlama Eğitimi bu kayıttan ayrıdır."
        )
    else:
        message = (
            f"Temel İSG eğitimi henüz kaydedilmemiş. İşe başlama tarihi {hire_date.strftime('%d.%m.%Y')}; "
            f"Temel eğitim en geç {due.strftime('%d.%m.%Y')} tarihine kadar tamamlanmalı "
            f"({days_left} gün kaldı). İşe Başlama Eğitimi fiilen işe başlamadan önce ayrıca verilmelidir."
        )
    return {
        "status": "never",
        "status_label": "Temel eğitim kaydı yok",
        "days_left": days_left,
        "last_training_end": None,
        "next_due": due.isoformat(),
        "message": message,
    }


def install_training_lifecycle_v2_validity() -> str:
    global _original_evaluate_employee

    from app.services import training_validity

    current = training_validity.evaluate_employee
    if getattr(current, "_premium_training_lifecycle_v2", False):
        return "already-active"
    _original_evaluate_employee = current

    @wraps(current)
    def premium_evaluate_employee(
        *,
        hire_date: date | None = None,
        last_training_end: date | None = None,
        next_due: date | None = None,
        today: date | None = None,
    ) -> dict:
        if premium_lifecycle_active() and last_training_end is None:
            return no_basic_training_state(hire_date=hire_date, today=today)
        return _original_evaluate_employee(
            hire_date=hire_date,
            last_training_end=last_training_end,
            next_due=next_due,
            today=today,
        )

    premium_evaluate_employee._premium_training_lifecycle_v2 = True
    training_validity.evaluate_employee = premium_evaluate_employee
    return "active"
