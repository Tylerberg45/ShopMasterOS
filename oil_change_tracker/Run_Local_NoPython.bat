@echo off
setlocal DisableDelayedExpansion
set "BASE=%LOCALAPPDATA%\OilChangeTracker"
cd /d "%BASE%"

echo.
echo ===============================================
echo  Oil Change Tracker - Local (No Python)
echo ===============================================
echo.

REM Settings
set "CONDA_DIR=%BASE%\miniconda3"
set "ENV_DIR=%BASE%\conda_env"
set "CONDA_EXE=%CONDA_DIR%\Scripts\conda.exe"
set "PY_EXE=%ENV_DIR%\python.exe"

REM Install Miniconda portable if missing
if not exist "%CONDA_EXE%" (
  echo Downloading Miniconda (first run only)...
  set "INST=%BASE%\miniconda_installer.exe"
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -OutFile '%INST%' https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe } catch { exit 1 }"
  if errorlevel 1 (
    echo PowerShell download failed. Trying curl...
    curl -L -o "%INST%" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
  )
  if not exist "%INST%" (
    echo [ERROR] Failed to download Miniconda. Check internet or firewall.
    pause
    exit /b 1
  )
  echo Installing Miniconda to "%CONDA_DIR%" (no admin)...
  "%INST%" /InstallationType=JustMe /AddToPath=0 /RegisterPython=0 /S /D=%CONDA_DIR%
  if not exist "%CONDA_EXE%" (
    echo [ERROR] Miniconda install failed.
    pause
    exit /b 1
  )
  del /f /q "%INST%" >nul 2>nul
)

REM Ensure project env exists
if not exist "%PY_EXE%" (
  echo Creating local conda env...
  call "%CONDA_DIR%\Scripts\activate.bat" "%CONDA_DIR%"
  "%CONDA_EXE%" create -y -p "%ENV_DIR%" python=3.11
  if errorlevel 1 (
    echo [ERROR] Failed to create conda env.
    pause
    exit /b 1
  )
  call "%CONDA_DIR%\Scripts\activate.bat" "%ENV_DIR%"
  echo Installing Python deps (first run only)...
  pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
  )
) else (
  call "%CONDA_DIR%\Scripts\activate.bat" "%ENV_DIR%"
)

REM Start keep-awake helper (hidden)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%BASE%\StayAwake.ps1"

REM Compute simple URL
set "APP_URL=http://%COMPUTERNAME%:8000"
echo App running at: %APP_URL%
start "" %APP_URL%

echo Starting server...
"%PY_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Server exited. Press any key to close.
pause
