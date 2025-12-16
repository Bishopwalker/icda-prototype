@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo    ICDA - Start Docker Stack
echo ============================================================
echo.

REM Check Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Check if frontend is built
if not exist "frontend\dist\index.html" (
    echo [INFO] Frontend not built, building now...
    cd frontend
    if not exist "node_modules" (
        echo      Installing dependencies...
        call npm ci
    )
    call npm run build
    if %errorlevel% neq 0 (
        echo [ERROR] Frontend build failed!
        cd ..
        pause
        exit /b 1
    )
    cd ..
)

REM Start core services
echo [INFO] Starting ICDA stack (icda + redis + opensearch)...
docker-compose up -d icda redis opensearch
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services!
    docker-compose logs --tail=50
    pause
    exit /b 1
)

REM Wait for health checks
echo [INFO] Waiting for services to be healthy...
set /a count=0
:wait_loop
timeout /t 5 /nobreak >nul
docker-compose ps --format "table {{.Name}}\t{{.Status}}" 2>nul | findstr "healthy" >nul
if %errorlevel% equ 0 goto healthy
set /a count+=1
if %count% gtr 24 (
    echo [WARN] Services taking longer than expected...
    docker-compose ps
    echo.
    echo Continuing anyway - OpenSearch may still be initializing.
    goto done
)
echo      Still waiting... (%count%/24)
goto wait_loop

:healthy
echo [OK] All services healthy!

:done
echo.
echo ============================================================
echo [SUCCESS] ICDA Docker stack is running!
echo ============================================================
echo.
echo   App:        http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   Health:     http://localhost:8000/api/health
echo.
echo   Stop with:  docker-compose down
echo   Logs:       docker-compose logs -f
echo.

REM Show service status
docker-compose ps

pause
