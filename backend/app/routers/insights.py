"""Halaman Insight & Penyebab (bagian data operasional restoran).

Faktor berpengaruh, perbandingan model, dan kurva kepekaan berasal dari skema
model_analysis (lihat routers/model.py). Router ini hanya mengagregasi data
operasional restoran sendiri.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.deps import CurrentUser, Db
from app.models import DailyOperation

router = APIRouter(prefix="/insights", tags=["Insight operasional"])
LOAD_GROUPS = [(0, 20, "ringan (<20 porsi/staf)"), (20, 35, "sedang (20-35)"),
               (35, 10**9, "berat (>35)")]


@router.get("/operational")
def operational(db: Db, user: CurrentUser, starts_on: date, ends_on: date):
    if ends_on < starts_on:
        raise HTTPException(422, "Tanggal akhir harus setelah tanggal mulai.")
    rows = db.scalars(
        select(DailyOperation).where(
            DailyOperation.restaurant_id == user.restaurant_id,
            DailyOperation.operation_date.between(starts_on, ends_on),
        )
    ).all()
    groups = []
    for low, high, label in LOAD_GROUPS:
        members = [r for r in rows if low <= r.meals_prepared / r.kitchen_staff < high]
        actuals = [r.actual_waste_kg for r in members if r.actual_waste_kg is not None]
        groups.append(
            {
                "group": label,
                "operation_count": len(members),
                "actual_recorded_count": len(actuals),
                "average_actual_waste_kg": (sum(actuals, Decimal(0)) / len(actuals)).quantize(
                    Decimal(".0001")
                )
                if actuals
                else None,
            }
        )
    categories = db.execute(
        select(
            DailyOperation.waste_category,
            func.count(),
            func.sum(DailyOperation.actual_waste_kg),
        )
        .where(
            DailyOperation.restaurant_id == user.restaurant_id,
            DailyOperation.operation_date.between(starts_on, ends_on),
        )
        .group_by(DailyOperation.waste_category)
        .order_by(func.sum(DailyOperation.actual_waste_kg).desc().nulls_last())
    ).all()
    return {
        "starts_on": starts_on,
        "ends_on": ends_on,
        "staff_load": groups,
        "categories": [
            {"category": c or "tanpa kategori", "operation_count": n, "actual_waste_kg": kg}
            for c, n, kg in categories
        ],
        "note": "Kategori limbah tidak dipakai model; hanya untuk analisis operasional.",
    }
