"""Read-only NACE training profile/risk inventory.

This script intentionally has no database session, no API/router registration and no
file writes. It reads the source-controlled training catalog in memory and prints a
deterministic JSON inventory that can be used to plan Education V3 work without
changing the running application.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any

from app.services import training_topics
from app.services.training_runtime_patches import _apply_exact_nace_topic_corrections

_EXACT_NACE_RE = re.compile(r"^\d{2}(?:\.\d{2}){1,2}$")
INVENTORY_SCHEMA_VERSION = "training-nace-inventory-v3"


def _is_official_nace_row(row: dict[str, Any]) -> bool:
    key = str(row.get("code") or "").strip()
    nace = str(row.get("nace") or "").strip()
    return key.startswith("nace_") and bool(_EXACT_NACE_RE.fullmatch(nace))


def _topic_signature(topics: tuple[str, ...]) -> str:
    payload = json.dumps(list(topics), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_inventory() -> dict[str, Any]:
    """Build a deterministic in-memory inventory without persisting anything."""
    _apply_exact_nace_topic_corrections(training_topics)

    # Import after approved in-memory corrections so the inventory sees the same
    # reviewed profile/risk mappings as the existing classification audit.
    from app.services.training_nace_classification import resolve_exact_nace
    from app.services.training_topics import sectors_list_for_api

    all_rows = list(sectors_list_for_api())
    official_rows = [row for row in all_rows if _is_official_nace_row(row)]
    non_nace_rows = [row for row in all_rows if not _is_official_nace_row(row)]

    statuses: Counter[str] = Counter()
    invalid_official: list[dict[str, str]] = []

    profiles: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "content_profile_name": "",
            "nace_count": 0,
            "hazard_class_counts": Counter(),
            "section_counts": Counter(),
            "topic_signatures": {},
            "technical_risk_tags": set(),
            "special_risks": set(),
            "sample_nace": [],
        }
    )
    risk_packs: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"nace_count": 0, "profiles": set()}
    )
    special_risks: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"nace_count": 0, "profiles": set()}
    )
    topic_signatures: dict[str, dict[str, Any]] = {}

    for row in official_rows:
        key = str(row.get("code") or "").strip()
        try:
            result = resolve_exact_nace(key)
        except ValueError as exc:
            invalid_official.append(
                {
                    "catalog_key": key,
                    "nace_code": str(row.get("nace") or ""),
                    "description": str(row.get("name") or ""),
                    "error": str(exc),
                }
            )
            continue

        statuses[result.classification_status] += 1
        profile_code = str(result.content_profile_code or "missing")
        profile = profiles[profile_code]
        profile["content_profile_name"] = str(result.content_profile_name or "")
        profile["nace_count"] += 1
        profile["hazard_class_counts"][str(result.hazard_class or "missing")] += 1
        section_key = str(result.nace_section_code or "missing")
        profile["section_counts"][section_key] += 1
        profile["technical_risk_tags"].update(result.technical_risk_tags)
        profile["special_risks"].update(result.special_risks)

        topics = tuple(result.training_topics)
        signature = _topic_signature(topics)
        profile["topic_signatures"][signature] = topics

        global_topic = topic_signatures.setdefault(
            signature,
            {
                "topics": topics,
                "nace_count": 0,
                "profiles": set(),
            },
        )
        global_topic["nace_count"] += 1
        global_topic["profiles"].add(profile_code)

        for risk_tag in result.technical_risk_tags:
            risk_pack = risk_packs[str(risk_tag)]
            risk_pack["nace_count"] += 1
            risk_pack["profiles"].add(profile_code)

        for special_risk in result.special_risks:
            special = special_risks[str(special_risk)]
            special["nace_count"] += 1
            special["profiles"].add(profile_code)

        if len(profile["sample_nace"]) < 5:
            profile["sample_nace"].append(
                {
                    "catalog_key": str(result.catalog_key or ""),
                    "nace_code": str(result.nace_code or ""),
                    "description": str(result.nace_description or ""),
                    "hazard_class": str(result.hazard_class or ""),
                }
            )

    profile_distribution: list[dict[str, Any]] = []
    for profile_code, raw in profiles.items():
        variants = raw["topic_signatures"]
        variant_rows = [
            {"signature": signature, "topics": list(topics)}
            for signature, topics in sorted(variants.items())
        ]
        profile_distribution.append(
            {
                "content_profile": profile_code,
                "content_profile_name": raw["content_profile_name"],
                "nace_count": int(raw["nace_count"]),
                "topic_slot_count": int(raw["nace_count"]) * 5,
                "hazard_class_counts": dict(sorted(raw["hazard_class_counts"].items())),
                "section_counts": dict(sorted(raw["section_counts"].items())),
                "training_topic_variant_count": len(variant_rows),
                "training_topic_variants": variant_rows,
                "technical_risk_tags": sorted(raw["technical_risk_tags"]),
                "special_risks": sorted(raw["special_risks"]),
                "sample_nace": raw["sample_nace"],
            }
        )
    profile_distribution.sort(
        key=lambda item: (-int(item["nace_count"]), str(item["content_profile"]))
    )

    risk_pack_distribution = [
        {
            "risk_tag": risk_tag,
            "nace_count": int(details["nace_count"]),
            "profile_count": len(details["profiles"]),
            "profiles": sorted(details["profiles"]),
        }
        for risk_tag, details in risk_packs.items()
    ]
    risk_pack_distribution.sort(
        key=lambda item: (-int(item["nace_count"]), str(item["risk_tag"]))
    )

    special_risk_distribution = [
        {
            "special_risk": risk,
            "nace_count": int(details["nace_count"]),
            "profile_count": len(details["profiles"]),
            "profiles": sorted(details["profiles"]),
        }
        for risk, details in special_risks.items()
    ]
    special_risk_distribution.sort(
        key=lambda item: (-int(item["nace_count"]), str(item["special_risk"]))
    )

    topic_signature_distribution = [
        {
            "signature": signature,
            "nace_count": int(details["nace_count"]),
            "profile_count": len(details["profiles"]),
            "profiles": sorted(details["profiles"]),
            "topics": list(details["topics"]),
        }
        for signature, details in topic_signatures.items()
    ]
    topic_signature_distribution.sort(
        key=lambda item: (-int(item["nace_count"]), str(item["signature"]))
    )

    resolved_official_count = len(official_rows) - len(invalid_official)
    verified_official_count = int(statuses.get("verified", 0))
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "safety": {
            "read_only": True,
            "database_writes": False,
            "api_routes_changed": False,
            "runtime_registration": False,
            "generated_files": False,
        },
        "catalog_option_count": len(all_rows),
        "official_nace_count": len(official_rows),
        "non_nace_option_count": len(non_nace_rows),
        "resolved_official_count": resolved_official_count,
        "verified_official_count": verified_official_count,
        "invalid_official_count": len(invalid_official),
        "status_counts": dict(sorted(statuses.items())),
        "structural_coverage_complete": resolved_official_count == len(official_rows),
        "verified_coverage_complete": verified_official_count == len(official_rows),
        "profile_count": len(profile_distribution),
        "technical_risk_pack_count": len(risk_pack_distribution),
        "special_risk_count": len(special_risk_distribution),
        "training_topic_signature_count": len(topic_signature_distribution),
        "topic_slot_count": resolved_official_count * 5,
        "profile_distribution": profile_distribution,
        "technical_risk_pack_distribution": risk_pack_distribution,
        "special_risk_distribution": special_risk_distribution,
        "training_topic_signature_distribution": topic_signature_distribution,
        "invalid_official": invalid_official,
    }


def main() -> int:
    payload = build_inventory()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["verified_coverage_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
