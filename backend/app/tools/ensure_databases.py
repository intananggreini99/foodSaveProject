"""Pastikan database "mlflow" ada di server PostgreSQL yang sama (idempoten).

Dijalankan service migrate sebelum Alembic: python -m app.tools.ensure_databases
Tidak bergantung pada skrip init PostgreSQL, sehingga tetap benar walaupun volume
database sudah ada dari percobaan sebelumnya.
"""

import logging
import time

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings

log = logging.getLogger("foodsave.ensure_databases")
EXTRA_DATABASES = ("mlflow",)


def main(attempts: int = 30, delay: float = 2.0) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = make_url(get_settings().database_url)
    dsn = url.set(drivername="postgresql").render_as_string(hide_password=False)
    for attempt in range(1, attempts + 1):
        try:
            with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
                for name in EXTRA_DATABASES:
                    exists = conn.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
                    ).fetchone()
                    if exists:
                        log.info("Database %s sudah ada.", name)
                    else:
                        conn.execute(
                            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                                sql.Identifier(name), sql.Identifier(url.username)
                            )
                        )
                        log.info("Database %s dibuat.", name)
            return
        except psycopg.OperationalError as exc:
            log.info("Menunggu PostgreSQL (%s/%s): %s", attempt, attempts, exc)
            time.sleep(delay)
    raise SystemExit("PostgreSQL tidak dapat dihubungi.")


if __name__ == "__main__":
    main()
