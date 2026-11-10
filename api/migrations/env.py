from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine, pool
from api.config import get_settings
from api.database import Base
from api import models  # noqa: F401 — daftarkan seluruh tabel

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = get_settings().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
