@echo off
REM ================================================
REM ICDA Quick Start - No Docker Required!
REM ================================================

echo.
echo ========================================
echo   ICDA Prototype - Quick Start
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Install Python 3.10+
    pause
    exit /b 1
)

REM Check if venv exists, create if not
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q

REM Check for .env file
if not exist ".env" (
    echo.
    echo WARNING: No .env file found!
    echo Creating from .env.example...
    copy .env.example .env
    echo.
    echo EDIT .env with your AWS credentials if you want Bedrock features.
    echo Without AWS creds, the app runs in LITE MODE (no AI features^).
    echo.
)

echo.
echo ========================================
echo   Starting ICDA Server
echo ========================================
echo.
echo   API:  http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo.
echo   Press Ctrl+C to stop
echo ========================================
echo.

REM Run the app
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
