from __future__ import annotations

import logging
import ssl
import sys
from pathlib import Path

from .config import load_config
from .server import create_app


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()
    port = int(cfg.get("ListenPort") or 17000)
    tls = cfg.get("Tls") or {}
    cert_path = Path(tls.get("CertificatePath") or "")
    password = tls.get("CertificatePassword") or ""

    app = create_app()

    # Export temp PEM pair for uvicorn (from PFX)
    import tempfile

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    if not cert_path.exists():
        logging.error("TLS PFX yok: %s — önce KUR.ps1 çalıştırın.", cert_path)
        return 2

    key, cert, _ = pkcs12.load_key_and_certificates(cert_path.read_bytes(), password.encode("utf-8"))
    tmp = Path(tempfile.gettempdir()) / "isg-suite-signer-tls"
    tmp.mkdir(parents=True, exist_ok=True)
    key_pem = tmp / "key.pem"
    cert_pem = tmp / "cert.pem"
    key_pem.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        ssl_keyfile=str(key_pem),
        ssl_certfile=str(cert_pem),
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
