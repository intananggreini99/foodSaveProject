"""FoodSave API (FastAPI): API /api/v1, layanan prediksi, dan pekerja laporan.

Peta router ke jenis data:
- prediksi realtime  : predictions, weekly, scenarios     (memanggil layanan prediksi)
- data operasional   : auth, restaurant, operations, imports, dashboard, notifications,
                       reports, insights, training_exports
- data statis model  : model                               (skema model_analysis)
"""

import logging
import uuid
from contextlib import asynccontextmanager

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.orm.exc import StaleDataError

from app import openapi_docs
from app.core import database
from app.core.config import BACKEND_ROOT, get_settings
from app.routers import (
    auth,
    dashboard,
    imports,
    insights,
    model,
    notifications,
    operations,
    predictions,
    reports,
    restaurant,
    scenarios,
    training_exports,
    weekly,
)
from app.services.common import model_storage
from app.services.prediction_service import prediction_service

log = logging.getLogger("foodsave.api")
HEAD_REVISION = ScriptDirectory.from_config(
    Config(str(BACKEND_ROOT / "alembic.ini"))
).get_current_head()


@asynccontextmanager
async def lifespan(app):
    # Muat model aktif sejak awal agar prediksi pertama tidak menunggu unduhan HDFS.
    try:
        with database.SessionLocal() as db:
            prediction_service.get(db)
    except Exception:  # noqa: BLE001 - API tetap hidup; /health/ready melaporkan masalahnya
        log.warning("Model aktif belum dimuat saat start; akan dicoba pada permintaan berikut.")
    yield


app = FastAPI(
    title="FoodSave Backend",
    version="2.0.0",
    description=openapi_docs.DESCRIPTION,
    swagger_ui_parameters=openapi_docs.SWAGGER_UI,
    lifespan=lifespan,
)
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
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and (
        origin not in get_settings().origins
    ):
        return JSONResponse(status_code=403, content={"detail": "Origin permintaan tidak diizinkan."})
    return await call_next(request)


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Data bertabrakan atau relasinya tidak valid. Muat ulang dan periksa input."},
    )


@app.exception_handler(StaleDataError)
async def stale(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Data sudah berubah. Muat ulang sebelum menyimpan kembali."},
    )


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeoutError)
async def database_unavailable(request, exc):
    log.error("Database tidak dapat dihubungi: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database tidak dapat dihubungi. Coba lagi beberapa saat."},
        headers={"Retry-After": "5"},
    )


@app.exception_handler(Exception)
async def unexpected(request, exc):
    # Pesan aman untuk pengguna; detail lengkap ada di log dengan kode yang sama.
    error_id = uuid.uuid4().hex[:12]
    log.exception("Kesalahan tak terduga %s pada %s %s", error_id, request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Terjadi kesalahan di server.", "error_id": error_id},
    )


@app.get("/health/live", tags=["Health"])
def live():
    return {"status": "alive", "service": "foodsave-api"}


@app.get("/health/ready", tags=["Health"])
def ready():
    checks = {}
    try:
        with database.SessionLocal() as db:
            db.execute(text("SELECT 1"))
            checks["database"] = "connected"
            revision = db.scalar(text("SELECT version_num FROM public.alembic_version"))
            if revision != HEAD_REVISION:
                raise HTTPException(503, "Migrasi database belum sesuai.")
            checks["migration"] = revision
            try:
                model_storage().ping()
                checks["storage"] = model_storage().kind
            except Exception as exc:
                raise HTTPException(503, "Penyimpanan model (HDFS) tidak dapat dihubungi.") from exc
            try:
                active = prediction_service.get(db)
            except HTTPException as exc:
                raise HTTPException(503, exc.detail) from exc
            checks["model"] = active.version_key
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database atau migrasi belum siap.") from exc
    return {"status": "ready", **checks}


for router in [
    auth.router,
    restaurant.router,
    operations.router,
    imports.router,
    predictions.router,
    weekly.router,
    scenarios.router,
    dashboard.router,
    notifications.router,
    reports.router,
    insights.router,
    model.router,
    training_exports.router,
]:
    app.include_router(router, prefix="/api/v1")

openapi_docs.install(app)
