from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import auth, branches, companies, dashboard, employees, users, isg_records, health, documents, annual_plans, reports, security, files, exports, subscriptions, notifications, system, osgb, operations, trainings, risks
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
    yield
app=FastAPI(title=settings.app_name,version='0.9.0',lifespan=lifespan)
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
for r in (auth.router,companies.router,branches.router,users.router,employees.router,isg_records.router,health.router,documents.router,annual_plans.router,reports.router,security.router,files.router,exports.router,subscriptions.router,notifications.router,system.router,dashboard.router,osgb.router,operations.router,trainings.router,risks.router): app.include_router(r,prefix='/api/v1')
@app.get('/health')
def health(): return {'status':'ok','service':settings.app_name,'version':'0.9.0'}
