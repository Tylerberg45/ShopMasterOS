# oil_change_tracker/app/database.py
import os
import pathlib
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
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
def _mask_url(url: str) -> str:
    try:
        if '://' not in url:
            return url
        scheme, rest = url.split('://', 1)
        if '@' not in rest:
            return url
        creds, tail = rest.split('@', 1)
        if ':' in creds:
            user, _pw = creds.split(':', 1)
            return f"{scheme}://{user}:***@{tail}"
        return f"{scheme}://***@{tail}"
    except Exception:
        return url

def _build_engine(url: str):
    print(f"🗄️  Initializing DB engine: {_mask_url(url)}")
    return create_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

engine = None
_engine_error = None
try:
    engine = _build_engine(DATABASE_URL)
    # Quick connectivity test (non-fatal if fails)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ Database connectivity OK")
except Exception as e:
    _engine_error = e
    print(f"❌ Failed to initialize primary database URL: {e}" )
    if os.getenv("DB_FALLBACK_SQLITE", "0") in ("1", "true", "yes"):
        fallback_url = "sqlite:///./oilchange.db"
        print("⚠️  Falling back to SQLite due to DB_FALLBACK_SQLITE=1")
        DATABASE_URL = fallback_url
        connect_args = {"check_same_thread": False}
        engine = _build_engine(fallback_url)
    else:
        # Re-raise so startup fails clearly
        raise

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# 5) FastAPI dependency to get a DB session per request
def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
