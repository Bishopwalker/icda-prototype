@echo off
echo Waiting for Docker Desktop to start...

:check_docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker not ready, waiting 5 seconds...
    timeout /t 5 /nobreak >nul
    goto check_docker
)

echo Docker is ready!
echo.

echo Stopping any existing containers...
docker-compose down

echo.
echo Building Docker images...
docker-compose build --no-cache

echo.
echo Starting containers...
docker-compose up -d

echo.
echo Deployment complete! Checking status...
docker-compose ps

echo.
echo ========================================
echo Frontend: http://localhost
echo Backend: http://localhost:8000
echo ========================================