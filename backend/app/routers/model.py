"""Data statis hasil analisis model (skema model_analysis, diisi pipeline MLflow).

Dipakai halaman Insight (faktor, perbandingan, kurva kepekaan), Pengaturan
(info model), dan unduhan laporan evaluasi dari HDFS.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.core.deps import CurrentUser, Db, Owner
from app.models import (
    EvaluationPrediction,
    EvaluationReport,
    FeatureImportance,
    ModelEvaluation,
    ModelVersion,
    SensitivityCurve,
    TrainingRun,
    TuningTrial,
)
from app.services.common import model_storage, serialize
from app.services.prediction_service import prediction_service
from foodsave_core.storage import StorageError

router = APIRouter(prefix="/model", tags=["Analisis model (statis)"])
PRIVATE = {"model_path", "preprocessing_path", "manifest_path", "storage_dir"}


def version_or_active(db, version_id: UUID | None) -> ModelVersion:
    if version_id:
        version = db.get(ModelVersion, version_id)
    else:
        version = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    if not version:
        raise HTTPException(404, "Versi model tidak ditemukan atau belum ada model aktif.")
    return version


@router.get("/active")
def active_model(db: Db, user: CurrentUser):
    version = version_or_active(db, None)
    cached = prediction_service.cached
    return {
        **serialize(version, exclude=PRIVATE),
        "loaded_in_memory": bool(cached and cached.version_id == version.id),
        "evaluations": [
            serialize(row)
            for row in db.scalars(
                select(ModelEvaluation).where(ModelEvaluation.model_version_id == version.id)
            )
        ],
    }


@router.get("/versions")
def versions(db: Db, user: CurrentUser):
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    return [serialize(row, exclude=PRIVATE | {"feature_columns", "training_ranges"}) for row in rows]


@router.get("/evaluations")
def evaluations(db: Db, user: CurrentUser, version_id: UUID | None = None):
    """Perbandingan: validasi silang, test 20%, dan pembanding median."""
    version = version_or_active(db, version_id)
    rows = db.scalars(
        select(ModelEvaluation).where(ModelEvaluation.model_version_id == version.id)
    ).all()
    return {"version_key": version.version_key, "items": [serialize(r) for r in rows]}


@router.get("/tuning")
def tuning(db: Db, user: CurrentUser, version_id: UUID | None = None):
    version = version_or_active(db, version_id)
    run = db.get(TrainingRun, version.training_run_id) if version.training_run_id else None
    trials = []
    if run:
        trials = db.scalars(
            select(TuningTrial)
            .where(TuningTrial.training_run_id == run.id)
            .order_by(TuningTrial.trial_number)
        ).all()
    return {
        "version_key": version.version_key,
        "training_run": serialize(run, exclude={"processed_path"}) if run else None,
        "trials": [serialize(t) for t in trials],
    }


@router.get("/feature-importances")
def feature_importances(db: Db, user: CurrentUser, version_id: UUID | None = None):
    version = version_or_active(db, version_id)
    rows = db.scalars(
        select(FeatureImportance)
        .where(FeatureImportance.model_version_id == version.id)
        .order_by(FeatureImportance.rank)
    ).all()
    return {"version_key": version.version_key, "items": [serialize(r) for r in rows]}


@router.get("/sensitivity")
def sensitivity(
    db: Db,
    user: CurrentUser,
    staff_experience: str = Query("intermediate", pattern="^(beginner|intermediate|expert)$"),
    special_event: bool = False,
    version_id: UUID | None = None,
):
    """Kurva kepekaan porsi statis (dihitung sekali oleh pipeline, tanpa memanggil model)."""
    version = version_or_active(db, version_id)
    rows = db.scalars(
        select(SensitivityCurve)
        .where(
            SensitivityCurve.model_version_id == version.id,
            SensitivityCurve.staff_experience == staff_experience,
            SensitivityCurve.special_event.is_(special_event),
        )
        .order_by(SensitivityCurve.meals_prepared)
    ).all()
    return {
        "version_key": version.version_key,
        "staff_experience": staff_experience,
        "special_event": special_event,
        "points": [
            {
                "meals_prepared": r.meals_prepared,
                "predicted_kg": r.predicted_kg,
                "within_training_range": r.within_training_range,
            }
            for r in rows
        ],
    }


@router.get("/evaluation-predictions")
def evaluation_predictions(
    db: Db,
    user: CurrentUser,
    scope: str = Query("test", pattern="^(test|oof_dev)$"),
    version_id: UUID | None = None,
    limit: int = Query(500, ge=1, le=2000),
):
    """Aktual vs prediksi saat evaluasi. Hanya data publik awal (seed) yang dibuka:
    data aktual restoran lain yang ikut dilatih tidak ditampilkan per tanggal."""
    version = version_or_active(db, version_id)
    rows = db.scalars(
        select(EvaluationPrediction)
        .where(
            EvaluationPrediction.model_version_id == version.id,
            EvaluationPrediction.scope == scope,
            EvaluationPrediction.source == "seed",
        )
        .order_by(EvaluationPrediction.observation_date)
        .limit(limit)
    ).all()
    return {
        "version_key": version.version_key,
        "scope": scope,
        "items": [serialize(r, exclude={"model_version_id", "id", "created_at"}) for r in rows],
    }


@router.get("/evaluation-reports")
def evaluation_reports(db: Db, user: CurrentUser, version_id: UUID | None = None):
    version = version_or_active(db, version_id)
    rows = db.scalars(
        select(EvaluationReport).where(EvaluationReport.model_version_id == version.id)
    ).all()
    return {
        "version_key": version.version_key,
        "items": [serialize(r, exclude={"storage_path"}) for r in rows],
    }


@router.get("/evaluation-reports/{report_id}/file")
def evaluation_report_file(report_id: UUID, db: Db, user: CurrentUser):
    report = db.get(EvaluationReport, report_id)
    if not report:
        raise HTTPException(404, "Laporan evaluasi tidak ditemukan.")
    version = db.get(ModelVersion, report.model_version_id)
    try:
        content = model_storage().read_bytes(report.storage_path)
    except FileNotFoundError:
        raise HTTPException(404, "File laporan tidak ada di penyimpanan.")
    except StorageError:
        raise HTTPException(503, "HDFS tidak dapat dihubungi.")
    media = {
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[report.file_format]
    name = f"laporan_evaluasi_{version.version_key}.{report.file_format}"
    return Response(
        content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.post("/reload")
def reload_model(db: Db, user: Owner):
    """Muat ulang model versi aktif dari HDFS ke memori layanan prediksi."""
    active = prediction_service.reload(db)
    return {"version_key": active.version_key, "loaded_at": active.loaded_at}
