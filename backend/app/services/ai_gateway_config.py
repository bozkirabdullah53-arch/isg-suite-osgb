"""Global AI gateway settings for the existing EİSA vision engine.

The extension is additive and fail-safe:
- until a global admin saves a managed configuration, legacy environment settings stay active;
- VISION_ANALYSIS_FORCE_OFF is never changed here;
- API keys are encrypted at rest and are never returned to the browser;
- API provider failures are fail-closed; heuristic mode is explicit.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import logging
import socket
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import EisaPlatformSetting

logger = logging.getLogger(__name__)

_KEY_PREFIX = "enc:ai:v1:"
_SETTING_PREFIX = "ai_gateway_"
MANAGED_KEY = f"{_SETTING_PREFIX}managed"
ENABLED_KEY = f"{_SETTING_PREFIX}enabled"
PROVIDER_KEY = f"{_SETTING_PREFIX}provider"
BASE_URL_KEY = f"{_SETTING_PREFIX}base_url"
MODEL_KEY = f"{_SETTING_PREFIX}model"
TIMEOUT_KEY = f"{_SETTING_PREFIX}timeout_sec"
UPDATED_AT_KEY = f"{_SETTING_PREFIX}updated_at"
CUSTOM_KEY_BASE_URL_KEY = f"{_SETTING_PREFIX}custom_openai_key_base_url"

PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "heuristic": {
        "label": "Yerel / API'siz güvenli mod",
        "base_url": "",
        "default_model": "",
        "requires_api_key": False,
        "description": "Dış servise veri göndermez; yalnızca metin ve seçili etiketlerden öneri üretir.",
    },
    "yolo": {
        "label": "Yerel YOLO nesne tespiti",
        "base_url": "",
        "default_model": "",
        "requires_api_key": False,
        "description": "Sunucuda YOLO modeli kuruluysa yerel nesne tespiti kullanılır; yoksa mevcut fallback devreye girer.",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "openai/gpt-5.4-mini",
        "requires_api_key": True,
        "description": "OpenAI Chat Completions uyumlu görsel analiz.",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "requires_api_key": True,
        "description": "Google'ın OpenAI uyumluluk katmanı üzerinden görsel analiz.",
    },
    "custom_openai": {
        "label": "Özel OpenAI-uyumlu API",
        "base_url": "",
        "default_model": "",
        "requires_api_key": True,
        "description": "OpenAI Chat Completions sözleşmesini destekleyen özel sağlayıcı.",
    },
}

_LEGACY_RUNTIME = {
    "vision_analysis_enabled": bool(getattr(settings, "vision_analysis_enabled", False)),
    "vision_provider": str(getattr(settings, "vision_provider", "heuristic") or "heuristic"),
    "vision_api_key": getattr(settings, "vision_api_key", None),
    "vision_api_base_url": getattr(settings, "vision_api_base_url", None),
    "vision_api_model": str(getattr(settings, "vision_api_model", "") or ""),
    "vision_api_timeout_sec": int(getattr(settings, "vision_api_timeout_sec", 30) or 30),
}

_HOOK_INSTALLED = False


def api_key_setting_key(provider: str) -> str:
    safe = str(provider or "").strip().lower()
    if safe not in PROVIDER_CATALOG:
        raise ValueError("Desteklenmeyen yapay zekâ sağlayıcısı.")
    return f"{_SETTING_PREFIX}api_key_{safe}"


def _bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "evet"}


def _row(db: Session, key: str) -> EisaPlatformSetting | None:
    return db.scalar(select(EisaPlatformSetting).where(EisaPlatformSetting.key == key))


def _get(db: Session, key: str, default: str = "") -> str:
    row = _row(db, key)
    return row.value if row is not None else default


def _set(db: Session, key: str, value: str) -> None:
    row = _row(db, key)
    if row is None:
        db.add(EisaPlatformSetting(key=key, value=value))
    else:
        row.value = value


def _fernet() -> Fernet:
    secret = str(getattr(settings, "secret_key", "") or "").strip()
    if not secret:
        raise RuntimeError("Uygulama SECRET_KEY değeri olmadığı için API anahtarı şifrelenemiyor.")
    material = hashlib.sha256(f"eisa-ai-gateway:v1:{secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_api_key(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("API anahtarı boş olamaz.")
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_KEY_PREFIX}{token}"


def decrypt_api_key(stored: str | None) -> str | None:
    value = str(stored or "").strip()
    if not value:
        return None
    if not value.startswith(_KEY_PREFIX):
        logger.error("AI gateway API key is not encrypted; refusing to use it.")
        return None
    token = value[len(_KEY_PREFIX):].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        logger.exception("AI gateway API key could not be decrypted.")
        return None


def _infer_provider(vision_provider: str, base_url: str | None) -> str:
    provider = str(vision_provider or "heuristic").strip().lower()
    if provider != "api":
        return "heuristic" if provider not in {"heuristic", "yolo"} else provider
    host = (urlsplit(str(base_url or "")).hostname or "").lower()
    if host == "api.openai.com":
        return "openai"
    if host.endswith("generativelanguage.googleapis.com"):
        return "gemini"
    return "custom_openai"


def _normalize_custom_base_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("Özel API için Base URL zorunludur.")
    if value.rstrip("/").endswith("/chat/completions"):
        value = value.rstrip("/")[: -len("/chat/completions")]
    parts = urlsplit(value)
    env = str(getattr(settings, "environment", "") or "").strip().lower()
    is_prod = env in {"production", "prod", "live"}
    if parts.scheme not in ({"https"} if is_prod else {"https", "http"}):
        raise ValueError("Canlı ortamda özel AI Base URL yalnızca HTTPS olabilir.")
    if not parts.hostname:
        raise ValueError("AI Base URL geçerli bir alan adı içermelidir.")
    if parts.username or parts.password:
        raise ValueError("AI Base URL içinde kullanıcı adı/parola kullanılamaz.")
    if parts.query or parts.fragment:
        raise ValueError("AI Base URL sorgu parametresi veya #fragment içeremez.")
    host = parts.hostname.lower()
    if host in {"localhost", "localhost.localdomain"} and is_prod:
        raise ValueError("Canlı ortamda localhost AI adresi kullanılamaz.")
    try:
        addr = ipaddress.ip_address(host.strip("[]"))
        if is_prod and (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise ValueError("Canlı ortamda yerel/özel ağ IP'sine AI yönlendirmesi yapılamaz.")
    except ValueError as exc:
        if "AI yönlendirmesi" in str(exc):
            raise
    clean_path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, clean_path, "", ""))


def resolve_base_url(provider: str, supplied: str | None = None) -> str:
    key = str(provider or "").strip().lower()
    meta = PROVIDER_CATALOG.get(key)
    if not meta:
        raise ValueError("Desteklenmeyen yapay zekâ sağlayıcısı.")
    if key == "custom_openai":
        return _normalize_custom_base_url(str(supplied or ""))
    return str(meta["base_url"])


def _validate_model(provider: str, model: str | None) -> str:
    if provider in {"heuristic", "yolo"}:
        return ""
    value = str(model or "").strip()
    if not value:
        value = str(PROVIDER_CATALOG[provider].get("default_model") or "").strip()
    if not value:
        raise ValueError("Seçilen sağlayıcı için model adı zorunludur.")
    if len(value) > 160 or any(ch.isspace() for ch in value):
        raise ValueError("Model adı geçersiz.")
    return value


def _validate_timeout(raw: int | str | None) -> int:
    try:
        value = int(raw if raw is not None else 30)
    except (TypeError, ValueError) as exc:
        raise ValueError("AI zaman aşımı sayısal olmalıdır.") from exc
    if value < 5 or value > 120:
        raise ValueError("AI zaman aşımı 5–120 saniye arasında olmalıdır.")
    return value


def managed_config(db: Session) -> dict[str, Any] | None:
    if not _bool(_get(db, MANAGED_KEY, "false")):
        return None
    provider = _get(db, PROVIDER_KEY, "heuristic").strip().lower()
    if provider not in PROVIDER_CATALOG:
        provider = "heuristic"
    base_url = resolve_base_url(provider, _get(db, BASE_URL_KEY, "")) if provider not in {"heuristic", "yolo"} else ""
    model = _validate_model(provider, _get(db, MODEL_KEY, "")) if provider not in {"heuristic", "yolo"} else ""
    timeout_sec = _validate_timeout(_get(db, TIMEOUT_KEY, "30"))
    requires_key = bool(PROVIDER_CATALOG[provider]["requires_api_key"])
    key_setting = api_key_setting_key(provider) if requires_key else ""
    stored_key = _get(db, key_setting, "") if key_setting else ""
    api_key = decrypt_api_key(stored_key)
    if provider == "custom_openai" and api_key:
        bound_base = _get(db, CUSTOM_KEY_BASE_URL_KEY, "")
        if bound_base != base_url:
            api_key = None
    return {
        "managed": True,
        "enabled": _bool(_get(db, ENABLED_KEY, "false")),
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "timeout_sec": timeout_sec,
        "api_key": api_key,
        "api_key_configured": bool(api_key),
        "updated_at": _get(db, UPDATED_AT_KEY, "") or None,
    }


def restore_legacy_runtime() -> None:
    for key, value in _LEGACY_RUNTIME.items():
        setattr(settings, key, value)


def apply_managed_runtime(db: Session) -> dict[str, Any] | None:
    config = managed_config(db)
    if config is None:
        restore_legacy_runtime()
        return None

    settings.vision_analysis_enabled = bool(config["enabled"])
    settings.vision_api_timeout_sec = int(config["timeout_sec"])
    if config["provider"] in {"heuristic", "yolo"}:
        settings.vision_provider = config["provider"]
        settings.vision_api_key = None
        settings.vision_api_base_url = None
        settings.vision_api_model = ""
    else:
        settings.vision_provider = "api"
        settings.vision_api_key = config["api_key"]
        settings.vision_api_base_url = config["base_url"]
        settings.vision_api_model = config["model"]
    return config


def apply_persisted_ai_settings() -> bool:
    try:
        with SessionLocal() as db:
            return apply_managed_runtime(db) is not None
    except Exception:
        logger.warning("AI gateway persisted settings could not be loaded; current runtime kept.", exc_info=True)
        return False


def install_runtime_hook() -> None:
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return
    from app.services import ai_vision

    original = ai_vision.build_full_analysis
    if getattr(original, "_eisa_ai_gateway_wrapped", False):
        _HOOK_INSTALLED = True
        return

    def wrapped_build_full_analysis(*args: Any, **kwargs: Any):
        apply_persisted_ai_settings()
        return original(*args, **kwargs)

    wrapped_build_full_analysis._eisa_ai_gateway_wrapped = True  # type: ignore[attr-defined]
    ai_vision.build_full_analysis = wrapped_build_full_analysis
    _HOOK_INSTALLED = True
    apply_persisted_ai_settings()
    logger.info("EİSA Global AI gateway runtime hook installed.")


def _provider_api_key_configured(
    db: Session,
    provider: str,
    *,
    active_provider: str,
    active_base_url: str,
) -> bool:
    meta = PROVIDER_CATALOG.get(provider) or {}
    if not meta.get("requires_api_key"):
        return False
    raw = decrypt_api_key(_get(db, api_key_setting_key(provider), ""))
    if not raw:
        return False
    if provider == "custom_openai":
        return active_provider == "custom_openai" and _get(db, CUSTOM_KEY_BASE_URL_KEY, "") == active_base_url
    return True


def public_config(db: Session) -> dict[str, Any]:
    config = managed_config(db)
    force_off = bool(getattr(settings, "vision_analysis_force_off", False))
    if config is None:
        provider = _infer_provider(
            str(_LEGACY_RUNTIME["vision_provider"]),
            _LEGACY_RUNTIME["vision_api_base_url"],
        )
        api_key_configured = bool(_LEGACY_RUNTIME["vision_api_key"])
        enabled = bool(_LEGACY_RUNTIME["vision_analysis_enabled"])
        base_url = str(_LEGACY_RUNTIME["vision_api_base_url"] or "")
        model = str(_LEGACY_RUNTIME["vision_api_model"] or "")
        timeout_sec = int(_LEGACY_RUNTIME["vision_api_timeout_sec"])
        source = "environment"
        managed = False
        updated_at = None
    else:
        provider = str(config["provider"])
        api_key_configured = bool(config["api_key_configured"])
        enabled = bool(config["enabled"])
        base_url = str(config["base_url"] or "")
        model = str(config["model"] or "")
        timeout_sec = int(config["timeout_sec"])
        source = "global_panel"
        managed = True
        updated_at = config["updated_at"]

    requires_key = bool(PROVIDER_CATALOG.get(provider, {}).get("requires_api_key", provider not in {"heuristic", "yolo"}))
    ready = bool(enabled and not force_off and (not requires_key or api_key_configured))
    return {
        "managed": managed,
        "source": source,
        "enabled": enabled,
        "force_off": force_off,
        "effective_enabled": bool(enabled and not force_off),
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "timeout_sec": timeout_sec,
        "api_key_configured": api_key_configured,
        "ready": ready,
        "updated_at": updated_at,
        "provider_catalog": [
            {
                "id": key,
                **value,
                "api_key_configured": _provider_api_key_configured(
                    db,
                    key,
                    active_provider=provider,
                    active_base_url=base_url,
                ),
            }
            for key, value in PROVIDER_CATALOG.items()
        ],
    }


def save_managed_config(
    db: Session,
    *,
    enabled: bool,
    provider: str,
    model: str | None,
    base_url: str | None,
    timeout_sec: int,
    api_key: str | None = None,
    clear_api_key: bool = False,
) -> dict[str, Any]:
    provider_key = str(provider or "").strip().lower()
    if provider_key not in PROVIDER_CATALOG:
        raise ValueError("Desteklenmeyen yapay zekâ sağlayıcısı.")

    resolved_base = resolve_base_url(provider_key, base_url) if provider_key not in {"heuristic", "yolo"} else ""
    resolved_model = _validate_model(provider_key, model)
    resolved_timeout = _validate_timeout(timeout_sec)

    requires_key = bool(PROVIDER_CATALOG[provider_key]["requires_api_key"])
    key_setting = api_key_setting_key(provider_key) if requires_key else ""
    existing_encrypted = _get(db, key_setting, "") if key_setting else ""
    incoming = str(api_key or "").strip()

    if provider_key == "custom_openai" and existing_encrypted:
        bound_base = _get(db, CUSTOM_KEY_BASE_URL_KEY, "")
        if bound_base != resolved_base:
            existing_encrypted = ""

    if clear_api_key and key_setting:
        existing_encrypted = ""
    if incoming:
        if len(incoming) < 8 or len(incoming) > 1200:
            raise ValueError("API anahtarı uzunluğu geçersiz.")
        existing_encrypted = encrypt_api_key(incoming)

    if enabled and requires_key and not existing_encrypted:
        raise ValueError("Bu sağlayıcıyı aktif etmek için bu sağlayıcıya ait API anahtarını girmeniz gerekir.")

    _set(db, MANAGED_KEY, "true")
    _set(db, ENABLED_KEY, "true" if enabled else "false")
    _set(db, PROVIDER_KEY, provider_key)
    _set(db, BASE_URL_KEY, resolved_base)
    _set(db, MODEL_KEY, resolved_model)
    _set(db, TIMEOUT_KEY, str(resolved_timeout))
    if key_setting:
        _set(db, key_setting, existing_encrypted)
    if provider_key == "custom_openai" and incoming:
        _set(db, CUSTOM_KEY_BASE_URL_KEY, resolved_base)
    _set(db, UPDATED_AT_KEY, datetime.utcnow().isoformat(timespec="seconds"))
    db.flush()

    if enabled and requires_key and not decrypt_api_key(existing_encrypted):
        raise ValueError("API anahtarı güvenli biçimde doğrulanamadı; ayarlar kaydedilmedi.")

    return public_config(db)


def reset_managed_config(db: Session) -> None:
    db.execute(delete(EisaPlatformSetting).where(EisaPlatformSetting.key.like(f"{_SETTING_PREFIX}%")))
    db.flush()


def _resolved_host_is_safe(base_url: str) -> bool:
    parts = urlsplit(base_url)
    host = parts.hostname
    if not host:
        return False
    env = str(getattr(settings, "environment", "") or "").strip().lower()
    if env not in {"production", "prod", "live"}:
        return True
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return True
    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def connection_test_payload(db: Session) -> dict[str, Any]:
    config = managed_config(db)
    if config is None:
        raise ValueError("Önce Yapay Zekâ Yönetimi panelinden ayarları kaydedin.")
    provider = config["provider"]
    if provider in {"heuristic", "yolo"}:
        return {
            "local": True,
            "provider": provider,
            "model": "",
            "base_url": "",
            "api_key": None,
            "timeout_sec": config["timeout_sec"],
        }
    if not config["api_key"]:
        raise ValueError("API anahtarı kayıtlı değil.")
    if not _resolved_host_is_safe(config["base_url"]):
        raise ValueError("AI hedef adresi güvenlik politikası nedeniyle engellendi.")
    return {
        "local": False,
        "provider": provider,
        "model": config["model"],
        "base_url": config["base_url"],
        "api_key": config["api_key"],
        "timeout_sec": config["timeout_sec"],
    }
