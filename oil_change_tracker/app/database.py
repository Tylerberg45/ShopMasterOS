# oil_change_tracker/app/database.py
import os, pathlib
from typing import Iterator
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

APP_ENV = os.getenv("APP_ENV", "prod").lower()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Auto-build from component vars (nice-to-have)
if not DATABASE_URL:
    host = os.getenv("POSTGRES_HOST") or os.getenv("PGHOST")
    user = os.getenv("POSTGRES_USER") or os.getenv("PGUSER")
    password = os.getenv("POSTGRES_PASSWORD") or os.getenv("PGPASSWORD")
    database = os.getenv("POSTGRES_DATABASE") or os.getenv("PGDATABASE")
    port = os.getenv("POSTGRES_PORT") or os.getenv("PGPORT") or "5432"
    if host and user and password and database:
        DATABASE_URL = f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(database)}"
        print("🔧 Constructed DATABASE_URL from component env vars")

# ---- normalize scheme for SQLAlchemy ----
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# ---- no silent SQLite in prod ----
if not DATABASE_URL:
    if APP_ENV in ("dev", "local"):
        DATABASE_URL = "sqlite:///./oilchange.db"
        print("🧪 Using local SQLite (APP_ENV=dev/local)")
    else:
        raise RuntimeError("DATABASE_URL is required in production")

# SQLite needs this connect arg; Postgres does not
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Ensure SQLite dir exists (dev only)
if DATABASE_URL.startswith("sqlite:///"):
    db_path = pathlib.Path(DATABASE_URL.replace("sqlite:///", "", 1))
    if not db_path.is_absolute():
        db_path = pathlib.Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

def _mask_url(url: str) -> str:
    try:
        scheme, rest = url.split("://", 1)
        if "@" not in rest:
            return url
        creds, tail = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{tail}"
    except Exception:
        return url

def _build_engine(url: str):
    print(f"🗄️  Initializing DB engine: {_mask_url(url)}")
    return create_engine(
        url,
        echo=True,  # Enable SQL query logging for debugging
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )

engine = _build_engine(DATABASE_URL)

# quick connectivity test (fail fast)
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
print("✅ Database connectivity OK")

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
