"""Ekspor terjadwal data aktual ke HDFS /foodsave/raw/actuals.

Jalankan: python -m app.workers.training_export [--once]
Interval diatur TRAINING_EXPORT_INTERVAL_HOURS (bawaan 24 jam).
"""

import argparse
import logging
import time

from app.core import database
from app.core.config import get_settings
from app.services.training_export import run_export

logger = logging.getLogger("foodsave.training_export")


def export_once() -> str:
    with database.SessionLocal() as db:
        record = run_export(db, triggered_by="schedule")
        db.commit()
        return record.status


def main(once: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    interval = max(60.0, get_settings().training_export_interval_hours * 3600)
    while True:
        try:
            status = export_once()
            logger.info("Ekspor selesai dengan status %s", status)
        except Exception:  # noqa: BLE001 - worker tetap berjalan untuk jadwal berikutnya
            logger.exception("Ekspor data aktual gagal; transaksi di-rollback.")
        if once:
            return
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    main(parser.parse_args().once)
