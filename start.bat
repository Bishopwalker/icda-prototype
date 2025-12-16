@echo off
REM ================================================================
REM ICDA Unified Startup - Auto-detect best mode
REM ================================================================
REM Usage: start.bat [mode] [options]
REM   Modes: auto, hybrid, docker, local
REM   Options: --verbose, --skip-health
REM ================================================================

setlocal enabledelayedexpansion

REM ==================== CONFIGURATION ====================
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"
set "REDIS_PORT=6379"
set "OPENSEARCH_PORT=9200"
set "HEALTH_TIMEOUT=60"

REM ==================== COLORS ====================
REM Note: Windows colors need ANSI support (Windows 10+)

REM ==================== PARSE ARGUMENTS ====================
set "MODE=auto"
set "VERBOSE=0"
set "SKIP_HEALTH=0"

:parse_args
if "%~1"=="" goto :detect_environment
if /i "%~1"=="hybrid" set "MODE=hybrid" & shift & goto :parse_args
if /i "%~1"=="docker" set "MODE=docker" & shift & goto :parse_args
if /i "%~1"=="local" set "MODE=local" & shift & goto :parse_args
if /i "%~1"=="--verbose" set "VERBOSE=1" & shift & goto :parse_args
if /i "%~1"=="--skip-health" set "SKIP_HEALTH=1" & shift & goto :parse_args
if /i "%~1"=="-v" set "VERBOSE=1" & shift & goto :parse_args
shift
goto :parse_args

REM ==================== ENVIRONMENT DETECTION ====================
:detect_environment
call :print_header

echo Detecting environment...
echo.

REM Check Docker availability
set "DOCKER_OK=0"
docker info >nul 2>&1
if %errorlevel%==0 (
    set "DOCKER_OK=1"
    echo   [OK] Docker: Available
) else (
    echo   [--] Docker: Not available
)

REM Check if services are already running
set "REDIS_RUNNING=0"
set "OPENSEARCH_RUNNING=0"
set "BACKEND_RUNNING=0"
set "FRONTEND_RUNNING=0"

netstat -ano 2>nul | findstr ":%REDIS_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 set "REDIS_RUNNING=1"

netstat -ano 2>nul | findstr ":%OPENSEARCH_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 set "OPENSEARCH_RUNNING=1"

netstat -ano 2>nul | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 set "BACKEND_RUNNING=1"

netstat -ano 2>nul | findstr ":%FRONTEND_PORT% " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 set "FRONTEND_RUNNING=1"

REM Check Python/Node
set "PYTHON_OK=0"
set "NODE_OK=0"
python --version >nul 2>&1 && set "PYTHON_OK=1"
node --version >nul 2>&1 && set "NODE_OK=1"

REM Check venv
set "VENV_OK=0"
if exist "venv\Scripts\activate.bat" set "VENV_OK=1"

if "%VERBOSE%"=="1" call :print_status

REM ==================== AUTO-MODE SELECTION ====================
if not "%MODE%"=="auto" goto :execute_mode

REM Decision logic
if "%DOCKER_OK%"=="1" (
    if "%REDIS_RUNNING%"=="0" if "%OPENSEARCH_RUNNING%"=="0" (
        set "MODE=hybrid"
        echo   [AUTO] Selected HYBRID mode ^(Docker services + native app^)
    ) else (
        REM Check if Docker containers are running
        docker ps 2>nul | findstr "redis" >nul 2>&1
        if %errorlevel%==0 (
            set "MODE=hybrid"
            echo   [AUTO] Selected HYBRID mode ^(existing Docker services detected^)
        ) else (
            set "MODE=local"
            echo   [AUTO] Selected LOCAL mode ^(external services detected^)
        )
    )
) else (
    if "%PYTHON_OK%"=="1" (
        set "MODE=local"
        echo   [AUTO] Selected LOCAL mode ^(no Docker available^)
    ) else (
        echo   [ERROR] No Docker and no Python - cannot start!
        exit /b 1
    )
)

REM ==================== EXECUTE SELECTED MODE ====================
:execute_mode
if "%MODE%"=="hybrid" goto :mode_hybrid
if "%MODE%"=="docker" goto :mode_docker
if "%MODE%"=="local" goto :mode_local
echo [ERROR] Unknown mode: %MODE%
exit /b 1

REM ==================== HYBRID MODE ====================
:mode_hybrid
echo.
echo ============================================================
echo   HYBRID MODE: Docker services + Native application
echo ============================================================
echo.

REM Start Redis if not running - REQUIRED!
if "%REDIS_RUNNING%"=="0" (
    echo Starting Redis in Docker...
    docker-compose up -d redis
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to start Redis - ICDA requires Redis!
        exit /b 1
    )
)

REM Start OpenSearch if not running - REQUIRED!
if "%OPENSEARCH_RUNNING%"=="0" (
    echo Starting OpenSearch in Docker...
    docker-compose up -d opensearch
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to start OpenSearch - ICDA requires OpenSearch!
        exit /b 1
    )
)

REM Wait for services if not skipping health
if "%SKIP_HEALTH%"=="0" call :wait_for_services

REM Kill any existing backend/frontend on ports
call :kill_ports

REM Activate venv if exists
if "%VENV_OK%"=="1" (
    echo Activating Python virtual environment...
    call venv\Scripts\activate.bat
)

REM Set environment for local services
set "OPENSEARCH_HOST=http://localhost:9200"
set "REDIS_URL=redis://localhost:6379"

REM Start application
echo.
echo Starting ICDA application...
npm run dev
goto :end

REM ==================== DOCKER MODE ====================
:mode_docker
echo.
echo ============================================================
echo   DOCKER MODE: Everything containerized
echo ============================================================
echo.

if "%DOCKER_OK%"=="0" (
    echo [ERROR] Docker is not available!
    exit /b 1
)

REM Kill any conflicting local processes
call :kill_ports

REM Build frontend if needed
if not exist "frontend\dist\index.html" (
    echo Building frontend...
    cd frontend && call npm ci && call npm run build && cd ..
)

REM Start all services
echo Starting full Docker stack...
docker-compose up -d icda redis opensearch

if "%SKIP_HEALTH%"=="0" call :wait_for_docker_health

echo.
echo [SUCCESS] Docker stack running!
docker-compose ps
goto :end

REM ==================== LOCAL MODE ====================
:mode_local
echo.
echo ============================================================
echo   LOCAL MODE: Everything native ^(no Docker^)
echo ============================================================
echo.

if "%PYTHON_OK%"=="0" (
    echo [ERROR] Python not found!
    exit /b 1
)

REM Create venv if needed
if "%VENV_OK%"=="0" (
    echo Creating virtual environment...
    python -m venv venv
    set "VENV_OK=1"
)

call venv\Scripts\activate.bat
pip install -r requirements.txt -q

REM Check for services - REQUIRED!
if "%REDIS_RUNNING%"=="0" (
    echo [ERROR] Redis not running - ICDA requires Redis!
    echo        Start Redis with: docker-compose up -d redis
    exit /b 1
)
if "%OPENSEARCH_RUNNING%"=="0" (
    echo [ERROR] OpenSearch not running - ICDA requires OpenSearch!
    echo        Start OpenSearch with: docker-compose up -d opensearch
    exit /b 1
)

REM Kill any conflicting processes
call :kill_ports

echo.
echo Starting ICDA application...
npm run dev
goto :end

REM ==================== UTILITY FUNCTIONS ====================

:print_header
echo.
echo ============================================================
echo    ICDA Unified Startup v2.0
echo    %date% %time%
echo ============================================================
echo.
exit /b 0

:print_status
echo.
echo Environment Status:
echo   Docker:     %DOCKER_OK% ^(1=available^)
echo   Python:     %PYTHON_OK%
echo   Node.js:    %NODE_OK%
echo   Venv:       %VENV_OK%
echo.
echo Port Status:
echo   Redis ^(%REDIS_PORT%^):      %REDIS_RUNNING% ^(1=in use^)
echo   OpenSearch ^(%OPENSEARCH_PORT%^): %OPENSEARCH_RUNNING%
echo   Backend ^(%BACKEND_PORT%^):    %BACKEND_RUNNING%
echo   Frontend ^(%FRONTEND_PORT%^):   %FRONTEND_RUNNING%
echo.
exit /b 0

:wait_for_services
echo Waiting for required services to be ready...
set /a "tries=0"
:wait_loop
if %tries% gtr 30 (
    echo [ERROR] Services failed to start within timeout!
    echo        Redis and OpenSearch are REQUIRED for ICDA.
    exit /b 1
)

REM Check Redis
docker exec icda-redis-1 redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    REM Try alternate container name
    docker exec redis redis-cli ping >nul 2>&1
    if %errorlevel% neq 0 (
        echo   Waiting for Redis... ^(%tries%/30^)
        timeout /t 2 >nul
        set /a "tries+=1"
        goto :wait_loop
    )
)

REM Check OpenSearch
curl -s http://localhost:9200 >nul 2>&1
if %errorlevel% neq 0 (
    echo   Waiting for OpenSearch... ^(%tries%/30^)
    timeout /t 2 >nul
    set /a "tries+=1"
    goto :wait_loop
)

echo   [OK] All services ready!
exit /b 0

:wait_for_docker_health
echo Waiting for Docker health checks...
set /a "tries=0"
:health_loop
if %tries% gtr 24 (
    echo [WARN] Health check timeout - continuing anyway
    exit /b 0
)
docker-compose ps 2>nul | findstr "healthy" >nul 2>&1
if %errorlevel%==0 (
    echo   [OK] All containers healthy!
    exit /b 0
)
timeout /t 5 >nul
set /a "tries+=1"
echo   Waiting for health checks... ^(%tries%/24^)
goto :health_loop

:kill_ports
echo Clearing ports...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
exit /b 0

:end
echo.
echo ============================================================
echo   ICDA Running - Mode: %MODE%
echo ============================================================
echo.
echo   Backend API:  http://localhost:%BACKEND_PORT%/api
echo   API Docs:     http://localhost:%BACKEND_PORT%/docs
echo   Frontend:     http://localhost:%FRONTEND_PORT%
echo   Admin:        http://localhost:%FRONTEND_PORT%/admin
echo   Health:       http://localhost:%BACKEND_PORT%/api/health
echo.
echo   Stop with: stop.bat ^(or Ctrl+C^)
echo ============================================================
