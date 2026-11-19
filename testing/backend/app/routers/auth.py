"""Akun dan sesi: daftar, login, logout, profil, sesi aktif, tambah pengguna."""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, Db, session_for
from app.core.security import (
    COOKIE,
    DUMMY_HASH,
    new_token,
    now,
    password_hash,
    token_digest,
    verify_password,
)
from app.models import Restaurant, User, UserSession
from app.schemas import Credentials, ProfileUpdate, Register, UserCreate
from app.services.accounts import TRIAL_EMAIL, initial_settings

router = APIRouter(prefix="/auth", tags=["Akun dan sesi"])


def public_user(user: User) -> dict:
    return {
        "id": user.id,
        "restaurant_id": user.restaurant_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "last_login_at": user.last_login_at,
        "notification_preferences": user.notification_preferences,
    }


def start_session(user, request, response, db):
    token = new_token()
    settings = get_settings()
    db.add(
        UserSession(
            restaurant_id=user.restaurant_id,
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=now() + timedelta(days=settings.session_days),
            user_agent=request.headers.get("user-agent", "")[:500],
        )
    )
    user.last_login_at = now()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_days * 86400,
        path="/",
    )


@router.post("/register", status_code=201)
def register(body: Register, request: Request, response: Response, db: Db):
    if not get_settings().registration_enabled:
        raise HTTPException(403, "Pendaftaran mandiri dinonaktifkan.")
    if body.email == TRIAL_EMAIL or db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Email sudah terdaftar.")
    restaurant = Restaurant(name=body.restaurant_name)
    db.add(restaurant)
    db.flush()
    db.add(initial_settings(db, restaurant.id))
    user = User(
        restaurant_id=restaurant.id,
        name=body.name,
        email=body.email,
        password_hash=password_hash(body.password),
        role="owner",
    )
    db.add(user)
    db.flush()
    start_session(user, request, response, db)
    db.commit()
    return public_user(user)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: Db):
    user = db.scalar(select(User).where(User.email == body.email))
    # Hashing tetap dilakukan saat email tidak ada, agar waktu respons serupa.
    stored = user.password_hash if user else DUMMY_HASH
    if not verify_password(body.password, stored) or not user or user.status != "active":
        raise HTTPException(401, "Email atau password tidak sesuai.")
    start_session(user, request, response, db)
    db.commit()
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db, user: CurrentUser):
    session_for(request, db).revoked_at = now()
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.get("/me")
def me(user: CurrentUser):
    return public_user(user)


@router.put("/me")
def update_me(body: ProfileUpdate, db: Db, user: CurrentUser):
    user.name = body.name
    user.notification_preferences = body.notification_preferences
    db.commit()
    return public_user(user)


@router.get("/sessions")
def sessions(db: Db, user: CurrentUser):
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.restaurant_id == user.restaurant_id)
        .order_by(UserSession.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "revoked_at": s.revoked_at,
            "user_agent": s.user_agent,
        }
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: UUID, db: Db, user: CurrentUser):
    session = db.scalar(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
            UserSession.restaurant_id == user.restaurant_id,
        )
    )
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan.")
    session.revoked_at = now()
    db.commit()


@router.post("/users", status_code=201)
def create_user(body: UserCreate, db: Db, user: CurrentUser):
    if user.role != "owner":
        raise HTTPException(403, "Hanya pemilik restoran yang dapat menambahkan akun.")
    if body.email == TRIAL_EMAIL or db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Email sudah terdaftar.")
    created = User(
        restaurant_id=user.restaurant_id,
        name=body.name,
        email=body.email,
        password_hash=password_hash(body.password),
        role=body.role,
    )
    db.add(created)
    db.commit()
    return public_user(created)
