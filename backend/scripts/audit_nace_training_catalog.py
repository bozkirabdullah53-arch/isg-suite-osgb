"""Fail-closed audit for every active NACE training catalog row."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.training_nace_classification import resolve_exact_nace  # noqa: E402
from app.services.training_nace_risk_catalog import apply_reviewed_risk_profiles  # noqa: E402
from app.services.training_topics import _SECTOR_RAW  # noqa: E402

NACE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")
VALID_HAZARDS = {"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"}
WRAPPED_PREFIXES = (
    "dahil)",
    "faaliyetleri)",
    "hariç)",
    "imalatı ",
    "kimyasal ürünler)",
    "müstahzarların imalatı ",
    "olanlar hariç)",
    "ticareti ",
    "ürünlerin imalatı ",
    "vb.)",
    "yayımlananlar)",
)


def audit_catalog() -> dict:
    apply_reviewed_risk_profiles()
    issues: list[str] = []
    official = [row for row in _SECTOR_RAW if row[0].startswith("nace_")]
    codes = [row[0] for row in official]
    if len(official) != 2141:
        issues.append(f"active NACE count is {len(official)}, expected 2141")
    duplicates = [code for code, count in Counter(codes).items() if count != 1]
    if duplicates:
        issues.append(f"duplicate catalog keys: {duplicates[:10]}")

    profile_counts: Counter[str] = Counter()
    hazard_counts: Counter[str] = Counter()
    nace_seen: set[str] = set()
    for catalog_key, name, hazard, _raw_topics in official:
        nace = catalog_key.removeprefix("nace_").replace("_", ".")
        if not NACE_RE.fullmatch(nace):
            issues.append(f"{catalog_key}: invalid exact NACE format")
        if nace in nace_seen:
            issues.append(f"{catalog_key}: duplicate exact NACE {nace}")
        nace_seen.add(nace)
        if not name.strip():
            issues.append(f"{nace}: empty activity name")
        if name.count("(") != name.count(")"):
            issues.append(f"{nace}: unbalanced activity name parentheses")
        if name.strip().casefold().startswith(tuple(item.casefold() for item in WRAPPED_PREFIXES)):
            issues.append(f"{nace}: probable wrapped-row prefix in activity name")
        if hazard not in VALID_HAZARDS:
            issues.append(f"{nace}: invalid hazard class {hazard!r}")

        result = resolve_exact_nace(nace)
        profile_counts[result.content_profile_code] += 1
        hazard_counts[result.hazard_class] += 1
        if result.classification_status != "verified":
            issues.append(f"{nace}: classification is {result.classification_status}")
        if len(result.training_topics) != 5 or len(set(result.training_topics)) != 5:
            issues.append(f"{nace}: topics are not five unique reviewed items")
        if any(not topic.strip() or len(topic.strip()) < 20 for topic in result.training_topics):
            issues.append(f"{nace}: empty or underspecified training topic")
        if len(result.technical_risk_tags) < 5:
            issues.append(f"{nace}: fewer than five technical risk tags")

    backend_json = json.loads(
        (BACKEND_ROOT / "app/services/data/nace_sectors.json").read_text(encoding="utf-8")
    )
    frontend_json = json.loads(
        (REPO_ROOT / "frontend/public/training-sectors.json").read_text(encoding="utf-8")
    )
    if backend_json != frontend_json:
        issues.append("backend and frontend NACE catalogs differ")

    return {
        "ok": not issues,
        "official_nace_count": len(official),
        "unique_nace_count": len(nace_seen),
        "profile_count": len(profile_counts),
        "profile_distribution": dict(sorted(profile_counts.items())),
        "hazard_distribution": dict(sorted(hazard_counts.items())),
        "issues": issues,
    }


def main() -> int:
    result = audit_catalog()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
