"""Siapkan folder HDFS dan unggah data mentah awal: python -m foodsave_ml.bootstrap

Aman dijalankan berulang: train.csv hanya diunggah bila belum ada di HDFS.

Urutan menunggu (penting di Docker, karena halaman namenode sudah hidup sebelum
HDFS bisa menerima file):
1. namenode menjawab WebHDFS;
2. minimal satu datanode terdaftar dan namenode keluar dari safemode (JMX);
3. folder /foodsave dibuat, lalu train.csv diunggah dengan beberapa kali percobaan.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

from foodsave_core.storage import RAW_SEED, StorageError, ensure_layout, storage_from_env

log = logging.getLogger("foodsave_ml")
DEFAULT_SEED = os.environ.get("SEED_CSV", "/app/seed/train.csv")


def wait_for(storage, attempts: int = 60, delay: float = 5.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            storage.ping()
            status = storage.cluster_status()
            if status is not None and (status["live_datanodes"] < 1 or status["safemode"]):
                raise StorageError(
                    f"datanode hidup {status['live_datanodes']}, safemode {status['safemode']}"
                )
            ensure_layout(storage)
            return
        except (StorageError, FileNotFoundError) as exc:
            log.info("Menunggu HDFS siap (%s/%s): %s", attempt, attempts, exc)
            time.sleep(delay)
    raise SystemExit("HDFS tidak siap. Periksa layanan namenode dan datanode.")


def upload_seed(storage, content: bytes, attempts: int = 20, delay: float = 5.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            storage.write_bytes(RAW_SEED, content)
            if storage.read_bytes(RAW_SEED) != content:
                raise StorageError("Isi train.csv di HDFS tidak sama dengan file lokal.")
            return
        except StorageError as exc:
            log.info("Unggah train.csv gagal (%s/%s): %s", attempt, attempts, exc)
            time.sleep(delay)
    raise SystemExit("train.csv gagal diunggah ke HDFS.")


def main(argv=None, delay: float = 5.0) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=DEFAULT_SEED, help="Path train.csv lokal")
    parser.add_argument("--force", action="store_true", help="Timpa train.csv di HDFS")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    storage = storage_from_env()
    wait_for(storage, delay=delay)
    if storage.exists(RAW_SEED) and not args.force:
        log.info("%s sudah ada; tidak diunggah ulang.", RAW_SEED)
        return
    seed = Path(args.seed)
    if not seed.is_file():
        raise SystemExit(f"File seed {seed} tidak ditemukan.")
    upload_seed(storage, seed.read_bytes(), delay=delay)
    log.info("Data mentah awal diunggah ke %s (%s byte).", RAW_SEED, seed.stat().st_size)


if __name__ == "__main__":
    main()
