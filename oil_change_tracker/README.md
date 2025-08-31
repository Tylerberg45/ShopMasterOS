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
