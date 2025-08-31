import os
import sys
import uvicorn

# Ensure working dir is the folder containing the executable (for bundled templates/static/db)
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
    os.chdir(os.path.dirname(sys.executable))
else:
    bundle_dir = os.path.dirname(__file__)

# Create default DB if missing
db_path = os.path.abspath(os.path.join(os.getcwd(), "oilchange.db"))
if not os.path.exists(db_path):
    open(db_path, "a").close()

from app.main import app  # import after we set cwd

if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    print("Starting Oil Change Tracker at http://127.0.0.1:8000 (or your LAN IP):")
    print("If you launched this on a work PC, other PCs can try: http://%s:8000" % os.environ.get("COMPUTERNAME", "localhost"))
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
