@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3.13+ and try again.
  exit /b 1
)

echo Syncing dependencies with uv...
python -m uv sync
if errorlevel 1 (
  echo Failed to sync the project environment.
  exit /b 1
)

echo Starting FlowFix Agent on http://127.0.0.1:8000
python -m uv run uvicorn app.main:app --reload
