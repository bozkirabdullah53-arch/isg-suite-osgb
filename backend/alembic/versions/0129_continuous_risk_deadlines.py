"""Remove invented due dates from untouched continuous-monitoring imports.

The old importer substituted a score-based deadline when Excel said only
"Sürekli izleme/kontrol". Explicit, manually edited and completed actions are
preserved. The audit entry retains the old generated dates.
"""
from datetime import datetime, timedelta
import json
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None


def _continuous(value):
    text = unicodedata.normalize("NFKD", str(value or "").lower().replace("ı", "i"))
    text = "".join(char for char in text if not unicodedata.combining(char)).strip()
    return bool(re.fullmatch(r"surekli(?:\s+(?:izleme|kontrol)(?:\s*[/+ve ]+\s*(?:izleme|kontrol))?)?", text))


def _untouched(row):
    created, updated = row.get("created_at"), row.get("updated_at")
    # ORM defaults for these two fields can differ by a few microseconds.
    return bool(created and updated and abs((updated - created).total_seconds()) < 1)


def repair_continuous_deadlines(bind):
    meta = sa.MetaData()
    risks = sa.Table("risk_assessments", meta, autoload_with=bind)
    dofs = sa.Table("risk_dofs", meta, autoload_with=bind)
    audit = sa.Table("audit_logs", meta, autoload_with=bind)
    repaired = {"risks": 0, "dofs": 0}
    rows = bind.execute(sa.select(risks).where(
        risks.c.record_origin == "excel_import", risks.c.source_fingerprint.is_not(None),
        risks.c.term_date.is_not(None), risks.c.term_overridden.is_(False),
    )).mappings().all()
    for risk in rows:
        if not _continuous(risk["term_text"]) or not risk["observed_at"]:
            continue
        if risk["term_days"] is None or risk["term_days"] != risk["term_suggested"]:
            continue
        expected = risk["observed_at"].date() + timedelta(days=risk["term_days"])
        if risk["term_date"] != expected:
            continue
        records = bind.execute(sa.select(dofs).where(
            dofs.c.risk_id == risk["id"],
            dofs.c.client_reference == f"excel:{risk['source_fingerprint']}:dof",
            dofs.c.term_date == expected, dofs.c.is_completed.is_(False),
            dofs.c.status == "Açık", dofs.c.completion_date.is_(None),
        )).mappings().all()
        for dof in records:
            if not _untouched(dof):
                continue
            bind.execute(dofs.update().where(dofs.c.id == dof["id"]).values(term_date=None))
            repaired["dofs"] += 1
            bind.execute(audit.insert().values(
                company_id=risk["company_id"], action="UPDATE", entity_type="risk_dof",
                entity_id=str(dof["id"]), module="risk", created_at=datetime.utcnow(),
                description="Sürekli izleme Excel kaydına atanmış otomatik termin düzeltildi (0129).",
                old_value=json.dumps({"term_date": expected.isoformat()}), new_value='{"term_date": null}',
            ))
        if _untouched(risk) and risk["status"] == "Açık" and not risk["revision_no"]:
            bind.execute(risks.update().where(risks.c.id == risk["id"]).values(
                term_date=None, term_days=None, term_overridden=True,
            ))
            repaired["risks"] += 1
            bind.execute(audit.insert().values(
                company_id=risk["company_id"], action="UPDATE", entity_type="risk_assessment",
                entity_id=str(risk["id"]), module="risk", created_at=datetime.utcnow(),
                description="Sürekli izleme Excel kaydının otomatik termini düzeltildi (0129).",
                old_value=json.dumps({"term_date": expected.isoformat(), "term_days": risk["term_days"]}),
                new_value='{"term_date": null, "term_days": null}',
            ))
    return repaired


def upgrade():
    repair_continuous_deadlines(op.get_bind())


def downgrade():
    # A downgrade must not invent deadlines again or overwrite later edits.
    # Original values remain available in the append-only audit log.
    pass
