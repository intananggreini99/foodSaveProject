"""Runner tes yang mengarahkan koneksi ke database *_test, bukan data utama."""

import os
import subprocess
import sys
from sqlalchemy.engine import make_url
from api.config import ROOT, get_settings

if __name__ == "__main__":
    original = make_url(get_settings().database_url)
    if original.get_backend_name() != "postgresql":
        raise SystemExit("Gunakan PostgreSQL untuk tes integrasi ini.")
    name = original.database if original.database.endswith("_test") else original.database + "_test"
    args = sys.argv[1:]
    if "--prepare" in args:
        import psycopg
        from psycopg import sql

        args.remove("--prepare")
        if len(name.encode()) > 63:
            raise SystemExit("Nama database uji terlalu panjang.")
        admin_url = original.set(drivername="postgresql", database="postgres").render_as_string(
            hide_password=False
        )
        with psycopg.connect(admin_url, autocommit=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname=%s", (name,)
            ).fetchone()
            if not exists:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print("Database pengujian siap:", name, flush=True)
    env = os.environ.copy()
    env["DATABASE_URL"] = original.set(database=name).render_as_string(hide_password=False)
    env["MPLCONFIGDIR"] = str(ROOT / ".venv") if (ROOT / ".venv").exists() else "/tmp/matplotlib"
    # URL/password hanya diteruskan ke environment subprocess, tidak dicetak.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "api/tests"), "-q", *args], env=env, cwd=ROOT
    )
    raise SystemExit(result.returncode)
