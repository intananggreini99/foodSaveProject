"""Jalankan tes backend pada database *_test (dibuat otomatis bila belum ada).

    python backend/run_tests.py            # memakai DATABASE_URL / POSTGRES_* dari .env
    python backend/run_tests.py -k model   # argumen tambahan diteruskan ke pytest
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402

if __name__ == "__main__":
    original = make_url(get_settings().database_url)
    if original.get_backend_name() != "postgresql":
        raise SystemExit("Gunakan PostgreSQL untuk tes integrasi ini.")
    name = original.database if original.database.endswith("_test") else original.database + "_test"
    import psycopg
    from psycopg import sql

    admin = original.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    with psycopg.connect(admin, autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    env = os.environ.copy()
    env["DATABASE_URL"] = original.set(database=name).render_as_string(hide_password=False)
    env.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    env.setdefault("N_JOBS", "2")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(BACKEND / "tests"), "-q", *sys.argv[1:]],
        env=env,
        cwd=BACKEND,
    )
    raise SystemExit(result.returncode)
