# Oil Change Tracker (MVP)

A minimal FastAPI app to track customer oil change plans and deduct uses manually. 
Search customers by **first+last name** or **phone number**. Add vehicles and (optionally) look up VIN by **license plate** via a plug-in service.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# First run (creates SQLite db automatically)
uvicorn app.main:app --reload
```

Visit: http://127.0.0.1:8000

## Environment

Copy `.env.example` to `.env` and fill in secrets if you want plate→VIN lookups.

- `PLATE_LOOKUP_PROVIDER` = one of: `abstract`, `vinapi`, `none`
- `PLATE_LOOKUP_KEY` = your API key
- `PLATE_LOOKUP_REGION` = e.g., `US`

If left as `none` (default), the service runs in demo mode and returns a fake VIN for known sample plates (e.g., `TEST123`).

## Features
- Create/search customers (name or phone).
- Assign default oil change plan (4 changes) or custom count.
- Deduct an oil change, undo mistakes (full audit log).
- Add vehicles by license plate, with optional VIN lookup via service hook.
- Simple web UI (Jinja) + JSON APIs.
- SQLite by default; swap to Postgres via `DATABASE_URL` if needed.

## Production Reliability

For the most reliable deployment use **PostgreSQL** instead of the default SQLite file.

Why PostgreSQL:
- Ephemeral deploys: host rebuilds wipe a SQLite file unless you attach a volume.
- Scaling: multiple instances each get their own isolated SQLite database.
- Concurrency & integrity: Postgres handles simultaneous writes safely; SQLite can lock.
- Backups & tooling: Easy snapshots, metrics, and migration management.

### Switch to Postgres on Railway
1. Add a Postgres service in Railway (Add → Database → Postgres).
2. Confirm the app service now has `DATABASE_URL` in Variables (Railway usually injects automatically).
3. Redeploy the app; tables auto-create via `Base.metadata.create_all`.
4. Test: create a customer; refresh page; data persists across redeploys.
5. Verify header `X-DB-Backend: postgresql` on any response and/or visit `/admin/db-info`.

If you had existing SQLite data and want to migrate, run the migrate script locally (see below) then deploy.

### Migrate Existing Local SQLite Data
Planned helper script `scripts/migrate_sqlite_to_postgres.py` usage:
```bash
python scripts/migrate_sqlite_to_postgres.py sqlite:///./oilchange.db $DATABASE_URL
```
It will read tables and bulk insert rows skipping duplicates.

### (Temporary) Keep SQLite with Persistence
If you must keep SQLite for now:
1. Attach a Railway Volume (e.g. mount at `/data`).
2. Set env var: `DATABASE_URL=sqlite:////data/oilchange.db` (note 4 slashes after `sqlite:`).
3. Redeploy. The file will survive restarts while the volume exists.

Postgres is strongly recommended once real customer data matters.

### Admin Endpoints Security
Admin pages now require a token if you set `ADMIN_TOKEN`.

Set an environment variable:
```
ADMIN_TOKEN=choose-a-long-random-string
```

Requests must then include either:
- Header: `X-Admin-Token: <token>`
- Query param: `?admin_token=<token>`

Protected endpoints:
- `/admin/errors`
- `/admin/db-info`
- `/admin/duplicates`
- `/admin/link-customer-to-vehicle` (POST)
- `/admin/merge-customers` (POST)

If `ADMIN_TOKEN` is unset, endpoints are open (development convenience).

## Roadmap (next)
- Role-based auth
- SMS check balance (Twilio)
- Export PDF receipts
- Postgres + Alembic migrations
```



## Local install (no Python on laptop)
1. Download and unzip this folder anywhere (e.g., Downloads).
2. Double‑click `Install_Local_NoPython.bat`.
3. This installs into `%LOCALAPPDATA%\OilChangeTracker`, creates Desktop and Start Menu shortcuts, and launches the app.
4. First run downloads Miniconda and builds a local env; later runs start instantly.


## Windows quick start (Python 3.11)
1. Install Python 3.11 and check **Add Python to PATH**.
2. Disable Microsoft Store aliases for `python` and `python3` (Settings → Apps → Advanced app settings → App execution aliases).
3. Double‑click `Run_Tracker.bat` (or `Run_Tracker_Dev.bat` for hot reload).
4. Open the URL shown (e.g., `http://YOUR-PC:8000`).
