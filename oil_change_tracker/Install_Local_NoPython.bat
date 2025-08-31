@echo off
setlocal DisableDelayedExpansion
set SRC=%~dp0
set "DST=%LOCALAPPDATA%\OilChangeTracker"
echo.
echo ===============================================
echo  Installing Oil Change Tracker (No Python)
echo ===============================================
echo Target: %DST%
echo.

if not exist "%DST%" mkdir "%DST%"
echo Copying files...
xcopy "%SRC%*" "%DST%\" /E /I /Y >nul

echo Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -File "%DST%\Create_Shortcuts.ps1"

echo Launching the app...
cd /d "%DST%"
call "%DST%\Run_Local_NoPython.bat"
