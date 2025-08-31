@echo off
setlocal EnableDelayedExpansion
set BASE=%~dp0
cd /d "%BASE%"

echo.
echo ==================================================
echo  Oil Change Tracker - Bootstrap (No Python)
echo ==================================================
echo.
echo If you see 'Stable' mode here, you're running the WRONG file.
echo Use RUN_TRACKER_NOPYTHON.BAT ONLY.
echo.

REM -------- Settings --------
set CONDA_DIR=%BASE%miniconda3
set ENV_DIR=%BASE%conda_env
set CONDA_EXE=%CONDA_DIR%\Scripts\conda.exe
set PY_EXE=%ENV_DIR%\python.exe
set UVICORN_CMD=uvicorn app.main:app --host 0.0.0.0 --port 8000
set DEV_MODE=0

REM --- Detect active IPv4 ---
set APP_IP=
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "try { (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.AddressState -eq 'Preferred' } | Select-Object -First 1 -ExpandProperty IPAddress) } catch { '' }"` ) do set APP_IP=%%A
if "%APP_IP%"=="" (
  for /f "tokens=2 delims=:" %%I in ('ipconfig ^| findstr /R "IPv4 Address"') do (
    set line=%%I
    for /f "tokens=* delims= " %%J in ("!line!") do set ip=%%J
    if not "!ip:~0,3!"=="127" if not "!ip:~0,7!"=="169.254" (
      if "!APP_IP!"=="" set APP_IP=!ip!
    )
  )
)
if "%APP_IP%"=="" set APP_IP=127.0.0.1
set APP_URL=http://%APP_IP%:8000

REM -------- Ensure Miniconda portable installed locally --------
if not exist "%CONDA_EXE%" (
  echo Miniconda not found on USB. Downloading portable installer...
  set INST=%BASE%miniconda_installer.exe
  REM Try PowerShell TLS 1.2 download
  powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -OutFile '%INST%' https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe } catch { exit 1 }"
  if errorlevel 1 (
    echo PowerShell download failed. Trying curl...
    curl -L -o "%INST%" https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
  )
  if not exist "%INST%" (
    echo [ERROR] Failed to download Miniconda. Check internet or firewall. 
    echo If this is blocked, tell me and I will ship a single-file EXE build.
    pause
    exit /b 1
  )
  echo Installing Miniconda to %CONDA_DIR% (no admin)...
  "%INST%" /InstallationType=JustMe /AddToPath=0 /RegisterPython=0 /S /D=%CONDA_DIR%
  if not exist "%CONDA_EXE%" (
    echo [ERROR] Miniconda install failed.
    pause
    exit /b 1
  )
  del /f /q "%INST%" >nul 2>nul
)

REM -------- Ensure project env exists --------
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

echo.
echo App running at: %APP_URL%
start "" %APP_URL%

REM Start keep-awake helper (hidden)
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%BASE%StayAwake.ps1"

echo Starting server...
if "%DEV_MODE%"=="1" (
  %PY_EXE% -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) else (
  %PY_EXE% -m %UVICORN_CMD%
)
echo.
echo Server exited. Press any key to close.
pause
