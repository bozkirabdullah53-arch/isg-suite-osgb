from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "İSG Suite OSGB"
    environment: str = "development"
    database_url: str = "sqlite:///./isgsuite.db"
    secret_key: str = "change-me-in-production-at-least-32-characters!"  # Field(min_length=32)
    access_token_expire_minutes: int = 60
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
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    # Canlıda kapalı: silinen demo OSGB'ler restart'ta geri gelmesin
    seed_demo_osgbs: bool = False
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_sec: float = 30.0
    # P0 upload gateway — kapalı; açılınca yeni yollar persist_upload kullanır
    upload_gateway_enabled: bool = False
    # P0-06 object storage — varsayılan local; s3/r2 için bucket + credential
    object_storage_backend: str = "local"
    object_storage_bucket: str | None = None
    object_storage_prefix: str = "uploads"
    object_storage_endpoint: str | None = None
    object_storage_region: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    # P0-07 geçici saha QR süresi (dakika)
    site_qr_ephemeral_ttl_minutes: int = 30
    # P0-08 geri yükleme — varsayılan kapalı (yalnızca plan her zaman açık)
    backup_restore_enabled: bool = False
    # P0-10 sağlık alan şifreleme — varsayılan kapalı; açılınca yeni yazılar enc:v1:
    health_field_encryption_enabled: bool = False
    health_field_encryption_key: str | None = None
    # P1-2 rate limit
    rate_limit_rpm: int = 120
    rate_limit_auth_rpm: int = 30
    # İBYS / İSG-KATİP adapter scaffold (optional; never commit real secrets)
    ibys_api_url: str | None = None
    ibys_api_key: str | None = None
    katip_api_url: str | None = None
    katip_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()

_INSECURE_SECRET_KEYS = frozenset({
    "change-me-in-production-at-least-32-characters!",
    "change-me",
    "secret",
    "changeme",
})


def validate_runtime_settings() -> None:
    """Üretimde zayıf/varsayılan SECRET_KEY ile başlamayı engelle."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return
    key = (settings.secret_key or "").strip()
    if len(key) < 32 or key.lower() in _INSECURE_SECRET_KEYS or key.startswith("change-me"):
        raise RuntimeError(
            "Production ortamında güçlü SECRET_KEY zorunludur (.env / Render env). "
            "Varsayılan anahtarla başlatılamaz."
        )
