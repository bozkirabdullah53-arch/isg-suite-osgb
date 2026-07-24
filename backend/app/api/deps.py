from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rls import apply_rls_user
from app.core.security import ALGORITHM
from app.core.tenant_context import bind_user_tenant
from app.models.entities import User, UserRole
from app.services.token_revoke import is_jti_revoked


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _user_from_token(token: str, db: Session, *, allowed_purposes: set[str]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Oturum doğrulanamadı.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        purpose = payload.get("purpose") or "access"
        jti = payload.get("jti")
        tv = int(payload.get("tv") or 0)
    except (JWTError, TypeError, ValueError):
        raise credentials_error

    if purpose not in allowed_purposes:
        raise credentials_error

    if jti and is_jti_revoked(db, str(jti)):
        raise credentials_error

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_error

    user_tv = int(getattr(user, "token_version", 0) or 0)
    if tv != user_tv:
        raise credentials_error

    # P1-03: istek boyunca TenantContext (osgb/firma kapsamı)
    if purpose == "access":
        bind_user_tenant(user)
        apply_rls_user(db, user.id)
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return _user_from_token(token, db, allowed_purposes={"access"})


def get_mfa_challenge_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    # Setup token ile /auth/mfa/verify üzerinden access JWT alınamaz (MFA bypass kapatıldı).
    return _user_from_token(token, db, allowed_purposes={"mfa_challenge"})


def get_mfa_setup_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return _user_from_token(token, db, allowed_purposes={"mfa_setup", "access"})


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok.")
        return user
    return dependency
