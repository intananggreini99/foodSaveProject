"""Daftarkan model lokal terpilih setelah migrasi database selesai."""

from api.database import SessionLocal
from api.services import register_experiment_catalog, register_selected_model

if __name__ == "__main__":
    with SessionLocal() as db:
        model = register_selected_model(db)
        if model is None:
            raise SystemExit(
                "Manifest tidak ditemukan. Siapkan artefak model di models/best_model."
            )
        count = register_experiment_catalog(db)
        db.commit()
        print("Model aktif:", model.version_key, "| eksperimen tambahan:", count)
