import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

def _build_database_url() -> str:
    return os.environ["DATABASE_URL"]

engine = create_engine(_build_database_url())
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """FastAPI dependency that provides a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()