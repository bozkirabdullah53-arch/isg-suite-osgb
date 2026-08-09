"""2026 İBYS + İSBS/e-Reçete application-readiness report.

This is a compliance/readiness inventory, not an approval certificate.
It intentionally separates:
  * source-controlled software controls,
  * production hardening controls,
  * applicant-owned corporate/certification evidence,
  * authority-issued test/profile/access material.

That separation prevents the product from ever claiming Ministry approval only
because a generic URL or API key was configured.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.services.authority_integration_gate import public_authority_status
from app.services.health_field_crypto import encryption_readiness
from app.services import ibys_client

REPORT_VERSION = "regulatory-application-readiness-2026-v1"
VERIFIED_ON = "2026-08-09"

OFFICIAL_REFERENCES = {
    "ibys": [
        "https://www.csgb.gov.tr/tr/sikca-sorulan-sorular/is-sagligi-ve-guvenligi-genel-mudurlugu/",
        "https://ibys.csgb.gov.tr/",
    ],
    "isbs_kts": [
        "https://kayittescil.saglik.gov.tr/TR-5571/kts-kayit-asamalari.html",
        "https://kayittescil.saglik.gov.tr/",
    ],
    "erecete": [
        "https://kayittescil.saglik.gov.tr/TR-63630/01022020-e-recete-entegrasyonu-hk-tum-sbys-ureticilerine.html",
        "https://renklirecete.saglik.gov.tr/",
    ],
}


def _flag(name: str) -> bool:
    return (os.getenv(name) or "").strip().casefold() in {"1", "true", "yes", "on"}


def _presence(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _check(code: str, title: str, status: str, *, owner: str, detail: str, mandatory: bool = True) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "status": status,
        "owner": owner,
        "mandatory": mandatory,
        "detail": detail,
    }


def _production_hardening() -> list[dict[str, Any]]:
    crypto = encryption_readiness()
    dedicated_health_key = crypto.get("key_status") == "dedicated"
    clamav_strict = bool(settings.clamav_required and (settings.clamav_host or "").strip())
    remote_storage = bool(
        settings.object_storage_remote_required
        and (settings.object_storage_bucket or "").strip()
        and (settings.object_storage_secret_key or "").strip()
    )
    esign_revocation = bool(settings.esign_ocsp_enabled and settings.esign_crl_enabled)
    tsa = bool((settings.esign_tsa_url or "").strip())
    redis_shared = bool((settings.redis_url or "").strip())
    refresh_cookie = bool(settings.auth_refresh_cookie_enabled and not settings.auth_refresh_cookie_force_off)

    return [
        _check(
            "health_dedicated_encryption_key",
            "Sağlık verisi için bağımsız şifreleme anahtarı",
            "ready" if dedicated_health_key else "hardening_required",
            owner="software_runtime",
            detail=f"health crypto key status={crypto.get('key_status')}; KTS ön denetimi için SECRET_KEY fallback yerine dedicated key önerilir.",
            mandatory=False,
        ),
        _check(
            "upload_antivirus_fail_closed",
            "Dosya yüklemelerinde zorunlu antivirüs taraması",
            "ready" if clamav_strict else "hardening_required",
            owner="software_runtime",
            detail="CLAMAV_REQUIRED=true + CLAMAV_HOST ile production fail-closed çalıştırılmalı.",
            mandatory=False,
        ),
        _check(
            "remote_object_storage",
            "Production nesne depolama / yedek dayanıklılığı",
            "ready" if remote_storage else "hardening_required",
            owner="software_runtime",
            detail="OBJECT_STORAGE_REMOTE_REQUIRED ile kontrollü remote storage önerilir.",
            mandatory=False,
        ),
        _check(
            "esign_revocation_checks",
            "E-imza sertifika iptal kontrolleri",
            "ready" if esign_revocation else "hardening_required",
            owner="software_runtime",
            detail="OCSP + CRL kontrollerinin resmî test ortamından önce etkinleştirilmesi önerilir.",
            mandatory=False,
        ),
        _check(
            "esign_timestamp",
            "Güvenilir zaman damgası servisi",
            "ready" if tsa else "hardening_required",
            owner="software_runtime",
            detail="TSA endpoint/kimliği resmî imza senaryosu için yapılandırılmalı.",
            mandatory=False,
        ),
        _check(
            "shared_rate_limit_store",
            "Çoklu instance ortak rate-limit/iş kuyruğu altyapısı",
            "ready" if redis_shared else "hardening_required",
            owner="software_runtime",
            detail="Redis production çoklu instance güvenilirliği için önerilir.",
            mandatory=False,
        ),
        _check(
            "secure_refresh_cookie",
            "HttpOnly refresh-cookie oturum modeli",
            "ready" if refresh_cookie else "hardening_required",
            owner="software_runtime",
            detail="Yetkili sağlık/profesyonel hesaplarında kısa access token + HttpOnly refresh cookie önerilir.",
            mandatory=False,
        ),
    ]


def _software_controls() -> list[dict[str, Any]]:
    return [
        _check(
            "tenant_scope",
            "OSGB/işyeri tenant izolasyonu",
            "implemented",
            owner="source_code",
            detail="Company/OSGB scope, assignment access and tenant middleware source-controlled.",
        ),
        _check(
            "esign_pipeline",
            "E-imza doğrulama zinciri",
            "implemented",
            owner="source_code",
            detail="Tek kullanımlık talep, source SHA-256, sertifika meta, OCSP/CRL/TSA ve kilitleme altyapısı mevcut; İBYS veri-imza profili resmî teknik dokümanla bağlanacak.",
        ),
        _check(
            "health_field_crypto",
            "Sağlık hassas alan şifreleme katmanı",
            "implemented",
            owner="source_code",
            detail="Hassas sağlık metin alanları için şifreleme/backfill katmanı mevcut.",
        ),
        _check(
            "prescription_lifecycle",
            "Reçete yaşam döngüsü ve yetki ayrımı",
            "implemented",
            owner="source_code",
            detail="Yalnız işyeri hekimi yazabilir; draft/ready/sending/approved/rejected/cancelled statüleri ve tenant doğrulaması mevcut.",
        ),
        _check(
            "prescription_submission_evidence",
            "E-Reçete gönderim/deneme/hata kanıt modeli",
            "implemented",
            owner="source_code",
            detail="PrescriptionSubmission, attempt ve MedulaErrorLog modelleri resmî adapter için hazır kanıt omurgası sağlar.",
        ),
        _check(
            "authority_gate",
            "Resmî olmayan endpoint'e yanlışlıkla resmi gönderim engeli",
            "implemented",
            owner="source_code",
            detail="Yeni formal gate resmî endpoint+profil+test/access code+explicit enable olmadan gönderimi fail-closed engeller.",
        ),
        _check(
            "submission_integrity",
            "Gönderim bütünlüğü ve idempotency",
            "implemented",
            owner="source_code",
            detail="Canonical JSON, SHA-256, request id ve deterministic idempotency key zarfı eklendi.",
        ),
    ]


def _ibys_external_evidence() -> list[dict[str, Any]]:
    return [
        _check(
            "ibys_current_application_pack",
            "İSGGM'nin güncel İBYS başvuru evrak seti",
            "ready" if _flag("IBYS_EVIDENCE_CURRENT_APPLICATION_PACK_COMPLETE") else "external_required",
            owner="applicant",
            detail="ÇSGB SSS başvuru evraklarının internet sitesinden hazırlanıp İSGGM randevusu ile sunulmasını ister. Güncel paket başvuru günü İSGGM/İBYS'den doğrulanmalıdır.",
        ),
        _check(
            "ibys_appointment",
            "İSGGM entegratör başvuru randevusu",
            "ready" if _flag("IBYS_EVIDENCE_APPOINTMENT_CONFIRMED") else "external_required",
            owner="applicant",
            detail="Yazılımla üretilemez; İSGGM ile randevu gerekir.",
        ),
    ]


def _kts_external_evidence() -> list[dict[str, Any]]:
    requirements = [
        ("kts_trade_registry_founding", "Kuruluş Ticaret Sicil Gazetesi"),
        ("kts_trade_registry_current", "Güncel Ticaret Sicil Gazetesi"),
        ("kts_sgk_workplace", "SGK işyeri tescil belgesi"),
        ("kts_balance_sheets_3y", "Son 3 yıla ait onaylı/doğrulanabilir bilançolar"),
        ("kts_sbys_authorized_person", "SBYS Yetkili Belgesi"),
        ("kts_sbys_software_list", "SBYS Yazılım Listesi (İSBS)"),
        ("kts_iso27001", "TÜRKAK kapsamlı TS ISO/IEC 27001 belgesi"),
        ("kts_process_maturity", "SPICE en az Seviye 2 veya CMMI en az Seviye 3 belgesi"),
        ("kts_confidentiality", "Bakanlık gizlilik sözleşmesi için iki asıl nüsha"),
        ("kts_management_personnel", "Firma yönetici/yetkili/personel bilgileri"),
    ]
    out = []
    for code, title in requirements:
        env = f"{code.upper()}_VERIFIED"
        out.append(
            _check(
                code,
                title,
                "ready" if _flag(env) else "external_required",
                owner="applicant",
                detail=f"KTS 2025 başvuru paketinde istenir. Kanıt hazır olduğunda yalnız var/yok işareti için {env}=true kullanılabilir; belge içeriği secret/env'e konulmamalıdır.",
            )
        )
    out.append(
        _check(
            "kts_ip_registration_optional",
            "Bilgisayar programı/veritabanı kayıt-tescil belgesi",
            "ready" if _flag("KTS_IP_REGISTRATION_OPTIONAL_VERIFIED") else "optional",
            owner="applicant",
            detail="Yurt içinde geliştirilen yazılım için KTS kılavuzunda ihtiyari belge olarak listelenir.",
            mandatory=False,
        )
    )
    return out


def _authority_pending() -> list[dict[str, Any]]:
    status = public_authority_status()
    return [
        _check(
            "ibys_authority_test_profile",
            "ÇSGB resmî İBYS teknik profil/test erişimi",
            "ready" if status["ibys"]["test"]["ready"] else "authority_pending",
            owner="csgb",
            detail="Başvuru/test aşamasında Bakanlıkça verilen güncel veri sözlüğü, imza profili, endpoint ve test kodu olmadan gerçek protokol uygulanmaz.",
        ),
        _check(
            "isbs_kts_test_code",
            "KTS yazılım erişim test kodu + test kılavuzu",
            "ready" if status["isbs_erecete"]["test"]["ready"] else "authority_pending",
            owner="saglik_bakanligi",
            detail="KTS ön kayıt sonrası Bakanlık test kodu/kılavuzu ile veri aktarım ve sağlık bilişimi standart testleri yapılır.",
        ),
        _check(
            "isbs_erecete_profile",
            "Sağlık Bakanlığı e-Reçete/RRS entegrasyon profili",
            "ready" if _presence("ISBS_ERECETE_PROFILE_VERSION") else "authority_pending",
            owner="saglik_bakanligi",
            detail="Wire format veya kimlik doğrulama yöntemi tahmin edilmeyecek; güncel RRS/e-Reçete entegrasyon dokümanı esas alınacak.",
        ),
    ]


def build_regulatory_application_readiness() -> dict[str, Any]:
    software = _software_controls()
    hardening = _production_hardening()
    ibys_external = _ibys_external_evidence()
    kts_external = _kts_external_evidence()
    pending = _authority_pending()
    legacy_ibys_status = ibys_client.status()

    software_blockers = [x for x in software if x["mandatory"] and x["status"] not in {"implemented", "ready"}]
    ibys_external_blockers = [x for x in ibys_external if x["mandatory"] and x["status"] != "ready"]
    kts_external_blockers = [x for x in kts_external if x["mandatory"] and x["status"] != "ready"]
    authority_pending = [x for x in pending if x["status"] != "ready"]

    return {
        "report_version": REPORT_VERSION,
        "verified_on": VERIFIED_ON,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": ["csgb_ibys_integrator_application", "saglik_kts_isbs_erecete_application"],
        "claims": {
            "ministry_approval_claimed": False,
            "legacy_ibys_adapter_is_official": False,
            "legacy_ibys_adapter_status": legacy_ibys_status,
            "wire_protocol_guessed": False,
        },
        "software_controls": software,
        "production_hardening": hardening,
        "ibys_applicant_evidence": ibys_external,
        "kts_isbs_applicant_evidence": kts_external,
        "authority_pending": pending,
        "authority_gate": public_authority_status(),
        "official_references": OFFICIAL_REFERENCES,
        "summary": {
            "code_application_layer_ready": not software_blockers,
            "software_blockers": len(software_blockers),
            "ibys_applicant_external_blockers": len(ibys_external_blockers),
            "kts_applicant_external_blockers": len(kts_external_blockers),
            "authority_pending_items": len(authority_pending),
            "official_live_send_ready": bool(
                public_authority_status()["ibys"]["production"]["ready"]
                and public_authority_status()["isbs_erecete"]["production"]["ready"]
            ),
            "status": (
                "APPLICATION_LAYER_READY_EXTERNAL_EVIDENCE_PENDING"
                if not software_blockers and (ibys_external_blockers or kts_external_blockers)
                else "APPLICATION_LAYER_READY"
                if not software_blockers
                else "SOFTWARE_BLOCKED"
            ),
        },
    }
