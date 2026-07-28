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
    # Production enable_backup_crypto_for_production secret_key kullanır; acil kapatma:
    backup_encryption_secret_fallback: bool = False
    backup_encryption_force_off: bool = False
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    # Canlıda kapalı: silinen demo OSGB'ler restart'ta geri gelmesin
    seed_demo_osgbs: bool = False
    clamav_host: str | None = None
    clamav_port: int = 3310
    clamav_timeout_sec: float = 30.0
    # P0 upload gateway — production'da apply_production_rollout açar
    upload_gateway_enabled: bool = False
    # Acil kapatma: UPLOAD_GATEWAY_FORCE_OFF=true (production override'ı iptal)
    upload_gateway_force_off: bool = False
    # P0-06 object storage — varsayılan local; s3/r2 için bucket + credential
    object_storage_backend: str = "local"
    object_storage_bucket: str | None = None
    object_storage_prefix: str = "uploads"
    object_storage_endpoint: str | None = None
    object_storage_region: str | None = None
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    # P0-05 geçici saha QR süresi (dakika) — kısa TTL + tek kullanım
    site_qr_ephemeral_ttl_minutes: int = 5
    # P0-08 geri yükleme — varsayılan kapalı (yalnızca plan her zaman açık)
    backup_restore_enabled: bool = False
    # P0-10 sağlık alan şifreleme — production rollout açabilir; acil kapatma:
    health_field_encryption_enabled: bool = False
    health_field_encryption_key: str | None = None
    health_field_encryption_force_off: bool = False
    # P0-06: credential + HeadBucket OK ise local→r2/s3 (production)
    object_storage_auto_cutover: bool = True
    object_storage_force_local: bool = False
    # P1-2 rate limit
    rate_limit_rpm: int = 120
    rate_limit_auth_rpm: int = 30
    # P1-02 Redis rate limit — boşsa bellek içi (çoklu instance paylaşılmaz)
    redis_url: str | None = None
    # P1-01 HttpOnly refresh cookie
    auth_refresh_cookie_enabled: bool = False
    # Canlıda acil kapatma: AUTH_REFRESH_COOKIE_FORCE_OFF=true
    auth_refresh_cookie_force_off: bool = False
    refresh_token_expire_days: int = 14
    # P1-10 async job — REDIS_URL veya ASYNC_JOBS_ENABLED; FORCE_OFF artık Redis varken no-op
    async_jobs_enabled: bool = False
    async_jobs_force_off: bool = False
    # İBYS / İSG-KATİP adapter scaffold (optional; never commit real secrets)
    ibys_api_url: str | None = None
    ibys_api_key: str | None = None
    katip_api_url: str | None = None
    katip_api_key: str | None = None
    # OSGB e-imza hattı (opsiyonel ağ kontrolleri — varsayılan kapalı, güvenli)
    esign_ocsp_enabled: bool = False
    esign_crl_enabled: bool = False
    esign_tsa_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()

_INSECURE_SECRET_KEYS = frozenset({
    "change-me-in-production-at-least-32-characters!",
    "change-me",
    "secret",
    "changeme",
})


def apply_production_rollout() -> None:
    """Canlı cutover: Redis varken async; production'da upload gateway (force-off yoksa)."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return
    if not bool(settings.upload_gateway_force_off):
        settings.upload_gateway_enabled = True


apply_production_rollout()


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
