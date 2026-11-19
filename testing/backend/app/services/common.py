"""Fungsi bersama: serialisasi, isolasi restoran, pengaturan, dan file aplikasi."""

from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, select

from app.core.config import get_settings
from app.models import RestaurantSettings
from app.schemas import DailyInput
from foodsave_core.storage import LocalStorage, Storage, WebHDFSStorage

HIDDEN = {"password_hash", "token_hash", "storage_key"}


def serialize(row, exclude=()):
    denied = {*HIDDEN, *exclude}
    return jsonable_encoder(
        {c.key: getattr(row, c.key) for c in inspect(row).mapper.column_attrs if c.key not in denied}
    )


def owned(db, model, identity, user, lock=False):
    """Ambil baris milik restoran pengguna; restoran lain mendapat 404."""
    statement = select(model).where(model.id == identity, model.restaurant_id == user.restaurant_id)
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if not row:
        raise HTTPException(404, "Data tidak ditemukan.")
    return row


def restaurant_settings(db, user) -> RestaurantSettings:
    result = db.get(RestaurantSettings, user.restaurant_id)
    if not result:
        raise HTTPException(409, "Pengaturan restoran belum dibuat.")
    return result


def ensure_capacity(body, settings):
    if body.meals_prepared > settings.max_portions:
        raise HTTPException(422, "Jumlah porsi melebihi kapasitas pada pengaturan restoran.")


def daily_snapshot(operation) -> dict:
    return DailyInput.model_validate(
        {name: getattr(operation, name) for name in DailyInput.model_fields}
    ).model_dump(mode="json")


def app_file(key: str) -> Path:
    """File unggahan dan laporan operasional di folder aplikasi (bukan HDFS)."""
    root = get_settings().app_storage_path.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(404, "File tidak ditemukan.")
    return path


@lru_cache
def model_storage() -> Storage:
    """Penyimpanan model dan laporan evaluasi (HDFS di Docker)."""
    settings = get_settings()
    if settings.foodsave_storage == "hdfs":
        return WebHDFSStorage(settings.hdfs_namenode_url, settings.hdfs_user)
    return LocalStorage(settings.local_storage_root)
