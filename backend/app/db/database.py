from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings


settings = get_settings()
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 3},
)


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
