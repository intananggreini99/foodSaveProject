"""Dependensi FastAPI: sesi database, pengguna login, dan peran."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import COOKIE, now, token_digest
from app.models import User, UserSession

Db = Annotated[Session, Depends(get_db)]


def session_for(request: Request, db: Session) -> UserSession:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Silakan login terlebih dahulu.")
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_digest(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now(),
        )
    )
    if not session:
        raise HTTPException(401, "Sesi berakhir. Silakan login kembali.")
    return session


def current_user(request: Request, db: Db) -> User:
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
