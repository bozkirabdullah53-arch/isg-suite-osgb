"""Çalışan bazlı temel İSG eğitimi geçerliliği.

Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında
Yönetmelik:
- md.6: çalışan işe başlamadan önce temel eğitimi almış olmalıdır.
- md.11: temel eğitim, tehlike sınıfına göre az tehlikeli 3, tehlikeli 2,
  çok tehlikeli 1 yılda bir yenilenir.
- md.6/2: iş değişikliği, uzun süreli işten uzak kalma ve iş ekipmanı
  değişikliğinde eğitim tekrarlanır.

Kayıt üzerinde tutulan `next_training_date` oturum bazlıdır; bu modül onu
çalışan bazına indirger ve "kimin eğitimi dolmuş?" sorusunu cevaplar.
Yalnız hesap yapar, kayıt yazmaz.
"""
from __future__ import annotations

from datetime import date

BASIC_RENEWAL_YEARS: dict[str, int] = {
    "Az Tehlikeli": 3,
    "Tehlikeli": 2,
    "Çok Tehlikeli": 1,
}

# Yenileme tarihine bu kadar gün kalınca planlamaya alınmalı.
DUE_SOON_DAYS = 60

STATUS_ORDER = {"never": 0, "expired": 1, "due_soon": 2, "ok": 3}

STATUS_LABELS = {
    "never": "Eğitim kaydı yok",
    "expired": "Süresi doldu",
    "due_soon": "Yaklaşıyor",
    "ok": "Geçerli",
}

RETRAINING_TRIGGERS = (
    "İş veya görev değişikliği",
    "Uzun süreli işten uzak kalma (hastalık, izin) sonrası dönüş",
    "İş ekipmanı veya çalışma yöntemi değişikliği",
    "İş kazası veya meslek hastalığı sonrası",
)


def renewal_years(hazard_class: str | None) -> int | None:
    return BASIC_RENEWAL_YEARS.get((hazard_class or "").strip())


def add_years(start: date, years: int) -> date:
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def _fmt(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def evaluate_employee(
    *,
    hire_date: date | None = None,
    last_training_end: date | None = None,
    next_due: date | None = None,
    today: date | None = None,
) -> dict:
    """Tek çalışanın temel eğitim durumu.

    `next_due` eğitim kaydından gelen yenileme tarihi; yoksa eğitim var ama
    tarih hesaplanmamış demektir (eski kayıt) ve süresiz sayılmaz.
    """
    now = today or date.today()

    if last_training_end is None:
        days_since_hire = (now - hire_date).days if hire_date else None
        if hire_date and days_since_hire is not None and days_since_hire >= 0:
            message = (
                f"Temel İSG eğitimi kaydı yok. İşe başlama {_fmt(hire_date)} "
                f"({days_since_hire} gün önce) — yönetmelik işe başlamadan önce eğitimi zorunlu tutar."
            )
        else:
            message = "Temel İSG eğitimi kaydı yok. İşe başlamadan önce eğitim verilmelidir."
        return {
            "status": "never",
            "status_label": STATUS_LABELS["never"],
            "days_left": None,
            "last_training_end": None,
            "next_due": None,
            "message": message,
        }

    base = {
        "last_training_end": last_training_end.isoformat(),
        "next_due": next_due.isoformat() if next_due else None,
    }

    if next_due is None:
        return {
            **base,
            "status": "expired",
            "status_label": STATUS_LABELS["expired"],
            "days_left": None,
            "message": (
                f"Son eğitim {_fmt(last_training_end)}. Yenileme tarihi hesaplanamadı "
                "(eski kayıt); eğitimi yenileyip kaydı güncelleyin."
            ),
        }

    days_left = (next_due - now).days
    if days_left < 0:
        status = "expired"
        message = (
            f"Eğitim {_fmt(next_due)} tarihinde doldu ({abs(days_left)} gün geçti). "
            "Yenileme eğitimi planlanmalı."
        )
    elif days_left <= DUE_SOON_DAYS:
        status = "due_soon"
        message = f"Eğitim {_fmt(next_due)} tarihinde yenilenmeli — {days_left} gün kaldı."
    else:
        status = "ok"
        message = f"Eğitim {_fmt(next_due)} tarihine kadar geçerli."

    return {
        **base,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "days_left": days_left,
        "message": message,
    }


def summarize(rows: list[dict]) -> dict:
    counts = {"never": 0, "expired": 0, "due_soon": 0, "ok": 0}
    for row in rows:
        status = row.get("status")
        if status in counts:
            counts[status] += 1
    total = len(rows)
    action_needed = counts["never"] + counts["expired"] + counts["due_soon"]
    return {
        "total_employees": total,
        **counts,
        "action_needed": action_needed,
        "compliance_rate": round((counts["ok"] / total) * 100, 1) if total else 0.0,
        "due_soon_days": DUE_SOON_DAYS,
        "retraining_triggers": list(RETRAINING_TRIGGERS),
    }


def sort_key(row: dict):
    """Önce hiç eğitimsiz, sonra en çok geciken."""
    order = STATUS_ORDER.get(row.get("status"), 9)
    days = row.get("days_left")
    return (order, days if days is not None else -10_000, row.get("full_name") or "")
