"""Jalankan seluruh pipeline: python -m foodsave_ml.pipeline

Satu run induk MLflow berisi enam run anak, satu untuk setiap langkah diagram.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import mlflow  # noqa: E402

from foodsave_core.storage import ensure_layout, storage_from_env  # noqa: E402
from foodsave_ml.config import PipelineConfig  # noqa: E402
from foodsave_ml.context import PipelineContext  # noqa: E402
from foodsave_ml.steps import STEPS  # noqa: E402

log = logging.getLogger("foodsave_ml")


def run(config: PipelineConfig | None = None, storage=None) -> dict:
    config = config or PipelineConfig.from_env()
    storage = storage or storage_from_env()
    ensure_layout(storage)
    mlflow.set_tracking_uri(config.tracking_uri)
    experiment = mlflow.set_experiment(config.experiment)
    started = datetime.now(timezone.utc)
    ctx = PipelineContext(
        config=config,
        storage=storage,
        started_at=started,
        version_key=f"rf-{started:%Y%m%d-%H%M%S}",
        experiment_id=experiment.experiment_id,
    )
    with mlflow.start_run(run_name=f"pipeline_{ctx.version_key}") as parent:
        ctx.parent_run_id = parent.info.run_id
        mlflow.set_tags({"foodsave.pipeline": "random-forest", "foodsave.storage": storage.kind})
        for number, (name, step) in enumerate(STEPS, start=1):
            log.info("Langkah %s/%s: %s", number, len(STEPS), name)
            with mlflow.start_run(run_name=f"{number}_{name}", nested=True):
                step(ctx)
    return {
        "version_key": ctx.version_key,
        "active": config.activate,
        "mlflow_run_id": ctx.parent_run_id,
        "best_params": ctx.best.params,
        "cv_mae": round(ctx.evaluation["cv_dev"]["mae"], 4),
        "test": {k: round(v, 4) for k, v in ctx.evaluation["test"].items() if isinstance(v, float)},
        "baseline_test_mae": round(ctx.evaluation["baseline_test"]["mae"], 4),
        "interval_radius_kg": round(ctx.interval_radius, 4),
        "model_dir": ctx.artifacts["storage_dir"],
        "registered": ctx.registered,
    }


def has_active_model(database_url: str) -> bool:
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            return bool(conn.scalar(text(
                "SELECT count(*) FROM model_analysis.model_versions WHERE is_active")))
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline pelatihan FoodSave (MLflow)")
    parser.add_argument("--no-activate", action="store_true",
                        help="Daftarkan versi baru tanpa menjadikannya model aktif.")
    parser.add_argument("--if-no-active", action="store_true",
                        help="Lewati pelatihan bila sudah ada model aktif (dipakai saat start awal).")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = PipelineConfig.from_env()
    if args.if_no_active and has_active_model(config.database_url):
        log.info("Model aktif sudah ada; pelatihan awal dilewati.")
        return
    if args.no_activate:
        config.activate = False
    print(json.dumps(run(config), indent=2, default=str))


if __name__ == "__main__":
    main()
