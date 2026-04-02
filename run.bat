@echo off
setlocal

set PYTHON=venv\Scripts\python.exe

if "%~1"=="" goto usage

if /I "%~1"=="install" goto install
if /I "%~1"=="run" goto run
if /I "%~1"=="api" goto api
if /I "%~1"=="dev" goto dev
if /I "%~1"=="test" goto test

goto usage

:install
"%PYTHON%" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b %errorlevel%
"%PYTHON%" -m playwright install chromium
if errorlevel 1 exit /b %errorlevel%
cd frontend && pnpm install
exit /b %errorlevel%

:run
cd backend && "..\%PYTHON%" scraper.py
exit /b %errorlevel%

:api
cd backend && "..\%PYTHON%" -m uvicorn api:app --host 127.0.0.1 --port 8000
exit /b %errorlevel%

:dev
cd frontend && pnpm dev
exit /b %errorlevel%

:test
cd backend && "..\%PYTHON%" -m pytest -q
exit /b %errorlevel%

:usage
echo Usage: run.bat ^<install^|run^|api^|dev^|test^>
exit /b 1
