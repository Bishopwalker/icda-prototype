@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo    ICDA - Full Docker Rebuild (No Cache)
echo ============================================================
echo.

REM Step 1: Stop everything
echo [1/6] Stopping all containers...
docker-compose down --remove-orphans
if %errorlevel% neq 0 (
    echo [WARN] docker-compose down had issues, continuing...
)

REM Step 2: Remove old images
echo [2/6] Removing old ICDA images...
docker rmi icda-prototype:latest 2>nul
docker rmi icda-mcp:latest 2>nul

REM Step 3: Prune build cache
echo [3/6] Pruning Docker build cache...
docker builder prune -f

REM Step 4: Rebuild frontend first (ensures fresh dist)
echo [4/6] Building fresh frontend...
cd frontend
if exist "node_modules" (
    echo      Using existing node_modules...
) else (
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

REM Step 5: Build all images with no cache
echo [5/6] Building Docker images (--no-cache)...
docker-compose build --no-cache --pull
if %errorlevel% neq 0 (
    echo [ERROR] Docker build failed!
    pause
    exit /b 1
)

REM Step 6: Start services
echo [6/6] Starting services...
docker-compose up -d icda redis opensearch
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start services!
    pause
    exit /b 1
)

REM Wait for health
echo.
echo Waiting for services to be healthy...
set /a count=0
:wait_loop
timeout /t 5 /nobreak >nul
docker-compose ps --format "table {{.Name}}\t{{.Status}}" 2>nul | findstr "healthy" >nul
if %errorlevel% equ 0 goto healthy
set /a count+=1
if %count% gtr 24 (
    echo [ERROR] Services did not become healthy in 2 minutes!
    docker-compose ps
    pause
    exit /b 1
)
echo      Still waiting... (%count%/24)
goto wait_loop

:healthy
echo.
echo ============================================================
echo [SUCCESS] Rebuild complete!
echo ============================================================
echo.
echo Services:
echo   ICDA App:    http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Health:      http://localhost:8000/api/health
echo   OpenSearch:  http://localhost:9200
echo   Redis:       localhost:6379
echo.
echo To start MCP Server: docker-compose --profile mcp up -d mcp-server
echo.

REM Show service status
docker-compose ps

pause
