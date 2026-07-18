"""Tehlike kütüphanesi seed — İSG PRO hazard_data (43 kategori / 552 tehlike)."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Hazard, HazardCategory
from app.services.hazard_library_data import CATEGORIES, HAZARDS
from app.services.risk_regulations import REGULATIONS, GENERAL_REGULATIONS


def seed_hazard_library(db: Session) -> dict:
    """Idempotent: kategori adı ve tehlike koduna göre upsert."""
    cat_ids: dict[str, int] = {}
    for item in CATEGORIES:
        name = item["name"]
        row = db.scalar(select(HazardCategory).where(HazardCategory.name == name))
        if not row:
            row = HazardCategory(
                name=name,
                icon=item.get("icon") or "bi-exclamation-triangle",
                sort_order=int(item.get("sort_order") or 0),
            )
            db.add(row)
            db.flush()
        else:
            row.icon = item.get("icon") or row.icon
            row.sort_order = int(item.get("sort_order") or row.sort_order)
        cat_ids[name] = row.id

    created = 0
    updated = 0
    for haz in HAZARDS:
        code = haz["code"]
        cat_name = haz["category"]
        cat_id = cat_ids.get(cat_name)
        if not cat_id:
            continue
        regs = REGULATIONS.get(cat_name) or GENERAL_REGULATIONS
        regs_json = json.dumps(regs, ensure_ascii=False)
        row = db.scalar(select(Hazard).where(Hazard.code == code))
        if not row:
            db.add(
                Hazard(
                    category_id=cat_id,
                    code=code,
                    name=haz["name"],
                    description=haz.get("description"),
                    risk_source=haz.get("risk_source"),
                    default_probability=haz.get("default_p"),
                    default_severity=haz.get("default_s"),
                    regulations=regs_json,
                    is_active=True,
                )
            )
            created += 1
        else:
            row.category_id = cat_id
            row.name = haz["name"]
            row.description = haz.get("description")
            row.risk_source = haz.get("risk_source")
            row.default_probability = haz.get("default_p")
            row.default_severity = haz.get("default_s")
            row.regulations = regs_json
            row.is_active = True
            updated += 1

    db.commit()
    return {
        "categories": len(cat_ids),
        "hazards_created": created,
        "hazards_updated": updated,
        "hazards_total": len(HAZARDS),
    }
