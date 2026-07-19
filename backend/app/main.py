from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import auth, branches, companies, dashboard, employees, users, isg_records, health, documents, annual_plans, reports, security, files, exports, subscriptions, notifications, system, osgb, operations, trainings, risks, incidents, ppe
from app.core.rate_limit import SimpleRateLimitMiddleware
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.services.seed import seed_admin
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        response=await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()'})
        return response
@asynccontextmanager
async def lifespan(_:FastAPI):
    Base.metadata.create_all(bind=engine)
    # Mevcut DB'ye yeni kolon (create_all mevcut tabloyu değiştirmez)
    try:
        from sqlalchemy import inspect, text
        insp = inspect(engine)
        if "risk_assessments" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("risk_assessments")}
            if "department_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE risk_assessments ADD COLUMN department_id INTEGER"))
        if "training_sessions" in insp.get_table_names():
            tcols = {c["name"] for c in insp.get_columns("training_sessions")}
            alters = []
            for col, sqltype in (
                ("workplace_physician", "VARCHAR(160)"),
                ("employer_representative", "VARCHAR(160)"),
                ("logo_path", "VARCHAR(500)"),
                ("stamp_text", "VARCHAR(400)"),
            ):
                if col not in tcols:
                    alters.append(f"ALTER TABLE training_sessions ADD COLUMN {col} {sqltype}")
            if "stamp_text" in tcols:
                alters.append("ALTER TABLE training_sessions ALTER COLUMN stamp_text TYPE VARCHAR(400)")
            if alters:
                with engine.begin() as conn:
                    for stmt in alters:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
        if "annual_plan_items" in insp.get_table_names():
            ap_cols = {c["name"] for c in insp.get_columns("annual_plan_items")}
            ap_alters = []
            for col, sqltype in (
                ("category", "VARCHAR(40)"),
                ("description", "VARCHAR(2000)"),
                ("target_date", "DATE"),
                ("deleted_at", "TIMESTAMP"),
            ):
                if col not in ap_cols:
                    ap_alters.append(f"ALTER TABLE annual_plan_items ADD COLUMN {col} {sqltype}")
            if ap_alters:
                with engine.begin() as conn:
                    for stmt in ap_alters:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TYPE annualplanstatus ADD VALUE IF NOT EXISTS 'cancelled'"))
            except Exception:
                pass
        if "health_records" in insp.get_table_names():
            hr_cols = {c["name"] for c in insp.get_columns("health_records")}
            hr_alters = []
            for col, sqltype in (
                ("audiometry_date", "DATE"),
                ("audiometry_result", "VARCHAR(240)"),
                ("spirometry_date", "DATE"),
                ("spirometry_result", "VARCHAR(240)"),
                ("chest_xray_date", "DATE"),
                ("chest_xray_result", "VARCHAR(240)"),
                ("blood_lead_date", "DATE"),
                ("blood_lead_value", "DOUBLE PRECISION"),
                ("blood_lead_unit", "VARCHAR(20)"),
                ("blood_lead_ref", "DOUBLE PRECISION"),
                ("blood_lead_eval", "VARCHAR(40)"),
                ("suggested_tests", "VARCHAR(1000)"),
                ("exposures", "VARCHAR(1000)"),
                ("follow_up_note", "VARCHAR(1500)"),
                ("other_biological_test", "VARCHAR(1000)"),
                ("report_file_name", "VARCHAR(255)"),
                ("report_storage_path", "VARCHAR(500)"),
                ("report_content_type", "VARCHAR(120)"),
                ("deleted_at", "TIMESTAMP"),
            ):
                if col not in hr_cols:
                    hr_alters.append(f"ALTER TABLE health_records ADD COLUMN {col} {sqltype}")
            if hr_alters:
                with engine.begin() as conn:
                    for stmt in hr_alters:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
            for enum_name, values in (
                ("healthrecordtype", ("return_exam", "job_change", "night_work", "heavy_hazardous", "other")),
                ("healthfitnessstatus", ("fit", "conditional", "tracking", "unfit", "pending")),
            ):
                for val in values:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{val}'"))
                    except Exception:
                        pass
        if "workplace_assignments" in insp.get_table_names():
            wa_cols = {c["name"] for c in insp.get_columns("workplace_assignments")}
            wa_alters = []
            for col, sqltype in (
                ("contract_file_name", "VARCHAR(255)"),
                ("contract_storage_path", "VARCHAR(500)"),
                ("contract_content_type", "VARCHAR(120)"),
            ):
                if col not in wa_cols:
                    wa_alters.append(f"ALTER TABLE workplace_assignments ADD COLUMN {col} {sqltype}")
            if wa_alters:
                with engine.begin() as conn:
                    for stmt in wa_alters:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
        if "service_visits" in insp.get_table_names():
            sv_cols = {c["name"] for c in insp.get_columns("service_visits")}
            sv_alters = []
            for col, sqltype in (
                ("notebook_file_name", "VARCHAR(255)"),
                ("notebook_storage_path", "VARCHAR(500)"),
                ("notebook_content_type", "VARCHAR(120)"),
            ):
                if col not in sv_cols:
                    sv_alters.append(f"ALTER TABLE service_visits ADD COLUMN {col} {sqltype}")
            if sv_alters:
                with engine.begin() as conn:
                    for stmt in sv_alters:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
    except Exception:
        pass
    with SessionLocal() as db:
        seed_admin(db)
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
app=FastAPI(title=settings.app_name,version='0.9.51',lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
_cors_origins=list(dict.fromkeys([
    settings.frontend_origin,
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'https://isg-suite-web-1u9t.onrender.com',
    'https://www.isgsuite.tr',
    'https://isgsuite.tr',
]))
app.add_middleware(CORSMiddleware,allow_origins=_cors_origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
for r in (auth.router,companies.router,branches.router,users.router,employees.router,isg_records.router,health.router,documents.router,annual_plans.router,reports.router,security.router,files.router,exports.router,subscriptions.router,notifications.router,system.router,dashboard.router,osgb.router,operations.router,trainings.router,risks.router,incidents.router,ppe.router): app.include_router(r,prefix='/api/v1')
@app.get('/health')
def health():
    import os
    return {
        'status': 'ok',
        'service': settings.app_name,
        'version': '0.9.51',
        'pdf_layout': 'pro-2026',
        'annual_plans': 'generate-wake-retry',
        'users_delete': 'reassign-fk-refs',
        'assignment_actions': 'end-suspend-delete',
        'companies_actions': 'deactivate-activate-hard-delete',
        'companies_sgk': 'required-on-create',
        'health': 'pro-saglik-hekim-personel-sec',
        'osgb_oversight': '6331-eval-error-detail',
        'assignment_form': 'katip-contract-upload',
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
        'csgb_pack': 'zero-ops-zero-ready',
        'nav_hardening': 'allowlist-boundary-mobile',
        'field_access': 'assignment-scoped-v2',
        'git': os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GIT_COMMIT') or 'local',
    }
