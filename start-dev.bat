@echo off
REM ICDA Development Server Startup Script
REM Starts Docker services, FastAPI backend and Vite frontend

echo ============================================================
echo    ICDA Prototype - Full Stack Development Server
echo ============================================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Start Docker services (Redis and OpenSearch)
echo [INFO] Starting Docker services (Redis, OpenSearch)...
docker-compose up -d redis opensearch
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker services!
    pause
    exit /b 1
)

REM Wait for OpenSearch to be ready
echo [INFO] Waiting for OpenSearch to be ready...
:wait_opensearch
timeout /t 2 >nul
curl -s http://localhost:9200 >nul 2>&1
if %errorlevel% neq 0 (
    echo        Still waiting for OpenSearch...
    goto wait_opensearch
)
echo [INFO] OpenSearch is ready!

REM Wait for Redis to be ready
echo [INFO] Checking Redis...
docker exec icda-redis redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Redis may not be ready yet, continuing anyway...
) else (
    echo [INFO] Redis is ready!
)

echo.

REM Check if port 8000 is in use (backend)
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo [WARNING] Port 8000 is already in use!
    echo Killing existing process...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 1 >nul
)

REM Check if port 5173 is in use (Vite default)
netstat -ano | findstr :5173 | findstr LISTENING >nul 2>&1
if %errorlevel%==0 (
    echo [WARNING] Port 5173 is already in use!
    echo Killing existing process...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 1 >nul
)

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating Python virtual environment...
    call venv\Scripts\activate.bat
)

echo.
echo [INFO] Starting Backend (FastAPI) on http://localhost:8000
echo [INFO] Starting Frontend (Vite) on http://localhost:5173
echo.
echo    Backend API:     http://localhost:8000/api
echo    API Docs:        http://localhost:8000/docs
echo    Frontend UI:     http://localhost:5173
echo    OpenSearch:      http://localhost:9200
echo    Redis:           localhost:6379
echo.
echo Press Ctrl+C to stop both servers
echo ============================================================
echo.

REM Run both in same terminal using concurrently
npm run dev
