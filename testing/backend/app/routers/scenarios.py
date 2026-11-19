"""Halaman Simulasi Porsi: what-if pengurangan porsi dan jumlah staf (prediksi realtime)."""

from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, Db, Manager
from app.core.security import now
from app.models import DailyOperation, DataCorrection, PortionScenario
from app.schemas import REDUCTIONS, ApplyScenario, DailyInput, ScenarioCreate, ScenarioOptions
from app.services.common import (
    daily_snapshot,
    ensure_capacity,
    owned,
    restaurant_settings,
    serialize,
)
from app.services.prediction_service import prediction_service
from app.services.predictions import calculate_prediction, risk_level

router = APIRouter(prefix="/portion-scenarios", tags=["Simulasi porsi"])


def reduced(portions: int, percent: int) -> int:
    """Pembulatan setengah ke atas, sama seperti tampilan frontend."""
    return int(
        (Decimal(portions) * (100 - percent) / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )


def variant(baseline: dict, percent: int, staff: int | None) -> dict:
    modified = dict(baseline)
    modified["meals_prepared"] = reduced(baseline["meals_prepared"], percent)
    modified["kitchen_staff"] = staff or baseline["kitchen_staff"]
    return modified


@router.post("/options")
def scenario_options(body: ScenarioOptions, db: Db, user: CurrentUser):
    """Empat pilihan (0/5/10/15%) + kondisi awal dalam satu panggilan model (5 baris).

    Untuk grafik perbandingan di halaman Simulasi Porsi; tidak menyimpan apa pun.
    """
    operation = owned(db, DailyOperation, body.daily_operation_id, user)
    settings = restaurant_settings(db, user)
    baseline = daily_snapshot(operation)
    variants = [variant(baseline, p, body.kitchen_staff) for p in REDUCTIONS]
    active, values = prediction_service.predict(
        db, [baseline, *variants], user=user, source="scenario"
    )
    db.commit()  # hanya log inferensi
    original = values[0]
    options = []
    for percent, snapshot, value in zip(REDUCTIONS, variants, values[1:]):
        saving = original - value
        options.append(
            {
                "reduction_percent": percent,
                "simulated_portions": snapshot["meals_prepared"],
                "kitchen_staff": snapshot["kitchen_staff"],
                "predicted_waste_kg": value,
                "savings_kg": saving,
                "savings_amount": (saving * settings.ingredient_cost_per_kg).quantize(
                    Decimal(".01")
                ),
                "risk_level": risk_level(value, settings),
                "outside_training_range": bool(
                    prediction_service.outside_training_range(active, snapshot)
                ),
            }
        )
    return {
        "daily_operation_id": operation.id,
        "operation_version": operation.version,
        "baseline_portions": operation.meals_prepared,
        "baseline_waste_kg": original,
        "baseline_risk_level": risk_level(original, settings),
        "model_version": active.version_key,
        "options": options,
    }


@router.post("", status_code=201)
def create_scenario(body: ScenarioCreate, db: Db, user: Manager):
    operation = owned(db, DailyOperation, body.daily_operation_id, user, lock=True)
    if body.application_date != operation.operation_date:
        raise HTTPException(422, "Tanggal penerapan harus sama dengan tanggal operasional terkait.")
    settings = restaurant_settings(db, user)
    baseline = daily_snapshot(operation)
    modified = variant(baseline, body.reduction_percent, body.kitchen_staff)
    ensure_capacity(DailyInput.model_validate(modified), settings)
    # Sebelum dan sesudah dihitung dalam satu panggilan model (2 baris).
    active, (original, prediction) = prediction_service.predict(
        db, [baseline, modified], user=user, source="scenario"
    )
    saving = original - prediction  # negatif dipertahankan bila simulasi lebih buruk
    row = PortionScenario(
        restaurant_id=user.restaurant_id,
        daily_operation_id=operation.id,
        created_by=user.id,
        model_version_id=active.version_id,
        operation_version=operation.version,
        application_date=body.application_date,
        baseline_portions=operation.meals_prepared,
        simulated_portions=modified["meals_prepared"],
        kitchen_staff=modified["kitchen_staff"],
        reduction_percent=body.reduction_percent,
        predicted_waste_kg=prediction,
        baseline_waste_kg=original,
        savings_kg=saving,
        savings_amount=(saving * settings.ingredient_cost_per_kg).quantize(Decimal(".01")),
        portions_per_staff=(
            Decimal(modified["meals_prepared"]) / modified["kitchen_staff"]
        ).quantize(Decimal(".0001")),
        status=body.status,
        notes=body.notes,
        input_snapshot=modified,
        settings_snapshot=serialize(settings),
    )
    db.add(row)
    db.commit()
    return serialize(row)


@router.get("")
def list_scenarios(
    db: Db,
    user: CurrentUser,
    daily_operation_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(PortionScenario).where(PortionScenario.restaurant_id == user.restaurant_id)
    if daily_operation_id:
        query = query.where(PortionScenario.daily_operation_id == daily_operation_id)
    rows = db.scalars(
        query.order_by(PortionScenario.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return [serialize(row) for row in rows]


@router.get("/{scenario_id}")
def read(scenario_id: UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, PortionScenario, scenario_id, user))


@router.post("/{scenario_id}/apply")
def apply_scenario(scenario_id: UUID, body: ApplyScenario, db: Db, user: Manager):
    scenario = owned(db, PortionScenario, scenario_id, user, lock=True)
    operation = owned(db, DailyOperation, scenario.daily_operation_id, user, lock=True)
    if scenario.status == "applied":
        return {
            "scenario": serialize(scenario),
            "operation": serialize(operation),
            "already_applied": True,
        }
    if (
        scenario.operation_version != operation.version
        or body.expected_operation_version != operation.version
    ):
        raise HTTPException(409, "Data operasional berubah sejak simulasi. Buat simulasi baru.")
    if scenario.model_version_id != prediction_service.active_version(db).id:
        raise HTTPException(409, "Versi model berubah. Buat simulasi baru.")
    ensure_capacity(
        DailyInput.model_validate(scenario.input_snapshot), restaurant_settings(db, user)
    )
    previous = daily_snapshot(operation)
    values = DailyInput.model_validate(scenario.input_snapshot)
    # Nilai aktual dan catatan tidak ditimpa; cek versi menjamin rencana dasar belum berubah.
    operation.meals_prepared = values.meals_prepared
    operation.kitchen_staff = values.kitchen_staff
    operation.updated_by = user.id
    db.add(
        DataCorrection(
            restaurant_id=user.restaurant_id,
            daily_operation_id=operation.id,
            changed_by=user.id,
            reason=f"Penerapan simulasi {scenario.id}",
            previous_values=previous,
            new_values=daily_snapshot(operation),
            previous_version=operation.version,
        )
    )
    scenario.status = "applied"
    scenario.applied_at = now()
    scenario.applied_by = user.id
    db.flush()
    result = calculate_prediction(
        db, user, daily_snapshot(operation), daily=operation, source="scenario"
    )
    db.commit()
    return {
        "scenario": serialize(scenario),
        "operation": serialize(operation),
        "prediction": serialize(result),
        "already_applied": False,
    }
