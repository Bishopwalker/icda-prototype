@echo off
REM ICDA - Start Local Development (Python 3.11 + Node)
REM Requires: setup-local.bat run first, start-services.bat running

echo ============================================================
echo    ICDA - Local Development Server (Python 3.11)
echo ============================================================
echo.

REM Check .venv exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found!
    echo Run setup-local.bat first.
    pause
    exit /b 1
)

REM Check frontend node_modules
if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed!
    echo Run setup-local.bat first.
    pause
    exit /b 1
)

REM Activate venv
echo [INFO] Activating Python 3.11 virtual environment...
call .venv\Scripts\activate.bat

REM Verify Python version
python --version | findstr "3.11" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Wrong Python version in venv!
    echo Expected Python 3.11
    python --version
    pause
    exit /b 1
)

REM Check Docker services
echo [INFO] Checking Redis...
docker exec icda-redis redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Redis not running! Run start-services.bat first.
    echo        Continuing without Redis (will use in-memory cache)...
)

echo [INFO] Checking OpenSearch...
curl -s http://localhost:9200 >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] OpenSearch not running! Run start-services.bat first.
    echo        Continuing without OpenSearch (will use keyword search)...
)

REM Kill any existing processes on our ports
echo [INFO] Checking ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo [INFO] Killing process on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING 2^>nul') do (
    echo [INFO] Killing process on port 5173...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ============================================================
echo    Starting ICDA Development Servers
echo ============================================================
echo.
echo    Backend:   http://localhost:8000
echo    API Docs:  http://localhost:8000/docs
echo    Frontend:  http://localhost:5173
echo.
echo    Press Ctrl+C to stop
echo ============================================================
echo.

REM Run both with concurrently
npm run dev
