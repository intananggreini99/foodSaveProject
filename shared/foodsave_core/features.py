"""Penerjemah antara nama kolom aplikasi dan nama kolom data mentah (Kaggle).

Aplikasi memakai nama yang mudah dibaca (meals_prepared, temperature_c, ...),
sedangkan model dan file raw di HDFS memakai nama asli dataset
(meals_served, temperature_C, ...). Semua konversi lewat modul ini.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

# Kolom file raw di HDFS (/foodsave/raw). Urutan sama dengan train.csv asli,
# ditambah identitas sumber untuk data aktual hasil ekspor aplikasi.
RAW_COLUMNS = [
    "ID",
    "date",
    "meals_served",
    "kitchen_staff",
    "temperature_C",
    "humidity_percent",
    "day_of_week",
    "special_event",
    "past_waste_kg",
    "staff_experience",
    "waste_category",
    "food_waste_kg",
]
EXPORT_EXTRA_COLUMNS = ["source", "operation_id", "restaurant_ref", "exported_at"]

APP_TO_RAW = {
    "operation_date": "date",
    "meals_prepared": "meals_served",
    "kitchen_staff": "kitchen_staff",
    "temperature_c": "temperature_C",
    "humidity_percent": "humidity_percent",
    "special_event": "special_event",
    "staff_experience": "staff_experience",
    "previous_waste_kg": "past_waste_kg",
    "waste_category": "waste_category",
    "actual_waste_kg": "food_waste_kg",
}
MODEL_INPUT_FIELDS = [
    "operation_date",
    "meals_prepared",
    "kitchen_staff",
    "staff_experience",
    "special_event",
    "temperature_c",
    "humidity_percent",
]


def snapshots_to_frame(snapshots: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    """Ubah input aplikasi menjadi DataFrame dengan nama kolom raw.

    Hanya tujuh isian rencana yang diteruskan. Nilai aktual (actual_waste_kg)
    sengaja tidak disertakan agar tidak bocor ke input model.
    """
    rows = []
    for snap in snapshots:
        rows.append(
            {
                "date": str(snap["operation_date"]),
                "meals_served": int(snap["meals_prepared"]),
                "kitchen_staff": int(snap["kitchen_staff"]),
                "staff_experience": str(snap["staff_experience"]),
                "special_event": int(bool(snap["special_event"])),
                "temperature_C": float(snap["temperature_c"]),
                "humidity_percent": float(snap["humidity_percent"]),
            }
        )
    return pd.DataFrame(rows)


def operation_to_raw_row(op: Mapping[str, Any]) -> dict[str, Any]:
    """Satu baris daily_operations menjadi satu baris format raw HDFS."""
    op_date = op["operation_date"]
    if isinstance(op_date, str):
        op_date = date.fromisoformat(op_date)
    return {
        "ID": "",
        "date": op_date.isoformat(),
        "meals_served": op["meals_prepared"],
        "kitchen_staff": op["kitchen_staff"],
        "temperature_C": float(op["temperature_c"]),
        "humidity_percent": float(op["humidity_percent"]),
        "day_of_week": op_date.weekday(),
        "special_event": int(bool(op["special_event"])),
        "past_waste_kg": (
            float(op["previous_waste_kg"]) if op.get("previous_waste_kg") is not None else ""
        ),
        "staff_experience": op["staff_experience"],
        "waste_category": op.get("waste_category") or "",
        "food_waste_kg": float(op["actual_waste_kg"]),
    }
