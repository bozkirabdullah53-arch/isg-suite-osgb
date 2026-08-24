from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Apply the additive OSGB professional metadata/service compatibility layer before
# profile routers bind service functions. Existing workplace modules are untouched.
from app.services.personnel_profile_osgb_scope import install_osgb_service_overrides
install_osgb_service_overrides()

from app.api import auth, branches, companies, dashboard, employees, personnel_profiles, personnel_profile_management, personnel_profile_osgb, personnel_profile_osgb_documents, users, isg_records, health, documents, annual_plans, annual_eval, reports, security, files, exports, subscriptions, notifications, system, osgb, professional_performance_exports, operations, trainings, training_nace, training_completion, training_lifecycle_v2, training_premium_dashboard_v1, training_presentation, training_presentation_editor, training_question_selection_audit, remote_training, self_service, risks, incidents, ppe, sds, drills, emergency_teams, eisa, eisa_orphan_users, osgb_applications, archives, legal, memberships, compliance_registers, committee_professional, esign, esign_orch, eyas, training_question_bank, prescriptions
from app.core.rate_limit import SimpleRateLimitMiddleware
from app.core.request_id import RequestIdMiddleware, install_request_id_logging
from app.core.tenant_middleware import TenantContextMiddleware
from app.core.access_log import StructuredAccessLogMiddleware
from app.core.subscription_middleware import OsgbSubscriptionWriteMiddleware
from app.core.config import settings, validate_runtime_settings
from app.core.cors_policy import build_cors_origins, is_production_environment
from app.core.database import Base, SessionLocal, engine
# Register the additive remote-training tables before development/test
# ``create_all``. Production remains Alembic-only, so 0088 is still the
# authoritative schema change there.
from app.models import remote_training as _remote_training_models  # noqa: F401
from app.core.version import APP_VERSION
from app.services.seed import seed_admin, seed_demo_osgbs
from app.services.training_runtime_patches import install_training_runtime_patches
from app.services.training_document_consistency import install_training_document_consistency
from app.services.training_lifecycle_v2 import install_training_lifecycle_v2, PremiumTrainingLifecycleMiddleware
from app.services.training_lifecycle_v2_record_hooks import install_training_lifecycle_v2_record_hooks
from app.services.training_lifecycle_v2_completion import install_training_lifecycle_v2_completion
from app.services.training_lifecycle_v2_content_guards import install_training_lifecycle_v2_content_guards
from app.services.training_lifecycle_v2_validity import install_training_lifecycle_v2_validity
from app.services.training_question_selection_v2 import install_exact_nace_question_selection
from app.services.training_completion import install_training_completion_guard
from app.services.training_presentation_phase8 import install_training_presentation_phase8
from app.services.training_presentation_phase8_generation_guard import install_phase8_generation_guard
from app.services.remote_training_custom_packages import install_remote_training_custom_packages
from app.services.remote_training_package_management import install_remote_training_package_management

logger = logging.getLogger(__name__)
_training_runtime_status = install_training_runtime_patches()
_training_document_consistency_status = install_training_document_consistency()
_training_lifecycle_v2_status = install_training_lifecycle_v2()
_training_lifecycle_v2_record_status = install_training_lifecycle_v2_record_hooks()
_training_lifecycle_v2_completion_status = install_training_lifecycle_v2_completion()
_training_lifecycle_v2_content_status = install_training_lifecycle_v2_content_guards()
_training_lifecycle_v2_validity_status = install_training_lifecycle_v2_validity()
_training_question_selection_status = install_exact_nace_question_selection()
_training_completion_status = install_training_completion_guard()
_training_presentation_phase8_status = install_training_presentation_phase8()
_training_presentation_phase8_generation_status = install_phase8_generation_guard()
_remote_training_custom_packages_status = install_remote_training_custom_packages()
_remote_training_package_management_status = install_remote_training_package_management()
logger.info("training runtime patches: %s", _training_runtime_status)
logger.info("training document consistency: %s", _training_document_consistency_status)
logger.info("training premium lifecycle v2: %s", _training_lifecycle_v2_status)
logger.info("training premium lifecycle v2 record hooks: %s", _training_lifecycle_v2_record_status)
logger.info("training premium lifecycle v2 completion: %s", _training_lifecycle_v2_completion_status)
logger.info("training premium lifecycle v2 content guards: %s", _training_lifecycle_v2_content_status)
logger.info("training premium lifecycle v2 validity: %s", _training_lifecycle_v2_validity_status)
logger.info("training exact NACE question selection: %s", _training_question_selection_status)
logger.info("training completion guard: %s", _training_completion_status)
logger.info("training presentation phase 8: %s", _training_presentation_phase8_status)
logger.info("training presentation phase 8 generation guard: %s", _training_presentation_phase8_generation_status)
logger.info("remote training custom packages: %s", _remote_training_custom_packages_status)
logger.info("remote training package management: %s", _remote_training_package_management_status)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(self), microphone=(), geolocation=(self)",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        })
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_settings()
    install_request_id_logging()
    try:
        from app.services.health_field_crypto import enable_health_crypto_for_production
        logger.info("health crypto rollout: %s", enable_health_crypto_for_production())
    except Exception:
        logger.exception("health crypto rollout failed at startup")
    try:
        from app.services.backup_restore import enable_backup_crypto_for_production
        logger.info("backup crypto rollout: %s", enable_backup_crypto_for_production())
    except Exception:
        logger.exception("backup crypto rollout failed at startup")
    try:
        from app.services.object_store import maybe_auto_cutover_object_storage
        logger.info("object storage rollout: %s", maybe_auto_cutover_object_storage())
    except Exception:
        logger.exception("object storage auto-cutover failed at startup")
        if bool(getattr(settings, "object_storage_remote_required", False)):
            raise
    if bool(getattr(settings, "object_storage_video_backfill_on_startup", False)):
        try:
            from app.services.job_queue import async_jobs_enabled
            from app.services.remote_training_video_r2_backfill import (
                enqueue_remote_training_video_r2_backfill,
            )

            if not async_jobs_enabled():
                raise RuntimeError("R2 video backfill requires the async job queue.")
            record = enqueue_remote_training_video_r2_backfill()
            logger.warning("R2 video backfill queued at startup: job_id=%s", record.id)
        except Exception:
            # A backfill problem must not make the working application
            # unavailable. The local video path remains the fallback.
            logger.exception("R2 video backfill could not be queued at startup")
    _boot_env = (settings.environment or "").strip().lower()
    if _boot_env in ("production", "prod", "live"):
        logger.info("production boot: skipping create_all/schema_repair (alembic-only)")
    else:
        Base.metadata.create_all(bind=engine)
        try:
            from app.services.schema_repair import repair_schema
            repair_schema()
        except Exception:
            logger.exception("schema_repair failed at startup")
    with SessionLocal() as db:
        seed_admin(db)
        try:
            seed_demo_osgbs(db)
        except Exception:
            logger.exception("seed_demo_osgbs failed at startup")
        try:
            from sqlalchemy import func, select
            from app.models.entities import HazardCategory
            from app.services.hazard_seed import seed_hazard_library
            if (db.scalar(select(func.count()).select_from(HazardCategory)) or 0) == 0:
                seed_hazard_library(db)
        except Exception:
            logger.exception("hazard_seed failed at startup")
        try:
            from app.api.company_access import sync_all_assigned_field_roles
            sync_all_assigned_field_roles(db)
        except Exception:
            logger.exception("sync_all_assigned_field_roles failed at startup")
        try:
            from sqlalchemy import select
            from app.models.entities import Company
            from app.services.site_verify import ensure_company_site_verify_code
            missing = list(db.scalars(select(Company).where((Company.site_verify_code.is_(None)) | (Company.site_verify_code == ""))).all())
            for company in missing:
                ensure_company_site_verify_code(db, company)
            if missing:
                db.commit()
                logger.info("Backfilled site_verify_code for %s companies", len(missing))
        except Exception:
            logger.exception("site_verify_code backfill failed at startup")
    yield


_is_prod = is_production_environment(settings.environment)
app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)

from app.core.validation_tr import register_turkish_validation
register_turkish_validation(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(StructuredAccessLogMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(OsgbSubscriptionWriteMiddleware)
app.add_middleware(PremiumTrainingLifecycleMiddleware)
app.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=settings.rate_limit_rpm, auth_requests_per_minute=settings.rate_limit_auth_rpm)
_cors_origins = build_cors_origins(environment=settings.environment, frontend_origin=settings.frontend_origin)
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for router in (
    auth.router,
    osgb_applications.router,
    eisa.router,
    eisa_orphan_users.router,
    companies.router,
    branches.router,
    users.router,
    employees.router,
    personnel_profile_osgb.osgb_router,
    personnel_profile_osgb_documents.router,
    personnel_profile_osgb.profile_router,
    personnel_profiles.router,
    personnel_profile_management.router,
    isg_records.router,
    health.router,
    prescriptions.router,
    documents.router,
    annual_plans.router,
    annual_eval.router,
    reports.router,
    security.router,
    files.router,
    exports.router,
    subscriptions.router,
    notifications.router,
    system.router,
    dashboard.router,
    osgb.router,
    professional_performance_exports.router,
    operations.router,
    training_lifecycle_v2.router,
    training_premium_dashboard_v1.router,
    training_completion.router,
    trainings.router,
    remote_training.router,
    self_service.router,
    training_nace.router,
    training_presentation.router,
    training_presentation_editor.router,
    training_question_selection_audit.router,
    training_question_bank.router,
    training_question_bank.exam_router,
    risks.router,
    incidents.router,
    ppe.router,
    sds.router,
    drills.router,
    emergency_teams.router,
    archives.router,
    legal.router,
    memberships.router,
    compliance_registers.pc_router,
    compliance_registers.ep_router,
    compliance_registers.wm_router,
    committee_professional.router,
    compliance_registers.oc_router,
    compliance_registers.da_router,
    esign.router,
    esign_orch.router,
    eyas.router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    from app.services.release_status import public_health_payload
    return public_health_payload()
