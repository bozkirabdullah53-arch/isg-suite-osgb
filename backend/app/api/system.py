from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter(prefix="/system", tags=["Sistem"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.utcnow(),
        "version": "0.9.123",
        "ai_hazard_hint": "keyword-v2",
        "mevzuat_panel": "highlights-v1",
        "sds_register": "chemical-register-v1",
        "ghs_label_checklist": "ghs-label-checklist-v1",
        "risk_photo_tags": "checklist-v1",
        "sds_review_reminders": "duty-notify-v1",
        "osgb_mevzuat_link": "dashboard-v1",
        "osgb_sds_due": "dashboard-v1",
        "integration_readiness": "checklist-v1",
        "osgb_home_kpis": "finance-contracts-sds-v3",
    }
