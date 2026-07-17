from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import auth, branches, companies, dashboard, employees, users, isg_records, health, documents, annual_plans, reports, security, files, exports, subscriptions, notifications, system, osgb, operations
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
    with SessionLocal() as db: seed_admin(db)
    yield
app=FastAPI(title=settings.app_name,version='0.9.0',lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_origin],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
for r in (auth.router,companies.router,branches.router,users.router,employees.router,isg_records.router,health.router,documents.router,annual_plans.router,reports.router,security.router,files.router,exports.router,subscriptions.router,notifications.router,system.router,dashboard.router,osgb.router,operations.router): app.include_router(r,prefix='/api/v1')
@app.get('/health')
def health(): return {'status':'ok','service':settings.app_name,'version':'0.9.0'}
