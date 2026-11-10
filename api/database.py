from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from api.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
