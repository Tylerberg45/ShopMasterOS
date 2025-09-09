# oil_change_tracker/app/main.py
from fastapi import FastAPI
from .database import engine  # ensures DB init runs at startup

app = FastAPI(title="Oil Change Tracker (MVP)")

# --- Health endpoints ---
@app.get("/health")
def health():
    return {"ok": True}

from sqlalchemy import text
@app.get("/health/db")
def db_health():
    with engine.connect() as conn:
        version = conn.execute(text("select version()")).scalar()
    return {"ok": True, "postgres_version": version}

# --- Include routers (if they exist) ---
try:
    from .routers import customers as customers_router
    from .routers import vehicles as vehicles_router
    app.include_router(customers_router.router, prefix="/customers", tags=["customers"])
    app.include_router(vehicles_router.router, prefix="/vehicles", tags=["vehicles"])
except Exception as e:
    # Safe to ignore missing routers during early setup
    print(f"⚠️ Skipped loading routers: {e}")
