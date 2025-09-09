# oil_change_tracker/app/database.py
import os
from typing import Iterator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# --- Require DATABASE_URL ---
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL must be set (Postgres required)")

# Railway and some providers still hand out "postgres://"
# SQLAlchemy prefers "postgresql+psycopg2://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# --- Create engine ---
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
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )

engine = _build_engine(DATABASE_URL)

# Quick connectivity test (fail fast if bad)
with engine.connect() as conn:
    conn.execute(text("SELECT 1"))
print("✅ Database connectivity OK")

# --- Session + Base ---
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

# FastAPI dependency
def get_db() -> Iterator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
