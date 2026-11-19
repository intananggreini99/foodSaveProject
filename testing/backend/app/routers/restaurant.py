"""Halaman Pengaturan: restoran, pengguna, dan pengaturan risiko/biaya."""

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, Db, Manager
from app.models import Restaurant, User
from app.routers.auth import public_user
from app.schemas import RestaurantUpdate, SettingsUpdate
from app.services.common import restaurant_settings, serialize

router = APIRouter(tags=["Pengaturan restoran"])


@router.get("/restaurant")
def restaurant(db: Db, user: CurrentUser):
    return serialize(db.get(Restaurant, user.restaurant_id))


@router.put("/restaurant")
def update_restaurant(body: RestaurantUpdate, db: Db, user: Manager):
    row = db.get(Restaurant, user.restaurant_id)
    row.name = body.name
    db.commit()
    return serialize(row)


@router.get("/users")
def users(db: Db, user: Manager):
    rows = db.scalars(select(User).where(User.restaurant_id == user.restaurant_id)).all()
    return [public_user(row) for row in rows]


@router.get("/settings")
def settings(db: Db, user: CurrentUser):
    return serialize(restaurant_settings(db, user))


@router.put("/settings")
def update_settings(body: SettingsUpdate, db: Db, user: Manager):
    row = restaurant_settings(db, user)
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    db.commit()
    return serialize(row)
