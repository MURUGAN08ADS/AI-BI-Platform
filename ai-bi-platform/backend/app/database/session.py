"""Database engines and session factories.

Two engines on purpose:
  * engine          — full read/write, used by ETL, auth, analytics.
  * readonly_engine — used ONLY to execute LLM-generated SQL. Combined
                      with the bi_readonly Postgres role, a malicious or
                      hallucinated write statement fails at the database
                      level even if it slipped past the SQL guard.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,     # drop dead connections instead of erroring mid-request
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

readonly_engine = create_engine(
    settings.readonly_url,
    pool_pre_ping=True,
    pool_size=5,
    # Postgres-level guarantee: this connection cannot start a write txn.
    connect_args={"options": "-c default_transaction_read_only=on"},
)


def get_db():
    """FastAPI dependency — one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
