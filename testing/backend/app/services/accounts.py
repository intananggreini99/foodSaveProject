"""Restoran, pengaturan awal, dan akun uji coba tanpa login."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH
from app.models import ModelVersion, Restaurant, RestaurantSettings, User

# Dipakai bila LOGIN_REQUIRED=false dan permintaan tidak membawa sesi login yang valid.
TRIAL_EMAIL = "uji-coba@foodsave.local"
TRIAL_RESTAURANT = "Restoran Uji Coba"
TRIAL_NAME = "Pengguna Uji Coba"


def initial_settings(db: Session, restaurant_id) -> RestaurantSettings:
    """Batas risiko awal mengikuti model aktif (tertil data latih) bila ada."""
    active = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    values = {}
    if active:
        values = {
            "safe_max_kg": Decimal(str(active.default_safe_max_kg)),
            "warning_max_kg": Decimal(str(active.default_warning_max_kg)),
        }
    return RestaurantSettings(restaurant_id=restaurant_id, **values)


def trial_user(db: Session) -> User:
    """Pemilik "Restoran Uji Coba", dibuat sekali saat pertama kali dibutuhkan.

    Hash password-nya tidak cocok dengan password apa pun, jadi akun ini tidak bisa
    dipakai login; hanya dipakai saat login tidak diwajibkan.
    """
    user = db.scalar(select(User).where(User.email == TRIAL_EMAIL))
    if user:
        if user.password_hash != DUMMY_HASH or user.status != "active":
            raise RuntimeError(f"Email {TRIAL_EMAIL} dipakai akun biasa; akun uji coba tidak dibuat.")
        return user
    restaurant = Restaurant(name=TRIAL_RESTAURANT)
    db.add(restaurant)
    db.flush()
    db.add(initial_settings(db, restaurant.id))
    user = User(
        restaurant_id=restaurant.id,
        name=TRIAL_NAME,
        email=TRIAL_EMAIL,
        password_hash=DUMMY_HASH,
        role="owner",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Permintaan lain membuat akun yang sama pada saat bersamaan.
        db.rollback()
        user = db.scalar(select(User).where(User.email == TRIAL_EMAIL))
    return user
