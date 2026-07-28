from __future__ import annotations

import json
import os
from pathlib import Path

PRODUCT = "OSGB Signer"
VERSION = "1.1.0"
DEFAULT_PORT = 17000

# HSNSigner (IBYSIS) 16999 kullanır — bilerek ayrı port; ikisi aynı anda çalışabilir.
DEFAULT_ORIGINS = [
    "https://www.isgsuite.tr",
    "https://isgsuite.tr",
    "https://isg-suite-web-1u9t.onrender.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def install_dir() -> Path:
    override = os.environ.get("ISG_SIGNER_HOME")
    if override:
        return Path(override)
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ISGSuiteSigner"


def config_path() -> Path:
    return install_dir() / "appsettings.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {
            "ListenPort": DEFAULT_PORT,
            "AllowedOrigins": list(DEFAULT_ORIGINS),
            "Tls": {"Enabled": True, "CertificatePath": "", "CertificatePassword": ""},
            "Signing": {
                "DemoCertPath": "",
                "DemoCertPassword": "",
                "Pkcs11Module": "",
            },
            "RequestSizeLimitBytes": 40 * 1024 * 1024,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    install_dir().mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
