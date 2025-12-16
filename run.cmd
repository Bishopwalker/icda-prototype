@echo off
REM ICDA - One Command Start
REM Just run: run.cmd

echo ============================================
echo   ICDA Prototype - Starting...
echo ============================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running. Please start Docker Desktop.
    exit /b 1
)

REM Set AWS credentials from aws cli config if not already set
if "%AWS_ACCESS_KEY_ID%"=="" (
    for /f "tokens=*" %%a in ('aws configure get aws_access_key_id 2^>nul') do set AWS_ACCESS_KEY_ID=%%a
)
if "%AWS_SECRET_ACCESS_KEY%"=="" (
    for /f "tokens=*" %%a in ('aws configure get aws_secret_access_key 2^>nul') do set AWS_SECRET_ACCESS_KEY=%%a
)
if "%AWS_REGION%"=="" (
    for /f "tokens=*" %%a in ('aws configure get region 2^>nul') do set AWS_REGION=%%a
)
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

echo AWS Region: %AWS_REGION%
if "%AWS_ACCESS_KEY_ID%"=="" (
    echo AWS Credentials: Not found - running in LITE mode
) else (
    echo AWS Credentials: Found - running in FULL mode
)
echo.

REM Build and start
docker-compose up --build -d

echo.
echo ============================================
echo   ICDA is starting up...
echo   Wait ~30 seconds for all services
echo ============================================
echo.
echo   App:  http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo.
echo   To view logs:  docker-compose logs -f icda
echo   To stop:       docker-compose down
echo ============================================
