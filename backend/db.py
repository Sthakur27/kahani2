import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://storysim_app:storysim_dev_pw@localhost:5432/storysim_db",
)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a session and always closes it. Within a single
    request FastAPI caches this, so auth + handlers share the same session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
