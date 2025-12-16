@echo off
REM ICDA - Local Development Setup (No Docker for app)
REM Uses Python 3.11 + venv, Docker only for Redis/OpenSearch

echo ============================================================
echo    ICDA - Local Development Setup (Python 3.11)
echo ============================================================
echo.

REM Check Python 3.11 exists
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11 not found!
    echo Install from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create .venv if not exists
if not exist ".venv" (
    echo [INFO] Creating Python 3.11 virtual environment...
    py -3.11 -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv!
        pause
        exit /b 1
    )
)

REM Activate venv
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install Python deps
echo [INFO] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed!
    pause
    exit /b 1
)

REM Install root npm (concurrently)
echo [INFO] Installing root npm packages...
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed!
    pause
    exit /b 1
)

REM Install frontend deps
echo [INFO] Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo [ERROR] Frontend npm install failed!
    cd ..
    pause
    exit /b 1
)
cd ..

echo.
echo ============================================================
echo [SUCCESS] Setup complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Start Docker services:  start-services.bat
echo   2. Start app:              start-local.bat
echo.
pause
