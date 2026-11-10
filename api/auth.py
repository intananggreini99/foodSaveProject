"""Password di-hash scrypt; token sesi hanya disimpan sebagai SHA-256."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from api.config import get_settings
from api.database import get_db
from api.models import Restaurant, RestaurantSettings, User, UserSession
from api.schemas import Credentials, ProfileUpdate, Register, UserCreate

router = APIRouter(prefix="/auth", tags=["Akun dan sesi"])
Db = Annotated[Session, Depends(get_db)]
COOKIE = "foodsave_session"


def now():
    return datetime.now(timezone.utc)


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password, stored):
    try:
        scheme, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        candidate = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def public_user(user):
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


def token_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def session_for(request, db):
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


def current_user(request: Request, db: Db):
    session = session_for(request, db)
    user = db.get(User, session.user_id)
    if not user or user.status != "active" or user.restaurant_id != session.restaurant_id:
        raise HTTPException(401, "Akun tidak aktif.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def manager(user: CurrentUser):
    if user.role not in ["owner", "manager"]:
        raise HTTPException(403, "Tindakan ini memerlukan peran manager.")
    return user


Manager = Annotated[User, Depends(manager)]


def start_session(user, request, response, db):
    token = secrets.token_urlsafe(32)
    expires = now() + timedelta(days=get_settings().session_days)
    db.add(
        UserSession(
            restaurant_id=user.restaurant_id,
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=expires,
            user_agent=request.headers.get("user-agent", "")[:500],
        )
    )
    user.last_login_at = now()
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        max_age=get_settings().session_days * 86400,
        path="/",
    )


@router.post("/register", status_code=201)
def register(body: Register, request: Request, response: Response, db: Db):
    if not get_settings().registration_enabled:
        raise HTTPException(403, "Pendaftaran mandiri dinonaktifkan.")
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, "Email sudah terdaftar.")
    restaurant = Restaurant(name=body.restaurant_name)
    db.add(restaurant)
    db.flush()
    db.add(RestaurantSettings(restaurant_id=restaurant.id))
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
    # Tetap lakukan hashing saat email tidak ditemukan untuk mengurangi perbedaan waktu.
    stored = user.password_hash if user else "scrypt$" + "00" * 16 + "$" + "00" * 64
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
def revoke_session(session_id: str, db: Db, user: CurrentUser):
    from uuid import UUID

    try:
        identity = UUID(session_id)
    except ValueError:
        raise HTTPException(404, "Sesi tidak ditemukan.")
    session = db.scalar(
        select(UserSession).where(
            UserSession.id == identity,
            UserSession.user_id == user.id,
            UserSession.restaurant_id == user.restaurant_id,
        )
    )
    if not session:
        raise HTTPException(404, "Sesi tidak ditemukan.")
    session.revoked_at = now()
    db.commit()


@router.post("/users", status_code=201)
def create_manager(body: UserCreate, db: Db, user: CurrentUser):
    if user.role != "owner":
        raise HTTPException(403, "Hanya pemilik restoran yang dapat menambahkan akun.")
    if db.scalar(select(User.id).where(User.email == body.email)):
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
