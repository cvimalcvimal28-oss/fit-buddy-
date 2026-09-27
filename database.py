"""
database.py
Sets up the SQLite connection and SQLAlchemy session used across FitBuddy.
"""

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or "sqlite:///./fitbuddy.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
else:
    engine_options.update(
        pool_size=max(1, int(os.getenv("DB_POOL_SIZE", "5"))),
        max_overflow=max(0, int(os.getenv("DB_MAX_OVERFLOW", "10"))),
        pool_timeout=max(1, int(os.getenv("DB_POOL_TIMEOUT", "30"))),
        pool_recycle=max(60, int(os.getenv("DB_POOL_RECYCLE", "1800"))),
    )
engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once on startup."""
    from app import models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "password_hash" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"))
        if "email" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(254)"))
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
        )
