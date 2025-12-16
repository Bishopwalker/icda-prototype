@echo off
REM ============================================
REM ICDA ONE-COMMAND BUILD
REM ============================================
REM This script builds and starts everything:
REM   - Backend (FastAPI) on port 8000
REM   - Redis on port 6379
REM   - OpenSearch on port 9200
REM   - Auto-indexes knowledge docs to OpenSearch
REM ============================================

echo.
echo ============================================
echo   ICDA ONE-COMMAND BUILD
echo ============================================
echo.

REM Check if docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Parse arguments
set "COMMAND=%1"
set "WITH_DEV="

if "%COMMAND%"=="dev" (
    echo Starting with Frontend Dev Server on port 5173...
    set "WITH_DEV=--profile dev"
    set "COMMAND=up"
)

if "%COMMAND%"=="" set "COMMAND=up"

if "%COMMAND%"=="up" (
    echo Building and starting all services...
    echo.
    echo Services:
    echo   - Backend ^(FastAPI^): http://localhost:8000
    echo   - API Docs:          http://localhost:8000/docs
    echo   - OpenSearch:        http://localhost:9200
    echo   - Redis:             localhost:6379
    if defined WITH_DEV (
        echo   - Frontend Dev:      http://localhost:5173
    )
    echo.
    docker-compose -f docker-compose.unified.yml %WITH_DEV% up --build -d
    echo.
    echo ============================================
    echo   ICDA is starting! Wait ~60s for init.
    echo   Then visit: http://localhost:8000
    echo ============================================
    echo.
    echo Showing logs (Ctrl+C to exit logs, services keep running)...
    docker-compose -f docker-compose.unified.yml logs -f
)

if "%COMMAND%"=="stop" (
    echo Stopping all services...
    docker-compose -f docker-compose.unified.yml --profile dev down
    echo Done.
)

if "%COMMAND%"=="clean" (
    echo Stopping and removing all data...
    docker-compose -f docker-compose.unified.yml --profile dev down -v
    echo Done.
)

if "%COMMAND%"=="logs" (
    docker-compose -f docker-compose.unified.yml logs -f
)

if "%COMMAND%"=="status" (
    docker-compose -f docker-compose.unified.yml ps
)

if "%COMMAND%"=="help" (
    echo.
    echo Usage: ONE-COMMAND.bat [command]
    echo.
    echo Commands:
    echo   up      - Build and start all services (default)
    echo   dev     - Start with frontend dev server on 5173
    echo   stop    - Stop all services
    echo   clean   - Stop and remove all data
    echo   logs    - Show container logs
    echo   status  - Show service status
    echo   help    - Show this help
    echo.
)
