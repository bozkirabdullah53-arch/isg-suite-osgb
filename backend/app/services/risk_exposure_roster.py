"""Named, company-scoped view of explainable exposure suggestions (read only)."""
from collections import Counter
from typing import Any

from app.services.risk_analytics import RISK_TYPE_META, classify_hazard_details, _is_cancelled, _safe_count
from app.services.risk_personnel import employee_scope, match_reasons, risk_scope, fold


def build_exposure_roster(company: Any, *, risks, employees, hazard_map, category_map,
                          hazard_type: str | None = None, risk_id: int | None = None) -> dict:
    people = {
        e.id: e for e in employees
        if e.is_active and getattr(e, "company_id", company.id) == company.id
    }
    prepared_people = {eid: employee_scope(e) for eid, e in people.items()}
    matches: dict[int, list] = {eid: [] for eid in people}
    risk_items = []
    reported_count = 0
    sources = Counter()
    for row in risks:
        if _is_cancelled(row) or getattr(row, "company_id", company.id) != company.id:
            continue
        hazard = hazard_map.get(row.hazard_id)
        category = category_map.get(getattr(hazard, "category_id", None))
        classification = classify_hazard_details(getattr(category, "name", None), getattr(hazard, "name", None), row.activity, row.risk_definition)
        kind = classification["hazard_type"]
        if (hazard_type and kind != hazard_type) or (risk_id is not None and row.id != risk_id):
            continue
        item = {
            "id": row.id, "risk_code": row.risk_code,
            "hazard": getattr(hazard, "name", None) or "Tehlike kaynağı",
            "hazard_type": kind, "hazard_type_label": RISK_TYPE_META[kind]["label"],
            **classification,
            "category": getattr(category, "name", None),
            "department": getattr(row, "department_name", None), "activity": row.activity,
            "risk_definition": row.risk_definition,
            "matched_worker_count": 0,
            "reported_worker_count": getattr(row, "exposed_worker_count", None),
        }
        # A reported number has no employee identities. Never invent a list
        # or silently associate an unrelated personnel suggestion with it.
        if item["reported_worker_count"] is not None:
            reported_count += _safe_count(item["reported_worker_count"])
            item["source"] = "reported"
        else:
            scope = risk_scope(row)
            for eid, person in prepared_people.items():
                reasons = match_reasons(scope, person)
                if reasons:
                    item["matched_worker_count"] += 1
                    matches[eid].append({"risk_id": row.id, "reasons": reasons})
            item["source"] = "personnel_match" if item["matched_worker_count"] else "unmatched"
        sources[item["source"]] += 1
        risk_items.append(item)
    rows = [{
        "id": eid, "full_name": e.full_name, "department": e.department,
        "job_title": e.job_title, "branch_id": e.branch_id, "matches": matches[eid],
    } for eid, e in people.items()]
    rows.sort(key=lambda e: (fold(e["full_name"]), e["id"]))
    label = RISK_TYPE_META[hazard_type]["label"] if hazard_type else "Tüm riskler"
    if risk_id is not None and risk_items:
        label = risk_items[0]["hazard"]
    return {
        "company": {"id": company.id, "name": company.name},
        "scope": {"hazard_type": hazard_type, "risk_id": risk_id, "label": label},
        "summary": {
            "matched_worker_count": sum(bool(row["matches"]) for row in rows),
            "risk_count": len(risk_items), "reported_worker_count": reported_count,
            "classification_review_count": sum(item["hazard_type"] == "other" for item in risk_items),
            "reported_risk_count": sources["reported"], "unmatched_risk_count": sources["unmatched"],
        },
        "employees": rows,
        # Complete scope, independent of the overview's 10/50 row display cap.
        "risks": risk_items,
    }
