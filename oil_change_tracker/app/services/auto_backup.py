import os
import shutil
import time
import threading
from datetime import datetime
from ..core.config import DATABASE_URL

def _db_file_from_url(db_url: str) -> str | None:
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "", 1)
        return os.path.abspath(path)
    return None

def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def _timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def backup_once():
    db_path = _db_file_from_url(DATABASE_URL)
    if not db_path or not os.path.exists(db_path):
        return False
    backups_dir = os.path.abspath(os.path.join(os.path.dirname(db_path), "backups"))
    _ensure_dir(backups_dir)
    fname = f"oilchange_{_timestamp()}.db"
    dest = os.path.join(backups_dir, fname)
    shutil.copy2(db_path, dest)
    return True

def start_periodic_backup(interval_hours: int = 6):
    # Backup once at startup, then every N hours
    def worker():
        backup_once()
        while True:
            time.sleep(interval_hours * 3600)
            try:
                backup_once()
            except Exception:
                pass
    t = threading.Thread(target=worker, daemon=True)
    t.start()
