@echo off
REM ICDA Docker Push Script
REM Builds and pushes to Docker Hub for team/demo

echo ============================================================
echo    ICDA Prototype - Build and Push to Docker Hub
echo ============================================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    pause
    exit /b 1
)

REM Get version from package.json or default
set VERSION=latest
if exist "package.json" (
    for /f "tokens=2 delims=:, " %%a in ('findstr /c:"\"version\"" package.json') do set VERSION=%%~a
)
echo [INFO] Version: %VERSION%

REM Build the image
echo.
echo [INFO] Building Docker image...
docker compose build icda
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

REM Tag for Docker Hub
echo.
echo [INFO] Tagging images...
docker tag icda-prototype:latest bwalker33/icda-prototype:latest
docker tag icda-prototype:latest bwalker33/icda-prototype:v%VERSION%

REM Push to Docker Hub
echo.
echo [INFO] Pushing to Docker Hub...
docker push bwalker33/icda-prototype:latest
if %errorlevel% neq 0 (
    echo [ERROR] Push failed! Are you logged in?
    echo Run: docker login
    pause
    exit /b 1
)

docker push bwalker33/icda-prototype:v%VERSION%

echo.
echo ============================================================
echo [SUCCESS] Pushed to Docker Hub!
echo.
echo    bwalker33/icda-prototype:latest
echo    bwalker33/icda-prototype:v%VERSION%
echo.
echo Team can pull with:
echo    docker pull bwalker33/icda-prototype:latest
echo ============================================================
pause
