# oil_change_tracker/app/database.py
import os
import pathlib
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1) Read from env (Railway/Render sets this); fallback is a local file in the repo root.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Auto-construct Postgres URL if not provided but component vars exist (Railway style)
if not DATABASE_URL:
    # Support both POSTGRES_* and PG* variants
    host = os.getenv("POSTGRES_HOST") or os.getenv("PGHOST")
    user = os.getenv("POSTGRES_USER") or os.getenv("PGUSER")
    password = os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD")
    database = os.getenv("POSTGRES_DATABASE") or os.getenv("PGDATABASE")
    port = os.getenv("POSTGRES_PORT") or os.getenv("PGPORT") or "5432"
    if host and user and password and database:
        DATABASE_URL = f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
        print("🔧 Constructed DATABASE_URL from component env vars")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./oilchange.db"

# Handle Railway's PostgreSQL URL format if provided
if DATABASE_URL.startswith("postgresql://"):
    # Railway sometimes uses postgresql:// but SQLAlchemy prefers postgresql+psycopg2://
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# 2) SQLite needs special connect args; others (Postgres, MySQL) don't.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# 3) If using SQLite, make sure the directory for the DB file exists (no errors on first run).
if DATABASE_URL.startswith("sqlite:///"):
    # Extract the path portion after "sqlite:///"
    db_path_str = DATABASE_URL.replace("sqlite:///", "", 1)
    db_path = pathlib.Path(db_path_str)
    # If it's relative, make it absolute relative to current working dir
    if not db_path.is_absolute():
        db_path = pathlib.Path.cwd() / db_path
    # Ensure parent directory exists (e.g., ./, /var/data, etc.)
    db_path.parent.mkdir(parents=True, exist_ok=True)

# 4) Create engine + session factory + base class
engine = create_engine(
    DATABASE_URL,
    echo=False,              # flip to True if you want SQL logs
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# 5) FastAPI dependency to get a DB session per request
def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
