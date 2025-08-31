@echo off
setlocal
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip show fastapi >nul 2>nul || pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Done. Press any key to close.
pause
