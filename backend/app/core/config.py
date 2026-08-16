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
    # Açıldığında antivirüs yapılandırılmadan production başlamaz ve tarama atlanmaz.
    clamav_required: bool = False
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
    # Açıldığında local-only veya başarısız dual mirror kabul edilmez.
    object_storage_remote_required: bool = False
    # P0-05 geçici saha QR süresi (dakika) — kısa TTL + tek kullanım
    site_qr_ephemeral_ttl_minutes: int = 5
    # P0-08 geri yükleme — varsayılan kapalı (yalnızca plan her zaman açık)
    backup_restore_enabled: bool = False
    # P0-10 sağlık alan şifreleme — production rollout açabilir; acil kapatma:
    health_field_encryption_enabled: bool = False
    health_field_encryption_key: str | None = None
    health_field_encryption_force_off: bool = False
    # P0-06: credential + HeadBucket OK ise local→dual (production, güvenli aynalama)
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
    # Eyas Digital Approval — eklemeli dijital onay; acil kapatma FORCE_OFF
    eyas_digital_approval_enabled: bool = True
    eyas_digital_approval_force_off: bool = False
    # Kaynaklı soru bankasından sınav üretimi — içerik kapsamı tamamlanana kadar kapalı.
    training_question_bank_exam_enabled: bool = False
    training_question_bank_exam_force_off: bool = False
    # NACE uyumlu eğitim sunumu — kontrollü pilot tamamlanana kadar kapalı.
    nace_training_presentation_enabled: bool = False
    nace_training_presentation_force_off: bool = False
    # Virgülle ayrılmış şirket kimlikleri. Boş allowlist fail-closed davranır.
    nace_training_presentation_pilot_company_ids: str = ""
    # Remote Basic Occupational Health and Safety Training — additive pilot.
    # Default-off keeps the existing training, examination and certificate flows
    # unchanged until the video module is explicitly enabled for a pilot.
    remote_basic_ohs_training_enabled: bool = False
    remote_basic_ohs_training_force_off: bool = False
    remote_basic_ohs_video_max_upload_mb: int = 2048
    remote_basic_ohs_playback_ttl_seconds: int = 300
    # Opt-in direct object delivery. Authorization remains on the API; after
    # validation, the protected stream route may redirect to a short-lived
    # S3/R2 URL. FORCE_OFF is the immediate rollback switch.
    remote_basic_ohs_direct_object_playback_enabled: bool = False
    remote_basic_ohs_direct_object_playback_force_off: bool = False
    remote_basic_ohs_direct_object_playback_ttl_seconds: int = 3600
    # Strict remote-training policy is a second, independent gate.  Existing
    # company programs remain legacy until they are explicitly materialized
    # from the central catalog and this pilot flag is enabled.
    remote_basic_ohs_strict_policy_enabled: bool = False
    remote_basic_ohs_strict_policy_force_off: bool = False
    # Comma-separated package codes allowed in the strict pilot.  The first
    # live pilot is deliberately limited to working-at-height-ohs.
    remote_basic_ohs_strict_policy_package_codes: str = "working-at-height-ohs"
    # Optional company allowlist.  Empty means package-code scope only; when
    # populated, only the listed company ids can publish/assign strict pilots.
    remote_basic_ohs_strict_policy_pilot_company_ids: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()


def remote_basic_ohs_direct_object_playback_active() -> bool:
    """Return the opt-in R2/S3 delivery state with an emergency kill switch."""
    if bool(getattr(settings, "remote_basic_ohs_direct_object_playback_force_off", False)):
        return False
    return bool(getattr(settings, "remote_basic_ohs_direct_object_playback_enabled", False))


def eyas_digital_approval_active() -> bool:
    """Anında kill-switch: FORCE_OFF veya enabled=false ile UI/API kapanır."""
    if bool(getattr(settings, "eyas_digital_approval_force_off", False)):
        return False
    return bool(getattr(settings, "eyas_digital_approval_enabled", True))


def training_question_bank_exam_active() -> bool:
    """Kapsam tamamlanmadan açılmaz; FORCE_OFF acil durumda her zaman önceliklidir."""
    if bool(getattr(settings, "training_question_bank_exam_force_off", False)):
        return False
    return bool(getattr(settings, "training_question_bank_exam_enabled", False))


def nace_training_presentation_pilot_company_ids() -> frozenset[int]:
    """Parse the source-controlled rollout allowlist; invalid tokens are ignored."""
    raw = str(getattr(settings, "nace_training_presentation_pilot_company_ids", "") or "")
    company_ids: set[int] = set()
    for token in raw.split(","):
        clean = token.strip()
        if not clean:
            continue
        try:
            company_id = int(clean)
        except (TypeError, ValueError):
            continue
        if company_id > 0:
            company_ids.add(company_id)
    return frozenset(company_ids)


def remote_basic_ohs_training_active() -> bool:
    """Feature flag helper; the emergency force-off always wins."""
    if bool(getattr(settings, "remote_basic_ohs_training_force_off", False)):
        return False
    return bool(getattr(settings, "remote_basic_ohs_training_enabled", False))


def _positive_csv(raw: str | None) -> frozenset[int]:
    values: set[int] = set()
    for token in str(raw or "").split(","):
        try:
            value = int(token.strip())
        except (TypeError, ValueError):
            continue
        if value > 0:
            values.add(value)
    return frozenset(values)


def remote_basic_ohs_strict_policy_package_codes() -> frozenset[str]:
    return frozenset(
        item.strip().lower()
        for item in str(getattr(settings, "remote_basic_ohs_strict_policy_package_codes", "") or "").split(",")
        if item.strip()
    )


def remote_basic_ohs_strict_policy_active(
    package_code: str | None, company_id: int | None = None
) -> bool:
    """Return whether the strict policy is open for one package/company.

    The global remote-training flag and this stricter rollout gate are both
    required.  An optional company allowlist narrows the pilot without
    changing the behavior of existing customers.
    """
    if bool(getattr(settings, "remote_basic_ohs_strict_policy_force_off", False)):
        return False
    if not bool(getattr(settings, "remote_basic_ohs_strict_policy_enabled", False)):
        return False
    code = str(package_code or "").strip().lower()
    if not code or code not in remote_basic_ohs_strict_policy_package_codes():
        return False
    allowed_companies = _positive_csv(
        getattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")
    )
    if allowed_companies and (company_id is None or int(company_id) not in allowed_companies):
        return False
    return True


def nace_training_presentation_active(company_id: int | None = None) -> bool:
    """Global flag + force-off + optional fail-closed pilot company boundary."""
    if bool(getattr(settings, "nace_training_presentation_force_off", False)):
        return False
    if not bool(getattr(settings, "nace_training_presentation_enabled", False)):
        return False
    if company_id is None:
        return True
    try:
        normalized_company_id = int(company_id)
    except (TypeError, ValueError):
        return False
    return normalized_company_id in nace_training_presentation_pilot_company_ids()


def nace_training_presentation_rollout(company_id: int | None) -> dict[str, object]:
    """Return non-sensitive rollout diagnostics without exposing allowlist members."""
    pilots = nace_training_presentation_pilot_company_ids()
    global_enabled = bool(getattr(settings, "nace_training_presentation_enabled", False))
    force_off = bool(getattr(settings, "nace_training_presentation_force_off", False))
    try:
        normalized_company_id = int(company_id) if company_id is not None else None
    except (TypeError, ValueError):
        normalized_company_id = None
    pilot_company = bool(normalized_company_id and normalized_company_id in pilots)
    return {
        "global_enabled": global_enabled,
        "force_off": force_off,
        "allowlist_configured": bool(pilots),
        "pilot_company": pilot_company,
        "active": bool(global_enabled and not force_off and pilot_company),
    }


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
    """Üretimde zayıf secret veya zorunlu altyapı eksiğiyle başlamayı engelle."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return
    key = (settings.secret_key or "").strip()
    if len(key) < 32 or key.lower() in _INSECURE_SECRET_KEYS or key.startswith("change-me"):
        raise RuntimeError(
            "Production ortamında güçlü SECRET_KEY zorunludur (.env / Render env). "
            "Varsayılan anahtarla başlatılamaz."
        )
    if bool(getattr(settings, "clamav_required", False)) and not (
        getattr(settings, "clamav_host", None) or ""
    ).strip():
        raise RuntimeError(
            "CLAMAV_REQUIRED=true iken CLAMAV_HOST zorunludur. "
            "Antivirüs taraması olmadan production başlatılamaz."
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
                "OBJECT_STORAGE_REMOTE_REQUIRED=true iken bucket, access key, secret key "
                "ve endpoint veya region zorunludur."
            )
