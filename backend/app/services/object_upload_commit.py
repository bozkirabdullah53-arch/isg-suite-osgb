"""Keep object-store writes and database metadata consistent on upload failures."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _cleanup(store: Any, key: str | None, *, context: str) -> None:
    if not key:
        return
    try:
        store.delete(key)
    except Exception:
        logger.exception("Object cleanup failed after %s: key=%s", context, key)


def commit_object_upload(
    db: Session,
    store: Any,
    new_key: str,
    *,
    old_key: str | None = None,
) -> None:
    """Commit DB metadata; remove the new object on DB failure and old object after success."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        _cleanup(store, new_key, context="database rollback")
        raise
    if old_key and old_key != new_key:
        _cleanup(store, old_key, context="successful replacement")
