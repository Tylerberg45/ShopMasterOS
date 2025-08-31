\
@echo off
setlocal
REM This script builds a single-file EXE for Windows using PyInstaller.
REM Requirements on THIS machine (builder only): Python 3.11+ and internet to install deps.

echo ==== Oil Change Tracker - Windows EXE Builder ====
echo.

REM Create venv in .builder if not exists
if not exist .builder (
  python -m venv .builder
)
call .builder\Scripts\activate

echo Installing build dependencies...
pip install --upgrade pip
pip install pyinstaller==6.6.0 uvicorn fastapi SQLAlchemy pydantic python-dotenv Jinja2 httpx watchfiles

echo Building EXE (this takes a minute)...
pyinstaller OilChangeTracker.spec --noconfirm

echo.
echo Build finished. EXE folder: dist\OilChangeTracker
echo Copy that entire folder to your USB drive and run OilChangeTracker.exe
pause
