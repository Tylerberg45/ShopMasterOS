import json, os, time
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "events.jsonl")

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def log_event(action: str, entity: str = "", details: dict | None = None, user: str | None = None):
    _ensure_dir(LOG_PATH)
    rec = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "action": action,
        "entity": entity,
        "user": user or "",
        "details": details or {},
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
