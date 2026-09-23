"""DÖF action access: assigned professionals and fixed workplace accounts."""
from fastapi import Depends, HTTPException

from app.api.deps import get_current_user
from app.models.entities import User, UserRole


def require_dof_editor(user: User = Depends(get_current_user)) -> User:
    if user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN}:
        return user
    if user.role == UserRole.COMPANY_ADMIN and user.company_id:
        return user
    raise HTTPException(403, "Bu hesap DÖF kayıtlarını yalnızca görüntüleyebilir.")
