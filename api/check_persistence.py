"""Uji bahwa restart service db FoodSave tidak menghapus input/prediksi.

Jalankan dari host yang memiliki Docker Compose. Script tidak menghapus volume.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SQL = """
SELECT json_build_object(
 'operations',(SELECT json_agg(r ORDER BY id) FROM
   (SELECT id,operation_date,meals_prepared,kitchen_staff,actual_waste_kg,version FROM daily_operations) r),
 'predictions',(SELECT json_agg(r ORDER BY id) FROM
   (SELECT id,model_version_id,predicted_waste_kg,input_snapshot FROM prediction_results) r),
 'emails',(SELECT json_agg(r ORDER BY id) FROM
   (SELECT id,report_export_id,message_id FROM email_deliveries) r)
)::text;
"""


def snapshot():
    return subprocess.check_output(
        [
            "docker-compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "foodsave",
            "-d",
            "foodsave",
            "-At",
            "-c",
            SQL,
        ],
        cwd=ROOT,
        stderr=subprocess.DEVNULL,
    ).strip()


if __name__ == "__main__":
    with urlopen("http://localhost:8000/health/ready", timeout=10) as response:
        assert response.status == 200
    before = snapshot()
    data = json.loads(before)
    if not data["operations"]:
        raise SystemExit("Jalankan smoke_backend dahulu agar ada data yang diuji.")
    subprocess.run(["docker-compose", "restart", "db"], cwd=ROOT, check=True)
    deadline = time.monotonic() + 45
    while True:
        try:
            after = snapshot()
            with urlopen("http://localhost:8000/health/ready", timeout=5) as response:
                if response.status == 200:
                    break
        except (OSError, subprocess.CalledProcessError):
            pass
        if time.monotonic() > deadline:
            raise SystemExit("Database/API belum kembali siap setelah restart.")
        time.sleep(1)
    assert (
        before == after
    ), "Isi data berubah. Pastikan tidak ada pengguna lain yang sedang mengedit selama tes."
    result = {
        "status": "passed",
        "same_snapshot_before_after": True,
        "sha256": hashlib.sha256(before).hexdigest(),
        "counts": {key: len(value or []) for key, value in data.items()},
        "health_after_restart": "ready",
    }
    folder = ROOT / "results/backend"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "backend-persistence-check.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
