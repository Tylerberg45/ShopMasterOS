@echo off
setlocal
set "BASE=%LOCALAPPDATA%\OilChangeTracker"
echo Uninstalling Oil Change Tracker...
echo Stopping any running servers (close windows if open).
timeout /t 2 >nul

REM Remove shortcuts
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Oil Change Tracker.lnk" >nul 2>nul
del "%USERPROFILE%\Desktop\Oil Change Tracker.lnk" >nul 2>nul

REM Remove folder
rmdir /s /q "%BASE%"
echo Done.
pause
