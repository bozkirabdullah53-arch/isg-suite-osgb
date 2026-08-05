from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "İSG Suite OSGB"
    environment: str = "development"
    database_url: str = "sqlite:///./isgsuite.db"
    secret_key: str = "change-me-in-production-at-least-32-characters!"  # Field(min_length=32)
    access_token_expire_minutes: int = 60
    # P1-01: refresh cookie açıkken kısa access (dakika)
    access_token_expire_minutes_short: int = 15
    frontend_origin: str = "http://localhost:5173"
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "noreply@example.com"
    smtp_use_tls: bool = True
    backup_dir: str = "./backups"
    backup_encryption_key: str | None = None
    backup_encryption_secret_fallback: bool = False
    backup_encryption_force_off: bool = False
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_demo_osgbs: bool = False
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_sec: float = 30.0
    clamav_required: bool = False
    upload_gateway_enabled: bool = False
    upload_gateway_force_off: bool = False
    object_storage_backend: str = "local"
    object_storage_bucket: str | None = None
    object_storage_prefix: str = "uploads"
    object_storage_endpoint: str | None = None
    object_storage_region: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_remote_required: bool = False
    site_qr_ephemeral_ttl_minutes: int = 5
    backup_restore_enabled: bool = False
    health_field_encryption_enabled: bool = False
    health_field_encryption_key: str | None = None
    health_field_encryption_force_off: bool = False
    object_storage_auto_cutover: bool = True
    object_storage_force_local: bool = False
    rate_limit_rpm: int = 120
    rate_limit_auth_rpm: int = 30
    redis_url: str | None = None
    auth_refresh_cookie_enabled: bool = False
    auth_refresh_cookie_force_off: bool = False
    refresh_token_expire_days: int = 14
    async_jobs_enabled: bool = False
    async_jobs_force_off: bool = False
    ibys_api_url: str | None = None
    ibys_api_key: str | None = None
    katip_api_url: str | None = None
    katip_api_key: str | None = None
    esign_ocsp_enabled: bool = False
    esign_crl_enabled: bool = False
    esign_tsa_url: str | None = None
    eyas_digital_approval_enabled: bool = True
    eyas_digital_approval_force_off: bool = False
    training_question_bank_exam_enabled: bool = False
    training_question_bank_exam_force_off: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()


def eyas_digital_approval_active() -> bool:
    if bool(getattr(settings, "eyas_digital_approval_force_off", False)):
        return False
    return bool(getattr(settings, "eyas_digital_approval_enabled", True))


def training_question_bank_exam_active() -> bool:
    if bool(getattr(settings, "training_question_bank_exam_force_off", False)):
        return False
    return bool(getattr(settings, "training_question_bank_exam_enabled", False))


_INSECURE_SECRET_KEYS = frozenset({
    "change-me-in-production-at-least-32-characters!",
    "change-me",
    "secret",
    "changeme",
})


def apply_production_rollout() -> None:
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return
    if not bool(settings.upload_gateway_force_off):
        settings.upload_gateway_enabled = True


apply_production_rollout()


def validate_runtime_settings() -> None:
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return
    key = (settings.secret_key or "").strip()
    if len(key) < 32 or key.lower() in _INSECURE_SECRET_KEYS or key.startswith("change-me"):
        raise RuntimeError(
            "Production ortamında güçlü SECRET_KEY zorunludur (.env / Render env). Varsayılan anahtarla başlatılamaz."
        )
    if bool(getattr(settings, "clamav_required", False)) and not (
        getattr(settings, "clamav_host", None) or ""
    ).strip():
        raise RuntimeError(
            "CLAMAV_REQUIRED=true iken CLAMAV_HOST zorunludur. Antivirüs taraması olmadan production başlatılamaz."
        )
    if bool(getattr(settings, "object_storage_remote_required", False)):
        bucket = (settings.object_storage_bucket or "").strip()
        access = (settings.object_storage_access_key or "").strip()
        secret = (settings.object_storage_secret_key or "").strip()
        endpoint = (settings.object_storage_endpoint or "").strip()
        region = (settings.object_storage_region or "").strip()
        if bool(getattr(settings, "object_storage_force_local", False)):
            raise RuntimeError(
                "OBJECT_STORAGE_REMOTE_REQUIRED=true iken OBJECT_STORAGE_FORCE_LOCAL kullanılamaz."
            )
        if not (bucket and access and secret and (endpoint or region)):
            raise RuntimeError(
                "OBJECT_STORAGE_REMOTE_REQUIRED=true iken bucket, access key, secret key ve endpoint veya region zorunludur."
            )
