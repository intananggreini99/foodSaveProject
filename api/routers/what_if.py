from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from api.auth import CurrentUser, Db, Manager, now
from api.models import DailyOperation, DataCorrection, PortionScenario
from api.schemas import ApplyScenario, DailyInput, ScenarioCreate
from api.services import (
    active_model,
    calculate_prediction,
    daily_snapshot,
    ensure_capacity,
    owned,
    predict_value,
    restaurant_settings,
    serialize,
)

router = APIRouter(prefix="/portion-scenarios", tags=["Simulasi porsi"])


@router.post("", status_code=201)
def create_scenario(body: ScenarioCreate, db: Db, user: Manager):
    operation = owned(db, DailyOperation, body.daily_operation_id, user, lock=True)
    if body.application_date != operation.operation_date:
        raise HTTPException(422, "Tanggal penerapan harus sama dengan tanggal operasional terkait.")
    settings = restaurant_settings(db, user)
    version = active_model(db)
    baseline = daily_snapshot(operation)
    original = predict_value(baseline, version)
    modified = dict(baseline)
    portions = int(
        (Decimal(operation.meals_prepared) * (100 - body.reduction_percent) / 100).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )
    modified["meals_prepared"] = portions
    modified["kitchen_staff"] = body.kitchen_staff or operation.kitchen_staff
    ensure_capacity(DailyInput.model_validate(modified), settings)
    prediction = predict_value(modified, version)
    saving = original - prediction  # Nilai negatif dipertahankan bila simulasi lebih buruk.
    row = PortionScenario(
        restaurant_id=user.restaurant_id,
        daily_operation_id=operation.id,
        created_by=user.id,
        model_version_id=version.id,
        operation_version=operation.version,
        application_date=body.application_date,
        baseline_portions=operation.meals_prepared,
        simulated_portions=portions,
        kitchen_staff=modified["kitchen_staff"],
        reduction_percent=body.reduction_percent,
        predicted_waste_kg=prediction,
        baseline_waste_kg=original,
        savings_kg=saving,
        savings_amount=(saving * settings.ingredient_cost_per_kg).quantize(Decimal(".01")),
        portions_per_staff=(Decimal(portions) / modified["kitchen_staff"]).quantize(
            Decimal(".0001")
        ),
        shortage_risk="unknown",
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
    return [
        serialize(row)
        for row in db.scalars(
            query.order_by(PortionScenario.created_at.desc()).limit(limit).offset(offset)
        ).all()
    ]


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
    if scenario.model_version_id != active_model(db).id:
        raise HTTPException(409, "Versi model berubah. Buat simulasi baru.")
    ensure_capacity(
        DailyInput.model_validate(scenario.input_snapshot), restaurant_settings(db, user)
    )
    previous = daily_snapshot(operation)
    values = DailyInput.model_validate(scenario.input_snapshot)
    # Actual dan catatan tidak ditimpa; version check menjamin rencana dasar belum berubah.
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
    result = calculate_prediction(db, user, daily_snapshot(operation), daily=operation)
    db.commit()
    return {
        "scenario": serialize(scenario),
        "operation": serialize(operation),
        "prediction": serialize(result),
        "already_applied": False,
    }
