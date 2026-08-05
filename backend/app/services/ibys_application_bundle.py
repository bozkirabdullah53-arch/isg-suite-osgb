"""İBYS başvuru dosyasını doğrulanmış şirket profiliyle deterministik ZIP'e dönüştürür."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BUNDLE_VERSION = "ibys-application-bundle-v1"
PLACEHOLDER_RE = re.compile(r"\[[^\[\]\n]{2,120}\]")

REQUIRED_PROFILE_FIELDS = (
    "legal_name",
    "tax_office",
    "tax_number",
    "mersis_number",
    "registered_address",
    "phone",
    "corporate_email",
    "representative_name",
    "representative_title",
)

TOKEN_MAP = {
    "[ŞİRKETİN TAM TİCARİ UNVANI]": "legal_name",
    "[TİCARİ UNVAN]": "legal_name",
    "[VERGİ DAİRESİ]": "tax_office",
    "[VERGİ NUMARASI]": "tax_number",
    "[MERSİS NUMARASI]": "mersis_number",
    "[TEBLİGAT ADRESİ]": "registered_address",
    "[TELEFON]": "phone",
    "[KURUMSAL E-POSTA]": "corporate_email",
    "[WEB ADRESİ]": "website",
    "[AD SOYAD]": "representative_name",
    "[UNVAN]": "representative_title",
    "[ISLAK İMZA / GÜVENLİ E-İMZA]": "signature_method",
}

REQUIRED_ATTACHMENT_GROUPS = {
    "trade_registry": ("ticaret", "sicil"),
    "activity_certificate": ("faaliyet",),
    "tax_certificate": ("vergi",),
    "signature_circular": ("imza", "sirk"),
}


@dataclass(frozen=True)
class BundleFile:
    path: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def _clean_profile_value(value: Any) -> str:
    return str(value or "").strip()


def validate_company_profile(profile: dict[str, Any]) -> dict[str, str]:
    cleaned = {str(key): _clean_profile_value(value) for key, value in profile.items()}
    missing = [field for field in REQUIRED_PROFILE_FIELDS if not cleaned.get(field)]
    suspicious = [
        field
        for field, value in cleaned.items()
        if value and (PLACEHOLDER_RE.search(value) or value in {"...", "-", "TBD", "TODO"})
    ]
    if missing or suspicious:
        parts: list[str] = []
        if missing:
            parts.append("missing=" + ",".join(sorted(missing)))
        if suspicious:
            parts.append("placeholder=" + ",".join(sorted(suspicious)))
        raise ValueError("company profile is incomplete: " + "; ".join(parts))
    cleaned.setdefault("website", "")
    cleaned.setdefault("signature_method", "Güvenli e-imza veya ıslak imza")
    return cleaned


def render_template(text: str, profile: dict[str, Any]) -> str:
    clean = validate_company_profile(profile)
    rendered = text
    for token, field in TOKEN_MAP.items():
        rendered = rendered.replace(token, clean.get(field, ""))
    unresolved = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if unresolved:
        raise ValueError("unresolved application placeholders: " + ", ".join(unresolved))
    return rendered


def _iter_attachment_files(attachments_dir: Path | None) -> list[Path]:
    if attachments_dir is None:
        return []
    if not attachments_dir.exists() or not attachments_dir.is_dir():
        raise ValueError("attachments directory does not exist")
    return sorted(path for path in attachments_dir.rglob("*") if path.is_file())


def validate_required_attachments(paths: Iterable[Path]) -> dict[str, str]:
    items = list(paths)
    lowered = {path: path.name.casefold() for path in items}
    matches: dict[str, str] = {}
    for group, tokens in REQUIRED_ATTACHMENT_GROUPS.items():
        found = next(
            (
                path
                for path, name in lowered.items()
                if all(token.casefold() in name for token in tokens)
            ),
            None,
        )
        if found is None:
            raise ValueError(f"required corporate attachment missing: {group}")
        matches[group] = found.name
    return matches


def _default_docs_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "ibys"


def build_application_bundle(
    profile: dict[str, Any],
    *,
    docs_dir: Path | None = None,
    attachments_dir: Path | None = None,
    require_attachments: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    clean_profile = validate_company_profile(profile)
    source_dir = (docs_dir or _default_docs_dir()).resolve()
    if not source_dir.exists():
        raise ValueError("İBYS application docs directory not found")

    files: list[BundleFile] = []
    template_overrides = {
        "BASVURU_DILEKCESI_TASLAGI.md": "01-BASVURU_DILEKCESI.md",
        "RANDEVU_TALEP_METNI.md": "02-RANDEVU_TALEP_METNI.md",
    }
    excluded = {"company-profile.template.json", "application-manifest.json"}

    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.name in excluded:
            continue
        raw = path.read_text(encoding="utf-8")
        if path.name in template_overrides:
            raw = render_template(raw, clean_profile)
            target = template_overrides[path.name]
        else:
            target = f"teknik-ekler/{path.name}"
        files.append(BundleFile(target, raw.encode("utf-8")))

    attachment_paths = _iter_attachment_files(attachments_dir)
    attachment_matches: dict[str, str] = {}
    if require_attachments:
        attachment_matches = validate_required_attachments(attachment_paths)
    for path in attachment_paths:
        relative = path.relative_to(attachments_dir).as_posix() if attachments_dir else path.name
        files.append(BundleFile(f"kurumsal-ekler/{relative}", path.read_bytes()))

    created_at = datetime.now(timezone.utc).isoformat()
    evidence = {
        "bundle_version": BUNDLE_VERSION,
        "created_at": created_at,
        "official_registration_claim": False,
        "company": {
            "legal_name": clean_profile["legal_name"],
            "tax_number_masked": "*" * max(0, len(clean_profile["tax_number"]) - 4) + clean_profile["tax_number"][-4:],
            "mersis_number_masked": "*" * max(0, len(clean_profile["mersis_number"]) - 4) + clean_profile["mersis_number"][-4:],
        },
        "required_attachment_matches": attachment_matches,
        "files": [
            {"path": item.path, "size": len(item.content), "sha256": item.sha256}
            for item in files
        ],
    }
    manifest_bytes = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    files.append(BundleFile("00-BUNDLE-MANIFEST.json", manifest_bytes))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(files, key=lambda value: value.path):
            info = zipfile.ZipInfo(item.path)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, item.content)
    return buf.getvalue(), evidence
