-- Query hanya membaca; tidak menghapus atau mengubah data aplikasi.
SELECT version_num AS migration FROM alembic_version;

SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

SELECT 'restaurants' AS tabel, count(*) FROM restaurants
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'daily_operations', count(*) FROM daily_operations
UNION ALL SELECT 'prediction_results', count(*) FROM prediction_results
UNION ALL SELECT 'weekly_predictions', count(*) FROM weekly_predictions
UNION ALL SELECT 'prediction_days', count(*) FROM prediction_days
UNION ALL SELECT 'portion_scenarios', count(*) FROM portion_scenarios
UNION ALL SELECT 'data_imports', count(*) FROM data_imports
UNION ALL SELECT 'report_exports', count(*) FROM report_exports;

SELECT name, preprocessing, is_active,
       metrics->>'validation_MAE' AS mae_validasi,
       metrics->>'test_MAE' AS mae_test
FROM model_versions ORDER BY is_active DESC, name, preprocessing;

SELECT r.name AS restoran, u.email, d.operation_date, d.meals_prepared,
       d.actual_waste_kg, d.version, d.source
FROM daily_operations d
JOIN restaurants r ON r.id = d.restaurant_id
JOIN users u ON u.id = d.created_by
ORDER BY d.created_at DESC LIMIT 20;

SELECT p.id, p.created_at, m.name AS model, m.preprocessing,
       p.predicted_waste_kg, p.interval_lower_kg, p.interval_upper_kg,
       p.risk_level, p.operation_version,
       p.input_snapshot->>'meals_prepared' AS porsi_saat_prediksi
FROM prediction_results p
JOIN model_versions m ON m.id = p.model_version_id
ORDER BY p.created_at DESC LIMIT 20;

SELECT status, baseline_portions, simulated_portions, savings_kg,
       savings_amount, shortage_risk, applied_at FROM portion_scenarios
ORDER BY created_at DESC LIMIT 10;

SELECT file_name, total_rows, valid_rows, invalid_rows, applied_rows
FROM data_imports ORDER BY created_at DESC LIMIT 10;

SELECT file_format, generation_status, downloaded_at, email_status
FROM report_exports ORDER BY created_at DESC LIMIT 10;

SELECT d.status, d.transport, d.attempts, d.max_attempts, d.sent_at,
       r.email_recipient, r.file_format, d.last_error
FROM email_deliveries d JOIN report_exports r ON r.id=d.report_export_id
ORDER BY d.created_at DESC LIMIT 10;

SELECT attempt_number, success, error_message, created_at
FROM email_attempts ORDER BY created_at DESC LIMIT 10;

-- Password harus berupa hash scrypt, token sesi hanya hash, tidak nilainya.
SELECT email, split_part(password_hash, '$', 1) AS metode_password FROM users;
