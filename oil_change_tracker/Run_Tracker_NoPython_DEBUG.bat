@echo off
setlocal EnableDelayedExpansion
set BASE=%~dp0
cd /d "%BASE%"

if not exist logs mkdir logs
set TS=%DATE:/=-%_%TIME::=-%
set TS=%TS: =_%
set LOG=logs\startup_%TS%.log

echo Writing debug log to %LOG%
echo (You can upload this file to me if it fails.)

REM Run the bootstrap and capture all output
call Run_Tracker_NoPython.bat > "%LOG%" 2>&1

echo.
echo ===== Console output (tail) =====
type "%LOG%"
echo.
echo Done. Press any key to close.
pause
