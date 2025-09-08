#!/usr/bin/env python3
"""
Simple Railway startup script for Oil Change Tracker
"""
import uvicorn
from app.main import app

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
