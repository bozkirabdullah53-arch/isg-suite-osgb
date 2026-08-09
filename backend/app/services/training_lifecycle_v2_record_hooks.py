"""Persisted-record hooks for premium training lifecycle v2.

Only NEW post-cutover Work Start / Information Refresh rows are normalized so
that they do not pretend to renew the Basic İSG training period. No historical
row is scanned or rewritten and no migration is required.
"""
from __future__ import annotations

from sqlalchemy import event, update
from sqlalchemy.orm import attributes

from app.models.entities import TrainingSession
from app.services.training_lifecycle_v2 import applies_to_created_at, training_kind

_installed = False


def clears_basic_renewal(training: TrainingSession) -> bool:
    if not applies_to_created_at(getattr(training, "created_at", None)):
        return False
    kind = training_kind(
        getattr(training, "training_type", ""),
        getattr(training, "title", ""),
    )
    return kind in {"work_start", "information_refresh"}


def install_training_lifecycle_v2_record_hooks() -> str:
    global _installed
    if _installed:
        return "already-active"

    @event.listens_for(TrainingSession, "after_insert")
    def _clear_non_basic_renewal(_mapper, connection, target: TrainingSession) -> None:
        if not clears_basic_renewal(target):
            return
        connection.execute(
            update(TrainingSession)
            .where(TrainingSession.id == target.id)
            .values(renewal_years=0, next_training_date=None)
        )
        attributes.set_committed_value(target, "renewal_years", 0)
        attributes.set_committed_value(target, "next_training_date", None)

    _installed = True
    return "active"
