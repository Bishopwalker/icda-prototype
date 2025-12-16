@echo off
REM ================================================================
REM ICDA - Unified Docker Build & Start Script
REM ================================================================
REM Usage: BUILD-ALL.bat [options]
REM   Options:
REM     --build         Force rebuild containers
REM     --detach, -d    Run in detached mode
REM     --logs          Follow logs after starting
REM     --clean         Clean all volumes and rebuild from scratch
REM     --help, -h      Show this help message
REM ================================================================

setlocal enabledelayedexpansion

REM ==================== CONFIGURATION ====================
set "BUILD_FLAG="
set "DETACH_FLAG="
set "SHOW_LOGS=0"
set "CLEAN_BUILD=0"

REM ==================== PARSE ARGUMENTS ====================
:parse_args
if "%~1"=="" goto :main
if /i "%~1"=="--build" set "BUILD_FLAG=--build" & shift & goto :parse_args
if /i "%~1"=="--detach" set "DETACH_FLAG=-d" & shift & goto :parse_args
if /i "%~1"=="-d" set "DETACH_FLAG=-d" & shift & goto :parse_args
if /i "%~1"=="--logs" set "SHOW_LOGS=1" & shift & goto :parse_args
if /i "%~1"=="--clean" set "CLEAN_BUILD=1" & shift & goto :parse_args
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
shift
goto :parse_args

:show_help
echo.
echo ICDA - Unified Docker Build ^& Start Script
echo.
echo Usage: BUILD-ALL.bat [options]
echo.
echo Options:
echo   --build         Force rebuild containers
echo   --detach, -d    Run in detached mode
echo   --logs          Follow logs after starting
echo   --clean         Clean all volumes and rebuild from scratch
echo   --help, -h      Show this help message
echo.
echo Examples:
echo   BUILD-ALL.bat                    Quick start with existing images
echo   BUILD-ALL.bat --build            Rebuild and start
echo   BUILD-ALL.bat --clean            Full clean rebuild
echo   BUILD-ALL.bat -d --logs          Detached with logs
echo.
exit /b 0

REM ==================== MAIN SCRIPT ====================
:main
echo.
echo ============================================================
echo    ICDA - Unified Docker Build ^& Start
echo    %date% %time%
echo ============================================================
echo.

REM ==================== DOCKER CHECK ====================
echo [1/6] Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo.
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo   [OK] Docker is running
echo.

REM ==================== CLEAN BUILD ====================
if "%CLEAN_BUILD%"=="1" (
    echo [2/6] Clean build - Removing all containers, images, and volumes...
    docker-compose down --remove-orphans -v 2>nul
    docker rmi icda-prototype:latest 2>nul
    docker builder prune -f >nul 2>&1
    set "BUILD_FLAG=--build"
    echo   [OK] Clean completed
    echo.
) else (
    echo [2/6] Stopping existing containers...
    docker-compose down --remove-orphans >nul 2>&1
    echo   [OK] Stopped
    echo.
)

REM ==================== PORT CONFLICTS ====================
echo [3/6] Checking for port conflicts...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":6379 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 6379...
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":9200 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 9200...
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK] Ports cleared
echo.

REM ==================== BUILD & START ====================
echo [4/6] Building and starting Docker stack...
echo.
if "%BUILD_FLAG%"=="--build" (
    echo   Building all containers...
    docker-compose build
    if %errorlevel% neq 0 (
        echo [ERROR] Docker build failed!
        pause
        exit /b 1
    )
)

echo [5/6] Starting services...
if "%DETACH_FLAG%"=="-d" (
    docker-compose up -d %BUILD_FLAG%
) else (
    if "%SHOW_LOGS%"=="1" (
        start "ICDA Docker" docker-compose up %BUILD_FLAG%
        timeout /t 5 >nul
    ) else (
        docker-compose up %BUILD_FLAG%
        goto :end
    )
)

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services!
    pause
    exit /b 1
)
echo   [OK] Services started
echo.

REM ==================== HEALTH CHECK ====================
echo [6/6] Waiting for services to be healthy...
set /a "count=0"
set /a "max_tries=30"

:health_check_loop
timeout /t 3 /nobreak >nul

REM Check ICDA app health
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel%==0 (
    echo   [OK] All services healthy!
    goto :show_status
)

set /a "count+=1"
if !count! gtr !max_tries! (
    echo [WARN] Health check timeout - services may still be starting
    goto :show_status
)

echo   Waiting for health checks... (!count!/!max_tries!)
goto :health_check_loop

:show_status
echo.
echo ============================================================
echo   ICDA Docker Stack - READY
echo ============================================================
echo.
echo Service URLs:
echo   Frontend:        http://localhost:8000
echo   API Docs:        http://localhost:8000/docs
echo   API Health:      http://localhost:8000/api/health
echo   Admin Panel:     http://localhost:8000/admin
echo   OpenSearch:      http://localhost:9200
echo   Redis:           localhost:6379
echo.
echo Container Status:
docker-compose ps
echo.
echo Management Commands:
echo   View logs:       docker-compose logs -f
echo   Stop all:        STOP-ALL.bat
echo   Restart:         docker-compose restart
echo   Shell access:    docker exec -it icda bash
echo.
echo ============================================================

if "%SHOW_LOGS%"=="1" (
    echo Following logs... (Ctrl+C to exit)
    docker-compose logs -f
)

:end
echo.
echo [SUCCESS] Build and start completed!
echo.
pause
exit /b 0