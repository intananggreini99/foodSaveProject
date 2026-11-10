"""Validasi jumlah hasil impor dan status ekspor di tingkat PostgreSQL.

Alembic tidak mendeteksi perubahan CHECK constraint secara otomatis, sehingga
constraint ini dinyatakan eksplisit dalam migrasi tersendiri.
"""

from alembic import op

revision = "0003_storage_states"
down_revision = "0002_storage_constraints"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "ck_import_status", "data_imports", "status IN ('validated','applied','rejected')"
    )
    op.create_check_constraint(
        "ck_import_counts",
        "data_imports",
        "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND valid_rows + invalid_rows = total_rows AND unusual_rows BETWEEN 0 AND valid_rows AND applied_rows BETWEEN 0 AND valid_rows",
    )
    op.create_check_constraint(
        "ck_report_generation_status",
        "report_exports",
        "generation_status IN ('requested','ready','failed')",
    )
    op.create_check_constraint(
        "ck_report_email_status",
        "report_exports",
        "email_status IN ('not_requested','not_configured','pending','sent','failed')",
    )
    op.create_check_constraint(
        "ck_report_ready_file",
        "report_exports",
        "generation_status != 'ready' OR (storage_key IS NOT NULL AND file_name IS NOT NULL)",
    )


def downgrade():
    for name, table in [
        ("ck_report_ready_file", "report_exports"),
        ("ck_report_email_status", "report_exports"),
        ("ck_report_generation_status", "report_exports"),
        ("ck_import_counts", "data_imports"),
        ("ck_import_status", "data_imports"),
    ]:
        op.drop_constraint(name, table, type_="check")
