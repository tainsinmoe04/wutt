"""SQLAlchemy database engine, session factory, and declarative base.

Uses SQLite for MVP with check_same_thread=False (required for FastAPI's
async thread pool).  Connection string comes from config.settings.database_url.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from config import settings

# ── Engine ─────────────────────────────────────────────
# SQLite requires check_same_thread=False when used with FastAPI
# because FastAPI's thread pool may handle requests across threads.
connect_args: dict[str, bool] = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,
)

# ── Session ────────────────────────────────────────────
SessionLocal: sessionmaker = sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
)


# ── Base ───────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy ORM models."""
    pass


# ── Dependency ─────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session and closes it after use.

    Usage in route:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Call once at application startup."""
    Base.metadata.create_all(bind=engine)
