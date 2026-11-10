"""FoodSave API: PostgreSQL menjadi sumber data operasional dan riwayat model."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError
from alembic.config import Config
from alembic.script import ScriptDirectory
from api.auth import router as auth_router
from api.config import ROOT, get_settings
from api.database import SessionLocal
from api.models import ModelVersion
from api.routers import imports, operations, overview, predict, report, weekly, what_if
from api.services import (
    artifact_path,
    load_artifacts,
    register_experiment_catalog,
    register_selected_model,
)


@asynccontextmanager
async def lifespan(app):
    try:
        with SessionLocal() as db:
            register_selected_model(db)
            register_experiment_catalog(db)
            db.commit()
    except (SQLAlchemyError, OSError, ValueError, KeyError):
        logging.getLogger(__name__).exception(
            "Registrasi model belum berhasil; periksa migrasi dan artefak."
        )
    yield


app = FastAPI(
    title="FoodSave Backend",
    version="1.0.0",
    description="Akun, restoran, input harian, model, prediksi dan simulasi dengan PostgreSQL.",
    lifespan=lifespan,
)
HEAD_REVISION = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def csrf_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method not in ["GET", "HEAD", "OPTIONS"]
        and origin
        and origin not in get_settings().origins
    ):
        return JSONResponse(
            status_code=403, content={"detail": "Origin permintaan tidak diizinkan."}
        )
    return await call_next(request)


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Data bertabrakan atau relasinya tidak valid. Muat ulang dan periksa input."
        },
    )


@app.exception_handler(StaleDataError)
async def stale(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Data sudah berubah. Muat ulang sebelum menyimpan kembali."},
    )


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "alive", "service": "foodsave-api"}


@app.get("/health/ready", tags=["Health"])
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            model = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)).limit(1))
            if revision != HEAD_REVISION:
                raise HTTPException(503, "Migrasi database belum sesuai.")
            if not model:
                raise HTTPException(503, "Database siap, tetapi model aktif belum terdaftar.")
            if model.name != "RandomForest":
                raise HTTPException(503, "Model aktif belum didukung runtime inferensi ini.")
            if (
                not artifact_path(model.artifact_path).is_file()
                or not artifact_path(model.preprocessing_path).is_file()
            ):
                raise HTTPException(503, "File model atau preprocessing tidak tersedia.")
            try:
                loaded, bundle = load_artifacts(
                    model.artifact_path,
                    model.preprocessing_path,
                    model.artifact_sha256,
                    model.preprocessing_sha256,
                )
                if loaded.n_features_in_ != len(bundle["preprocessor"].columns):
                    raise ValueError("Jumlah fitur model dan preprocessing tidak cocok.")
            except Exception as exc:
                raise HTTPException(503, "Model atau preprocessing belum valid.") from exc
        return {
            "status": "ready",
            "database": "connected",
            "migration": revision,
            "model": "registered",
        }
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database atau migrasi belum siap.") from exc


@app.get("/health", tags=["Health"])
def health():
    return ready()


for router in [
    auth_router,
    operations.router,
    predict.router,
    weekly.router,
    what_if.router,
    imports.router,
    overview.router,
    report.router,
]:
    app.include_router(router, prefix="/api/v1")
