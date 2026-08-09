"""Canonical, auditable envelope for future authority submissions.

No Ministry wire format is assumed here.  The envelope gives the eventual
İBYS/İSBS adapter stable integrity/idempotency primitives while the actual
payload schema remains authority-owned.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

AuthorityKind = Literal["ibys", "isbs_erecete"]


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class SubmissionEnvelope:
    envelope_version: str
    authority: AuthorityKind
    schema_profile: str
    request_id: str
    idempotency_key: str
    payload_sha256: str
    created_at: str
    actor_user_id: int
    osgb_id: int | None
    company_id: int | None
    payload: dict[str, Any]

    def public_audit(self) -> dict[str, object]:
        """Audit metadata only; never includes health/personal payload contents."""
        return {
            "envelope_version": self.envelope_version,
            "authority": self.authority,
            "schema_profile": self.schema_profile,
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "payload_sha256": self.payload_sha256,
            "created_at": self.created_at,
            "actor_user_id": self.actor_user_id,
            "osgb_id": self.osgb_id,
            "company_id": self.company_id,
        }


def build_submission_envelope(
    *,
    authority: AuthorityKind,
    schema_profile: str,
    payload: dict[str, Any],
    actor_user_id: int,
    osgb_id: int | None = None,
    company_id: int | None = None,
    request_id: str | None = None,
) -> SubmissionEnvelope:
    if not schema_profile.strip():
        raise ValueError("Authority schema profile is required.")
    if actor_user_id <= 0:
        raise ValueError("A real authenticated actor_user_id is required.")
    digest = sha256_hex(payload)
    rid = request_id or str(uuid4())
    idem_source = {
        "authority": authority,
        "schema_profile": schema_profile,
        "payload_sha256": digest,
        "actor_user_id": actor_user_id,
        "osgb_id": osgb_id,
        "company_id": company_id,
    }
    return SubmissionEnvelope(
        envelope_version="authority-envelope-v1",
        authority=authority,
        schema_profile=schema_profile.strip(),
        request_id=rid,
        idempotency_key=sha256_hex(idem_source),
        payload_sha256=digest,
        created_at=datetime.now(timezone.utc).isoformat(),
        actor_user_id=actor_user_id,
        osgb_id=osgb_id,
        company_id=company_id,
        payload=dict(payload),
    )
