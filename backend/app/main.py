from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import auth, branches, companies, dashboard, employees, users, isg_records, health, documents, annual_plans, annual_eval, reports, security, files, exports, subscriptions, notifications, system, osgb, operations, trainings, risks, incidents, ppe, sds, drills, emergency_teams, eisa, osgb_applications, archives, legal, memberships
from app.core.rate_limit import SimpleRateLimitMiddleware, rate_limit_backend
from app.core.request_id import RequestIdMiddleware
from app.core.tenant_middleware import TenantContextMiddleware
from app.core.access_log import StructuredAccessLogMiddleware
from app.core.subscription_middleware import OsgbSubscriptionWriteMiddleware
from app.core.config import settings, validate_runtime_settings
from app.core.database import Base, SessionLocal, engine
from app.core.version import APP_VERSION
from app.core.auth_cookies import refresh_cookie_enabled
from app.services.job_queue import job_backend_label
from app.services.seed import seed_admin, seed_demo_osgbs
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
    # Schema parity: alembic upgrade head (start.sh). create_all for fresh local SQLite only.
    Base.metadata.create_all(bind=engine)
    try:
        from app.services.schema_repair import repair_schema

        repair_schema()
    except Exception:
        pass
    with SessionLocal() as db:
        seed_admin(db)
        try:
            seed_demo_osgbs(db)
        except Exception:
            pass
        try:
            from sqlalchemy import func, select
            from app.models.entities import HazardCategory
            from app.services.hazard_seed import seed_hazard_library
            if (db.scalar(select(func.count()).select_from(HazardCategory)) or 0) == 0:
                seed_hazard_library(db)
        except Exception:
            pass
        try:
            from app.api.company_access import sync_all_assigned_field_roles
            sync_all_assigned_field_roles(db)
        except Exception:
            pass
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
for r in (auth.router,osgb_applications.router,eisa.router,companies.router,branches.router,users.router,employees.router,isg_records.router,health.router,documents.router,annual_plans.router,annual_eval.router,reports.router,security.router,files.router,exports.router,subscriptions.router,notifications.router,system.router,dashboard.router,osgb.router,operations.router,trainings.router,risks.router,incidents.router,ppe.router,sds.router,drills.router,emergency_teams.router,archives.router,legal.router,memberships.router): app.include_router(r,prefix='/api/v1')
@app.get('/health')
def health():
    import os
    from app.services.clamav_scan import is_clamav_configured
    from app.services.object_store import storage_backend_label
    return {
        'status': 'ok',
        'service': settings.app_name,
        'version': APP_VERSION,
        'environment': (settings.environment or 'development').strip().lower() or 'development',
        'object_storage': storage_backend_label(),
        'upload_gateway': 'on' if settings.upload_gateway_enabled else 'off',
        'upload_gateway_wired': 'full-modules-v1',
        'health_field_encryption': 'on' if settings.health_field_encryption_enabled else 'off',
        'ai_hazard_hint': 'keyword-v2',
        'mevzuat_panel': 'highlights-v1',
        'sds_register': 'chemical-register-v1',
        'ghs_label_checklist': 'ghs-label-checklist-v1',
        'risk_photo_tags': 'checklist-v1',
        'sds_review_reminders': 'duty-notify-v1',
        'osgb_mevzuat_link': 'dashboard-v1',
        'osgb_sds_due': 'dashboard-v1',
        'integration_readiness': 'checklist-v1',
        'integrations_adapter': 'stub-clients-v1',
        'integrations_dry_run': 'log-v1',
        'integrations_probe': 'live-check-v1',
        'integrations_live_send': 'live-post-v1',
        'tatbikat': 'drill-management-v1',
        'acil_ekipler': 'emergency-teams-v1',
        'annual_eval_report': 'annual-eval-v7',
        'osgb_trial': 'settings-v1',
        'crm_convert': 'lead-to-contract-v1',
        'contracts_ui': 'osgb-monitor-v1',
        'contracts_actions': 'end-suspend-v1',
        'finance_status': 'patch-paid-v1',
        'crm_finance_link': 'company-filter-v1',
        'finance_accrual': 'monthly-v1',
        'finance_overdue_alert': 'dashboard-v2',
        'crm_stage_filters': 'won-lost-v1',
        'pdf_layout': 'pro-2026',
        'companies_admin': 'osgb-admin-crud-v1',
        'company_fields': 'address-phone-contact-v1',
        'professional_login': 'email-temp-password-v1',
        'creds_copy': 'clipboard-v1',
        'duty_dashboard_import': 'fixed-v1',
        'duty_home': 'done-missing-report-v1',
        'annual_plans': 'generate-wake-retry',
        'annual_plan_export': 'xlsx-v1',
        'annual_plan_status': 'varchar-enum-fix-v1',
        'annual_plan_holidays': 'tr-workday-shift-v2',
        'osgb_performance': 'company-admin-restored-v1',
        'oversight_score': 'no-vacuous-pass-v2',
        'health_roles': 'company-admin-monitor-v1',
        'validation_tr': 'turkish-422-v1',
        'input_rules': 'date-text-sanity-v2',
        'osgb_menu': 'no-field-modules-v1',
        'demo_osgb_seed': 'alfa-beta-v1',
        'training_verify_code': 'uuid-unique',
        'upload_security': 'magic-byte-quarantine',
        'clamav_scan': 'enabled' if is_clamav_configured() else 'disabled',
        'ga_osgb_fallback': 'user-or-first-active',
        'schema_bootstrap': 'alembic-only-v1',
        'render_warmup': 'cron-14m',
        'eisa_platform': 'eisa-error-reports-v1',
        'security_faz0': 'mfa-reset-lock-logout-revoke-v1',
        'token_revoke': 'jti-denylist-tv-v1',
        'request_id': 'x-request-id-v1',
        'logout_all': 'token-version-v1',
        'company_name_unique': 'osgb-scoped-v1',
        'ci_postgres': 'workflow-v1-migrate-parity',
        'tenant_context': 'contextvar-wired-v1',
        'auth_refresh_cookie': 'on' if refresh_cookie_enabled() else 'off',
        'auth_refresh_rollout': 'prod-on-samesite-none-v2',
        'assignment_unique': 'active-partial-v2',
        'access_log': 'json-request-id-v1',
        'async_jobs': 'on' if settings.async_jobs_enabled else 'off-sync-fallback',
        'job_backend': job_backend_label(),
        'release_manifest': 'single-version-v1',
        'legal_consent': 'cms-ui-v2',
        'memberships': 'admin-api-ui-v1',
        'frontend_tests': 'vitest-eslint-pw-smoke-v1',
        'rls_pilot': 'legal-memberships-docs-health-v3',
        'access_ttl': 'short-when-refresh-cookie',
        'customer_360': 'company-overview-v1',
        'capacity_engine': '6331-legal-minutes-v1',
        'visit_calendar': 'plan-overdue-coverage-v1',
        'module_kpis': 'risk-training-health-v1',
        'field_gps': 'visit-complete-stamp-v1',
        'field_qr': 'workplace-ephemeral-v1',
        'field_signature': 'visit-sign-offline-v1',
        'tenant_isolation': 'osgb-scoped-v1',
        'central_archive': 'tenant-backup-restore-plan-v1',
        'backup_restore': 'off' if not settings.backup_restore_enabled else 'on',
        'users_delete': 'reassign-fk-refs',
        'assignment_actions': 'end-suspend-delete',
        'companies_actions': 'deactivate-activate-hard-delete',
        'companies_sgk': 'required-on-create',
        'health': 'field-crypto-ready-v1',
        'osgb_oversight': '6331-eval-error-detail',
        'assignment_form': 'katip-contract-upload',
        'katip_prep': 'missing-contract-v1',
        'ibys_export': 'csv-package-v1',
        'visit_notebook': 'tespit-oneri-defteri',
        'visit_crud': 'field-edit-delete',
        'visit_access': 'field-own-visits-list',
        'role_sync': 'assignment-bulk-field-menus',
        'training_excel': 'resilient-import',
        'access_boundary': 'global-reports-field-isolation',
        'users_admin': 'suspend-delete',
        'professionals_admin': 'edit-search-assign-perf',
        'training_osgb_access': 'assignment-scoped',
        'duty_board': 'resilient-my-duties',
        'osgb_menu': 'global-monitor-no-docs',
        'osgb_home': 'workplaces-pros-unassigned-contracts',
        'osgb_home_kpis': 'finance-contracts-sds-v3',
        'csgb_pack': 'audit-bundle-v3',
        'csgb_company_snapshot': 'read-only-v1',
        'pro_performance_export': 'csv-v1',
        'notifications': 'osgb-deadline-eval-v2',
        'rate_limit': f'rpm-{settings.rate_limit_rpm}-auth-{settings.rate_limit_auth_rpm}-xff-{rate_limit_backend()}',
        'secret_key_guard': 'prod-block-default',
        'nav_hardening': 'allowlist-boundary-mobile',
        'field_access': 'assignment-scoped-v2',
        'git': os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or 'local',
    }
