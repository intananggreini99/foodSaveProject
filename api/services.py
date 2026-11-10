"""Logika bersama: isolasi restoran, audit, dan inferensi model terpilih."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from decimal import Decimal
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, select
from api.config import ROOT, get_settings
from api.models import ModelVersion, Notification, PredictionResult, RestaurantSettings, User
from api.schemas import DailyInput


def serialize(row, exclude=()):
    denied = {"password_hash", "token_hash", "storage_key", *exclude}
    return jsonable_encoder(
        {
            c.key: getattr(row, c.key)
            for c in inspect(row).mapper.column_attrs
            if c.key not in denied
        }
    )


def owned(db, model, identity, user, lock=False):
    statement = select(model).where(model.id == identity, model.restaurant_id == user.restaurant_id)
    if lock:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if not row:
        raise HTTPException(404, "Data tidak ditemukan.")
    return row


def restaurant_settings(db, user):
    result = db.get(RestaurantSettings, user.restaurant_id)
    if not result:
        raise HTTPException(409, "Pengaturan restoran belum dibuat.")
    return result


def ensure_capacity(body, settings):
    if body.meals_prepared > settings.max_portions:
        raise HTTPException(422, "Jumlah porsi melebihi kapasitas pada pengaturan restoran.")


def daily_snapshot(operation):
    return DailyInput.model_validate(
        {name: getattr(operation, name) for name in DailyInput.model_fields}
    ).model_dump(mode="json")


def artifact_path(relative):
    path = (ROOT / Path(str(relative).replace("\\", "/"))).resolve()
    if not path.is_relative_to((ROOT / "models").resolve()):
        raise ValueError("Artefak model harus berada di folder models.")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_selected_model(db):
    """Registrasi dari file server tepercaya; tidak menerima file pickle pengguna."""
    manifest_path = get_settings().model_manifest
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_path = artifact_path(manifest["model_path"])
    prep_path = artifact_path(manifest["preprocessing_path"])
    model_hash, prep_hash = digest(model_path), digest(prep_path)
    key = f"{manifest['model']}_{manifest['preprocessing']}_{model_hash[:16]}_{prep_hash[:16]}"
    existing = db.scalar(select(ModelVersion).where(ModelVersion.version_key == key))
    for old in db.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))).all():
        old.is_active = False
    db.flush()  # Lepaskan unique active index sebelum mengaktifkan versi lain.
    if existing:
        existing.is_active = True
        db.flush()
        return existing
    model = ModelVersion(
        version_key=key,
        name=manifest["model"],
        preprocessing=manifest["preprocessing"],
        artifact_path=str(model_path.relative_to(ROOT)).replace("\\", "/"),
        preprocessing_path=str(prep_path.relative_to(ROOT)).replace("\\", "/"),
        artifact_sha256=model_hash,
        preprocessing_sha256=prep_hash,
        metrics=manifest,
        input_features=[
            "operation_date",
            "meals_prepared",
            "kitchen_staff",
            "staff_experience",
            "special_event",
            "temperature_c",
            "humidity_percent",
        ],
    )
    db.add(model)
    db.flush()
    return model


def register_experiment_catalog(db):
    """Simpan metrik delapan eksperimen, tanpa memuat model nonaktif ke memori."""
    import csv

    path = ROOT / "results/evaluation/experiment_results.csv"
    if not path.exists():
        return 0
    added = 0
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            name, method = row["model"], row["preprocessing"]
            if name not in {"RandomForest", "LSTM", "XGBoost", "CatBoost"} or method not in {
                "standard",
                "robust",
            }:
                raise ValueError("Nama eksperimen tidak dikenal.")
            label = f"{name}_{method}"
            relative = f"models/best_model/{label}" + (".keras" if name == "LSTM" else ".joblib")
            prep_relative = f"models/best_model/{label}_preprocessing.joblib"
            model_hash, prep_hash = digest(artifact_path(relative)), digest(
                artifact_path(prep_relative)
            )
            key = f"{label}_{model_hash[:16]}_{prep_hash[:16]}"
            if db.scalar(select(ModelVersion.id).where(ModelVersion.version_key == key)):
                continue
            metrics = {}
            for field, value in row.items():
                try:
                    metrics[field] = float(value)
                except (ValueError, TypeError):
                    metrics[field] = value
            db.add(
                ModelVersion(
                    version_key=key,
                    name=name,
                    preprocessing=method,
                    artifact_path=relative,
                    preprocessing_path=prep_relative,
                    artifact_sha256=model_hash,
                    preprocessing_sha256=prep_hash,
                    metrics=metrics,
                    is_active=False,
                    input_features=[
                        "operation_date",
                        "meals_prepared",
                        "kitchen_staff",
                        "staff_experience",
                        "special_event",
                        "temperature_c",
                        "humidity_percent",
                    ],
                )
            )
            db.flush()
            added += 1
    return added


@lru_cache(maxsize=4)
def load_artifacts(model_relative, prep_relative, model_hash, prep_hash):
    import joblib

    paths = [artifact_path(model_relative), artifact_path(prep_relative)]
    if [digest(p) for p in paths] != [model_hash, prep_hash]:
        raise ValueError("Checksum model berubah; registrasikan versi model baru.")
    return joblib.load(paths[0]), joblib.load(paths[1])


def predict_value(snapshot, version):
    if version.name != "RandomForest":
        raise HTTPException(503, "Runtime ini dikonfigurasi untuk model Random Forest terpilih.")
    try:
        import pandas as pd

        model, bundle = load_artifacts(
            version.artifact_path,
            version.preprocessing_path,
            version.artifact_sha256,
            version.preprocessing_sha256,
        )
        frame = pd.DataFrame(
            [
                {
                    "date": snapshot["operation_date"],
                    "meals_served": snapshot["meals_prepared"],
                    "kitchen_staff": snapshot["kitchen_staff"],
                    "staff_experience": snapshot["staff_experience"],
                    "special_event": int(snapshot["special_event"]),
                    "temperature_C": float(snapshot["temperature_c"]),
                    "humidity_percent": float(snapshot["humidity_percent"]),
                }
            ]
        )
        result = float(model.predict(bundle["preprocessor"].transform(frame))[0])
        if not __import__("math").isfinite(result):
            raise ValueError("Prediksi tidak finite.")
        return Decimal(str(max(0, result))).quantize(Decimal(".0001"))
    except HTTPException:
        raise
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("Inferensi model gagal")
        raise HTTPException(
            503, "Model belum siap atau artefaknya tidak cocok. Periksa log backend."
        ) from exc


def active_model(db):
    version = db.scalar(
        select(ModelVersion)
        .where(ModelVersion.is_active.is_(True))
        .order_by(ModelVersion.created_at.desc())
    )
    if not version:
        raise HTTPException(503, "Belum ada model aktif. Jalankan python -m api.seed_model.")
    return version


def calculate_prediction(db, user, snapshot, daily=None, plan_day=None):
    settings = restaurant_settings(db, user)
    body = DailyInput.model_validate(snapshot)
    ensure_capacity(body, settings)
    version = active_model(db)
    value = predict_value(snapshot, version)
    radius = Decimal(str(version.metrics.get("empirical_90_percent_interval_radius_kg", 0)))
    risk = (
        "safe"
        if value <= settings.safe_max_kg
        else ("warning" if value <= settings.warning_max_kg else "high")
    )
    result = PredictionResult(
        restaurant_id=user.restaurant_id,
        created_by=user.id,
        model_version_id=version.id,
        daily_operation_id=daily.id if daily else None,
        prediction_day_id=plan_day.id if plan_day else None,
        operation_version=daily.version if daily else plan_day.version,
        predicted_waste_kg=value,
        interval_lower_kg=max(Decimal(0), value - radius).quantize(Decimal(".0001")),
        interval_upper_kg=(value + radius).quantize(Decimal(".0001")),
        risk_level=risk,
        portions_per_staff=(Decimal(body.meals_prepared) / body.kitchen_staff).quantize(
            Decimal(".0001")
        ),
        estimated_waste_cost=(value * settings.ingredient_cost_per_kg).quantize(Decimal(".01")),
        input_snapshot=snapshot,
        settings_snapshot=serialize(settings),
        explanation="Prediksi memakai fitur rencana operasional. Kategori limbah dan limbah sebelumnya disimpan tetapi tidak dipakai model ini. Interval empiris, bukan jaminan; biaya mengikuti harga bahan pada pengaturan.",
    )
    db.add(result)
    db.flush()
    if risk == "high" and settings.high_risk_notifications:
        for recipient in db.scalars(
            select(User).where(User.restaurant_id == user.restaurant_id, User.status == "active")
        ).all():
            if recipient.notification_preferences.get("high_risk", True):
                db.add(
                    Notification(
                        restaurant_id=user.restaurant_id,
                        user_id=recipient.id,
                        prediction_result_id=result.id,
                        title="Prediksi limbah tinggi",
                        message=f"Rencana {snapshot['operation_date']} diperkirakan menghasilkan {value} kg limbah.",
                    )
                )
    return result
