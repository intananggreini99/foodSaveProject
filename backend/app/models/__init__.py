"""Semua model SQLAlchemy, dikelompokkan per skema PostgreSQL.

operational    : akun, restoran, input harian, laporan, notifikasi, ekspor data aktual
prediction     : hasil prediksi realtime, rencana 7 hari, simulasi porsi, log inferensi
model_analysis : hasil analisis statis dari pipeline MLflow (diisi langkah register model)
"""

from sqlalchemy import ForeignKeyConstraint

from app.core.database import Base
from app.models.common import OP
from app.models.model_analysis import (
    DatasetVersion,
    EvaluationPrediction,
    EvaluationReport,
    FeatureImportance,
    ModelEvaluation,
    ModelVersion,
    SensitivityCurve,
    TrainingRun,
    TuningTrial,
)
from app.models.operational import (
    DailyOperation,
    DataCorrection,
    DataImport,
    EmailAttempt,
    EmailDelivery,
    Notification,
    ReportExport,
    Restaurant,
    RestaurantSettings,
    TrainingExport,
    User,
    UserSession,
)
from app.models.prediction import (
    InferenceLog,
    PlanRevision,
    PortionScenario,
    PredictionDay,
    PredictionResult,
    WeeklyPrediction,
)

# Pengguna yang tercatat sebagai pelaku harus berasal dari restoran yang sama.
# FK tunggal ke users.id tetap ada; FK komposit menambah perlindungan di database.
for _table in Base.metadata.tables.values():
    if "restaurant_id" not in _table.c:
        continue
    for _field in ["created_by", "updated_by", "changed_by", "applied_by", "user_id"]:
        if _field in _table.c and _table.name not in {"user_sessions", "notifications"}:
            _table.append_constraint(
                ForeignKeyConstraint(
                    ["restaurant_id", _field],
                    [f"{OP}.users.restaurant_id", f"{OP}.users.id"],
                    name=f"fk_{_table.name}_{_field}_same_restaurant",
                )
            )

__all__ = [
    "DailyOperation",
    "DataCorrection",
    "DataImport",
    "DatasetVersion",
    "EmailAttempt",
    "EmailDelivery",
    "EvaluationPrediction",
    "EvaluationReport",
    "FeatureImportance",
    "InferenceLog",
    "ModelEvaluation",
    "ModelVersion",
    "Notification",
    "PlanRevision",
    "PortionScenario",
    "PredictionDay",
    "PredictionResult",
    "ReportExport",
    "Restaurant",
    "RestaurantSettings",
    "SensitivityCurve",
    "TrainingExport",
    "TrainingRun",
    "TuningTrial",
    "User",
    "UserSession",
    "WeeklyPrediction",
]
