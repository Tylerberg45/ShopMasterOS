@echo off
setlocal EnableDelayedExpansion
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ===============================================
echo  Oil Change Tracker - DEV (Hot Reload)
echo ===============================================
echo.

REM Ensure Python is real (not Store alias)
python --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Please install Python 3.11 and re-open this window.
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

REM Ensure local venv exists
if not exist .venv (
  echo Creating local Python virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate

REM Install deps if needed
pip show fastapi >nul 2>nul || pip install -r requirements.txt

REM Detect active IPv4 (fallback to computer name)
set APP_IP=
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "try { (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.AddressState -eq 'Preferred' } | Select-Object -First 1 -ExpandProperty IPAddress) } catch { '' }"` ) do set APP_IP=%%A
if "%APP_IP%"=="" set APP_IP=%COMPUTERNAME%

set APP_URL=http://%APP_IP%:8000
echo App running at: %APP_URL%
start "" %APP_URL%

REM Start keep-awake helper (hidden)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT_DIR%StayAwake.ps1"

echo Starting server...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo Server exited. Press any key to close.
pause
