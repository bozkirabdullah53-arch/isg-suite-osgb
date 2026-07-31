from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import PRODUCT, VERSION, load_config
from .signing import cert_info, load_pfx, sign_pdf_pades, sign_pdf_pkcs11

log = logging.getLogger("osgb-signer")


class SignRequest(BaseModel):
    pdf_base64: str = Field(min_length=8)
    cert_id: str = Field(default="demo")
    reason: str = Field(default="OSGB belge imzası", max_length=200)
    location: str = Field(default="Türkiye", max_length=120)
    document_title: str | None = Field(default=None, max_length=220)
    # Sunucudan gelen tek kullanımlık talep — agent doğrular / echo eder
    request_token: str | None = Field(default=None, max_length=80)
    expected_sha256: str | None = Field(default=None, max_length=64)
    # PKCS#11 PIN — asla loglanmaz, sunucuya gönderilmez
    pin: str | None = Field(default=None, max_length=64)


def create_app() -> FastAPI:
    cfg = load_config()
    origins = cfg.get("AllowedOrigins") or []
    size_limit = int(cfg.get("RequestSizeLimitBytes") or 40 * 1024 * 1024)

    app = FastAPI(title=PRODUCT, version=VERSION, docs_url="/docs", redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def limit_body(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > size_limit:
            return JSONResponse({"detail": "İstek çok büyük."}, status_code=413)
        return await call_next(request)

    def _resolve_soft_certs() -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        signing = cfg.get("Signing") or {}
        demo_path = Path(signing.get("DemoCertPath") or "")
        demo_pw = signing.get("DemoCertPassword") or ""
        if demo_path.exists() and demo_pw:
            try:
                key, cert, extras = load_pfx(demo_path, demo_pw)
                info = cert_info(cert, "demo", "demo-pfx")
                out["demo"] = {"info": info, "key": key, "cert": cert, "extras": extras}
            except Exception as exc:  # noqa: BLE001
                log.warning("Demo cert load failed: %s", exc)

        user_pfx = Path(signing.get("UserCertPath") or "")
        user_pw = signing.get("UserCertPassword") or ""
        if user_pfx.exists() and user_pw:
            try:
                key, cert, extras = load_pfx(user_pfx, user_pw)
                info = cert_info(cert, "user-pfx", "user-pfx")
                out["user-pfx"] = {"info": info, "key": key, "cert": cert, "extras": extras}
            except Exception as exc:  # noqa: BLE001
                log.warning("User PFX load failed: %s", exc)
        return out

    @app.get("/health")
    def health():
        certs = _resolve_soft_certs()
        signing = cfg.get("Signing") or {}
        pkcs11 = bool((signing.get("Pkcs11Module") or "").strip())
        return {
            "status": "healthy",
            "product": PRODUCT,
            "version": VERSION,
            "port": cfg.get("ListenPort"),
            "origins": origins,
            "certs_available": len(certs) + (1 if pkcs11 else 0),
            "demo_mode": "demo" in certs,
            "pkcs11_configured": pkcs11,
            "pkcs11_module": Path(signing.get("Pkcs11Module") or "").name or None,
            "note": "PIN yalnızca /v1/sign isteğinde lokal işlenir; OSGB sunucusuna gitmez.",
        }

    @app.get("/v1/certs")
    def list_certs():
        certs = _resolve_soft_certs()
        items = [v["info"] for v in certs.values()]
        signing = cfg.get("Signing") or {}
        if (signing.get("Pkcs11Module") or "").strip():
            items.append(
                {
                    "id": "pkcs11",
                    "common_name": "USB E-İmza Kartı (PKCS#11)",
                    "subject": "pkcs11",
                    "issuer": "",
                    "serial": "",
                    "not_after": "",
                    "source": "pkcs11",
                    "sha256": "",
                }
            )
        return {"certs": items}

    @app.post("/v1/sign")
    def sign(payload: SignRequest):
        try:
            raw = base64.b64decode(payload.pdf_base64, validate=False)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"pdf_base64 geçersiz: {exc}") from exc
        if not raw.startswith(b"%PDF"):
            raise HTTPException(400, "Girdi PDF değil.")
        if len(raw) > size_limit:
            raise HTTPException(413, "PDF çok büyük.")

        if payload.expected_sha256:
            got = hashlib.sha256(raw).hexdigest()
            if got.lower() != payload.expected_sha256.lower():
                raise HTTPException(400, "PDF hash, sunucu talebiyle uyuşmuyor (bütünlük).")

        signing = cfg.get("Signing") or {}
        mode = "demo-pfx"
        signer_info: dict

        if payload.cert_id == "pkcs11" or (
            payload.cert_id == "auto" and (signing.get("Pkcs11Module") or "").strip()
        ):
            module = (signing.get("Pkcs11Module") or "").strip()
            if not module:
                raise HTTPException(400, "Pkcs11Module appsettings.json içinde tanımlı değil.")
            if not payload.pin:
                raise HTTPException(400, "PKCS#11 için PIN gerekli (yalnızca bu cihazda).")
            try:
                signed, signer_info = sign_pdf_pkcs11(
                    raw, module, payload.pin, reason=payload.reason, location=payload.location
                )
                mode = "pkcs11"
            except Exception as exc:  # noqa: BLE001
                log.exception("pkcs11 sign failed")
                raise HTTPException(500, f"Kart imzası başarısız: {exc}") from exc
            finally:
                # PIN'i bellekten silmeye çalış
                payload.pin = None
        else:
            certs = _resolve_soft_certs()
            cid = payload.cert_id if payload.cert_id in certs else ("demo" if "demo" in certs else None)
            if not cid:
                raise HTTPException(404, "Sertifika bulunamadı. Demo kurun veya PKCS#11 seçin.")
            entry = certs[cid]
            try:
                signed = sign_pdf_pades(
                    raw, entry["key"], entry["cert"], entry["extras"], reason=payload.reason, location=payload.location
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("sign failed")
                raise HTTPException(500, f"İmzalama başarısız: {exc}") from exc
            signer_info = entry["info"]
            mode = signer_info.get("source") or cid

        digest = hashlib.sha256(signed).hexdigest()
        return {
            "ok": True,
            "signed_pdf_base64": base64.b64encode(signed).decode("ascii"),
            "sha256": digest,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(signed),
            "signer": signer_info,
            "document_title": payload.document_title,
            "request_token": payload.request_token,
            "signature_id": secrets.token_hex(8),
            "qualified": mode == "pkcs11",
            "mode": mode,
            "legal_note": (
                "PKCS#11 kart imzası nitelikli e-imza adayıdır; nihai 5070 geçerliliği "
                "sertifika politikası + sunucu OCSP/CRL/TSA hattına bağlıdır. "
                "Demo PFX yalnızca akış testidir."
            ),
        }

    return app


app = create_app()
