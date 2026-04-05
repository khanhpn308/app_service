import time

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _pymysql_connect():
    """Direct PyMySQL connect — matches manual tests and avoids URL/encoding quirks."""
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
    )


def get_engine() -> Engine:
    return create_engine(
        "mysql+pymysql://",
        creator=_pymysql_connect,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def db_ping() -> float:
    started_at = time.perf_counter()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    latency_ms = (time.perf_counter() - started_at) * 1000
    return round(latency_ms, 2)

