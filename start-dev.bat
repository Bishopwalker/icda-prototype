@echo off
REM ICDA Development Server Startup Script
REM Starts both FastAPI backend and Vite frontend in same terminal

echo ============================================================
echo    ICDA Prototype - Full Stack Development Server
echo ============================================================
echo.

REM Start Infrastructure Dependencies (Redis & OpenSearch)
echo [INFO] Starting infrastructure (Redis ^& OpenSearch)...
call docker-compose up -d redis opensearch
if errorlevel 1 goto infra_fail
echo [SUCCESS] Infrastructure services started.
goto infra_done

:infra_fail
echo [WARNING] Failed to start Docker services. Ensure Docker Desktop is running.
echo           Continuing without Redis/OpenSearch (some features may fail).

:infra_done

REM Set OpenSearch Host for local development
set OPENSEARCH_HOST=http://localhost:9200
echo [INFO] Set OPENSEARCH_HOST=%OPENSEARCH_HOST%

REM Check if port 8000 is in use (backend)
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if errorlevel 1 goto check_port_5173

echo [WARNING] Port 8000 is already in use!
echo Killing existing process...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 >nul

:check_port_5173
REM Check if port 5173 is in use (Vite default)
netstat -ano | findstr :5173 | findstr LISTENING >nul 2>&1
if errorlevel 1 goto venv_setup

echo [WARNING] Port 5173 is already in use!
echo Killing existing process...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 >nul

:venv_setup
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
echo.
echo Press Ctrl+C to stop both servers
echo ============================================================
echo.

REM Run both in same terminal using concurrently
npm run dev