"""Skema awal: satu database foodsave dengan skema operational, prediction, model_analysis."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("operational", "prediction", "model_analysis")


def upgrade():
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    op.create_table('dataset_versions',
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('sources', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('raw_rows', sa.Integer(), nullable=False),
    sa.Column('usable_rows', sa.Integer(), nullable=False),
    sa.Column('invalid_removed', sa.Integer(), nullable=False),
    sa.Column('duplicates_removed', sa.Integer(), nullable=False),
    sa.Column('date_start', sa.Date(), nullable=False),
    sa.Column('date_end', sa.Date(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dataset_versions')),
    sa.UniqueConstraint('fingerprint', name=op.f('uq_dataset_versions_fingerprint')),
    schema='model_analysis'
    )
    op.create_table('restaurants',
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('timezone', sa.String(length=60), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_restaurants')),
    schema='operational'
    )
    op.create_table('training_runs',
    sa.Column('mlflow_run_id', sa.String(length=64), nullable=False),
    sa.Column('mlflow_experiment_id', sa.String(length=64), nullable=True),
    sa.Column('dataset_version_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('processed_path', sa.String(length=500), nullable=False),
    sa.Column('dev_rows', sa.Integer(), nullable=False),
    sa.Column('test_rows', sa.Integer(), nullable=False),
    sa.Column('dev_start', sa.Date(), nullable=False),
    sa.Column('dev_end', sa.Date(), nullable=False),
    sa.Column('test_start', sa.Date(), nullable=False),
    sa.Column('test_end', sa.Date(), nullable=False),
    sa.Column('cv_folds', sa.Integer(), nullable=False),
    sa.Column('selection_rule', sa.Text(), nullable=False),
    sa.Column('best_params', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('completed','failed')", name=op.f('ck_training_runs_status')),
    sa.CheckConstraint('dev_end < test_start', name=op.f('ck_training_runs_temporal_split')),
    sa.ForeignKeyConstraint(['dataset_version_id'], ['model_analysis.dataset_versions.id'], name=op.f('fk_training_runs_dataset_version_id_dataset_versions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_training_runs')),
    sa.UniqueConstraint('mlflow_run_id', name=op.f('uq_training_runs_mlflow_run_id')),
    schema='model_analysis'
    )
    op.create_table('restaurant_settings',
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('ingredient_cost_per_kg', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('safe_max_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('warning_max_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('max_portions', sa.Integer(), nullable=False),
    sa.Column('reduction_target_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('high_risk_notifications', sa.Boolean(), nullable=False),
    sa.Column('report_recipient_email', sa.String(length=254), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('ingredient_cost_per_kg >= 0 AND safe_max_kg >= 0 AND warning_max_kg > safe_max_kg AND max_portions > 0 AND reduction_target_percent BETWEEN 0 AND 100', name=op.f('ck_restaurant_settings_values')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_restaurant_settings_restaurant_id_restaurants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('restaurant_id', name=op.f('pk_restaurant_settings')),
    schema='operational'
    )
    op.create_table('users',
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=300), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notification_preferences', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('owner','manager','staff')", name=op.f('ck_users_role')),
    sa.CheckConstraint("status IN ('active','disabled')", name=op.f('ck_users_status')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_users_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_users_restaurant_id_id')),
    schema='operational'
    )
    op.create_index(op.f('ix_users_restaurant_id'), 'users', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('model_versions',
    sa.Column('version_key', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('training_run_id', sa.Uuid(), nullable=True),
    sa.Column('params', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('storage_dir', sa.String(length=500), nullable=False),
    sa.Column('model_path', sa.String(length=500), nullable=False),
    sa.Column('preprocessing_path', sa.String(length=500), nullable=False),
    sa.Column('manifest_path', sa.String(length=500), nullable=False),
    sa.Column('model_sha256', sa.String(length=64), nullable=False),
    sa.Column('preprocessing_sha256', sa.String(length=64), nullable=False),
    sa.Column('input_features', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('feature_columns', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('training_ranges', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('interval_radius_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('default_safe_max_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('default_warning_max_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('trained_rows', sa.Integer(), nullable=False),
    sa.Column('trained_from', sa.Date(), nullable=False),
    sa.Column('trained_to', sa.Date(), nullable=False),
    sa.Column('sklearn_version', sa.String(length=20), nullable=False),
    sa.Column('mlflow_run_id', sa.String(length=64), nullable=True),
    sa.Column('mlflow_model_name', sa.String(length=120), nullable=True),
    sa.Column('mlflow_model_version', sa.String(length=20), nullable=True),
    sa.Column('metrics', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('interval_radius_kg >= 0 AND default_warning_max_kg > default_safe_max_kg', name=op.f('ck_model_versions_values')),
    sa.ForeignKeyConstraint(['training_run_id'], ['model_analysis.training_runs.id'], name=op.f('fk_model_versions_training_run_id_training_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_versions')),
    sa.UniqueConstraint('version_key', name=op.f('uq_model_versions_version_key')),
    schema='model_analysis'
    )
    op.create_index('uq_model_versions_single_active', 'model_versions', ['is_active'], unique=True, schema='model_analysis', postgresql_where=sa.text('is_active'))
    op.create_table('tuning_trials',
    sa.Column('training_run_id', sa.Uuid(), nullable=False),
    sa.Column('trial_number', sa.Integer(), nullable=False),
    sa.Column('stage', sa.String(length=20), nullable=False),
    sa.Column('params', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('cv_mae', sa.Float(), nullable=False),
    sa.Column('cv_mse', sa.Float(), nullable=False),
    sa.Column('cv_rmse', sa.Float(), nullable=False),
    sa.Column('cv_mape', sa.Float(), nullable=False),
    sa.Column('cv_r2', sa.Float(), nullable=False),
    sa.Column('fold_mae', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('is_best', sa.Boolean(), nullable=False),
    sa.Column('mlflow_run_id', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("stage IN ('baseline','tuning')", name=op.f('ck_tuning_trials_stage')),
    sa.ForeignKeyConstraint(['training_run_id'], ['model_analysis.training_runs.id'], name=op.f('fk_tuning_trials_training_run_id_training_runs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tuning_trials')),
    sa.UniqueConstraint('training_run_id', 'trial_number', name=op.f('uq_tuning_trials_training_run_id_trial_number')),
    schema='model_analysis'
    )
    op.create_table('data_imports',
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=10), nullable=False),
    sa.Column('storage_key', sa.String(length=100), nullable=True),
    sa.Column('file_sha256', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('total_rows', sa.Integer(), nullable=False),
    sa.Column('valid_rows', sa.Integer(), nullable=False),
    sa.Column('invalid_rows', sa.Integer(), nullable=False),
    sa.Column('unusual_rows', sa.Integer(), nullable=False),
    sa.Column('applied_rows', sa.Integer(), nullable=False),
    sa.Column('validation_results', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('validated','applied','rejected')", name=op.f('ck_data_imports_status')),
    sa.CheckConstraint('total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND valid_rows + invalid_rows = total_rows AND unusual_rows BETWEEN 0 AND valid_rows AND applied_rows BETWEEN 0 AND valid_rows', name=op.f('ck_data_imports_counts')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_data_imports_created_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_data_imports_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_data_imports_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_data_imports')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_data_imports_restaurant_id_id')),
    schema='operational'
    )
    op.create_index(op.f('ix_data_imports_restaurant_id'), 'data_imports', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('report_exports',
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=False),
    sa.Column('period_type', sa.String(length=20), nullable=False),
    sa.Column('waste_category', sa.String(length=80), nullable=True),
    sa.Column('search', sa.String(length=200), nullable=True),
    sa.Column('sort_order', sa.String(length=20), nullable=False),
    sa.Column('file_format', sa.String(length=10), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('storage_key', sa.String(length=100), nullable=True),
    sa.Column('generation_status', sa.String(length=20), nullable=False),
    sa.Column('downloaded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_recipient', sa.String(length=254), nullable=True),
    sa.Column('email_subject', sa.String(length=200), nullable=True),
    sa.Column('email_message', sa.Text(), nullable=True),
    sa.Column('email_status', sa.String(length=20), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("email_status IN ('not_requested','not_configured','pending','sent','failed')", name=op.f('ck_report_exports_email_status')),
    sa.CheckConstraint("file_format IN ('pdf','xlsx')", name=op.f('ck_report_exports_format')),
    sa.CheckConstraint("generation_status != 'ready' OR (storage_key IS NOT NULL AND file_name IS NOT NULL)", name=op.f('ck_report_exports_ready_file')),
    sa.CheckConstraint("generation_status IN ('requested','ready','failed')", name=op.f('ck_report_exports_generation_status')),
    sa.CheckConstraint('ends_on >= starts_on', name=op.f('ck_report_exports_dates')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_report_exports_created_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_report_exports_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_report_exports_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_exports')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_report_exports_restaurant_id_id')),
    schema='operational'
    )
    op.create_index(op.f('ix_report_exports_restaurant_id'), 'report_exports', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('training_exports',
    sa.Column('triggered_by', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('changed_since', sa.DateTime(timezone=True), nullable=True),
    sa.Column('changed_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('restaurant_count', sa.Integer(), nullable=False),
    sa.Column('first_operation_date', sa.Date(), nullable=True),
    sa.Column('last_operation_date', sa.Date(), nullable=True),
    sa.Column('storage_path', sa.String(length=500), nullable=True),
    sa.Column('sha256', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error_message', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status != 'completed' OR (storage_path IS NOT NULL AND sha256 IS NOT NULL AND row_count > 0)", name=op.f('ck_training_exports_completed_file')),
    sa.CheckConstraint("status IN ('completed','empty','failed')", name=op.f('ck_training_exports_status')),
    sa.CheckConstraint("triggered_by IN ('schedule','manual')", name=op.f('ck_training_exports_trigger')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_training_exports_created_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_training_exports')),
    schema='operational'
    )
    op.create_table('user_sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_agent', sa.String(length=500), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['restaurant_id', 'user_id'], ['operational.users.restaurant_id', 'operational.users.id'], name=op.f('fk_user_sessions_restaurant_id_user_id_users')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_user_sessions_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_user_sessions_token_hash')),
    schema='operational'
    )
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False, schema='operational')
    op.create_index(op.f('ix_user_sessions_restaurant_id'), 'user_sessions', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('weekly_predictions',
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('draft','saved')", name=op.f('ck_weekly_predictions_status')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_weekly_predictions_created_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_weekly_predictions_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_weekly_predictions_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_weekly_predictions')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_weekly_predictions_restaurant_id_id')),
    schema='prediction'
    )
    op.create_index(op.f('ix_weekly_predictions_restaurant_id'), 'weekly_predictions', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('evaluation_predictions',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('observation_date', sa.Date(), nullable=False),
    sa.Column('fold', sa.Integer(), nullable=True),
    sa.Column('actual_kg', sa.Float(), nullable=False),
    sa.Column('predicted_kg', sa.Float(), nullable=False),
    sa.Column('error_kg', sa.Float(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('seed','actuals')", name=op.f('ck_evaluation_predictions_source')),
    sa.CheckConstraint("scope IN ('oof_dev','test')", name=op.f('ck_evaluation_predictions_scope')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_evaluation_predictions_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evaluation_predictions')),
    schema='model_analysis'
    )
    op.create_index('ix_evaluation_predictions_version_scope_date', 'evaluation_predictions', ['model_version_id', 'scope', 'observation_date'], unique=False, schema='model_analysis')
    op.create_table('evaluation_reports',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('file_format', sa.String(length=10), nullable=False),
    sa.Column('storage_path', sa.String(length=500), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("file_format IN ('xlsx','pdf')", name=op.f('ck_evaluation_reports_format')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_evaluation_reports_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evaluation_reports')),
    sa.UniqueConstraint('model_version_id', 'file_format', name=op.f('uq_evaluation_reports_model_version_id_file_format')),
    schema='model_analysis'
    )
    op.create_table('feature_importances',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('feature', sa.String(length=80), nullable=False),
    sa.Column('importance_mae', sa.Float(), nullable=False),
    sa.Column('importance_std', sa.Float(), nullable=False),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_feature_importances_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feature_importances')),
    sa.UniqueConstraint('model_version_id', 'feature', name=op.f('uq_feature_importances_model_version_id_feature')),
    schema='model_analysis'
    )
    op.create_table('model_evaluations',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('n_rows', sa.Integer(), nullable=False),
    sa.Column('mae', sa.Float(), nullable=False),
    sa.Column('mse', sa.Float(), nullable=False),
    sa.Column('rmse', sa.Float(), nullable=False),
    sa.Column('mape', sa.Float(), nullable=False),
    sa.Column('r2', sa.Float(), nullable=False),
    sa.Column('interval_coverage', sa.Float(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("scope IN ('cv_dev','test','baseline_test')", name=op.f('ck_model_evaluations_scope')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_model_evaluations_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_evaluations')),
    sa.UniqueConstraint('model_version_id', 'scope', name=op.f('uq_model_evaluations_model_version_id_scope')),
    schema='model_analysis'
    )
    op.create_table('sensitivity_curves',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('staff_experience', sa.String(length=20), nullable=False),
    sa.Column('special_event', sa.Boolean(), nullable=False),
    sa.Column('meals_prepared', sa.Integer(), nullable=False),
    sa.Column('predicted_kg', sa.Float(), nullable=False),
    sa.Column('within_training_range', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_sensitivity_curves_model_version_id_model_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sensitivity_curves')),
    sa.UniqueConstraint('model_version_id', 'staff_experience', 'special_event', 'meals_prepared', name=op.f('uq_sensitivity_curves_model_version_id_staff_experience_special_event_meals_prepared')),
    schema='model_analysis'
    )
    op.create_table('daily_operations',
    sa.Column('operation_date', sa.Date(), nullable=False),
    sa.Column('meals_prepared', sa.Integer(), nullable=False),
    sa.Column('kitchen_staff', sa.Integer(), nullable=False),
    sa.Column('staff_experience', sa.String(length=20), nullable=False),
    sa.Column('special_event', sa.Boolean(), nullable=False),
    sa.Column('event_type', sa.String(length=120), nullable=True),
    sa.Column('temperature_c', sa.Numeric(precision=7, scale=2), nullable=False),
    sa.Column('humidity_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('previous_waste_kg', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('waste_category', sa.String(length=80), nullable=True),
    sa.Column('actual_waste_kg', sa.Numeric(precision=12, scale=4), nullable=True),
    sa.Column('manager_notes', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('import_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('manual','import')", name=op.f('ck_daily_operations_source')),
    sa.CheckConstraint("staff_experience IN ('beginner','intermediate','expert')", name=op.f('ck_daily_operations_experience')),
    sa.CheckConstraint('meals_prepared >= 0 AND kitchen_staff > 0 AND humidity_percent BETWEEN 0 AND 100 AND (actual_waste_kg IS NULL OR actual_waste_kg >= 0) AND (previous_waste_kg IS NULL OR previous_waste_kg >= 0)', name=op.f('ck_daily_operations_values')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_daily_operations_created_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_daily_operations_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'import_id'], ['operational.data_imports.restaurant_id', 'operational.data_imports.id'], name=op.f('fk_daily_operations_restaurant_id_import_id_data_imports')),
    sa.ForeignKeyConstraint(['restaurant_id', 'updated_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_daily_operations_updated_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_daily_operations_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by'], ['operational.users.id'], name=op.f('fk_daily_operations_updated_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_daily_operations')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_daily_operations_restaurant_id_id')),
    sa.UniqueConstraint('restaurant_id', 'operation_date', name=op.f('uq_daily_operations_restaurant_id_operation_date')),
    schema='operational'
    )
    op.create_index(op.f('ix_daily_operations_restaurant_id'), 'daily_operations', ['restaurant_id'], unique=False, schema='operational')
    op.create_index(op.f('ix_daily_operations_updated_at'), 'daily_operations', ['updated_at'], unique=False, schema='operational')
    op.create_table('email_deliveries',
    sa.Column('report_export_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('transport', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('message_id', sa.String(length=160), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_error', sa.String(length=500), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending','sent','failed') AND transport = 'mailpit'", name=op.f('ck_email_deliveries_status')),
    sa.CheckConstraint('attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts', name=op.f('ck_email_deliveries_attempts')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_email_deliveries_created_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_email_deliveries_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'report_export_id'], ['operational.report_exports.restaurant_id', 'operational.report_exports.id'], name=op.f('fk_email_deliveries_restaurant_id_report_export_id_report_exports')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_email_deliveries_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_deliveries')),
    sa.UniqueConstraint('message_id', name=op.f('uq_email_deliveries_message_id')),
    sa.UniqueConstraint('report_export_id', name=op.f('uq_email_deliveries_report_export_id')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_email_deliveries_restaurant_id_id')),
    schema='operational'
    )
    op.create_index(op.f('ix_email_deliveries_next_attempt_at'), 'email_deliveries', ['next_attempt_at'], unique=False, schema='operational')
    op.create_index(op.f('ix_email_deliveries_restaurant_id'), 'email_deliveries', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('inference_logs',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('model_version_id', sa.Uuid(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Numeric(precision=12, scale=3), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('error_message', sa.String(length=300), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('daily','weekly','scenario','preview')", name=op.f('ck_inference_logs_source')),
    sa.CheckConstraint('row_count >= 0 AND duration_ms >= 0', name=op.f('ck_inference_logs_values')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_inference_logs_model_version_id_model_versions')),
    sa.ForeignKeyConstraint(['restaurant_id', 'user_id'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_inference_logs_user_id_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_inference_logs_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['operational.users.id'], name=op.f('fk_inference_logs_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inference_logs')),
    schema='prediction'
    )
    op.create_index('ix_inference_logs_restaurant_created', 'inference_logs', ['restaurant_id', 'created_at'], unique=False, schema='prediction')
    op.create_index(op.f('ix_inference_logs_restaurant_id'), 'inference_logs', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('prediction_days',
    sa.Column('weekly_prediction_id', sa.Uuid(), nullable=False),
    sa.Column('prediction_date', sa.Date(), nullable=False),
    sa.Column('input_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['restaurant_id', 'weekly_prediction_id'], ['prediction.weekly_predictions.restaurant_id', 'prediction.weekly_predictions.id'], name=op.f('fk_prediction_days_restaurant_id_weekly_prediction_id_weekly_predictions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_prediction_days_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prediction_days')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_prediction_days_restaurant_id_id')),
    sa.UniqueConstraint('weekly_prediction_id', 'prediction_date', name=op.f('uq_prediction_days_weekly_prediction_id_prediction_date')),
    schema='prediction'
    )
    op.create_index(op.f('ix_prediction_days_restaurant_id'), 'prediction_days', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('data_corrections',
    sa.Column('daily_operation_id', sa.Uuid(), nullable=False),
    sa.Column('changed_by', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('previous_values', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('new_values', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('previous_version', sa.Integer(), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['operational.users.id'], name=op.f('fk_data_corrections_changed_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'changed_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_data_corrections_changed_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'daily_operation_id'], ['operational.daily_operations.restaurant_id', 'operational.daily_operations.id'], name=op.f('fk_data_corrections_restaurant_id_daily_operation_id_daily_operations')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_data_corrections_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_data_corrections')),
    schema='operational'
    )
    op.create_index(op.f('ix_data_corrections_restaurant_id'), 'data_corrections', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('email_attempts',
    sa.Column('email_delivery_id', sa.Uuid(), nullable=False),
    sa.Column('attempt_number', sa.Integer(), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('error_message', sa.String(length=500), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('attempt_number > 0', name=op.f('ck_email_attempts_attempt_number')),
    sa.ForeignKeyConstraint(['restaurant_id', 'email_delivery_id'], ['operational.email_deliveries.restaurant_id', 'operational.email_deliveries.id'], name=op.f('fk_email_attempts_restaurant_id_email_delivery_id_email_deliveries')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_email_attempts_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_attempts')),
    sa.UniqueConstraint('email_delivery_id', 'attempt_number', name=op.f('uq_email_attempts_email_delivery_id_attempt_number')),
    schema='operational'
    )
    op.create_index(op.f('ix_email_attempts_restaurant_id'), 'email_attempts', ['restaurant_id'], unique=False, schema='operational')
    op.create_table('plan_revisions',
    sa.Column('prediction_day_id', sa.Uuid(), nullable=False),
    sa.Column('changed_by', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('previous_input', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('new_input', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['operational.users.id'], name=op.f('fk_plan_revisions_changed_by_users')),
    sa.ForeignKeyConstraint(['restaurant_id', 'changed_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_plan_revisions_changed_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'prediction_day_id'], ['prediction.prediction_days.restaurant_id', 'prediction.prediction_days.id'], name=op.f('fk_plan_revisions_restaurant_id_prediction_day_id_prediction_days')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_plan_revisions_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plan_revisions')),
    schema='prediction'
    )
    op.create_index(op.f('ix_plan_revisions_restaurant_id'), 'plan_revisions', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('portion_scenarios',
    sa.Column('daily_operation_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('operation_version', sa.Integer(), nullable=False),
    sa.Column('application_date', sa.Date(), nullable=False),
    sa.Column('baseline_portions', sa.Integer(), nullable=False),
    sa.Column('simulated_portions', sa.Integer(), nullable=False),
    sa.Column('kitchen_staff', sa.Integer(), nullable=False),
    sa.Column('reduction_percent', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('predicted_waste_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('baseline_waste_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('savings_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('savings_amount', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('portions_per_staff', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('input_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('settings_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('applied_by', sa.Uuid(), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('draft','saved','applied')", name=op.f('ck_portion_scenarios_status')),
    sa.CheckConstraint('baseline_portions >= 0 AND simulated_portions >= 0 AND kitchen_staff > 0 AND reduction_percent BETWEEN 0 AND 100', name=op.f('ck_portion_scenarios_values')),
    sa.ForeignKeyConstraint(['applied_by'], ['operational.users.id'], name=op.f('fk_portion_scenarios_applied_by_users')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_portion_scenarios_created_by_users')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_portion_scenarios_model_version_id_model_versions')),
    sa.ForeignKeyConstraint(['restaurant_id', 'applied_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_portion_scenarios_applied_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_portion_scenarios_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'daily_operation_id'], ['operational.daily_operations.restaurant_id', 'operational.daily_operations.id'], name=op.f('fk_portion_scenarios_restaurant_id_daily_operation_id_daily_operations')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_portion_scenarios_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_portion_scenarios')),
    schema='prediction'
    )
    op.create_index(op.f('ix_portion_scenarios_restaurant_id'), 'portion_scenarios', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('prediction_results',
    sa.Column('model_version_id', sa.Uuid(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('daily_operation_id', sa.Uuid(), nullable=True),
    sa.Column('prediction_day_id', sa.Uuid(), nullable=True),
    sa.Column('operation_version', sa.Integer(), nullable=True),
    sa.Column('predicted_waste_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('interval_lower_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('interval_upper_kg', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('risk_level', sa.String(length=20), nullable=False),
    sa.Column('portions_per_staff', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('estimated_waste_cost', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('outside_training_range', sa.Boolean(), nullable=False),
    sa.Column('input_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('settings_snapshot', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("risk_level IN ('safe','warning','high')", name=op.f('ck_prediction_results_risk')),
    sa.CheckConstraint('(daily_operation_id IS NOT NULL AND prediction_day_id IS NULL) OR (daily_operation_id IS NULL AND prediction_day_id IS NOT NULL)', name=op.f('ck_prediction_results_parent')),
    sa.CheckConstraint('predicted_waste_kg >= 0 AND interval_lower_kg >= 0 AND interval_upper_kg >= interval_lower_kg', name=op.f('ck_prediction_results_values')),
    sa.ForeignKeyConstraint(['created_by'], ['operational.users.id'], name=op.f('fk_prediction_results_created_by_users')),
    sa.ForeignKeyConstraint(['model_version_id'], ['model_analysis.model_versions.id'], name=op.f('fk_prediction_results_model_version_id_model_versions')),
    sa.ForeignKeyConstraint(['restaurant_id', 'created_by'], ['operational.users.restaurant_id', 'operational.users.id'], name='fk_prediction_results_created_by_same_restaurant'),
    sa.ForeignKeyConstraint(['restaurant_id', 'daily_operation_id'], ['operational.daily_operations.restaurant_id', 'operational.daily_operations.id'], name=op.f('fk_prediction_results_restaurant_id_daily_operation_id_daily_operations')),
    sa.ForeignKeyConstraint(['restaurant_id', 'prediction_day_id'], ['prediction.prediction_days.restaurant_id', 'prediction.prediction_days.id'], name=op.f('fk_prediction_results_restaurant_id_prediction_day_id_prediction_days')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_prediction_results_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_prediction_results')),
    sa.UniqueConstraint('restaurant_id', 'id', name=op.f('uq_prediction_results_restaurant_id_id')),
    schema='prediction'
    )
    op.create_index('ix_prediction_results_restaurant_created', 'prediction_results', ['restaurant_id', 'created_at'], unique=False, schema='prediction')
    op.create_index(op.f('ix_prediction_results_restaurant_id'), 'prediction_results', ['restaurant_id'], unique=False, schema='prediction')
    op.create_table('notifications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('prediction_result_id', sa.Uuid(), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('restaurant_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['restaurant_id', 'prediction_result_id'], ['prediction.prediction_results.restaurant_id', 'prediction.prediction_results.id'], name=op.f('fk_notifications_restaurant_id_prediction_result_id_prediction_results')),
    sa.ForeignKeyConstraint(['restaurant_id', 'user_id'], ['operational.users.restaurant_id', 'operational.users.id'], name=op.f('fk_notifications_restaurant_id_user_id_users')),
    sa.ForeignKeyConstraint(['restaurant_id'], ['operational.restaurants.id'], name=op.f('fk_notifications_restaurant_id_restaurants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    schema='operational'
    )
    op.create_index(op.f('ix_notifications_restaurant_id'), 'notifications', ['restaurant_id'], unique=False, schema='operational')

def downgrade():
    op.drop_index(op.f('ix_notifications_restaurant_id'), table_name='notifications', schema='operational')
    op.drop_table('notifications', schema='operational')
    op.drop_index(op.f('ix_prediction_results_restaurant_id'), table_name='prediction_results', schema='prediction')
    op.drop_index('ix_prediction_results_restaurant_created', table_name='prediction_results', schema='prediction')
    op.drop_table('prediction_results', schema='prediction')
    op.drop_index(op.f('ix_portion_scenarios_restaurant_id'), table_name='portion_scenarios', schema='prediction')
    op.drop_table('portion_scenarios', schema='prediction')
    op.drop_index(op.f('ix_plan_revisions_restaurant_id'), table_name='plan_revisions', schema='prediction')
    op.drop_table('plan_revisions', schema='prediction')
    op.drop_index(op.f('ix_email_attempts_restaurant_id'), table_name='email_attempts', schema='operational')
    op.drop_table('email_attempts', schema='operational')
    op.drop_index(op.f('ix_data_corrections_restaurant_id'), table_name='data_corrections', schema='operational')
    op.drop_table('data_corrections', schema='operational')
    op.drop_index(op.f('ix_prediction_days_restaurant_id'), table_name='prediction_days', schema='prediction')
    op.drop_table('prediction_days', schema='prediction')
    op.drop_index(op.f('ix_inference_logs_restaurant_id'), table_name='inference_logs', schema='prediction')
    op.drop_index('ix_inference_logs_restaurant_created', table_name='inference_logs', schema='prediction')
    op.drop_table('inference_logs', schema='prediction')
    op.drop_index(op.f('ix_email_deliveries_restaurant_id'), table_name='email_deliveries', schema='operational')
    op.drop_index(op.f('ix_email_deliveries_next_attempt_at'), table_name='email_deliveries', schema='operational')
    op.drop_table('email_deliveries', schema='operational')
    op.drop_index(op.f('ix_daily_operations_updated_at'), table_name='daily_operations', schema='operational')
    op.drop_index(op.f('ix_daily_operations_restaurant_id'), table_name='daily_operations', schema='operational')
    op.drop_table('daily_operations', schema='operational')
    op.drop_table('sensitivity_curves', schema='model_analysis')
    op.drop_table('model_evaluations', schema='model_analysis')
    op.drop_table('feature_importances', schema='model_analysis')
    op.drop_table('evaluation_reports', schema='model_analysis')
    op.drop_index('ix_evaluation_predictions_version_scope_date', table_name='evaluation_predictions', schema='model_analysis')
    op.drop_table('evaluation_predictions', schema='model_analysis')
    op.drop_index(op.f('ix_weekly_predictions_restaurant_id'), table_name='weekly_predictions', schema='prediction')
    op.drop_table('weekly_predictions', schema='prediction')
    op.drop_index(op.f('ix_user_sessions_restaurant_id'), table_name='user_sessions', schema='operational')
    op.drop_index(op.f('ix_user_sessions_expires_at'), table_name='user_sessions', schema='operational')
    op.drop_table('user_sessions', schema='operational')
    op.drop_table('training_exports', schema='operational')
    op.drop_index(op.f('ix_report_exports_restaurant_id'), table_name='report_exports', schema='operational')
    op.drop_table('report_exports', schema='operational')
    op.drop_index(op.f('ix_data_imports_restaurant_id'), table_name='data_imports', schema='operational')
    op.drop_table('data_imports', schema='operational')
    op.drop_table('tuning_trials', schema='model_analysis')
    op.drop_index('uq_model_versions_single_active', table_name='model_versions', schema='model_analysis', postgresql_where=sa.text('is_active'))
    op.drop_table('model_versions', schema='model_analysis')
    op.drop_index(op.f('ix_users_restaurant_id'), table_name='users', schema='operational')
    op.drop_table('users', schema='operational')
    op.drop_table('restaurant_settings', schema='operational')
    op.drop_table('training_runs', schema='model_analysis')
    op.drop_table('restaurants', schema='operational')
    op.drop_table('dataset_versions', schema='model_analysis')
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}"')
