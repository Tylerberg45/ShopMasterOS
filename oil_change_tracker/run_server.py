#!/usr/bin/env python3
import subprocess
import sys
import os

# Explicit check for uvicorn
try:
    import uvicorn
    print("✅ uvicorn is available")
except ImportError:
    print("❌ uvicorn not found, installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]"])
    import uvicorn

# Start the app
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Oil Change Tracker on port {port}")
    print("📍 Using uvicorn directly (NOT gunicorn)")
    
    # Import the app
    from app.main import app
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=port,
        log_level="info",
        access_log=True
    )
