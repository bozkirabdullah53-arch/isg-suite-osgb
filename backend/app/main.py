from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import auth, branches, companies, dashboard, employees, users, isg_records, health, documents, annual_plans, annual_eval, reports, security, files, exports, subscriptions, notifications, system, osgb, operations, trainings, risks, incidents, ppe, sds, drills, emergency_teams, eisa, osgb_applications, archives, legal, memberships, compliance_registers
from app.core.rate_limit import SimpleRateLimitMiddleware
from app.core.request_id import RequestIdMiddleware, install_request_id_logging
from app.core.tenant_middleware import TenantContextMiddleware
from app.core.access_log import StructuredAccessLogMiddleware
from app.core.subscription_middleware import OsgbSubscriptionWriteMiddleware
from app.core.config import settings, validate_runtime_settings
from app.core.database import Base, SessionLocal, engine
from app.core.version import APP_VERSION
from app.services.seed import seed_admin, seed_demo_osgbs

logger = logging.getLogger(__name__)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        response=await call_next(request)
        response.headers.update({
            'X-Content-Type-Options':'nosniff',
            'X-Frame-Options':'DENY',
            'Referrer-Policy':'strict-origin-when-cross-origin',
            'Permissions-Policy':'camera=(self), microphone=(), geolocation=(self)',
            'Strict-Transport-Security':'max-age=31536000; includeSubDomains',
        })
        return response
@asynccontextmanager
async def lifespan(_:FastAPI):
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
    # Schema: production = alembic-only (start.sh). create_all/repair yalnız local/dev.
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

            missing = list(
                db.scalars(
                    select(Company).where(
                        (Company.site_verify_code.is_(None)) | (Company.site_verify_code == "")
                    )
                ).all()
            )
            for company in missing:
                ensure_company_site_verify_code(db, company)
            if missing:
                db.commit()
                logger.info("Backfilled site_verify_code for %s companies", len(missing))
        except Exception:
            logger.exception("site_verify_code backfill failed at startup")
    yield
_is_prod = (settings.environment or '').strip().lower() in {'production', 'prod', 'live'}
app=FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None if _is_prod else '/docs',
    redoc_url=None if _is_prod else '/redoc',
    openapi_url=None if _is_prod else '/openapi.json',
)

from app.core.validation_tr import register_turkish_validation
register_turkish_validation(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(StructuredAccessLogMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(OsgbSubscriptionWriteMiddleware)
app.add_middleware(
    SimpleRateLimitMiddleware,
    requests_per_minute=settings.rate_limit_rpm,
    auth_requests_per_minute=settings.rate_limit_auth_rpm,
)
_cors_origins=list(dict.fromkeys([
    settings.frontend_origin,
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'https://isg-suite-web-1u9t.onrender.com',
    'https://www.isgsuite.tr',
    'https://isgsuite.tr',
]))
app.add_middleware(CORSMiddleware,allow_origins=_cors_origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
for r in (auth.router,osgb_applications.router,eisa.router,companies.router,branches.router,users.router,employees.router,isg_records.router,health.router,documents.router,annual_plans.router,annual_eval.router,reports.router,security.router,files.router,exports.router,subscriptions.router,notifications.router,system.router,dashboard.router,osgb.router,operations.router,trainings.router,risks.router,incidents.router,ppe.router,sds.router,drills.router,emergency_teams.router,archives.router,legal.router,memberships.router,compliance_registers.pc_router,compliance_registers.ep_router,compliance_registers.wm_router,compliance_registers.oc_router,compliance_registers.da_router): app.include_router(r,prefix='/api/v1')
@app.get('/health')
def health():
    from app.services.release_status import public_health_payload
    return public_health_payload()
