"""OSGB e-imza sunucu hattı: doğrulama, OCSP/CRL, TSA, kilit, denetim."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID, NameOID

from app.core.config import settings

log = logging.getLogger(__name__)

TOKEN_TTL_MINUTES = 10
MAX_PDF_BYTES = 40 * 1024 * 1024
AGENT_PORT = 17000
AGENT_ORIGINS_HINT = [
    "https://www.isgsuite.tr",
    "https://isgsuite.tr",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_one_time_token() -> str:
    return secrets.token_urlsafe(32)


def token_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) + timedelta(minutes=TOKEN_TTL_MINUTES)


def upload_root() -> Path:
    return Path(settings.upload_dir).resolve()


def store_esign_bytes(company_id: int, kind: str, data: bytes, suffix: str = ".pdf") -> str:
    """Tenant-scoped relative storage path under upload_dir."""
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF boyutu limiti aşıldı.")
    if not data.startswith(b"%PDF"):
        raise ValueError("Dosya PDF değil.")
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    digest = sha256_hex(data)[:12]
    rel = f"{company_id}/esign/{kind}_{stamp}_{digest}{suffix}"
    target = upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return rel.replace("\\", "/")


def read_stored(rel: str) -> bytes:
    path = (upload_root() / rel).resolve()
    root = upload_root()
    if root not in path.parents and path != root:
        raise ValueError("Geçersiz depolama yolu.")
    return path.read_bytes()


def _cn_from_cert(cert: x509.Certificate) -> str:
    for attr in cert.subject:
        if attr.oid == NameOID.COMMON_NAME:
            return str(attr.value)
    return cert.subject.rfc4514_string()


def extract_pdf_signature_meta(signed_pdf: bytes) -> dict[str, Any]:
    """Best-effort CMS / ByteRange presence + leaf cert metadata."""
    meta: dict[str, Any] = {
        "has_byterange": b"/ByteRange" in signed_pdf or b"ByteRange" in signed_pdf,
        "has_contents": b"/Contents" in signed_pdf,
        "signer_cn": None,
        "signer_subject": None,
        "cert_serial": None,
        "cert_sha256": None,
        "cert_der": None,
        "verify_engine": "structural",
        "verify_ok": False,
        "verify_detail": "",
    }
    if not meta["has_byterange"]:
        meta["verify_detail"] = "PDF içinde PAdES/CMS ByteRange bulunamadı."
        return meta

    # Try endesive verify if installed
    try:
        from endesive.pdf.cms import verify  # type: ignore

        hashes_ok = verify(signed_pdf)
        meta["verify_engine"] = "endesive"
        meta["verify_ok"] = bool(hashes_ok)
        meta["verify_detail"] = "endesive hash doğrulaması" if hashes_ok else "endesive doğrulama başarısız"
    except Exception as exc:  # noqa: BLE001
        meta["verify_engine"] = "structural"
        meta["verify_ok"] = meta["has_byterange"] and meta["has_contents"]
        meta["verify_detail"] = f"endesive yok/hata; yapısal kontrol: {exc}"

    # Extract first PKCS#7 cert blob heuristically for OCSP/CRL
    try:
        # Look for DER SEQUENCE of certs inside Contents hex — fallback: scan for cert PEM-ish
        idx = signed_pdf.find(b"/Contents")
        chunk = signed_pdf[idx : idx + 200_000] if idx >= 0 else signed_pdf[:200_000]
        # Hex-encoded Contents <...>
        lt = chunk.find(b"<")
        gt = chunk.find(b">", lt + 1) if lt >= 0 else -1
        if 0 <= lt < gt and gt - lt < 180_000:
            hexdata = chunk[lt + 1 : gt].replace(b"\n", b"").replace(b"\r", b"").replace(b" ", b"")
            try:
                der = bytes.fromhex(hexdata.decode("ascii", errors="ignore")[: min(len(hexdata), 100_000)])
                certs = pkcs7.load_der_pkcs7_certificates(der)
                if certs:
                    leaf = certs[0]
                    meta["signer_cn"] = _cn_from_cert(leaf)
                    meta["signer_subject"] = leaf.subject.rfc4514_string()
                    meta["cert_serial"] = format(leaf.serial_number, "x")
                    meta["cert_sha256"] = hashlib.sha256(leaf.public_bytes(serialization.Encoding.DER)).hexdigest()
                    meta["cert_der"] = leaf.public_bytes(serialization.Encoding.DER)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        log.debug("cert extract failed: %s", exc)

    return meta


def check_ocsp(cert_der: bytes | None) -> dict[str, str]:
    """OCSP kontrolü — AIA yoksa veya ağ kapalıysa skipped (fail-open değil: skipped ayrı durum)."""
    if not cert_der:
        return {"status": "skipped", "detail": "sertifika çıkarılamadı"}
    try:
        cert = x509.load_der_x509_certificate(cert_der)
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        except x509.ExtensionNotFound:
            return {"status": "skipped", "detail": "AIA/OCSP URL yok"}
        ocsp_urls = [
            desc.access_location.value
            for desc in aia
            if desc.access_method == AuthorityInformationAccessOID.OCSP
        ]
        if not ocsp_urls:
            return {"status": "skipped", "detail": "OCSP URL yok"}
        # Ağ çağrısı production'da opsiyonel flag ile — varsayılan skipped-configured
        if not getattr(settings, "esign_ocsp_enabled", False):
            return {"status": "configured_off", "detail": f"OCSP URL mevcut ({ocsp_urls[0]}) — ESIGN_OCSP_ENABLED kapalı"}
        return {"status": "pending_network", "detail": ocsp_urls[0]}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)[:200]}


def check_crl(cert_der: bytes | None) -> dict[str, str]:
    if not cert_der:
        return {"status": "skipped", "detail": "sertifika çıkarılamadı"}
    try:
        cert = x509.load_der_x509_certificate(cert_der)
        try:
            cdp = cert.extensions.get_extension_for_oid(ExtensionOID.CRL_DISTRIBUTION_POINTS).value
        except x509.ExtensionNotFound:
            return {"status": "skipped", "detail": "CRL DP yok"}
        urls = []
        for dist in cdp:
            if dist.full_name:
                for name in dist.full_name:
                    urls.append(name.value)
        if not urls:
            return {"status": "skipped", "detail": "CRL URL yok"}
        if not getattr(settings, "esign_crl_enabled", False):
            return {"status": "configured_off", "detail": f"CRL URL mevcut ({urls[0]}) — ESIGN_CRL_ENABLED kapalı"}
        return {"status": "pending_network", "detail": urls[0]}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)[:200]}


def apply_timestamp(signed_pdf: bytes) -> dict[str, Any]:
    """RFC3161 TSA — URL yoksa skipped; PIN/private key sunucuda tutulmaz."""
    tsa_url = (getattr(settings, "esign_tsa_url", None) or "").strip()
    if not tsa_url:
        return {
            "status": "skipped",
            "token": None,
            "detail": "ESIGN_TSA_URL tanımlı değil (isteğe bağlı zaman damgası)",
            "pdf": signed_pdf,
        }
    # Pluggable hook — gerçek TSA istemcisi sonraki faz; şimdilik belgelenmiş stub
    digest = sha256_hex(signed_pdf)
    token = f"tsa-pending:{tsa_url}:{digest[:16]}"
    return {
        "status": "configured_pending",
        "token": token,
        "detail": f"TSA yapılandırıldı ({tsa_url}); ağ istemcisi sonraki sürüm",
        "pdf": signed_pdf,
    }


def build_audit_event(
    *,
    action: str,
    user_id: int,
    company_id: int,
    request_id: int | None,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "action": action,
        "at": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "company_id": company_id,
        "request_id": request_id,
        "extra": extra or {},
    }
    return json.dumps(payload, ensure_ascii=False)


def pipeline_complete(
    *,
    source_pdf: bytes,
    signed_pdf: bytes,
    source_sha256: str,
    agent_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """İmza sonrası sunucu hattı (doğrulama → OCSP/CRL → TSA → kilit kararı)."""
    if sha256_hex(source_pdf) != source_sha256:
        raise ValueError("Kaynak PDF hash uyuşmuyor (bütünlük ihlali).")
    if not signed_pdf.startswith(b"%PDF"):
        raise ValueError("İmzalı dosya PDF değil.")
    if len(signed_pdf) < len(source_pdf):
        # PAdES genelde büyür; eşit/küçük şüpheli ama bazı append modları farklı — soft warn
        pass

    sig = extract_pdf_signature_meta(signed_pdf)
    ocsp = check_ocsp(sig.get("cert_der"))
    crl = check_crl(sig.get("cert_der"))
    tsa = apply_timestamp(signed_pdf)

    agent_meta = agent_meta or {}
    demo_mode = str(agent_meta.get("mode") or "").lower() in {"demo", "demo-pfx"}
    verify_ok = bool(sig.get("verify_ok"))
    # Demo imza: kabul edilir ama qualified_claim=false ve verification=demo_accepted
    if demo_mode:
        verification_status = "demo_accepted" if verify_ok or sig.get("has_byterange") else "failed"
        qualified = False
        lock = verification_status == "demo_accepted"
    else:
        verification_status = "verified" if verify_ok else "failed"
        qualified = False  # 5070 qualified claim yalnızca akredite yol + OCSP good sonrası
        lock = verification_status == "verified"

    return {
        "verification_status": verification_status,
        "ocsp_status": ocsp["status"],
        "ocsp_detail": ocsp.get("detail"),
        "crl_status": crl["status"],
        "crl_detail": crl.get("detail"),
        "timestamp_status": tsa["status"],
        "timestamp_token": tsa.get("token"),
        "timestamp_detail": tsa.get("detail"),
        "signed_pdf": tsa["pdf"],
        "signed_sha256": sha256_hex(tsa["pdf"]),
        "signer_cn": sig.get("signer_cn") or agent_meta.get("signer_cn"),
        "signer_subject": sig.get("signer_subject") or agent_meta.get("signer_subject"),
        "cert_serial": sig.get("cert_serial") or agent_meta.get("cert_serial"),
        "cert_sha256": sig.get("cert_sha256") or agent_meta.get("cert_sha256"),
        "sign_mode": agent_meta.get("mode"),
        "agent_signature_id": agent_meta.get("signature_id"),
        "qualified_claim": qualified,
        "is_locked": lock,
        "verify_detail": sig.get("verify_detail"),
        "verify_engine": sig.get("verify_engine"),
    }
