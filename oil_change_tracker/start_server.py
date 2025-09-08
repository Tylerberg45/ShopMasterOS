#!/usr/bin/env python3
"""
Persistent server starter that keeps the FastAPI app running
"""
import subprocess
import time
import sys
import os
from pathlib import Path

def start_server():
    """Start the uvicorn server with auto-restart on failure"""
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "app.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000", 
        "--reload"
    ]
    
    print("🚀 Starting Oil Change Tracker...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🔄 Auto-restart enabled for code changes")
    print("⏰ Will restart automatically if server crashes")
    print("-" * 50)
    
    while True:
        try:
            # Change to the correct directory
            os.chdir(Path(__file__).parent)
            
            # Start the server process
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                bufsize=1
            )
            
            # Print output in real-time
            for line in process.stdout:
                print(line.rstrip())
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down server...")
            process.terminate()
            break
        except Exception as e:
            print(f"❌ Server crashed: {e}")
            print("🔄 Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    start_server()
