"""Dependensi FastAPI: sesi database, pengguna login, dan peran.

Bila LOGIN_REQUIRED=false, permintaan tanpa sesi login yang valid memakai akun uji coba
bawaan (lihat app.services.accounts). Sesi login yang valid tetap diutamakan.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import COOKIE, now, token_digest
from app.models import User, UserSession
from app.services.accounts import trial_user

Db = Annotated[Session, Depends(get_db)]


def find_session(request: Request, db: Session) -> UserSession | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now(),
        )
    )


def session_for(request: Request, db: Session) -> UserSession:
    session = find_session(request, db)
    if session:
        return session
    if not request.cookies.get(COOKIE):
        raise HTTPException(401, "Silakan login terlebih dahulu.")
    raise HTTPException(401, "Sesi berakhir. Silakan login kembali.")


def current_user(request: Request, db: Db) -> User:
    if not get_settings().login_required and find_session(request, db) is None:
        return trial_user(db)
    session = session_for(request, db)
    user = db.get(User, session.user_id)
    if not user or user.status != "active" or user.restaurant_id != session.restaurant_id:
        raise HTTPException(401, "Akun tidak aktif.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def manager(user: CurrentUser) -> User:
    if user.role not in ("owner", "manager"):
        raise HTTPException(403, "Tindakan ini memerlukan peran pemilik atau manager.")
    return user


Manager = Annotated[User, Depends(manager)]


def owner(user: CurrentUser) -> User:
    if user.role != "owner":
        raise HTTPException(403, "Tindakan ini hanya untuk pemilik restoran.")
    return user


Owner = Annotated[User, Depends(owner)]
